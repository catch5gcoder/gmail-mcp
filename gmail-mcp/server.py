#!/usr/bin/env python3
"""Gmail MCP Server — exposes Gmail read/write operations as MCP tools."""

import json
import sys
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

import gmail_client as gmail

app = Server("gmail-mcp")
_service = None


def service():
    global _service
    if _service is None:
        _service = gmail.get_service()
    return _service


# ── Tool definitions ──────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_emails",
            description="List emails from Gmail. Supports filtering by label and full Gmail search syntax.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail search query (e.g. 'from:alice@example.com', 'is:unread', 'subject:invoice'). Leave empty for inbox.",
                    },
                    "label": {
                        "type": "string",
                        "description": "Label name to filter by (e.g. 'INBOX', 'SENT', 'STARRED', or a custom label).",
                        "default": "INBOX",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of emails to return (1–50).",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
            },
        ),
        types.Tool(
            name="get_email",
            description="Get the full content of a specific email by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The Gmail message ID (returned by list_emails or search_emails).",
                    },
                },
                "required": ["message_id"],
            },
        ),
        types.Tool(
            name="get_thread",
            description="Get all emails in a conversation thread.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {
                        "type": "string",
                        "description": "The Gmail thread ID.",
                    },
                },
                "required": ["thread_id"],
            },
        ),
        types.Tool(
            name="search_emails",
            description="Search emails using Gmail's full search syntax (same as the Gmail search bar).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail search query, e.g. 'from:boss@company.com after:2024/01/01 has:attachment'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (1–50).",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="list_labels",
            description="List all Gmail labels (system labels like INBOX, SENT, SPAM, and custom labels).",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="send_email",
            description="Send an email from the authenticated Gmail account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address (or comma-separated list).",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content.",
                    },
                    "cc": {
                        "type": "string",
                        "description": "CC recipients (optional, comma-separated).",
                        "default": "",
                    },
                    "html": {
                        "type": "boolean",
                        "description": "Set to true if body contains HTML content.",
                        "default": False,
                    },
                },
                "required": ["to", "subject", "body"],
            },
        ),
    ]


# ── Tool execution ────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        svc = service()

        if name == "list_emails":
            label = arguments.get("label", "INBOX").upper()
            emails = gmail.list_emails(
                svc,
                label_ids=[label],
                max_results=arguments.get("max_results", 10),
                query=arguments.get("query", ""),
            )
            return [types.TextContent(type="text", text=json.dumps(emails, indent=2))]

        elif name == "get_email":
            email = gmail.get_email(svc, arguments["message_id"])
            return [types.TextContent(type="text", text=json.dumps(email, indent=2))]

        elif name == "get_thread":
            messages = gmail.get_thread(svc, arguments["thread_id"])
            return [types.TextContent(type="text", text=json.dumps(messages, indent=2))]

        elif name == "search_emails":
            emails = gmail.list_emails(
                svc,
                max_results=arguments.get("max_results", 20),
                query=arguments["query"],
            )
            return [types.TextContent(type="text", text=json.dumps(emails, indent=2))]

        elif name == "list_labels":
            labels = gmail.list_labels(svc)
            return [types.TextContent(type="text", text=json.dumps(labels, indent=2))]

        elif name == "send_email":
            result = gmail.send_email(
                svc,
                to=arguments["to"],
                subject=arguments["subject"],
                body=arguments["body"],
                cc=arguments.get("cc", ""),
                html=arguments.get("html", False),
            )
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except FileNotFoundError as e:
        return [types.TextContent(type="text", text=f"Setup error: {e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error calling {name}: {e}")]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
