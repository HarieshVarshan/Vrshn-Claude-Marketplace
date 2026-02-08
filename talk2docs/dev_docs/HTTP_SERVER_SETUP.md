# HTTP MCP Server Setup for Team Access

This document describes how to set up a centralized HTTP-based MCP server so your team can search indexed documents without needing Ollama, the codebase, or any knowledge of embeddings.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Admin Machine (You)                        │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐   │
│  │  Ollama  │◄──►│ ChromaDB │◄──►│  HTTP MCP Server     │   │
│  │ (embed)  │    │ (vectors)│    │  (port 8080)         │   │
│  └──────────┘    └──────────┘    └──────────┬───────────┘   │
│                                              │               │
└──────────────────────────────────────────────┼───────────────┘
                                               │
                                          HTTP/Network
                                               │
            ┌──────────────────────────────────┼──────────────────────────────────┐
            │                                  │                                  │
            ▼                                  ▼                                  ▼
    ┌───────────────┐                 ┌───────────────┐                 ┌───────────────┐
    │ Team Member 1 │                 │ Team Member 2 │                 │ Team Member 3 │
    │  Claude Code  │                 │  Claude Code  │                 │  Claude Code  │
    │ (search only) │                 │ (search only) │                 │ (search only) │
    └───────────────┘                 └───────────────┘                 └───────────────┘
```

---

## What Team Members Get

| Feature | Available |
|---------|-----------|
| Search documents | Yes |
| List indexed documents | Yes |
| View index stats | Yes |
| Add new documents | No (admin only) |
| Remove documents | No (admin only) |
| Access to embeddings/code | No |

---

## What Needs to Be Done

### On Admin Machine (You)

#### 1. Create HTTP MCP Server

Create a new file `mcp_http_server.py` that:
- Exposes the same MCP tools over HTTP instead of stdio
- Handles CORS for cross-origin requests
- Authenticates requests (optional but recommended)

**Dependencies to add:**
```
fastapi
uvicorn
mcp[server]
```

#### 2. Server Endpoints

The HTTP MCP server needs to implement:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/mcp` | POST | MCP protocol messages |
| `/health` | GET | Health check |
| `/sse` | GET | Server-sent events (optional) |

#### 3. Run the Server

```bash
# Start HTTP server on port 8080
python mcp_http_server.py --host 0.0.0.0 --port 8080
```

Or run as a background service:
```bash
nohup python mcp_http_server.py --host 0.0.0.0 --port 8080 &
```

#### 4. Firewall / Network

- Open port 8080 (or chosen port) on your machine
- Ensure team members can reach your machine's IP
- Consider VPN if not on same network

---

### On Team Member Machines

#### Single Command Setup

```bash
claude mcp add --transport http doc-search http://<admin-ip>:8080/mcp
```

That's it! No other setup required.

#### Verify Connection

```bash
claude mcp list
# Should show: doc-search: http://<admin-ip>:8080/mcp - ✓ Connected
```

---

## Implementation Checklist

### Phase 1: Create HTTP Server

- [ ] Create `mcp_http_server.py`
- [ ] Add FastAPI/uvicorn dependencies
- [ ] Implement MCP protocol over HTTP
- [ ] Add health check endpoint
- [ ] Test locally

### Phase 2: Security (Optional but Recommended)

- [ ] Add API key authentication
- [ ] Add rate limiting
- [ ] Enable HTTPS (TLS)
- [ ] Restrict to internal network

### Phase 3: Deployment

- [ ] Configure firewall
- [ ] Set up as system service (auto-start on boot)
- [ ] Document team setup instructions
- [ ] Test from team member machine

### Phase 4: Maintenance

- [ ] Monitor server health
- [ ] Log search queries (optional)
- [ ] Backup ChromaDB periodically

---

## Server Configuration Options

### Basic (No Auth)

```python
# Anyone on network can access
python mcp_http_server.py --host 0.0.0.0 --port 8080
```

### With API Key

```python
# Requires API key header
python mcp_http_server.py --host 0.0.0.0 --port 8080 --api-key "your-secret-key"
```

Team members would add:
```bash
claude mcp add --transport http doc-search http://<ip>:8080/mcp \
  --header "Authorization: Bearer your-secret-key"
```

### With HTTPS

```python
# Secure connection
python mcp_http_server.py --host 0.0.0.0 --port 8443 \
  --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem
```

---

## Running as a Service (Linux)

### Create systemd service

```bash
sudo nano /etc/systemd/system/doc-mcp-server.service
```

```ini
[Unit]
Description=Document MCP HTTP Server
After=network.target

[Service]
Type=simple
User=harieshvarshan
WorkingDirectory=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/pdf-mcp-server
Environment="CHROMA_DB_PATH=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/pdf-mcp-server/chroma_db"
ExecStart=/home/harieshvarshan/ti/SWATI/vrshn-marketplace/pdf-mcp-server/venv/bin/python mcp_http_server.py --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable doc-mcp-server
sudo systemctl start doc-mcp-server

# Check status
sudo systemctl status doc-mcp-server
```

---

## Comparison: Current vs HTTP Server

| Aspect | Current (stdio) | HTTP Server |
|--------|-----------------|-------------|
| Access | Local only | Network-wide |
| Team setup | Complex | Single command |
| Ollama needed | On each machine | Only on server |
| Code repo needed | On each machine | Only on server |
| Central control | No | Yes |
| Offline access | Yes | No (needs server) |

---

## Quick Reference for Team

Once HTTP server is running, share this with your team:

```
=== Document Search Setup ===

Run this single command:

    claude mcp add --transport http doc-search http://<admin-ip>:8080/mcp

Then restart Claude Code:

    /exit
    claude

Verify with /mcp - you should see "doc-search" listed.

Now you can ask Claude:
- "Search documents for DMA configuration"
- "List all indexed documents"
- "What do the specs say about clock topology?"
```

---

## Next Steps

1. **Create the HTTP server** - `mcp_http_server.py`
2. **Test locally** - Verify it works
3. **Open network access** - Configure firewall
4. **Share with team** - One-line setup command

Ready to create the HTTP server code? See `mcp_http_server.py`.
