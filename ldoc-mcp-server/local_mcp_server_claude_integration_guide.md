# Setting Up ldoc-search MCP Server for Claude Code

This document describes how to add the `ldoc-search` MCP server to Claude Code.

---

## Quick Setup

### Add the MCP Server (Global)

```bash
claude mcp add --transport stdio --scope user ldoc-search \
  --env CHROMA_DB_PATH=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/ldoc-mcp-server/chroma_db \
  --env PYTHONPATH=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/ldoc-mcp-server \
  -- /home/harieshvarshan/ti/SWATI/vrshn-marketplace/ldoc-mcp-server/venv/bin/python \
  /home/harieshvarshan/ti/SWATI/vrshn-marketplace/ldoc-mcp-server/mcp_server.py
```

### Verify

```bash
claude mcp list
```

Expected output:
```
ldoc-search: ... - ✓ Connected
```

### Restart Claude Code

```bash
/exit
claude
/mcp  # Should list ldoc-search
```

---

## Command Reference

| Command | Description |
|---------|-------------|
| `claude mcp list` | List all MCP servers |
| `claude mcp get ldoc-search` | Get server details |
| `claude mcp remove ldoc-search` | Remove the server |

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
    "ldoc-search": {
      "type": "stdio",
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "CHROMA_DB_PATH": "/path/to/chroma_db",
        "PYTHONPATH": "/path/to/ldoc-mcp-server"
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
claude mcp remove ldoc-search
claude mcp add --transport stdio --scope user ldoc-search ...
```
