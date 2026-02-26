#!/usr/bin/env python3
"""
Obsidian MCP Server - Provides Obsidian vault tools for Claude.

Usage:
    python mcp_server.py

Environment Variables:
    OBSIDIAN_VAULT_PATH - Path to the Obsidian vault directory
"""

import json
import os
import re
import shutil
import traceback
from datetime import datetime, date
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import lzstring

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# Create the MCP server
server = Server("obsidian")

VAULT_PATH: Path | None = None


def get_vault_path() -> Path:
    """Get and validate the vault path."""
    global VAULT_PATH
    if VAULT_PATH is None:
        vault = os.environ.get("OBSIDIAN_VAULT_PATH")
        if not vault:
            raise ValueError("OBSIDIAN_VAULT_PATH environment variable is not set")
        VAULT_PATH = Path(vault).resolve()
        if not VAULT_PATH.is_dir():
            raise ValueError(f"Vault path does not exist: {VAULT_PATH}")
    return VAULT_PATH


def safe_path(note_path: str) -> Path:
    """Resolve a note path safely within the vault, preventing directory traversal."""
    vault = get_vault_path()
    # Normalize and resolve
    resolved = (vault / note_path).resolve()
    # Ensure it's within the vault
    if not str(resolved).startswith(str(vault)):
        raise ValueError(f"Path escapes vault directory: {note_path}")
    return resolved


def ensure_md_extension(note_path: str) -> str:
    """Add .md extension if not present."""
    if not note_path.endswith(".md"):
        note_path += ".md"
    return note_path


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from note content.

    Returns (frontmatter_dict, body_content).
    If no frontmatter exists, returns ({}, full_content).
    """
    if content.startswith("---"):
        # Find the closing ---
        end = content.find("---", 3)
        if end != -1:
            fm_text = content[3:end].strip()
            body = content[end + 3:].lstrip("\n")
            try:
                fm = yaml.safe_load(fm_text) or {}
            except yaml.YAMLError:
                fm = {}
            return fm, body
    return {}, content


def serialize_frontmatter(frontmatter: dict, body: str) -> str:
    """Serialize frontmatter dict and body back into note content."""
    if not frontmatter:
        return body
    fm_text = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True).strip()
    return f"---\n{fm_text}\n---\n{body}"


def collect_tags_from_content(content: str) -> set[str]:
    """Collect both frontmatter tags and inline #tags from content."""
    tags = set()
    fm, body = parse_frontmatter(content)

    # Frontmatter tags
    fm_tags = fm.get("tags", [])
    if isinstance(fm_tags, list):
        tags.update(str(t) for t in fm_tags)
    elif isinstance(fm_tags, str):
        tags.add(fm_tags)

    # Inline tags: #tag (but not inside code blocks or links)
    # Simple regex: match #word patterns not preceded by [[ or `
    for match in re.finditer(r'(?<!\[)(?<!`)#([a-zA-Z_][\w/-]*)', body):
        tags.add(match.group(1))

    return tags


def parse_task_line(line: str) -> dict | None:
    """Parse a markdown task line into a structured dict.

    Handles: - [ ] text #tag1 #tag2, - [x] text ✅ YYYY-MM-DD, indented tasks.
    Returns None if the line is not a task.
    """
    m = re.match(r'^(\s*)-\s+\[([ xX])\]\s+(.*)', line)
    if not m:
        return None

    indent = len(m.group(1))
    status_char = m.group(2)
    raw_text = m.group(3).strip()

    completed = status_char in ('x', 'X')

    # Extract completion date: ✅ YYYY-MM-DD
    completion_date = None
    date_match = re.search(r'✅\s*(\d{4}-\d{2}-\d{2})', raw_text)
    if date_match:
        completion_date = date_match.group(1)

    # Extract priority from emoji markers
    priority = None
    if '⏫' in raw_text:
        priority = 'highest'
    elif '🔼' in raw_text:
        priority = 'high'
    elif '🔽' in raw_text:
        priority = 'low'
    elif '⏬' in raw_text:
        priority = 'lowest'

    # Extract due date: 📅 YYYY-MM-DD
    due_date = None
    due_match = re.search(r'📅\s*(\d{4}-\d{2}-\d{2})', raw_text)
    if due_match:
        due_date = due_match.group(1)

    # Extract inline tags
    tags = re.findall(r'(?<!\[)(?<!`)#([a-zA-Z_][\w/-]*)', raw_text)

    # Clean text: remove emoji markers and completion date for display
    clean_text = re.sub(r'[✅📅⏫🔼🔽⏬]\s*\d{4}-\d{2}-\d{2}', '', raw_text)
    clean_text = re.sub(r'[✅📅⏫🔼🔽⏬]', '', clean_text).strip()

    return {
        'status': 'completed' if completed else 'open',
        'text': clean_text,
        'raw_text': raw_text,
        'tags': tags,
        'completion_date': completion_date,
        'due_date': due_date,
        'priority': priority,
        'indent': indent,
    }


