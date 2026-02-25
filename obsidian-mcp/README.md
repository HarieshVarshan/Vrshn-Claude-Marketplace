# obsidian-mcp

An MCP server that gives Claude Code full access to your Obsidian vault. Read, create, edit, and search notes. Manage tags, query tasks, explore backlinks, run Dataview-style queries, and read/save Excalidraw drawings -- all from the Claude CLI.

## Prerequisites

- **Python 3.10+**
- An **Obsidian vault** directory

## Setup

### 1. Install Dependencies

```bash
cd obsidian-mcp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Register with Claude Code

```bash
claude mcp add --transport stdio --scope user obsidian \
  --env OBSIDIAN_VAULT_PATH=/path/to/your/vault \
  -- $(pwd)/venv/bin/python $(pwd)/mcp_server.py
```

### 3. Verify

```bash
claude mcp list    # Should show obsidian
/mcp               # Inside Claude Code, should list obsidian
```

## Usage

Once configured, just talk to Claude about your vault:

- *"List all my notes"*
- *"Search my vault for kubernetes"*
- *"Create a new note called meeting-notes with today's date"*
- *"Show me all open tasks tagged #work"*
- *"What notes link to my daily logger?"*
- *"List all tags in my vault"*
- *"Query notes in the projects/ folder sorted by last modified"*

## Tools

### Notes

| Tool | Description |
|------|-------------|
| `obsidian_read_note` | Read a note by path (`.md` extension auto-added) |
| `obsidian_create_note` | Create a new note with optional frontmatter tags |
| `obsidian_edit_note` | Edit a note: append, prepend, or replace content |
| `obsidian_delete_note` | Delete a note |
| `obsidian_move_note` | Move or rename a note within the vault |

### Search & List

| Tool | Description |
|------|-------------|
| `obsidian_search_vault` | Full-text search across all notes (plain text or regex) |
| `obsidian_list_notes` | List notes in a directory or the entire vault |

### Tags

| Tool | Description |
|------|-------------|
| `obsidian_add_tags` | Add tags to a note's YAML frontmatter |
| `obsidian_remove_tags` | Remove tags from frontmatter |
| `obsidian_list_tags` | List all tags in the vault with usage counts |

### Links

| Tool | Description |
|------|-------------|
| `obsidian_get_backlinks` | Find all notes that `[[link]]` to a given note |

### Tasks

| Tool | Description |
|------|-------------|
| `obsidian_query_tasks` | Query `- [ ]` / `- [x]` tasks with filters: status, tags, text, date range, file pattern |
| `obsidian_toggle_task` | Toggle a task's completion (adds `✅ YYYY-MM-DD` on complete) |

### Dataview & Metadata

| Tool | Description |
|------|-------------|
| `obsidian_dataview_query` | Query notes by tags, folder, file name pattern, and frontmatter fields. Returns a sortable markdown table. |
| `obsidian_get_note_metadata` | Get full metadata: frontmatter, tags, outgoing links, task counts, word count |

### Directories

| Tool | Description |
|------|-------------|
| `obsidian_create_directory` | Create a directory in the vault |

### Excalidraw

| Tool | Description |
|------|-------------|
| `obsidian_list_drawings` | List all Excalidraw drawings (`.excalidraw`, `.excalidraw.md`) |
| `obsidian_read_drawing` | Read a drawing's JSON (handles LZ-String compressed `.excalidraw.md`) |
| `obsidian_save_drawing` | Save Excalidraw JSON to the vault as `.excalidraw` |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OBSIDIAN_VAULT_PATH` | Yes | Absolute path to your Obsidian vault directory |

## Security

All note paths are resolved and validated to stay within the vault directory. Directory traversal attempts (`../` escaping the vault) are rejected.

## Project Structure

```
obsidian-mcp/
├── mcp_server.py              # MCP server (18 tools)
├── mcp-servers.json           # MCP server configuration
├── requirements.txt           # Dependencies (mcp, pyyaml, lzstring)
└── .claude-plugin/
    └── plugin.json            # Marketplace plugin metadata
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `OBSIDIAN_VAULT_PATH not set` | Set the env var in your `claude mcp add` command |
| `Vault path does not exist` | Verify the path points to your vault root directory |
| `Note not found` | Paths are relative to vault root; `.md` is added automatically |
| Server not showing in `/mcp` | Run `claude mcp list` to verify, then restart Claude Code |
