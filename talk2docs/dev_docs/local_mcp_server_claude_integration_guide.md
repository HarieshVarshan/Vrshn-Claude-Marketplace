# Setting Up talk2docs MCP Server for Claude Code

This document describes how to add the `talk2docs` MCP server to Claude Code.

---

## Quick Setup

### Add the MCP Server (Global)

```bash
claude mcp add --transport stdio --scope user talk2docs \
  --env CHROMA_DB_PATH=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/talk2docs/chroma_db \
  --env PYTHONPATH=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/talk2docs \
  -- /home/harieshvarshan/ti/SWATI/vrshn-marketplace/talk2docs/venv/bin/python \
  /home/harieshvarshan/ti/SWATI/vrshn-marketplace/talk2docs/mcp_server.py
```

### Verify

```bash
claude mcp list
```

Expected output:
```
talk2docs: ... - ✓ Connected
```

### Restart Claude Code

```bash
/exit
claude
/mcp  # Should list talk2docs
```

---

## Command Reference

| Command | Description |
|---------|-------------|
| `claude mcp list` | List all MCP servers |
| `claude mcp get talk2docs` | Get server details |
| `claude mcp remove talk2docs` | Remove the server |

---

## Scope Options

| Flag | Description |
|------|-------------|
| `--scope user` | Available from any directory (global) |
| `--scope project` | Only in current directory (default) |

---

## Where Config is Stored

Config is saved in `~/.claude.json`:

```json
{
  "mcpServers": {
    "talk2docs": {
      "type": "stdio",
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "CHROMA_DB_PATH": "/path/to/chroma_db",
        "PYTHONPATH": "/path/to/talk2docs"
      }
    }
  }
}
```

---

## After System Reboot

| Component | Status After Reboot |
|-----------|---------------------|
| MCP config (`~/.claude.json`) | Persists - no action needed |
| Claude Code | Starts the server automatically when launched |
| **Ollama** | Must be running for embeddings to work |

**Ensure Ollama is running after reboot:**

```bash
# Check if Ollama is running
curl -s http://localhost:11434/api/tags

# If not running, start it
ollama serve
```

---

## Troubleshooting

**Server not in `/mcp`:**
1. Run `claude mcp list` to check registration
2. Restart Claude Code (`/exit` then `claude`)
3. Ensure `--scope user` was used for global access

**Server won't connect:**
1. Test manually: `python mcp_server.py`
2. Check Ollama is running: `curl http://localhost:11434/api/tags`
3. Verify all paths are absolute

**What does `python mcp_server.py` do?**

Running it manually starts the MCP server in stdio mode. It will sit quietly waiting for MCP protocol messages on stdin. The purpose is to check for errors - if there are import errors, missing dependencies, or syntax errors, they'll appear immediately. If it sits quietly, the server code is fine. Press `Ctrl+C` to stop.

**Re-add server:**
```bash
claude mcp remove talk2docs
claude mcp add --transport stdio --scope user talk2docs ...
```
