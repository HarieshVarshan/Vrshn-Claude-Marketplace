# Obsidian MCP Server - Quick Reference

## Overview

MCP server that gives Claude full read/write access to an Obsidian vault. Supports notes, tags, tasks, backlinks, Dataview-style queries, and Excalidraw drawings.

## Prerequisites

- Python 3.10+
- An Obsidian vault directory

## Setup

```bash
cd obsidian-mcp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OBSIDIAN_VAULT_PATH` | Absolute path to the Obsidian vault directory (required) |

## Available Tools (18)

### Notes
| Tool | Description |
|------|-------------|
| `obsidian_read_note` | Read a note by path |
| `obsidian_create_note` | Create a new note with optional tags |
| `obsidian_edit_note` | Edit a note (append, prepend, or replace) |
| `obsidian_delete_note` | Delete a note |
| `obsidian_move_note` | Move or rename a note |

### Search & List
| Tool | Description |
|------|-------------|
| `obsidian_search_vault` | Full-text search with regex support |
| `obsidian_list_notes` | List notes in a directory or entire vault |

### Tags
| Tool | Description |
|------|-------------|
| `obsidian_add_tags` | Add tags to frontmatter |
| `obsidian_remove_tags` | Remove tags from frontmatter |
| `obsidian_list_tags` | List all tags with usage counts |

### Links
| Tool | Description |
|------|-------------|
| `obsidian_get_backlinks` | Find notes linking to a given note |

### Tasks
| Tool | Description |
|------|-------------|
| `obsidian_query_tasks` | Query tasks with filters (status, tags, date range) |
| `obsidian_toggle_task` | Toggle task completion by line number or text match |

### Dataview & Metadata
| Tool | Description |
|------|-------------|
| `obsidian_dataview_query` | Query notes by tags, folder, frontmatter fields |
| `obsidian_get_note_metadata` | Get full metadata for a note |

### Directories
| Tool | Description |
|------|-------------|
| `obsidian_create_directory` | Create a directory in the vault |

### Excalidraw
| Tool | Description |
|------|-------------|
| `obsidian_list_drawings` | List all Excalidraw drawings |
| `obsidian_read_drawing` | Read drawing JSON (handles compressed .excalidraw.md) |
| `obsidian_save_drawing` | Save Excalidraw JSON to the vault |

## Key Files

- `mcp_server.py` - MCP server (18 tools, single file)
- `mcp-servers.json` - MCP server configuration
- `requirements.txt` - Python dependencies (mcp, pyyaml, lzstring)

## Security

- All paths are resolved and validated to stay within the vault directory
- Directory traversal attempts (`../`) are rejected
