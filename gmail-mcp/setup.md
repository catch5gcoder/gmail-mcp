# Gmail MCP Server — Setup Guide

## 1. Install dependencies

```bash
cd gmail-mcp
pip install -r requirements.txt
```

## 2. Create a Google Cloud project & OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Gmail API**: APIs & Services → Library → search "Gmail API" → Enable
4. Create credentials: APIs & Services → Credentials → **Create Credentials** → OAuth 2.0 Client ID
   - Application type: **Desktop app**
   - Download the JSON file and save it as `credentials.json` inside the `gmail-mcp/` folder

## 3. First-run authentication

Run the server once manually to complete the OAuth flow:

```bash
python server.py
```

A browser window will open asking you to sign in to Google and grant permissions.  
After authorizing, a `token.json` file is saved — subsequent runs are automatic.

## 4. Register with Claude Code

Add this to your Claude Code MCP config (`~/.claude/claude_desktop_config.json` or via `claude mcp add`):

```json
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": ["C:/Users/Abhishek.Doon/Claude_CLI/gmail-mcp/server.py"],
      "env": {}
    }
  }
}
```

Or run from the terminal:

```bash
claude mcp add gmail -- python "C:/Users/Abhishek.Doon/Claude_CLI/gmail-mcp/server.py"
```

## Available tools

| Tool | Description |
|------|-------------|
| `list_emails` | List emails from a label (default: INBOX), with optional query filter |
| `get_email` | Fetch full email content by message ID |
| `get_thread` | Fetch all messages in a conversation thread |
| `search_emails` | Search using Gmail query syntax (`from:`, `subject:`, `has:attachment`, etc.) |
| `list_labels` | List all Gmail labels |
| `send_email` | Send an email (plain text or HTML) |

## Gmail search query examples

- `is:unread` — unread emails
- `from:boss@company.com` — from a specific sender
- `subject:invoice after:2024/01/01` — invoices since 2024
- `has:attachment larger:5M` — large attachments
- `label:work is:starred` — starred work emails
