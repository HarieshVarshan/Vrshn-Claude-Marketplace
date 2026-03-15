#!/usr/bin/env python3
"""
Email MCP Server - Provides email tools for Claude via IMAP/SMTP.

Usage:
    python mcp_server.py

Environment Variables:
    EMAIL_CONFIG - Path to .env file (default: ~/.config/email-mcp/.env)
"""

import traceback
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from email_client import get_email_client

# Create the MCP server
server = Server("email")


def _format_address(addr: dict) -> str:
    """Format an address dict as 'Name <email>' or just 'email'."""
    name = addr.get('name', '')
    address = addr.get('address', '')
    if name:
        return f"{name} <{address}>"
    return address


def _format_address_list(addrs: list) -> str:
    """Format a list of address dicts."""
    return ', '.join(_format_address(a) for a in addrs) if addrs else 'N/A'


def _format_email_detail(msg: dict) -> str:
    """Format a full email message for display."""
    output = []
    output.append(f"# {msg.get('subject', '(No Subject)')}")
    output.append("")
    output.append(f"**UID:** {msg.get('uid')}")
    output.append(f"**Message-ID:** {msg.get('messageId', 'N/A')}")
    output.append(f"**From:** {_format_address_list(msg.get('from', []))}")
    output.append(f"**To:** {_format_address_list(msg.get('to', []))}")
    if msg.get('cc'):
        output.append(f"**CC:** {_format_address_list(msg['cc'])}")
    output.append(f"**Date:** {msg.get('date', 'Unknown')}")

    if msg.get('attachments'):
        output.append("")
        output.append(f"**Attachments ({len(msg['attachments'])}):**")
        for att in msg['attachments']:
            size_kb = att.get('size', 0) / 1024
            output.append(f"  - {att['filename']} ({att.get('contentType', 'unknown')}, {size_kb:.1f} KB)")

    output.append("")
    output.append("## Body")
    output.append(msg.get('body', '(empty)'))

    return '\n'.join(output)


