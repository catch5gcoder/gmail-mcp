# Gmail MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects Claude to your Gmail account — letting you read, search, and send emails directly from Claude Code conversations.

## Tools

| Tool | Description |
|------|-------------|
| `list_emails` | List emails from a label (default: INBOX) with optional query filter |
| `get_email` | Fetch full email content by message ID |
| `get_thread` | Fetch all messages in a conversation thread |
| `search_emails` | Search using Gmail query syntax (`from:`, `subject:`, `has:attachment`, etc.) |
| `list_labels` | List all Gmail labels (system + custom) |
| `send_email` | Send plain text or HTML email |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Google Cloud credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Gmail API** (APIs & Services → Library → Gmail API)
3. Configure the **OAuth consent screen** (External, add your Gmail as a test user)
4. Create credentials: APIs & Services → Credentials → **OAuth 2.0 Client ID** → Desktop app
5. Download the JSON file and save it as `creds.json` in this directory

### 3. Authenticate

Run once to complete the OAuth browser flow:

```bash
python server.py
```

A `token.json` file is saved after login — subsequent runs authenticate automatically.

### 4. Register with Claude Code

```bash
claude mcp add -s user gmail -- python /path/to/gmail-mcp/server.py
```

Restart Claude Code — the Gmail tools are now available in every session.

## Usage examples

Once registered, ask Claude things like:

- *"List my unread emails"*
- *"Search for emails from shopwise"*
- *"Get the full content of email `<id>`"*
- *"Send an email to alice@example.com with subject Hello"*

### Gmail search syntax

| Query | Matches |
|-------|---------|
| `is:unread` | Unread emails |
| `from:boss@company.com` | From a specific sender |
| `subject:invoice` | Subject contains "invoice" |
| `has:attachment larger:5M` | Large attachments |
| `after:2024/01/01` | Emails since Jan 2024 |
| `label:work is:starred` | Starred emails in a label |

## Security

- `creds.json` and `token.json` are excluded from git via `.gitignore` — never commit them
- The app requests minimal scopes: `gmail.readonly`, `gmail.send`, `gmail.labels`
- OAuth tokens are stored locally and refreshed automatically
