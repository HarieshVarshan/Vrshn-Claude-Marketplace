#!/usr/bin/env python3
"""
Confluence MCP Server - Provides Confluence tools for Claude.

Usage:
    python mcp_server.py

Environment Variables:
    CONFLUENCE_CONFIG - Path to .env file (default: ~/.config/confluence-mcp/.env)
"""

import json
import os
import traceback
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from confluence_client import get_confluence_client
from confluence_converter import (
    confluence_xhtml_to_markdown,
    is_xhtml_content,
    markdown_to_confluence_xhtml,
)
from confluence_errors import classify_error, cleanup_old_logs, log_error
from confluence_file_io import (
    read_content_from_file,
    save_page_to_directory,
    save_page_to_file,
)

# Create the MCP server
server = Server("confluence")


def _convert_content_for_storage(content: str) -> str:
    """Auto-detect Markdown vs XHTML and convert to Confluence storage format if needed."""
    if is_xhtml_content(content):
        return content
    return markdown_to_confluence_xhtml(content)


def _xhtml_to_markdown_safe(xhtml: str) -> str:
    """Convert XHTML to Markdown, returning raw XHTML on failure."""
    try:
        return confluence_xhtml_to_markdown(xhtml)
    except Exception:
        return xhtml


def format_page(page: dict) -> str:
    """Format a Confluence page for display, converting XHTML content to Markdown."""
    output = []
    output.append(f"# {page.get('title', 'Untitled')}")
    output.append("")
    output.append(f"**ID:** {page.get('id')}")
    output.append(f"**Space:** {page.get('space', {}).get('key', 'Unknown')}")

    version = page.get('version', {})
    output.append(f"**Version:** {version.get('number', 'Unknown')}")
    output.append(f"**Last Modified:** {version.get('when', 'Unknown')}")
    if version.get('by'):
        output.append(f"**Modified By:** {version['by'].get('displayName', 'Unknown')}")

    output.append("")
    output.append("## Content")
    body = page.get('body', {})
    raw_content = body.get('view', {}).get('value') or body.get('storage', {}).get('value') or 'No content'
    content = _xhtml_to_markdown_safe(raw_content) if raw_content != 'No content' else raw_content
    output.append(content)

    return '\n'.join(output)


def format_pages_list(pages: list, title: str = "Pages") -> str:
    """Format a list of pages."""
    output = [f"# {title} ({len(pages)} found)\n"]
    for page in pages:
        space = page.get('space', {}).get('key', 'Unknown')
        page_title = page.get('title', 'Untitled')
        page_id = page.get('id')
        output.append(f"- [{space}] **{page_title}** (ID: {page_id})")
    return '\n'.join(output)


def _build_page_metadata(page: dict, base_url: str) -> dict:
    """Extract metadata dict from a page response for file I/O front matter."""
    page_id = page.get('id')
    return {
        'page_id': page_id,
        'space': page.get('space', {}).get('key', ''),
        'version': page.get('version', {}).get('number'),
        'url': f"{base_url}/pages/viewpage.action?pageId={page_id}",
        'last_modified': page.get('version', {}).get('when', ''),
    }