def _format_email_list(data: dict) -> str:
    """Format email list results."""
    emails = data.get('emails', [])
    total = data.get('total', 0)
    folder = data.get('folder', 'INBOX')

    output = [f"# Emails in {folder} ({len(emails)} of {total})\n"]

    for msg in emails:
        from_str = _format_address_list(msg.get('from', []))
        subject = msg.get('subject', '(No Subject)')
        date = msg.get('date', '')[:10]  # Just the date part
        flags = msg.get('flags', [])
        uid = msg.get('uid')

        seen = 'Seen' in flags
        flag_str = ' '.join(f'[{f}]' for f in flags) if flags else ''
        att_count = msg.get('attachmentCount', 0)
        att_str = f' [{att_count} att]' if att_count > 0 else ''
        read_marker = '' if seen else '* '

        output.append(f"- {read_marker}**{subject}** (UID: {uid})")
        output.append(f"  From: {from_str} | {date}{att_str} {flag_str}")

    if data.get('offset') is not None:
        output.append(f"\n_Showing offset {data['offset']} to {data['offset'] + len(emails)}_")

    return '\n'.join(output)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available email tools."""
    return [
        # ========== Send ==========
        Tool(
            name="email_send",
            description="Send an email with optional attachments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of recipient email addresses"
                    },
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email content (plain text or HTML)"},
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of CC email addresses"
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of BCC email addresses"
                    },
                    "attachments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "filename": {"type": "string"},
                                "path": {"type": "string"}
                            },
                            "required": ["path"]
                        },
                        "description": "Array of attachment objects with 'filename' and 'path'"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        ),

        # ========== Get ==========
        Tool(
            name="email_get",
            description="Get full details of a specific email by UID. Use the numeric 'uid' from email_list/email_search results, NOT the 'messageId'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "uid": {"type": "integer", "description": "IMAP UID (numeric, from email_list/email_search results)"},
                    "folder": {"type": "string", "description": "Folder name (default: INBOX)"},
                    "mark_seen": {"type": "boolean", "description": "Mark email as seen (default: false)"}
                },
                "required": ["uid"]
            }
        ),

        # ========== List ==========
        Tool(
            name="email_list",
            description="List emails from a folder. Returns summaries with UIDs for further operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Folder name (default: INBOX)"},
                    "limit": {"type": "integer", "description": "Maximum emails to return (default: 50)"},
                    "offset": {"type": "integer", "description": "Starting offset for pagination (default: 0)"},
                    "unread_only": {"type": "boolean", "description": "Return only unread emails (default: false)"}
                },
                "required": []
            }
        ),

        # ========== Search ==========
        Tool(
            name="email_search",
            description="Search emails by multiple criteria. All parameters are optional filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (searches in subject and body)"},
                    "folder": {"type": "string", "description": "Folder name (default: INBOX)"},
                    "from_addr": {"type": "string", "description": "Filter by sender email address"},
                    "subject": {"type": "string", "description": "Filter by subject"},
                    "date_from": {"type": "string", "description": "Filter by start date (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "Filter by end date (YYYY-MM-DD)"},
                    "limit": {"type": "integer", "description": "Maximum results (default: 50)"}
                },
                "required": []
            }
        ),

        # ========== Delete ==========
        Tool(
            name="email_delete",
            description="Delete one or more emails by UID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of IMAP UIDs to delete"
                    },
                    "folder": {"type": "string", "description": "Folder name (default: INBOX)"},
                    "permanent": {"type": "boolean", "description": "Permanently delete instead of moving to trash (default: false)"}
                },
                "required": ["ids"]
            }
        ),

        # ========== Move ==========
        Tool(
            name="email_move",
            description="Move one or more emails to a different folder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of IMAP UIDs to move"
                    },
                    "source_folder": {"type": "string", "description": "Source folder (default: INBOX)"},
                    "target_folder": {"type": "string", "description": "Target folder name"}
                },
                "required": ["ids", "target_folder"]
            }
        ),

        # ========== Folders ==========
        Tool(
            name="email_get_folders",
            description="List all available email folders.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # ========== Download Attachment ==========
        Tool(
            name="email_download_attachment",
            description="Download attachment(s) from an email. Use the numeric 'uid' from email_list/email_search results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "uid": {"type": "integer", "description": "IMAP UID (numeric, from email_list/email_search results)"},
                    "folder": {"type": "string", "description": "Folder name (default: INBOX)"},
                    "filename": {"type": "string", "description": "Specific filename to download (omit for all attachments)"},
                    "save_path": {"type": "string", "description": "Directory path to save files (omit to return base64 content)"}
                },
                "required": ["uid"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        client = get_email_client()
        result = ""

        # ========== Send ==========
        if name == "email_send":
            response = client.send_email(
                to=arguments["to"],
                subject=arguments["subject"],
                body=arguments["body"],
                cc=arguments.get("cc"),
                bcc=arguments.get("bcc"),
                attachments=arguments.get("attachments"),
            )
            att_str = f" with {response['attachmentCount']} attachment(s)" if response['attachmentCount'] else ""
            result = (
                f"Email sent{att_str}.\n"
                f"**To:** {', '.join(response['to'])}\n"
                f"**Subject:** {response['subject']}"
            )
            if response.get('cc'):
                result += f"\n**CC:** {', '.join(response['cc'])}"

        # ========== Get ==========
        elif name == "email_get":
            msg = client.get_email(
                uid=arguments["uid"],
                folder=arguments.get("folder", "INBOX"),
                mark_seen=arguments.get("mark_seen", False),
            )
            result = _format_email_detail(msg)

        # ========== List ==========
        elif name == "email_list":
            data = client.list_emails(
                folder=arguments.get("folder", "INBOX"),
                limit=arguments.get("limit", 50),
                offset=arguments.get("offset", 0),
                unread_only=arguments.get("unread_only", False),
            )
            result = _format_email_list(data)

        # ========== Search ==========
        elif name == "email_search":
            data = client.search_emails(
                folder=arguments.get("folder", "INBOX"),
                query=arguments.get("query"),
                from_addr=arguments.get("from_addr"),
                subject=arguments.get("subject"),
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
                limit=arguments.get("limit", 50),
            )
            result = _format_email_list(data)
            if data.get('query'):
                result += f"\n\n_IMAP search: `{data['query']}`_"

        # ========== Delete ==========
        elif name == "email_delete":
            response = client.delete_emails(
                ids=arguments["ids"],
                folder=arguments.get("folder", "INBOX"),
                permanent=arguments.get("permanent", False),
            )
            action = "permanently deleted" if response['permanent'] else "moved to trash"
            result = f"{len(response['ids'])} email(s) {action} from {response['folder']}."

        # ========== Move ==========
        elif name == "email_move":
            response = client.move_emails(
                ids=arguments["ids"],
                target_folder=arguments["target_folder"],
                source_folder=arguments.get("source_folder", "INBOX"),
            )
            result = (
                f"{len(response['ids'])} email(s) moved.\n"
                f"**From:** {response['sourceFolder']}\n"
                f"**To:** {response['targetFolder']}"
            )

        # ========== Folders ==========
        elif name == "email_get_folders":
            folders = client.get_folders()
            output = [f"# Email Folders ({len(folders)} found)\n"]
            for f in folders:
                flags = f.get('flags', '')
                flag_info = f" ({flags})" if flags else ""
                output.append(f"- **{f['name']}**{flag_info}")
            result = '\n'.join(output)

        # ========== Download Attachment ==========
        elif name == "email_download_attachment":
            attachments = client.download_attachment(
                uid=arguments["uid"],
                folder=arguments.get("folder", "INBOX"),
                filename=arguments.get("filename"),
                save_path=arguments.get("save_path"),
            )
            if not attachments:
                result = "No attachments found matching the criteria."
            else:
                output = [f"# Downloaded {len(attachments)} attachment(s)\n"]
                for att in attachments:
                    size_kb = att.get('size', 0) / 1024
                    if att.get('path'):
                        output.append(f"- **{att['filename']}** ({size_kb:.1f} KB) -> `{att['path']}`")
                    else:
                        output.append(f"- **{att['filename']}** ({size_kb:.1f} KB) [base64 content returned]")
                result = '\n'.join(output)

        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        error_msg = f"**Error** in `{name}`: {str(e)}\n\n<details><summary>Traceback</summary>\n\n```\n{traceback.format_exc()}\n```\n</details>"
        return [TextContent(type="text", text=error_msg)]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
