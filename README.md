# gmail-read

CLI tool to read and send Gmail messages from the command line.

## Installation

```bash
# Install with uv
uv tool install git+https://github.com/konradish/gmail-read.git

# Or run directly without installing
uvx --from git+https://github.com/konradish/gmail-read.git gmail-read
```

## Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a project (or use existing)
3. Enable the **Gmail API**
4. Create **OAuth 2.0 Client ID** (Desktop app)
5. Download the credentials JSON
6. Save as `~/.gmail-read/credentials.json`

First run will open browser for OAuth authorization.

## Usage

### Reading Email

```bash
# List recent messages (* = unread)
gmail-read

# List 20 messages
gmail-read -n 20

# Unread only
gmail-read --unread

# Search query
gmail-read --query "from:boss@company.com"
gmail-read --query "subject:urgent is:unread"

# Read specific message by ID
gmail-read --id <message_id>

# JSON output (for piping to other tools)
gmail-read --id <message_id> --json

# List available labels
gmail-read --labels
```

### Sending Email

```bash
# Send a simple email
gmail-read send --to "someone@example.com" --subject "Hello" --body "Message body here"

# Send with CC/BCC
gmail-read send --to "a@b.com" --cc "c@d.com" --bcc "e@f.com" -s "Subject" -b "Body"

# Read body from stdin (great for piping from Claude)
echo "Email body" | gmail-read send --to "a@b.com" --subject "Hi" --body-stdin

# Reply to a message (auto-threads, auto-fills To and Subject)
gmail-read send --reply-to <message_id> --body "Thanks for your email!"

# Dry run - see what would be sent without sending
gmail-read send --to "a@b.com" -s "Test" -b "Body" --dry-run
```

## Automation Examples

```bash
# Morning briefing
gmail-read --unread -n 5 | claude -p "Summarize my unread emails"

# Check for urgent messages
gmail-read --query "is:unread subject:urgent" --json | jq '.subject'

# AI-composed email
claude -p "Draft a polite follow-up email to Bob about the project deadline" | \
  gmail-read send --to "bob@example.com" --subject "Project follow-up" --body-stdin

# Reply with AI assistance
gmail-read --id <msg_id> --json | \
  claude -p "Draft a helpful reply to this email" | \
  gmail-read send --reply-to <msg_id> --body-stdin --dry-run
```

## Config

Credentials stored in `~/.gmail-read/`:
- `credentials.json` - OAuth client credentials (you provide)
- `token.json` - Access token (auto-generated)

## Scopes

This tool requests the following Gmail API scopes:
- `gmail.readonly` - Read email messages
- `gmail.send` - Send email messages

## License

MIT