def _handle_page_save(page: dict, arguments: dict, client) -> str:
    """Handle save_to_file / save_to_dir for get_page and get_page_by_title tools.

    Returns additional output text about the save operation, or empty string.
    """
    extra = ''
    body = page.get('body', {})
    raw_content = body.get('storage', {}).get('value') or body.get('view', {}).get('value') or ''
    md_content = _xhtml_to_markdown_safe(raw_content) if raw_content else ''
    title = page.get('title', 'Untitled')
    metadata = _build_page_metadata(page, client.base_url)

    if arguments.get('save_to_file'):
        saved = save_page_to_file(arguments['save_to_file'], title, md_content, metadata)
        extra += f"\n\nSaved to: `{saved}`"

    if arguments.get('save_to_dir'):
        saved = save_page_to_directory(arguments['save_to_dir'], title, md_content, metadata)
        extra += f"\n\nSaved to directory: `{os.path.dirname(saved)}`"
        # Download attachments into attachments/ subdir
        try:
            attachments = client.get_page_attachments(page.get('id'), limit=100)
            att_dir = os.path.join(os.path.dirname(saved), 'attachments')
            for att in attachments.get('results', []):
                att_title = att.get('title', 'unknown')
                att_path = os.path.join(att_dir, att_title)
                try:
                    client.download_attachment(att.get('id'), att_path)
                    extra += f"\n  - Downloaded: `{att_title}`"
                except Exception:
                    extra += f"\n  - Failed to download: `{att_title}`"
        except Exception:
            pass

    return extra


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Confluence tools."""
    return [
        # ========== Pages ==========
        Tool(
            name="confluence_get_page",
            description="Get a Confluence page by ID or URL. Returns content as Markdown.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or full Confluence URL"},
                    "save_to_file": {"type": "string", "description": "Optional local file path to save page as Markdown"},
                    "save_to_dir": {"type": "string", "description": "Optional local directory path to save page as index.md + attachments/"}
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_get_page_by_title",
            description="Get a Confluence page by space key and title. Returns content as Markdown.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string", "description": "Space key (e.g., DOCS)"},
                    "title": {"type": "string", "description": "Exact page title"},
                    "save_to_file": {"type": "string", "description": "Optional local file path to save page as Markdown"},
                    "save_to_dir": {"type": "string", "description": "Optional local directory path to save page as index.md + attachments/"}
                },
                "required": ["space_key", "title"]
            }
        ),
        Tool(
            name="confluence_create_page",
            description="Create a new Confluence page. Content can be Markdown (auto-converted) or XHTML. Optionally read content from a local file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string", "description": "Space key"},
                    "title": {"type": "string", "description": "Page title"},
                    "content": {"type": "string", "description": "Page content in Markdown or XHTML (optional if file_path provided)"},
                    "file_path": {"type": "string", "description": "Local file path to read content from (Markdown or XHTML)"},
                    "parent_id": {"type": "string", "description": "Optional parent page ID"}
                },
                "required": ["space_key", "title"]
            }
        ),
        Tool(
            name="confluence_update_page",
            description="Update an existing Confluence page. Content can be Markdown (auto-converted) or XHTML. Optionally read content from a local file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID"},
                    "title": {"type": "string", "description": "New title"},
                    "content": {"type": "string", "description": "New content in Markdown or XHTML (optional if file_path provided)"},
                    "file_path": {"type": "string", "description": "Local file path to read content from (Markdown or XHTML)"}
                },
                "required": ["page_id", "title"]
            }
        ),
        Tool(
            name="confluence_delete_page",
            description="Delete a Confluence page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"}
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_get_page_children",
            description="Get child pages of a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_get_page_ancestors",
            description="Get parent hierarchy of a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"}
                },
                "required": ["page_id"]
            }
        ),

        # ========== Search ==========
        Tool(
            name="confluence_search",
            description="Search Confluence using CQL or text. Examples: 'text ~ \"term\"', 'space = DOCS'",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (text or CQL)"},
                    "space_key": {"type": "string", "description": "Limit to space"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["query"]
            }
        ),

        # ========== Spaces ==========
        Tool(
            name="confluence_get_all_spaces",
            description="List all Confluence spaces.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": []
            }
        ),
        Tool(
            name="confluence_get_space",
            description="Get space details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string", "description": "Space key"}
                },
                "required": ["space_key"]
            }
        ),
        Tool(
            name="confluence_get_space_pages",
            description="List all pages in a space.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string", "description": "Space key"},
                    "limit": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["space_key"]
            }
        ),

        # ========== Comments ==========
        Tool(
            name="confluence_add_comment",
            description="Add a comment to a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID"},
                    "comment": {"type": "string", "description": "Comment text"}
                },
                "required": ["page_id", "comment"]
            }
        ),
        Tool(
            name="confluence_get_page_comments",
            description="Get comments for a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["page_id"]
            }
        ),

        # ========== Labels ==========
        Tool(
            name="confluence_get_page_labels",
            description="Get labels for a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"}
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_add_page_label",
            description="Add a label to a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "label": {"type": "string", "description": "Label name"}
                },
                "required": ["page_id", "label"]
            }
        ),
        Tool(
            name="confluence_remove_page_label",
            description="Remove a label from a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "label": {"type": "string", "description": "Label name"}
                },
                "required": ["page_id", "label"]
            }
        ),

        # ========== Attachments ==========
        Tool(
            name="confluence_get_page_attachments",
            description="Get attachments for a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["page_id"]
            }
        ),

        # ========== History & Versions ==========
        Tool(
            name="confluence_get_page_history",
            description="Get page version history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"}
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_list_page_versions",
            description="List all versions of a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_get_page_version",
            description="Read a specific historical version of a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "version_number": {"type": "integer", "description": "Version number to read"}
                },
                "required": ["page_id", "version_number"]
            }
        ),

        # ========== Page Move/Copy ==========
        Tool(
            name="confluence_move_page",
            description="Move a page to a different space or parent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "target_space_key": {"type": "string", "description": "Destination space key"},
                    "target_parent_id": {"type": "string", "description": "New parent page ID"}
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_copy_page",
            description="Copy a page to a new location.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Source page ID or URL"},
                    "destination_space_key": {"type": "string", "description": "Destination space key"},
                    "destination_parent_id": {"type": "string", "description": "Destination parent page ID"},
                    "new_title": {"type": "string", "description": "Title for the copy"},
                    "copy_labels": {"type": "boolean", "description": "Copy labels", "default": True}
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_get_page_descendants",
            description="Get all descendant pages (recursive children).",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "limit": {"type": "integer", "description": "Max results", "default": 100}
                },
                "required": ["page_id"]
            }
        ),

        # ========== Space Management ==========
        Tool(
            name="confluence_create_space",
            description="Create a new Confluence space.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string", "description": "Unique space key (uppercase)"},
                    "name": {"type": "string", "description": "Space name"},
                    "description": {"type": "string", "description": "Space description"}
                },
                "required": ["space_key", "name"]
            }
        ),
        Tool(
            name="confluence_update_space",
            description="Update a space's name or description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string", "description": "Space key"},
                    "name": {"type": "string", "description": "New name"},
                    "description": {"type": "string", "description": "New description"}
                },
                "required": ["space_key"]
            }
        ),
        Tool(
            name="confluence_delete_space",
            description="Delete a Confluence space.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string", "description": "Space key"}
                },
                "required": ["space_key"]
            }
        ),

        # ========== Attachment Management ==========
        Tool(
            name="confluence_get_attachment",
            description="Get attachment metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "attachment_id": {"type": "string", "description": "Attachment ID"}
                },
                "required": ["attachment_id"]
            }
        ),
        Tool(
            name="confluence_upload_attachment",
            description="Upload an attachment to a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "file_path": {"type": "string", "description": "Local file path to upload"},
                    "comment": {"type": "string", "description": "Attachment comment"}
                },
                "required": ["page_id", "file_path"]
            }
        ),
        Tool(
            name="confluence_download_attachment",
            description="Download an attachment to local filesystem.",
            inputSchema={
                "type": "object",
                "properties": {
                    "attachment_id": {"type": "string", "description": "Attachment ID"},
                    "download_path": {"type": "string", "description": "Local path to save file"}
                },
                "required": ["attachment_id", "download_path"]
            }
        ),
        Tool(
            name="confluence_delete_attachment",
            description="Delete an attachment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "attachment_id": {"type": "string", "description": "Attachment ID"}
                },
                "required": ["attachment_id"]
            }
        ),

        # ========== Page Restrictions ==========
        Tool(
            name="confluence_get_page_restrictions",
            description="Get view/edit restrictions for a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"}
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_set_page_restrictions",
            description="Set view/edit restrictions for a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"},
                    "operation": {"type": "string", "description": "'read' for view, 'update' for edit"},
                    "users": {"type": "array", "items": {"type": "string"}, "description": "Usernames to grant access"},
                    "groups": {"type": "array", "items": {"type": "string"}, "description": "Groups to grant access"}
                },
                "required": ["page_id", "operation"]
            }
        ),
        Tool(
            name="confluence_remove_page_restrictions",
            description="Remove all restrictions from a page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID or URL"}
                },
                "required": ["page_id"]
            }
        ),

        # ========== Users ==========
        Tool(
            name="confluence_search_users",
            description="Search for Confluence users.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (name or username)"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="confluence_get_current_user",
            description="Get the currently authenticated user.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # ========== Watch ==========
        Tool(
            name="confluence_is_watching_content",
            description="Check if the current user is watching a piece of content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {"type": "string", "description": "Content ID (page, blog post, etc.)"}
                },
                "required": ["content_id"]
            }
        ),
        Tool(
            name="confluence_watch_content",
            description="Start watching a piece of content (page, blog post, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {"type": "string", "description": "Content ID to watch"}
                },
                "required": ["content_id"]
            }
        ),
        Tool(
            name="confluence_unwatch_content",
            description="Stop watching a piece of content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {"type": "string", "description": "Content ID to unwatch"}
                },
                "required": ["content_id"]
            }
        ),
        Tool(
            name="confluence_watch_space",
            description="Start watching a space.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string", "description": "Space key to watch"}
                },
                "required": ["space_key"]
            }
        ),
        Tool(
            name="confluence_unwatch_space",
            description="Stop watching a space.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string", "description": "Space key to unwatch"}
                },
                "required": ["space_key"]
            }
        ),

        # ========== Raw API ==========
        Tool(
            name="confluence_raw_api",
            description="Make a raw API call to Confluence. Use this for operations not covered by other tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method (GET, POST, PUT, DELETE)"},
                    "endpoint": {"type": "string", "description": "API endpoint (e.g., '/rest/api/content/123456')"},
                    "body": {"type": "object", "description": "Request body for POST/PUT requests"},
                    "params": {"type": "object", "description": "Query parameters"}
                },
                "required": ["method", "endpoint"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        client = get_confluence_client()
        result = ""

        # ========== Pages ==========
        if name == "confluence_get_page":
            page = client.get_page(arguments["page_id"])
            result = format_page(page)
            result += _handle_page_save(page, arguments, client)

        elif name == "confluence_get_page_by_title":
            response = client.get_page_by_title(arguments["space_key"], arguments["title"])
            pages = response.get('results', [])
            if not pages:
                result = f"No page found with title '{arguments['title']}' in space '{arguments['space_key']}'"
            else:
                page = client.get_page(pages[0]['id'])
                result = format_page(page)
                result += _handle_page_save(page, arguments, client)

        elif name == "confluence_create_page":
            # Resolve content from file_path or content param
            content = arguments.get("content", "")
            if arguments.get("file_path"):
                content = read_content_from_file(arguments["file_path"])
            if not content:
                return [TextContent(type="text", text="Error: Either 'content' or 'file_path' must be provided.")]
            content = _convert_content_for_storage(content)
            created = client.create_page(
                space_key=arguments["space_key"],
                title=arguments["title"],
                content=content,
                parent_id=arguments.get("parent_id")
            )
            page_id = created.get('id')
            page_url = f"{client.base_url}/pages/viewpage.action?pageId={page_id}"
            result = f"Page created: **{arguments['title']}**\nID: {page_id}\nURL: {page_url}"

        elif name == "confluence_update_page":
            # Resolve content from file_path or content param
            content = arguments.get("content", "")
            if arguments.get("file_path"):
                content = read_content_from_file(arguments["file_path"])
            if not content:
                return [TextContent(type="text", text="Error: Either 'content' or 'file_path' must be provided.")]
            content = _convert_content_for_storage(content)
            updated = client.update_page(
                page_id=arguments["page_id"],
                title=arguments["title"],
                content=content
            )
            version = updated.get('version', {}).get('number', 'unknown')
            result = f"Page updated: **{arguments['title']}**\nNew version: {version}"

        elif name == "confluence_delete_page":
            client.delete_page(arguments["page_id"])
            result = f"Page {arguments['page_id']} deleted."

        elif name == "confluence_get_page_children":
            children = client.get_page_children(arguments["page_id"], arguments.get("limit", 25))
            result = format_pages_list(children.get('results', []), "Child Pages")

        elif name == "confluence_get_page_ancestors":
            ancestors = client.get_page_ancestors(arguments["page_id"])
            output = ["# Page Ancestors\n"]
            for i, a in enumerate(ancestors):
                indent = "  " * i
                output.append(f"{indent}- **{a.get('title', 'Unknown')}** (ID: {a.get('id')})")
            result = '\n'.join(output) if ancestors else "No ancestors (root page)"

        # ========== Search ==========
        elif name == "confluence_search":
            space_key = arguments.get("space_key")
            limit = arguments.get("limit", 25)
            response = client.search_content(arguments["query"], space_key=space_key, limit=limit)
            result = format_pages_list(response.get('results', []), "Search Results")

        # ========== Spaces ==========
        elif name == "confluence_get_all_spaces":
            spaces = client.get_all_spaces(arguments.get("limit", 50))
            output = [f"# Spaces ({len(spaces.get('results', []))} found)\n"]
            for space in spaces.get('results', []):
                output.append(f"- **{space.get('key')}**: {space.get('name', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "confluence_get_space":
            space = client.get_space(arguments["space_key"])
            output = [f"# Space: {space.get('name', 'Unknown')}"]
            output.append(f"**Key:** {space.get('key')}")
            output.append(f"**Type:** {space.get('type', 'N/A')}")
            desc = space.get('description', {}).get('plain', {}).get('value', 'N/A')
            output.append(f"**Description:** {desc}")
            if space.get('homepage'):
                output.append(f"**Homepage:** {space['homepage'].get('title', 'N/A')}")
            result = '\n'.join(output)

        elif name == "confluence_get_space_pages":
            response = client.get_space_pages(arguments["space_key"], arguments.get("limit", 50))
            result = format_pages_list(response.get('results', []), f"Pages in {arguments['space_key']}")

        # ========== Comments ==========
        elif name == "confluence_add_comment":
            client.add_comment(arguments["page_id"], arguments["comment"])
            result = f"Comment added to page {arguments['page_id']}"

        elif name == "confluence_get_page_comments":
            comments = client.get_page_comments(arguments["page_id"], arguments.get("limit", 25))
            output = [f"# Comments ({len(comments.get('results', []))} found)\n"]
            for c in comments.get('results', []):
                body = c.get('body', {}).get('storage', {}).get('value', 'No content')
                output.append(f"- {body[:200]}...")
            result = '\n'.join(output)

        # ========== Labels ==========
        elif name == "confluence_get_page_labels":
            labels = client.get_page_labels(arguments["page_id"])
            output = [f"# Labels ({len(labels)} found)\n"]
            for label in labels:
                output.append(f"- {label.get('name', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "confluence_add_page_label":
            client.add_page_label(arguments["page_id"], arguments["label"])
            result = f"Label '{arguments['label']}' added to page {arguments['page_id']}"

        elif name == "confluence_remove_page_label":
            client.remove_page_label(arguments["page_id"], arguments["label"])
            result = f"Label '{arguments['label']}' removed from page {arguments['page_id']}"

        # ========== Attachments ==========
        elif name == "confluence_get_page_attachments":
            attachments = client.get_page_attachments(arguments["page_id"], arguments.get("limit", 25))
            output = [f"# Attachments ({len(attachments.get('results', []))} found)\n"]
            for a in attachments.get('results', []):
                output.append(f"- **{a.get('title', 'Unknown')}** (ID: {a.get('id')})")
            result = '\n'.join(output)

        # ========== History ==========
        elif name == "confluence_get_page_history":
            history = client.get_page_history(arguments["page_id"])
            output = ["# Page History"]
            output.append(f"**Created:** {history.get('createdDate', 'Unknown')}")
            if history.get('createdBy'):
                output.append(f"**Created By:** {history['createdBy'].get('displayName', 'Unknown')}")
            output.append(f"**Latest Version:** {history.get('lastUpdated', {}).get('number', 'Unknown')}")
            result = '\n'.join(output)

        # ========== Page Versions ==========
        elif name == "confluence_list_page_versions":
            versions = client.list_page_versions(arguments["page_id"], arguments.get("limit", 25))
            output = [f"# Page Versions ({len(versions.get('results', []))} found)\n"]
            for v in versions.get('results', []):
                by_name = v.get('by', {}).get('displayName', 'Unknown')
                output.append(f"- **v{v.get('number')}**: {v.get('when', 'Unknown')} by {by_name}")
                if v.get('message'):
                    output.append(f"  _{v.get('message')}_")
            result = '\n'.join(output)

        elif name == "confluence_get_page_version":
            version = client.get_page_version(arguments["page_id"], arguments["version_number"])
            output = [f"# Page Version {version.get('number')}"]
            output.append(f"**When:** {version.get('when', 'Unknown')}")
            if version.get('by'):
                output.append(f"**By:** {version['by'].get('displayName', 'Unknown')}")
            if version.get('message'):
                output.append(f"**Message:** {version.get('message')}")
            content = version.get('content', {})
            if content:
                raw_body = content.get('body', {}).get('storage', {}).get('value', 'No content')
                md_body = _xhtml_to_markdown_safe(raw_body) if raw_body != 'No content' else raw_body
                output.append("\n## Content")
                output.append(md_body)
            result = '\n'.join(output)

        # ========== Page Move/Copy ==========
        elif name == "confluence_move_page":
            moved = client.move_page(
                arguments["page_id"],
                target_space_key=arguments.get("target_space_key"),
                target_parent_id=arguments.get("target_parent_id")
            )
            result = f"Page moved: **{moved.get('title')}**\nNew version: {moved.get('version', {}).get('number')}"

        elif name == "confluence_copy_page":
            copied = client.copy_page(
                arguments["page_id"],
                destination_space_key=arguments.get("destination_space_key"),
                destination_parent_id=arguments.get("destination_parent_id"),
                new_title=arguments.get("new_title"),
                copy_labels=arguments.get("copy_labels", True)
            )
            page_url = f"{client.base_url}/pages/viewpage.action?pageId={copied.get('id')}"
            result = f"Page copied: **{copied.get('title')}**\nID: {copied.get('id')}\nURL: {page_url}"

        elif name == "confluence_get_page_descendants":
            descendants = client.get_page_descendants(arguments["page_id"], arguments.get("limit", 100))
            result = format_pages_list(descendants.get('results', []), "Descendant Pages")

        # ========== Space Management ==========
        elif name == "confluence_create_space":
            created = client.create_space(
                arguments["space_key"],
                arguments["name"],
                arguments.get("description")
            )
            result = f"Space created: **{created.get('name')}**\nKey: {created.get('key')}"

        elif name == "confluence_update_space":
            updated = client.update_space(
                arguments["space_key"],
                name=arguments.get("name"),
                description=arguments.get("description")
            )
            result = f"Space updated: **{updated.get('name')}**\nKey: {updated.get('key')}"

        elif name == "confluence_delete_space":
            client.delete_space(arguments["space_key"])
            result = f"Space {arguments['space_key']} deleted."

        # ========== Attachment Management ==========
        elif name == "confluence_get_attachment":
            attachment = client.get_attachment(arguments["attachment_id"])
            output = [f"# Attachment: {attachment.get('title', 'Unknown')}"]
            output.append(f"**ID:** {attachment.get('id')}")
            output.append(f"**Type:** {attachment.get('metadata', {}).get('mediaType', 'Unknown')}")
            container = attachment.get('container', {})
            output.append(f"**Container:** {container.get('title', 'Unknown')} (ID: {container.get('id')})")
            version = attachment.get('version', {})
            output.append(f"**Version:** {version.get('number', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "confluence_upload_attachment":
            uploaded = client.upload_attachment(
                arguments["page_id"],
                arguments["file_path"],
                arguments.get("comment")
            )
            results = uploaded.get('results', [uploaded])
            if results:
                att = results[0] if isinstance(results, list) else results
                result = f"Attachment uploaded: **{att.get('title')}**\nID: {att.get('id')}"
            else:
                result = "Attachment uploaded successfully"

        elif name == "confluence_download_attachment":
            saved_path = client.download_attachment(
                arguments["attachment_id"],
                arguments["download_path"]
            )
            result = f"Attachment downloaded to: {saved_path}"

        elif name == "confluence_delete_attachment":
            client.delete_attachment(arguments["attachment_id"])
            result = f"Attachment {arguments['attachment_id']} deleted."

        # ========== Page Restrictions ==========
        elif name == "confluence_get_page_restrictions":
            restrictions = client.get_page_restrictions(arguments["page_id"])
            output = ["# Page Restrictions"]
            read_restrictions = restrictions.get('read', {}).get('restrictions', {})
            edit_restrictions = restrictions.get('update', {}).get('restrictions', {})

            output.append("\n## View Restrictions")
            users = read_restrictions.get('user', {}).get('results', [])
            groups = read_restrictions.get('group', {}).get('results', [])
            if users:
                output.append("**Users:** " + ", ".join(u.get('username', 'Unknown') for u in users))
            if groups:
                output.append("**Groups:** " + ", ".join(g.get('name', 'Unknown') for g in groups))
            if not users and not groups:
                output.append("_No view restrictions_")

            output.append("\n## Edit Restrictions")
            users = edit_restrictions.get('user', {}).get('results', [])
            groups = edit_restrictions.get('group', {}).get('results', [])
            if users:
                output.append("**Users:** " + ", ".join(u.get('username', 'Unknown') for u in users))
            if groups:
                output.append("**Groups:** " + ", ".join(g.get('name', 'Unknown') for g in groups))
            if not users and not groups:
                output.append("_No edit restrictions_")

            result = '\n'.join(output)

        elif name == "confluence_set_page_restrictions":
            client.set_page_restrictions(
                arguments["page_id"],
                arguments["operation"],
                users=arguments.get("users"),
                groups=arguments.get("groups")
            )
            op_name = "View" if arguments["operation"] == "read" else "Edit"
            result = f"{op_name} restrictions set for page {arguments['page_id']}"

        elif name == "confluence_remove_page_restrictions":
            client.remove_page_restrictions(arguments["page_id"])
            result = f"All restrictions removed from page {arguments['page_id']}"

        # ========== Users ==========
        elif name == "confluence_search_users":
            users = client.search_users(arguments["query"], arguments.get("limit", 25))
            output = [f"# Users ({len(users)} found)\n"]
            for u in users:
                user = u.get('user', u)
                output.append(f"- **{user.get('displayName', 'Unknown')}** ({user.get('username', 'Unknown')})")
            result = '\n'.join(output)

        elif name == "confluence_get_current_user":
            user = client.get_current_user()
            output = ["# Current User"]
            output.append(f"**Username:** {user.get('username', 'Unknown')}")
            output.append(f"**Display Name:** {user.get('displayName', 'Unknown')}")
            output.append(f"**Email:** {user.get('email', 'N/A')}")
            output.append(f"**Type:** {user.get('type', 'Unknown')}")
            result = '\n'.join(output)

        # ========== Watch ==========
        elif name == "confluence_is_watching_content":
            watching = client.is_watching_content(arguments["content_id"])
            status = "watching" if watching else "not watching"
            result = f"You are **{status}** content {arguments['content_id']}."

        elif name == "confluence_watch_content":
            client.watch_content(arguments["content_id"])
            result = f"Now watching content {arguments['content_id']}."

        elif name == "confluence_unwatch_content":
            client.unwatch_content(arguments["content_id"])
            result = f"Stopped watching content {arguments['content_id']}."

        elif name == "confluence_watch_space":
            client.watch_space(arguments["space_key"])
            result = f"Now watching space {arguments['space_key']}."

        elif name == "confluence_unwatch_space":
            client.unwatch_space(arguments["space_key"])
            result = f"Stopped watching space {arguments['space_key']}."

        # ========== Raw API ==========
        elif name == "confluence_raw_api":
            response = client.raw_api(
                method=arguments["method"],
                endpoint=arguments["endpoint"],
                body=arguments.get("body"),
                params=arguments.get("params")
            )
            result = f"# Raw API Response\n\n```json\n{json.dumps(response, indent=2)}\n```"

        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        error = classify_error(name, e)
        log_error(error)
        error_msg = error.format_for_user()
        error_msg += f"\n\n<details><summary>Traceback</summary>\n\n```\n{traceback.format_exc()}\n```\n</details>"
        return [TextContent(type="text", text=error_msg)]


async def main():
    """Run the MCP server."""
    cleanup_old_logs()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
