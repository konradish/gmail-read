#!/usr/bin/env python3
"""
gmail-read: CLI tool to read and send Gmail messages.

Usage:
    gmail-read                     # List recent messages
    gmail-read --count 20          # List 20 recent messages
    gmail-read --unread            # List unread only
    gmail-read --query "from:boss" # Search query
    gmail-read --id <message_id>   # Read specific message
    gmail-read --labels            # List available labels

    gmail-read send --to "a@b.com" --subject "Hi" --body "Hello"
    gmail-read send --to "a@b.com" --subject "Hi" --body-stdin < msg.txt
    gmail-read send --reply-to <msg_id> --body "Thanks!"
"""

import argparse
import base64
import json
import os
import sys
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scopes - need both read and send
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

# Config paths
CONFIG_DIR = Path.home() / ".gmail-read"
TOKEN_FILE = CONFIG_DIR / "token.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


def get_credentials() -> Credentials:
    """Get or refresh OAuth credentials."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        # Check if we have all required scopes
        if creds and creds.scopes:
            missing_scopes = set(SCOPES) - set(creds.scopes)
            if missing_scopes:
                print(f"New scopes required: {missing_scopes}", file=sys.stderr)
                print("Re-authenticating...", file=sys.stderr)
                creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                # Refresh failed, need to re-auth
                creds = None

        if not creds:
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
        metadataHeaders=["From", "To", "Subject", "Date", "Message-ID"]
    ).execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    return {
        "id": msg_id,
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", "(no subject)"),
        "date": headers.get("Date", ""),
        "message_id": headers.get("Message-ID", ""),
        "snippet": msg.get("snippet", ""),
        "labels": msg.get("labelIds", []),
        "threadId": msg.get("threadId", ""),
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
        "message_id": headers.get("Message-ID", ""),
        "body": body,
        "labels": msg.get("labelIds", []),
        "threadId": msg.get("threadId", ""),
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

        print(f"{unread_marker} {msg['id']}  {from_addr}  {subject}")


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


def send_message(service, to: str, subject: str, body: str,
                 reply_to_id: str = None, cc: str = None, bcc: str = None,
                 dry_run: bool = False):
    """Send an email message."""
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    if cc:
        message["cc"] = cc
    if bcc:
        message["bcc"] = bcc

    thread_id = None

    # If replying, get original message headers
    if reply_to_id:
        original = get_message_full(service, reply_to_id)

        # Set References and In-Reply-To headers for proper threading
        if original.get("message_id"):
            message["In-Reply-To"] = original["message_id"]
            message["References"] = original["message_id"]

        # Use original thread
        thread_id = original.get("threadId")

        # Add Re: prefix if not already there
        if not subject.lower().startswith("re:"):
            message.replace_header("subject", f"Re: {original['subject']}")

    # Encode the message
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    body_dict = {"raw": raw}
    if thread_id:
        body_dict["threadId"] = thread_id

    if dry_run:
        print("=== DRY RUN - Would send: ===")
        print(f"To:      {to}")
        if cc:
            print(f"Cc:      {cc}")
        if bcc:
            print(f"Bcc:     {bcc}")
        print(f"Subject: {message['subject']}")
        print("-" * 40)
        print(body)
        print("-" * 40)
        print("(Use without --dry-run to actually send)")
        return None

    result = service.users().messages().send(userId="me", body=body_dict).execute()

    print(f"Message sent successfully!")
    print(f"Message ID: {result['id']}")
    if thread_id:
        print(f"Thread ID: {result['threadId']} (replied to thread)")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Read and send Gmail from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Send subcommand
    send_parser = subparsers.add_parser("send", help="Send an email")
    send_parser.add_argument(
        "--to", type=str, required=False,
        help="Recipient email address"
    )
    send_parser.add_argument(
        "--cc", type=str,
        help="CC recipients (comma-separated)"
    )
    send_parser.add_argument(
        "--bcc", type=str,
        help="BCC recipients (comma-separated)"
    )
    send_parser.add_argument(
        "--subject", "-s", type=str, default="",
        help="Email subject"
    )
    send_parser.add_argument(
        "--body", "-b", type=str,
        help="Email body text"
    )
    send_parser.add_argument(
        "--body-stdin", action="store_true",
        help="Read email body from stdin"
    )
    send_parser.add_argument(
        "--reply-to", type=str,
        help="Message ID to reply to (threads the response)"
    )
    send_parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be sent without actually sending"
    )

    # Main parser arguments (for read operations)
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

        if args.command == "send":
            # Handle send command
            body = args.body

            if args.body_stdin:
                body = sys.stdin.read()

            if not body:
                print("Error: Must provide --body or --body-stdin", file=sys.stderr)
                sys.exit(1)

            # For replies, --to is optional (replies to sender)
            to = args.to
            if args.reply_to and not to:
                original = get_message_snippet(service, args.reply_to)
                # Extract email from "Name <email>" format
                from_addr = original["from"]
                if "<" in from_addr:
                    to = from_addr.split("<")[1].rstrip(">")
                else:
                    to = from_addr
                print(f"Replying to: {to}")

            if not to:
                print("Error: Must provide --to or --reply-to", file=sys.stderr)
                sys.exit(1)

            subject = args.subject
            if args.reply_to and not subject:
                original = get_message_snippet(service, args.reply_to)
                subject = original["subject"]
                if not subject.lower().startswith("re:"):
                    subject = f"Re: {subject}"

            send_message(
                service,
                to=to,
                subject=subject,
                body=body,
                reply_to_id=args.reply_to,
                cc=args.cc,
                bcc=args.bcc,
                dry_run=args.dry_run
            )
        elif args.labels:
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
