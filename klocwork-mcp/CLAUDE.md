# Klocwork MCP Server - Quick Reference

## Overview

MCP server for Klocwork project management via kwadmin CLI and Web API.
Supports multiple Klocwork servers.

## Prerequisites

- Python 3.11+
- `uv` package manager
- Klocwork client tools (kwadmin) in PATH

## Configuration

Credentials: `~/.config/atlassian/.env` (primary) or `~/.config/klocwork-mcp/.env` (optional override)

### Multi-Server Configuration
```bash
# List of configured servers
KLOCWORK_SERVERS=india,stage

# India server
KLOCWORK_INDIA_URL=https://klocworkweb.india.ti.com:8095
KLOCWORK_INDIA_USERNAME=your-username
KLOCWORK_INDIA_TOKEN=your-ltoken

# Stage server
KLOCWORK_STAGE_URL=https://klocwork-stage.itg.ti.com:8090
KLOCWORK_STAGE_USERNAME=your-username
KLOCWORK_STAGE_TOKEN=your-ltoken

# Default server
KLOCWORK_DEFAULT_SERVER=india
```

### Single Server (Legacy)
```bash
KLOCWORK_URL=https://klocworkweb.india.ti.com:8095
KLOCWORK_USERNAME=your-username
KLOCWORK_TOKEN=your-ltoken
```

### Getting Your Token

1. Run: `kwauth --url https://klocworkweb.india.ti.com:8095`
2. Check: `cat ~/.klocwork/ltoken`
3. Format: `host;port;user;token` - copy the **4th field**

## Available Tools

**Note:** All tools accept an optional `server` parameter ('india' or 'stage'). Defaults to KLOCWORK_DEFAULT_SERVER.

### Server Operations
| Tool | Description |
|------|-------------|
| `klocwork_list_servers` | List all configured servers |
| `klocwork_get_config` | Get current server configuration |
| `klocwork_get_server_info` | Get server version and info |

### Project Operations
| Tool | Description |
|------|-------------|
| `klocwork_list_projects` | List all projects |
| `klocwork_create_project` | Create a new project (with optional config import) |
| `klocwork_delete_project` | Delete a project |
| `klocwork_get_project_info` | Get project details |

### Configuration Operations
| Tool | Description |
|------|-------------|
| `klocwork_import_config` | Import config from one project to another |
| `klocwork_export_config` | Export project config to file |
| `klocwork_load_config` | Load config from file |

### Module Operations
| Tool | Description |
|------|-------------|
| `klocwork_list_modules` | List modules in a project |
| `klocwork_create_module` | Create a new module |
| `klocwork_delete_module` | Delete a module |
| `klocwork_replicate_modules` | Copy all modules between projects |

### Permission Operations
| Tool | Description |
|------|-------------|
| `klocwork_list_users` | List project users and roles |
| `klocwork_add_user` | Add user to project |
| `klocwork_remove_user` | Remove user from project |
| `klocwork_set_user_role` | Change user's role |

### Build Operations
| Tool | Description |
|------|-------------|
| `klocwork_list_builds` | List recent builds |
| `klocwork_get_build_info` | Get build details |

### Issue Operations
| Tool | Description |
|------|-------------|
| `klocwork_search_issues` | Search for issues/defects |
| `klocwork_get_issue` | Get issue details |
| `klocwork_update_issue_status` | Update issue status (triage) |

### Raw API (Fallback)
| Tool | Description |
|------|-------------|
| `klocwork_raw_kwadmin` | Execute any kwadmin command |

## Usage Examples

### Create a Project on Stage Server
```
User: "Create a new Klocwork project called TEST_PROJECT on stage server"
Claude: [Calls klocwork_create_project with project_name="TEST_PROJECT", server="stage"]
        ✓ Project created!
```

### List Projects on India Server
```
User: "List all Klocwork projects on India"
Claude: [Calls klocwork_list_projects with server="india"]
```

### Replicate Modules
```
User: "Copy modules from PROCESSOR_SDK_QNX to PSDKQA_SDP710"
Claude: [Calls klocwork_replicate_modules]
        ✓ 12 modules copied successfully
```

## Quick Start

```bash
# Install dependencies
cd klocwork-mcp
uv sync

# Configure credentials in ~/.config/atlassian/.env

# Run the server
uv run python mcp_server.py
```

## Key Files

- `mcp_server.py` - Main entry point (22 tools)
- `klocwork_client.py` - Klocwork API client (kwadmin wrapper)
- `pyproject.toml` - Project configuration for uv
- `requirements.txt` - Python dependencies
