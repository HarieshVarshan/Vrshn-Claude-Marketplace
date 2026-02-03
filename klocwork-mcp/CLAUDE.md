# Klocwork MCP Server - Quick Reference

## Overview

MCP server for Klocwork project management via kwadmin CLI and Web API.
Supports multiple servers (Dallas and India).

## Prerequisites

- Python 3.11+
- `uv` package manager
- Klocwork client tools (kwadmin, kwauth) in PATH
- Valid Klocwork authentication token

## Authentication

```bash
# Authenticate with Dallas server
kwauth --url https://klocwork.itg.ti.com:8090/

# Or India server
kwauth --url https://klocworkweb.india.ti.com:8095/
```

This creates an ltoken file at `~/.klocwork/ltoken`.

## Configuration

Optional environment file: `~/.config/atlassian/.env` or `~/.config/klocwork-mcp/.env`

```bash
KLOCWORK_DEFAULT_SERVER=dallas
```

## Available Tools

### Server Operations
| Tool | Description |
|------|-------------|
| `klocwork_list_servers` | List configured Klocwork servers |
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

**Usage:**
```python
klocwork_raw_kwadmin(command="list-projects", args=[])
klocwork_raw_kwadmin(command="get-project", args=["PROJECT_NAME"], server="india")
```

## Server URLs

| Location | URL |
|----------|-----|
| Dallas | https://klocwork.itg.ti.com:8090/ |
| India | https://klocworkweb.india.ti.com:8095/ |

**Note:** All tools accept an optional `server` parameter ('dallas' or 'india'). Defaults to dallas.

## Usage Examples

### Create a Project
```
User: "Create a new Klocwork project called OTP_KW_F29H85X"
Claude: [Calls klocwork_create_project with project_name="OTP_KW_F29H85X"]
        ✓ Project created!
        URL: https://klocwork.itg.ti.com:8090/review/insight-review.html#goto:project=OTP_KW_F29H85X
```

### Create with Reference Project
```
User: "Create NEW_AUTOMOTIVE_PROJECT using AUTOMOTIVE_REFERENCE as template"
Claude: [Calls klocwork_create_project with reference_project="AUTOMOTIVE_REFERENCE"]
        ✓ Project created with configuration from AUTOMOTIVE_REFERENCE
```

### Replicate Modules
```
User: "Copy modules from PROCESSOR_SDK_QNX to PSDKQA_SDP710"
Claude: [Calls klocwork_replicate_modules]
        ✓ 12 modules copied successfully
```

### Add User Permission
```
User: "Give john_doe admin access to MY_PROJECT on the India server"
Claude: [Calls klocwork_add_user with server="india", role="admin"]
        ✓ User john_doe added as admin
```

## Quick Start

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
cd klocwork-mcp
uv sync

# Authenticate with Klocwork
kwauth --url https://klocwork.itg.ti.com:8090/

# Run the server
uv run python mcp_server.py
```

## Key Files

- `mcp_server.py` - Main entry point
- `klocwork_client.py` - Klocwork API client (kwadmin wrapper)
- `pyproject.toml` - Project configuration for uv
- `requirements.txt` - Python dependencies
