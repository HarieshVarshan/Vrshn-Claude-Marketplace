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

## Available Tools (21)

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
| `obsidian_update_frontmatter` | Update specific frontmatter fields without touching the note body |
| `obsidian_get_note_sections` | Parse a note into heading-delimited sections with content |

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

## Knowledge Sync Agent

Agent definition at `agents/knowledge-sync.md`. Syncs knowledge from Claude conversations
into the Obsidian vault using a "Knowledge PR" review model.

### How It Works
1. User triggers sync (e.g., "sync to vault", "save these learnings to Obsidian")
2. Agent asks for scope (current conversation, specific topics, etc.)
3. Extracts concepts with intelligent tags, searches vault for related notes
4. Generates "Knowledge PRs" — proposed changes shown as diffs
5. User reviews and approves each change
6. Agent applies approved changes, updates cross-links, and proposes diagrams where helpful
7. Evaluates whether accumulated knowledge warrants a paper candidate in `papers/`

### Two Merge Modes
- **Style-Preserving**: Appends/inserts matching the note's existing style
- **Refactor-While-Merging**: Proposes a clean rewrite when the note is messy

### Key Features
- **Intelligent tagging**: Aligns with vault's existing tag taxonomy for discoverability
- **Diagrams**: Proposes Mermaid (inline) or Excalidraw diagrams for visual concepts
- **Paper candidates**: Identifies publishable topics in `papers/` as depth accumulates across sessions
- Agent NEVER writes to vault without user approval

## Key Files

- `mcp_server.py` - MCP server (21 tools, single file)
- `agents/knowledge-sync.md` - Knowledge Sync agent definition
- `mcp-servers.json` - MCP server configuration
- `requirements.txt` - Python dependencies (mcp, pyyaml, lzstring)

## Security

- All paths are resolved and validated to stay within the vault directory
- Directory traversal attempts (`../`) are rejected