def decompress_excalidraw_md(content: str) -> str | None:
    """Extract and decompress the compressed-json block from an .excalidraw.md file.

    The Obsidian Excalidraw plugin uses LZ-String compressToBase64 encoding.
    Returns the decompressed JSON string, or None if extraction fails.
    """
    # Find the compressed-json code block
    m = re.search(r'```compressed-json\s*\n([\s\S]*?)\n```', content)
    if not m:
        return None

    b64_data = m.group(1).replace('\n', '').replace('\r', '').strip()
    try:
        lz = lzstring.LZString()
        decompressed = lz.decompressFromBase64(b64_data)
        return decompressed if decompressed else None
    except Exception:
        return None


def is_excalidraw_md(content: str) -> bool:
    """Check if a .md file has excalidraw-plugin frontmatter indicating it's an Excalidraw drawing."""
    fm, _ = parse_frontmatter(content)
    return fm.get('excalidraw-plugin') in ('parsed', 'raw')


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Obsidian tools."""
    return [
        # ========== Notes ==========
        Tool(
            name="obsidian_read_note",
            description="Read a note's content by path. Path is relative to vault root (e.g., 'daily logger.md' or 'subfolder/note.md'). The .md extension is added automatically if omitted.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root (e.g., 'todo.md', 'subfolder/note.md')"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="obsidian_create_note",
            description="Create a new note with content. Will fail if the note already exists. Parent directories are created automatically.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root"},
                    "content": {"type": "string", "description": "Note content (markdown)"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags to add to frontmatter"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="obsidian_edit_note",
            description="Edit an existing note. Supports three modes: 'append' (add to end), 'prepend' (add to beginning, after frontmatter), or 'replace' (replace entire content).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root"},
                    "content": {"type": "string", "description": "Content to append/prepend/replace with"},
                    "mode": {
                        "type": "string",
                        "enum": ["append", "prepend", "replace"],
                        "description": "Edit mode: append, prepend, or replace",
                        "default": "append"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="obsidian_delete_note",
            description="Delete a note from the vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="obsidian_move_note",
            description="Move or rename a note within the vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Current note path relative to vault root"},
                    "destination": {"type": "string", "description": "New note path relative to vault root"}
                },
                "required": ["source", "destination"]
            }
        ),

        # ========== Search & List ==========
        Tool(
            name="obsidian_search_vault",
            description="Search notes by text content. Supports plain text and regex patterns. Returns matching notes with context around matches.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (plain text or regex pattern)"},
                    "regex": {"type": "boolean", "description": "Whether to treat query as regex", "default": False},
                    "case_sensitive": {"type": "boolean", "description": "Case-sensitive search", "default": False},
                    "max_results": {"type": "integer", "description": "Maximum number of matching notes to return", "default": 20}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="obsidian_list_notes",
            description="List notes in a directory or the entire vault. Returns note paths relative to vault root.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path relative to vault root (empty or omit for entire vault)", "default": ""},
                    "recursive": {"type": "boolean", "description": "Include subdirectories", "default": True},
                    "include_content_preview": {"type": "boolean", "description": "Include first 100 chars of each note", "default": False}
                },
                "required": []
            }
        ),

        # ========== Tags ==========
        Tool(
            name="obsidian_add_tags",
            description="Add tags to a note's YAML frontmatter. Creates frontmatter if it doesn't exist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to add (without # prefix)"
                    }
                },
                "required": ["path", "tags"]
            }
        ),
        Tool(
            name="obsidian_remove_tags",
            description="Remove tags from a note's YAML frontmatter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to remove (without # prefix)"
                    }
                },
                "required": ["path", "tags"]
            }
        ),
        Tool(
            name="obsidian_list_tags",
            description="List all tags used across the vault (both frontmatter and inline tags). Returns tags with their usage count.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # ========== Metadata ==========
        Tool(
            name="obsidian_update_frontmatter",
            description="Update specific fields in a note's YAML frontmatter without modifying the body. Creates frontmatter block if none exists. Set a value to null to remove that field.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root"},
                    "fields": {
                        "type": "object",
                        "description": "Key-value pairs to set in frontmatter. Use null to delete a field."
                    }
                },
                "required": ["path", "fields"]
            }
        ),
        Tool(
            name="obsidian_get_note_sections",
            description="Parse a note into its heading-delimited sections. Returns each section's heading level, title, line range, and optionally its content. Useful for understanding note structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root"},
                    "include_content": {
                        "type": "boolean",
                        "description": "Include each section's body text in the response (default: true)",
                        "default": True
                    }
                },
                "required": ["path"]
            }
        ),

        # ========== Directories ==========
        Tool(
            name="obsidian_create_directory",
            description="Create a new directory in the vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path relative to vault root"}
                },
                "required": ["path"]
            }
        ),

        # ========== Links ==========
        Tool(
            name="obsidian_get_backlinks",
            description="Find all notes that link to a given note using [[wiki-link]] syntax.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path to find backlinks for (e.g., 'todo.md')"}
                },
                "required": ["path"]
            }
        ),

        # ========== Tasks ==========
        Tool(
            name="obsidian_query_tasks",
            description="Query tasks (checkboxes) across the vault. Finds '- [ ]' and '- [x]' lines with filtering by status, tags, file pattern, text, and completion date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "completed", "all"],
                        "description": "Filter by task status",
                        "default": "all"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter tasks containing ALL of these tags (without # prefix)"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.md', 'project/*.md')"
                    },
                    "text_search": {
                        "type": "string",
                        "description": "Filter tasks containing this text (case-insensitive)"
                    },
                    "completed_after": {
                        "type": "string",
                        "description": "Only completed tasks after this date (YYYY-MM-DD)"
                    },
                    "completed_before": {
                        "type": "string",
                        "description": "Only completed tasks before this date (YYYY-MM-DD)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return",
                        "default": 50
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="obsidian_toggle_task",
            description="Toggle a task's completion status. Switches '- [ ]' to '- [x] ✅ YYYY-MM-DD' and vice versa. Identify the task by file path and either line number or text match.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root"},
                    "line_number": {
                        "type": "integer",
                        "description": "1-based line number of the task to toggle"
                    },
                    "text_match": {
                        "type": "string",
                        "description": "Unique text substring to find the task (used if line_number not provided)"
                    }
                },
                "required": ["path"]
            }
        ),

        # ========== Dataview ==========
        Tool(
            name="obsidian_dataview_query",
            description="Query notes like Dataview: filter by tags, folder, file name pattern, and frontmatter fields. Sort by mtime, name, or size. Returns a markdown table of results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter notes containing ALL of these tags (without # prefix)"
                    },
                    "from_folder": {
                        "type": "string",
                        "description": "Filter notes in this folder (relative to vault root)"
                    },
                    "file_name_pattern": {
                        "type": "string",
                        "description": "Glob pattern for file names (e.g., '*jenkins*')"
                    },
                    "where_frontmatter": {
                        "type": "object",
                        "description": "Filter by frontmatter key-value pairs (e.g., {\"status\": \"draft\"})"
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["file.mtime", "file.name", "file.size"],
                        "description": "Sort field",
                        "default": "file.name"
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort order",
                        "default": "asc"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to include in output. Options: file.name, file.path, file.mtime, file.size, file.tags, file.folder. Default: [file.name, file.mtime, file.tags]"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="obsidian_get_note_metadata",
            description="Get detailed metadata for a single note: file stats, frontmatter, all tags, outgoing [[links]], task counts, and word count.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Note path relative to vault root"}
                },
                "required": ["path"]
            }
        ),

        # ========== Excalidraw ==========
        Tool(
            name="obsidian_list_drawings",
            description="List all Excalidraw drawings in the vault (.excalidraw, .excalidraw.md, and .md files with excalidraw frontmatter). Returns path, type, size, modified date, and element count.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="obsidian_read_drawing",
            description="Read an Excalidraw drawing and return its JSON content. Handles both pure .excalidraw files and compressed .excalidraw.md files. Output can be fed into excalidraw-mcp's import_scene tool.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Drawing path relative to vault root (e.g., 'Excalidraw/diagram.excalidraw')"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="obsidian_save_drawing",
            description="Save Excalidraw JSON to the vault as a .excalidraw file. Use with excalidraw-mcp's export_scene output to save diagrams back to the vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to vault root (should end with .excalidraw)"},
                    "json_content": {"type": "string", "description": "Excalidraw JSON string to save"},
                    "overwrite": {
                        "type": "boolean",
                        "description": "Whether to overwrite if file exists",
                        "default": False
                    }
                },
                "required": ["path", "json_content"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        result = ""

        # ========== Notes ==========
        if name == "obsidian_read_note":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if not full_path.exists():
                result = f"Note not found: {note_path}"
            else:
                content = full_path.read_text(encoding="utf-8")
                result = f"## {note_path}\n\n{content}"

        elif name == "obsidian_create_note":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if full_path.exists():
                result = f"Note already exists: {note_path}. Use obsidian_edit_note to modify it."
            else:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                content = arguments["content"]
                tags = arguments.get("tags")
                if tags:
                    fm, body = parse_frontmatter(content)
                    existing = fm.get("tags", [])
                    if not isinstance(existing, list):
                        existing = [existing] if existing else []
                    for tag in tags:
                        tag = tag.lstrip("#")
                        if tag not in existing:
                            existing.append(tag)
                    fm["tags"] = existing
                    content = serialize_frontmatter(fm, body)
                full_path.write_text(content, encoding="utf-8")
                result = f"Created note: {note_path}"

        elif name == "obsidian_edit_note":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if not full_path.exists():
                result = f"Note not found: {note_path}. Use obsidian_create_note to create it."
            else:
                mode = arguments.get("mode", "append")
                new_content = arguments["content"]
                existing = full_path.read_text(encoding="utf-8")

                if mode == "replace":
                    final = new_content
                elif mode == "append":
                    final = existing.rstrip("\n") + "\n\n" + new_content
                elif mode == "prepend":
                    # Prepend after frontmatter if it exists
                    fm, body = parse_frontmatter(existing)
                    if fm:
                        final = serialize_frontmatter(fm, new_content + "\n\n" + body)
                    else:
                        final = new_content + "\n\n" + existing
                else:
                    result = f"Invalid mode: {mode}. Use 'append', 'prepend', or 'replace'."
                    return [TextContent(type="text", text=result)]

                full_path.write_text(final, encoding="utf-8")
                result = f"Edited note ({mode}): {note_path}"

        elif name == "obsidian_delete_note":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if not full_path.exists():
                result = f"Note not found: {note_path}"
            else:
                full_path.unlink()
                result = f"Deleted note: {note_path}"

        elif name == "obsidian_move_note":
            src_path = ensure_md_extension(arguments["source"])
            dst_path = ensure_md_extension(arguments["destination"])
            src_full = safe_path(src_path)
            dst_full = safe_path(dst_path)
            if not src_full.exists():
                result = f"Source note not found: {src_path}"
            elif dst_full.exists():
                result = f"Destination already exists: {dst_path}"
            else:
                dst_full.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_full), str(dst_full))
                result = f"Moved note: {src_path} -> {dst_path}"

        # ========== Search & List ==========
        elif name == "obsidian_search_vault":
            query = arguments["query"]
            use_regex = arguments.get("regex", False)
            case_sensitive = arguments.get("case_sensitive", False)
            max_results = arguments.get("max_results", 20)

            vault = get_vault_path()
            flags = 0 if case_sensitive else re.IGNORECASE

            if use_regex:
                try:
                    pattern = re.compile(query, flags)
                except re.error as e:
                    result = f"Invalid regex pattern: {e}"
                    return [TextContent(type="text", text=result)]
            else:
                pattern = re.compile(re.escape(query), flags)

            matches = []
            for md_file in vault.rglob("*.md"):
                # Skip hidden directories
                if any(part.startswith(".") for part in md_file.relative_to(vault).parts):
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8")
                except (UnicodeDecodeError, PermissionError):
                    continue

                found = list(pattern.finditer(content))
                if found:
                    rel_path = str(md_file.relative_to(vault))
                    lines = content.split("\n")
                    context_snippets = []
                    for m in found[:3]:  # Show up to 3 matches per file
                        # Find the line number
                        line_start = content.count("\n", 0, m.start())
                        start_line = max(0, line_start - 1)
                        end_line = min(len(lines), line_start + 2)
                        snippet = "\n".join(lines[start_line:end_line]).strip()
                        context_snippets.append(f"  L{line_start + 1}: {snippet}")

                    total = len(found)
                    match_text = f"({total} match{'es' if total > 1 else ''})"
                    matches.append(f"- **{rel_path}** {match_text}\n" + "\n".join(context_snippets))

                    if len(matches) >= max_results:
                        break

            if matches:
                result = f"# Search Results for '{query}' ({len(matches)} notes)\n\n" + "\n\n".join(matches)
            else:
                result = f"No results found for '{query}'"

        elif name == "obsidian_list_notes":
            directory = arguments.get("directory", "")
            recursive = arguments.get("recursive", True)
            preview = arguments.get("include_content_preview", False)

            vault = get_vault_path()
            if directory:
                base = safe_path(directory)
                if not base.is_dir():
                    result = f"Directory not found: {directory}"
                    return [TextContent(type="text", text=result)]
            else:
                base = vault

            glob_pattern = "**/*.md" if recursive else "*.md"
            notes = []
            for md_file in sorted(base.glob(glob_pattern)):
                # Skip hidden directories
                if any(part.startswith(".") for part in md_file.relative_to(vault).parts):
                    continue
                rel_path = str(md_file.relative_to(vault))
                if preview:
                    try:
                        content = md_file.read_text(encoding="utf-8")[:100]
                        content = content.replace("\n", " ").strip()
                        notes.append(f"- {rel_path}: {content}...")
                    except (UnicodeDecodeError, PermissionError):
                        notes.append(f"- {rel_path}")
                else:
                    notes.append(f"- {rel_path}")

            dir_label = directory if directory else "(entire vault)"
            result = f"# Notes in {dir_label} ({len(notes)} found)\n\n" + "\n".join(notes)

        # ========== Tags ==========
        elif name == "obsidian_add_tags":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if not full_path.exists():
                result = f"Note not found: {note_path}"
            else:
                content = full_path.read_text(encoding="utf-8")
                fm, body = parse_frontmatter(content)
                existing = fm.get("tags", [])
                if not isinstance(existing, list):
                    existing = [existing] if existing else []
                added = []
                for tag in arguments["tags"]:
                    tag = tag.lstrip("#")
                    if tag not in existing:
                        existing.append(tag)
                        added.append(tag)
                fm["tags"] = existing
                full_path.write_text(serialize_frontmatter(fm, body), encoding="utf-8")
                if added:
                    result = f"Added tags to {note_path}: {', '.join(added)}"
                else:
                    result = f"All specified tags already exist on {note_path}"

        elif name == "obsidian_remove_tags":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if not full_path.exists():
                result = f"Note not found: {note_path}"
            else:
                content = full_path.read_text(encoding="utf-8")
                fm, body = parse_frontmatter(content)
                existing = fm.get("tags", [])
                if not isinstance(existing, list):
                    existing = [existing] if existing else []
                removed = []
                for tag in arguments["tags"]:
                    tag = tag.lstrip("#")
                    if tag in existing:
                        existing.remove(tag)
                        removed.append(tag)
                if existing:
                    fm["tags"] = existing
                else:
                    fm.pop("tags", None)
                full_path.write_text(serialize_frontmatter(fm, body), encoding="utf-8")
                if removed:
                    result = f"Removed tags from {note_path}: {', '.join(removed)}"
                else:
                    result = f"None of the specified tags were found on {note_path}"

        elif name == "obsidian_update_frontmatter":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if not full_path.exists():
                result = f"Note not found: {note_path}"
            else:
                content = full_path.read_text(encoding="utf-8")
                fm, body = parse_frontmatter(content)
                fields = arguments["fields"]
                updated = []
                removed = []
                for key, value in fields.items():
                    if value is None:
                        if key in fm:
                            fm.pop(key)
                            removed.append(key)
                    else:
                        fm[key] = value
                        updated.append(f"{key}={value}")
                full_path.write_text(serialize_frontmatter(fm, body), encoding="utf-8")
                parts = []
                if updated:
                    parts.append(f"Updated: {', '.join(updated)}")
                if removed:
                    parts.append(f"Removed: {', '.join(removed)}")
                result = f"Frontmatter updated for {note_path}. {'; '.join(parts)}" if parts else f"No changes made to {note_path}"

        elif name == "obsidian_list_tags":
            vault = get_vault_path()
            tag_counts: dict[str, int] = {}
            for md_file in vault.rglob("*.md"):
                if any(part.startswith(".") for part in md_file.relative_to(vault).parts):
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8")
                except (UnicodeDecodeError, PermissionError):
                    continue
                for tag in collect_tags_from_content(content):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            if tag_counts:
                sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
                output = [f"# Tags in Vault ({len(sorted_tags)} unique tags)\n"]
                for tag, count in sorted_tags:
                    output.append(f"- #{tag} ({count} note{'s' if count > 1 else ''})")
                result = "\n".join(output)
            else:
                result = "No tags found in the vault."

        # ========== Directories ==========
        elif name == "obsidian_create_directory":
            dir_path = safe_path(arguments["path"])
            if dir_path.exists():
                result = f"Directory already exists: {arguments['path']}"
            else:
                dir_path.mkdir(parents=True, exist_ok=True)
                result = f"Created directory: {arguments['path']}"

        # ========== Links ==========
        elif name == "obsidian_get_backlinks":
            note_path = arguments["path"]
            # Build possible link targets from the path
            # [[note]] or [[note.md]] or [[subfolder/note]] etc.
            targets = set()
            # Full path with .md
            targets.add(note_path if note_path.endswith(".md") else note_path + ".md")
            # Full path without .md
            targets.add(note_path.removesuffix(".md"))
            # Just the filename without .md
            basename = Path(note_path).stem
            targets.add(basename)

            # Build regex pattern for [[target]] or [[target|alias]]
            escaped = [re.escape(t) for t in targets]
            pattern = re.compile(r'\[\[(' + '|'.join(escaped) + r')(\|[^\]]+)?\]\]', re.IGNORECASE)

            vault = get_vault_path()
            backlinks = []
            for md_file in vault.rglob("*.md"):
                if any(part.startswith(".") for part in md_file.relative_to(vault).parts):
                    continue
                rel = str(md_file.relative_to(vault))
                # Don't count self-references
                if rel == note_path or rel == ensure_md_extension(note_path):
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8")
                except (UnicodeDecodeError, PermissionError):
                    continue
                found = pattern.findall(content)
                if found:
                    backlinks.append(f"- [[{rel.removesuffix('.md')}]] ({len(found)} link{'s' if len(found) > 1 else ''})")

            if backlinks:
                result = f"# Backlinks to {note_path} ({len(backlinks)} notes)\n\n" + "\n".join(backlinks)
            else:
                result = f"No backlinks found for {note_path}"

        # ========== Tasks ==========
        elif name == "obsidian_query_tasks":
            status_filter = arguments.get("status", "all")
            tag_filter = arguments.get("tags", [])
            file_pattern = arguments.get("file_pattern")
            text_search = arguments.get("text_search", "").lower()
            completed_after = arguments.get("completed_after")
            completed_before = arguments.get("completed_before")
            max_results = arguments.get("max_results", 50)

            vault = get_vault_path()
            tasks = []

            for md_file in sorted(vault.rglob("*.md")):
                if any(part.startswith(".") for part in md_file.relative_to(vault).parts):
                    continue
                rel_path = str(md_file.relative_to(vault))

                # File pattern filter
                if file_pattern and not fnmatch(rel_path, file_pattern):
                    continue

                try:
                    lines = md_file.read_text(encoding="utf-8").split("\n")
                except (UnicodeDecodeError, PermissionError):
                    continue

                for line_num, line in enumerate(lines, 1):
                    task = parse_task_line(line)
                    if task is None:
                        continue

                    # Status filter
                    if status_filter != "all" and task["status"] != status_filter:
                        continue

                    # Tag filter (ALL tags must be present)
                    if tag_filter:
                        task_tags_lower = [t.lower() for t in task["tags"]]
                        if not all(t.lower() in task_tags_lower for t in tag_filter):
                            continue

                    # Text search
                    if text_search and text_search not in task["text"].lower():
                        continue

                    # Completion date range
                    if completed_after and task["completion_date"]:
                        if task["completion_date"] < completed_after:
                            continue
                    if completed_before and task["completion_date"]:
                        if task["completion_date"] > completed_before:
                            continue
                    # If filtering by date range but task has no completion date, skip
                    if (completed_after or completed_before) and not task["completion_date"]:
                        continue

                    task["file"] = rel_path
                    task["line"] = line_num
                    tasks.append(task)

                    if len(tasks) >= max_results:
                        break
                if len(tasks) >= max_results:
                    break

            if tasks:
                output = [f"# Tasks ({len(tasks)} found)\n"]
                for t in tasks:
                    checkbox = "[x]" if t["status"] == "completed" else "[ ]"
                    tags_str = " ".join(f"#{tag}" for tag in t["tags"]) if t["tags"] else ""
                    date_str = f" ✅ {t['completion_date']}" if t["completion_date"] else ""
                    output.append(f"- {checkbox} {t['text']}{date_str} {tags_str}".rstrip())
                    output.append(f"  📄 {t['file']}:{t['line']}")
                result = "\n".join(output)
            else:
                result = "No tasks found matching the specified filters."

        elif name == "obsidian_toggle_task":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if not full_path.exists():
                result = f"Note not found: {note_path}"
            else:
                line_number = arguments.get("line_number")
                text_match = arguments.get("text_match")

                if not line_number and not text_match:
                    result = "Provide either 'line_number' or 'text_match' to identify the task."
                else:
                    lines = full_path.read_text(encoding="utf-8").split("\n")
                    target_idx = None

                    if line_number:
                        target_idx = line_number - 1
                        if target_idx < 0 or target_idx >= len(lines):
                            result = f"Line {line_number} is out of range (file has {len(lines)} lines)."
                            return [TextContent(type="text", text=result)]
                    else:
                        # Find by text match
                        for i, line in enumerate(lines):
                            if text_match and text_match in line and parse_task_line(line) is not None:
                                target_idx = i
                                break
                        if target_idx is None:
                            result = f"No task found matching text: '{text_match}'"
                            return [TextContent(type="text", text=result)]

                    old_line = lines[target_idx]
                    task = parse_task_line(old_line)
                    if task is None:
                        result = f"Line {target_idx + 1} is not a task: {old_line.strip()}"
                    else:
                        today_str = date.today().isoformat()
                        if task["status"] == "open":
                            # Mark as completed
                            new_line = re.sub(r'\[\s\]', '[x]', old_line, count=1)
                            new_line = new_line.rstrip() + f" ✅ {today_str}"
                        else:
                            # Mark as open: remove [x]/[X] -> [ ], remove ✅ date
                            new_line = re.sub(r'\[[xX]\]', '[ ]', old_line, count=1)
                            new_line = re.sub(r'\s*✅\s*\d{4}-\d{2}-\d{2}', '', new_line)

                        lines[target_idx] = new_line
                        full_path.write_text("\n".join(lines), encoding="utf-8")
                        result = f"Toggled task in {note_path}:{target_idx + 1}\n  Before: {old_line.strip()}\n  After:  {new_line.strip()}"

        # ========== Dataview ==========
        elif name == "obsidian_dataview_query":
            from_tags = arguments.get("from_tags", [])
            from_folder = arguments.get("from_folder")
            file_name_pattern = arguments.get("file_name_pattern")
            where_fm = arguments.get("where_frontmatter", {})
            sort_by = arguments.get("sort_by", "file.name")
            sort_order = arguments.get("sort_order", "asc")
            limit = arguments.get("limit", 20)
            fields = arguments.get("fields", ["file.name", "file.mtime", "file.tags"])

            vault = get_vault_path()
            results_list = []

            # Determine base directory
            if from_folder:
                base = safe_path(from_folder)
                if not base.is_dir():
                    result = f"Folder not found: {from_folder}"
                    return [TextContent(type="text", text=result)]
            else:
                base = vault

            for md_file in base.rglob("*.md"):
                if any(part.startswith(".") for part in md_file.relative_to(vault).parts):
                    continue
                rel_path = str(md_file.relative_to(vault))

                # File name pattern
                if file_name_pattern and not fnmatch(md_file.name, file_name_pattern):
                    continue

                # Lazy: only read content if we need tags or frontmatter filtering
                content = None
                all_tags = None
                fm = None

                if from_tags or where_fm or "file.tags" in fields:
                    try:
                        content = md_file.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, PermissionError):
                        continue
                    all_tags = collect_tags_from_content(content)
                    fm, _ = parse_frontmatter(content)

                # Tag filter
                if from_tags:
                    if all_tags is None:
                        continue
                    tags_lower = {t.lower() for t in all_tags}
                    if not all(t.lower() in tags_lower for t in from_tags):
                        continue

                # Frontmatter filter
                if where_fm:
                    if fm is None:
                        continue
                    match = True
                    for k, v in where_fm.items():
                        if str(fm.get(k, "")) != str(v):
                            match = False
                            break
                    if not match:
                        continue

                stat = md_file.stat()
                entry = {
                    "file.name": md_file.stem,
                    "file.path": rel_path,
                    "file.mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "file.size": stat.st_size,
                    "file.tags": ", ".join(f"#{t}" for t in sorted(all_tags)) if all_tags else "",
                    "file.folder": str(md_file.parent.relative_to(vault)),
                    "_sort_mtime": stat.st_mtime,
                }
                results_list.append(entry)

            # Sort
            if sort_by == "file.mtime":
                results_list.sort(key=lambda e: e["_sort_mtime"], reverse=(sort_order == "desc"))
            elif sort_by == "file.size":
                results_list.sort(key=lambda e: e["file.size"], reverse=(sort_order == "desc"))
            else:
                results_list.sort(key=lambda e: e["file.name"].lower(), reverse=(sort_order == "desc"))

            # Limit
            results_list = results_list[:limit]

            if results_list:
                # Build markdown table
                header = " | ".join(fields)
                separator = " | ".join("---" for _ in fields)
                rows = []
                for entry in results_list:
                    row = " | ".join(str(entry.get(f, "")) for f in fields)
                    rows.append(row)
                result = f"# Query Results ({len(results_list)} notes)\n\n| {header} |\n| {separator} |\n"
                result += "\n".join(f"| {r} |" for r in rows)
            else:
                result = "No notes found matching the specified filters."

        elif name == "obsidian_get_note_metadata":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if not full_path.exists():
                result = f"Note not found: {note_path}"
            else:
                content = full_path.read_text(encoding="utf-8")
                stat = full_path.stat()
                fm, body = parse_frontmatter(content)
                all_tags = collect_tags_from_content(content)

                # Outgoing links
                links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
                unique_links = sorted(set(links))

                # Task counts
                open_tasks = 0
                completed_tasks = 0
                for line in content.split("\n"):
                    t = parse_task_line(line)
                    if t:
                        if t["status"] == "open":
                            open_tasks += 1
                        else:
                            completed_tasks += 1

                # Word count (body only)
                word_count = len(body.split())

                meta = [
                    f"# Metadata: {note_path}\n",
                    f"**Size:** {stat.st_size} bytes",
                    f"**Modified:** {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}",
                    f"**Word count:** {word_count}",
                    f"**Tasks:** {open_tasks} open, {completed_tasks} completed",
                ]

                if fm:
                    fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
                    meta.append(f"\n**Frontmatter:**\n```yaml\n{fm_str}\n```")

                if all_tags:
                    meta.append(f"\n**Tags:** {', '.join(f'#{t}' for t in sorted(all_tags))}")

                if unique_links:
                    meta.append(f"\n**Outgoing links ({len(unique_links)}):**")
                    for link in unique_links:
                        meta.append(f"- [[{link}]]")

                result = "\n".join(meta)

        elif name == "obsidian_get_note_sections":
            note_path = ensure_md_extension(arguments["path"])
            full_path = safe_path(note_path)
            if not full_path.exists():
                result = f"Note not found: {note_path}"
            else:
                content = full_path.read_text(encoding="utf-8")
                include_content = arguments.get("include_content", True)
                _, body = parse_frontmatter(content)
                lines = body.split("\n")

                sections = []
                current_section = {"level": 0, "title": "(preamble)", "start_line": 1, "lines": []}

                for i, line in enumerate(lines):
                    heading_match = re.match(r'^(#{1,6})\s+(.+)', line)
                    if heading_match:
                        # Close previous section
                        current_section["end_line"] = i
                        if include_content:
                            current_section["content"] = "\n".join(current_section["lines"]).strip()
                        del current_section["lines"]
                        if current_section.get("content") or current_section["level"] > 0:
                            sections.append(current_section)

                        # Start new section
                        level = len(heading_match.group(1))
                        title = heading_match.group(2).strip()
                        current_section = {"level": level, "title": title, "start_line": i + 1, "lines": []}
                    else:
                        current_section["lines"].append(line)

                # Close last section
                current_section["end_line"] = len(lines)
                if include_content:
                    current_section["content"] = "\n".join(current_section["lines"]).strip()
                del current_section["lines"]
                sections.append(current_section)

                output = [f"# Sections in {note_path} ({len(sections)} sections)\n"]
                for s in sections:
                    prefix = "#" * s["level"] + " " if s["level"] > 0 else ""
                    output.append(f"### {prefix}{s['title']} (lines {s['start_line']}-{s['end_line']})")
                    if include_content and s.get("content"):
                        content_preview = s["content"][:500]
                        if len(s["content"]) > 500:
                            content_preview += f"\n... ({len(s['content'])} chars total)"
                        output.append(content_preview)
                    output.append("")

                result = "\n".join(output)

        # ========== Excalidraw ==========
        elif name == "obsidian_list_drawings":
            vault = get_vault_path()
            drawings = []

            # Pass 1: Pure .excalidraw files
            for f in vault.rglob("*.excalidraw"):
                if any(part.startswith(".") for part in f.relative_to(vault).parts):
                    continue
                # Skip if there's also a .excalidraw.md (avoid double-listing)
                rel = str(f.relative_to(vault))
                stat = f.stat()
                elem_count = None
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    elem_count = len(data.get("elements", []))
                except Exception:
                    pass
                drawings.append({
                    "path": rel,
                    "type": "excalidraw (JSON)",
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "elements": elem_count,
                })

            # Pass 2: .excalidraw.md files
            for f in vault.rglob("*.excalidraw.md"):
                if any(part.startswith(".") for part in f.relative_to(vault).parts):
                    continue
                rel = str(f.relative_to(vault))
                stat = f.stat()
                drawings.append({
                    "path": rel,
                    "type": "excalidraw.md (compressed)",
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "elements": None,
                })

            # Pass 3: .md files with excalidraw frontmatter (not already caught by .excalidraw.md)
            excalidraw_dir = vault / "excalidraw"
            if excalidraw_dir.is_dir():
                for f in excalidraw_dir.rglob("*.md"):
                    if f.name.endswith(".excalidraw.md"):
                        continue
                    if any(part.startswith(".") for part in f.relative_to(vault).parts):
                        continue
                    try:
                        content = f.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, PermissionError):
                        continue
                    if is_excalidraw_md(content):
                        rel = str(f.relative_to(vault))
                        stat = f.stat()
                        drawings.append({
                            "path": rel,
                            "type": "md (excalidraw frontmatter)",
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                            "elements": None,
                        })

            if drawings:
                drawings.sort(key=lambda d: d["path"])
                output = [f"# Excalidraw Drawings ({len(drawings)} found)\n"]
                output.append("| Path | Type | Size | Modified | Elements |")
                output.append("| --- | --- | --- | --- | --- |")
                for d in drawings:
                    elem = str(d["elements"]) if d["elements"] is not None else "—"
                    size_kb = f"{d['size'] / 1024:.1f}KB"
                    output.append(f"| {d['path']} | {d['type']} | {size_kb} | {d['modified']} | {elem} |")
                result = "\n".join(output)
            else:
                result = "No Excalidraw drawings found in the vault."

        elif name == "obsidian_read_drawing":
            draw_path = arguments["path"]
            full_path = safe_path(draw_path)
            if not full_path.exists():
                result = f"Drawing not found: {draw_path}"
            else:
                try:
                    content = full_path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, PermissionError) as e:
                    result = f"Cannot read file: {e}"
                    return [TextContent(type="text", text=result)]

                json_str = None

                if draw_path.endswith(".excalidraw"):
                    # Pure JSON file
                    try:
                        json.loads(content)  # Validate
                        json_str = content
                    except json.JSONDecodeError as e:
                        result = f"Invalid JSON in {draw_path}: {e}"
                        return [TextContent(type="text", text=result)]
                else:
                    # .excalidraw.md or .md with excalidraw frontmatter
                    if is_excalidraw_md(content) or draw_path.endswith(".excalidraw.md"):
                        json_str = decompress_excalidraw_md(content)
                        if json_str is None:
                            result = f"Could not decompress drawing data from {draw_path}. No compressed-json block found or decompression failed."
                            return [TextContent(type="text", text=result)]
                        # Validate
                        try:
                            json.loads(json_str)
                        except json.JSONDecodeError as e:
                            result = f"Decompressed data is not valid JSON: {e}"
                            return [TextContent(type="text", text=result)]
                    else:
                        result = f"File {draw_path} does not appear to be an Excalidraw drawing."
                        return [TextContent(type="text", text=result)]

                result = json_str

        elif name == "obsidian_save_drawing":
            draw_path = arguments["path"]
            json_content = arguments["json_content"]
            overwrite = arguments.get("overwrite", False)

            # Validate JSON
            try:
                data = json.loads(json_content)
            except json.JSONDecodeError as e:
                result = f"Invalid JSON content: {e}"
                return [TextContent(type="text", text=result)]

            if not draw_path.endswith(".excalidraw"):
                draw_path += ".excalidraw"

            full_path = safe_path(draw_path)

            if full_path.exists() and not overwrite:
                result = f"File already exists: {draw_path}. Set overwrite=true to replace."
            else:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                # Pretty-print with tab indent to match Obsidian Excalidraw plugin format
                formatted = json.dumps(data, indent="\t", ensure_ascii=False)
                full_path.write_text(formatted, encoding="utf-8")
                elem_count = len(data.get("elements", []))
                result = f"Saved drawing: {draw_path} ({elem_count} elements, {full_path.stat().st_size} bytes)"

        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        error_msg = f"Error executing {name}: {str(e)}\n{traceback.format_exc()}"
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
