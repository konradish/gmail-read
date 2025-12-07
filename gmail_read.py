#!/usr/bin/env python3
"""
gmail-read: CLI tool to read Gmail messages.

Usage:
    gmail-read                     # List recent messages
    gmail-read --count 20          # List 20 recent messages
    gmail-read --unread            # List unread only
    gmail-read --query "from:boss" # Search query
    gmail-read --id <message_id>   # Read specific message
    gmail-read --labels            # List available labels
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Config paths
CONFIG_DIR = Path.home() / ".gmail-read"
TOKEN_FILE = CONFIG_DIR / "token.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


def get_credentials() -> Credentials:
    """Get or refresh OAuth credentials."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"Error: No credentials file found at {CREDENTIALS_FILE}", file=sys.stderr)
                print("\nSetup instructions:", file=sys.stderr)
                print("1. Go to https://console.cloud.google.com/apis/credentials", file=sys.stderr)
                print("2. Create OAuth 2.0 Client ID (Desktop app)", file=sys.stderr)
                print("3. Download JSON and save as:", file=sys.stderr)
                print(f"   {CREDENTIALS_FILE}", file=sys.stderr)
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())

    return creds


def get_service():
    """Build Gmail API service."""
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)


def list_labels(service):
    """List all Gmail labels."""
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])

    for label in sorted(labels, key=lambda x: x["name"]):
        print(f"{label['name']:<30} (id: {label['id']})")


def get_message_snippet(service, msg_id: str) -> dict:
    """Get message metadata and snippet."""
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="metadata",
        metadataHeaders=["From", "To", "Subject", "Date"]
    ).execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    return {
        "id": msg_id,
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", "(no subject)"),
        "date": headers.get("Date", ""),
        "snippet": msg.get("snippet", ""),
        "labels": msg.get("labelIds", []),
    }


def get_message_full(service, msg_id: str) -> dict:
    """Get full message content."""
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    # Extract body
    body = ""
    payload = msg.get("payload", {})

    if "body" in payload and payload["body"].get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    elif "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                break
            elif part.get("mimeType") == "text/html" and not body:
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

    return {
        "id": msg_id,
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", "(no subject)"),
        "date": headers.get("Date", ""),
        "body": body,
        "labels": msg.get("labelIds", []),
    }


def list_messages(service, query: str = "", max_results: int = 10, unread_only: bool = False):
    """List messages matching criteria."""
    if unread_only:
        query = f"is:unread {query}".strip()

    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = results.get("messages", [])

    if not messages:
        print("No messages found.")
        return

    for msg_meta in messages:
        msg = get_message_snippet(service, msg_meta["id"])
        unread_marker = "*" if "UNREAD" in msg["labels"] else " "

        # Truncate for display
        from_addr = msg["from"][:30].ljust(30)
        subject = msg["subject"][:50].ljust(50)

        print(f"{unread_marker} {msg['id'][:12]}  {from_addr}  {subject}")


def read_message(service, msg_id: str, output_json: bool = False):
    """Read and display a specific message."""
    msg = get_message_full(service, msg_id)

    if output_json:
        print(json.dumps(msg, indent=2))
    else:
        print(f"From:    {msg['from']}")
        print(f"To:      {msg['to']}")
        print(f"Date:    {msg['date']}")
        print(f"Subject: {msg['subject']}")
        print(f"Labels:  {', '.join(msg['labels'])}")
        print("-" * 60)
        print(msg["body"])


def main():
    parser = argparse.ArgumentParser(
        description="Read Gmail from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "-n", "--count", type=int, default=10,
        help="Number of messages to list (default: 10)"
    )
    parser.add_argument(
        "-u", "--unread", action="store_true",
        help="Show only unread messages"
    )
    parser.add_argument(
        "-q", "--query", type=str, default="",
        help="Gmail search query (e.g., 'from:someone@example.com')"
    )
    parser.add_argument(
        "-i", "--id", type=str,
        help="Read specific message by ID"
    )
    parser.add_argument(
        "-l", "--labels", action="store_true",
        help="List available labels"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output in JSON format"
    )

    args = parser.parse_args()

    try:
        service = get_service()

        if args.labels:
            list_labels(service)
        elif args.id:
            read_message(service, args.id, output_json=args.json)
        else:
            list_messages(
                service,
                query=args.query,
                max_results=args.count,
                unread_only=args.unread
            )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
