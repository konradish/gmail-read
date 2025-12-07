# gmail-read

CLI tool to read Gmail messages from the command line.

## Installation

```bash
# Install with uv
uv tool install gmail-read

# Or with pip
pip install gmail-read

# Or run directly without installing
uvx gmail-read
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

```bash
# List recent messages
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

## Automation Examples

```bash
# Morning briefing
gmail-read --unread -n 5 | claude -p "Summarize my unread emails"

# Check for urgent messages
gmail-read --query "is:unread subject:urgent" --json | jq '.subject'
```

## Config

Credentials stored in `~/.gmail-read/`:
- `credentials.json` - OAuth client credentials (you provide)
- `token.json` - Access token (auto-generated)

## License

MIT
