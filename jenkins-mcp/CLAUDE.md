# Jenkins MCP Server - Quick Reference

## Overview

MCP server for Jenkins Server via REST API. Supports multiple Jenkins server configurations.

## Configuration

Credentials: `~/.config/atlassian/.env` (primary) or `~/.config/jenkins-mcp/.env` (optional override)

### Single Server (Legacy)
```bash
JENKINS_URL=https://jenkins.example.com
JENKINS_USERNAME=username
JENKINS_TOKEN=api-token
```

### Multiple Servers
```bash
# Comma-separated list of server names
JENKINS_SERVERS=proc,epsw

# Server-specific credentials (uppercase server name)
JENKINS_PROC_URL=https://jenkins-proc.example.com
JENKINS_PROC_USERNAME=username
JENKINS_PROC_TOKEN=api-token

JENKINS_EPSW_URL=https://jenkins-epsw.example.com
JENKINS_EPSW_USERNAME=username
JENKINS_EPSW_TOKEN=api-token
```

## Available Tools

### Server Management
| Tool | Description |
|------|-------------|
| `jenkins_list_servers` | List available configured Jenkins servers |

### Jobs
| Tool | Description |
|------|-------------|
| `jenkins_get_job` | Get job details and status |
| `jenkins_list_jobs` | List all jobs (optionally in a folder) |
| `jenkins_get_job_config` | Get job configuration (SCM, triggers, parameters, build steps) |

### Builds
| Tool | Description |
|------|-------------|
| `jenkins_get_build` | Get specific build information |
| `jenkins_get_last_build` | Get the most recent build for a job |
| `jenkins_list_builds` | List builds for a job with summary |
| `jenkins_get_build_log` | Get build console output |
| `jenkins_get_build_test_results` | Get test results (JUnit) for a build |
| `jenkins_get_build_artifacts` | List artifacts from a build |
| `jenkins_download_artifact` | Download an artifact from a build |

### Views
| Tool | Description |
|------|-------------|
| `jenkins_list_views` | List all Jenkins views |
| `jenkins_get_view` | Get jobs in a specific view |

### Infrastructure
| Tool | Description |
|------|-------------|
| `jenkins_get_queue` | Get pending builds queue |
| `jenkins_get_nodes` | Get build agent status |
| `jenkins_get_node_details` | Get detailed info about a specific node |

### System Info
| Tool | Description |
|------|-------------|
| `jenkins_get_system_info` | Get Jenkins version and system details |
| `jenkins_get_plugins` | List installed plugins |
| `jenkins_get_credentials_list` | List credential IDs (metadata only, not secrets) |

### Build Operations (Write)
| Tool | Description |
|------|-------------|
| `jenkins_trigger_build` | Start a build (with optional parameters) |
| `jenkins_stop_build` | Abort a running build |

### Job Operations (Write)
| Tool | Description |
|------|-------------|
| `jenkins_enable_job` | Enable a disabled job |
| `jenkins_disable_job` | Disable a job |
| `jenkins_create_job` | Create a new job from XML config |
| `jenkins_copy_job` | Copy an existing job |
| `jenkins_delete_job` | Delete a job |
| `jenkins_update_job_config` | Update job XML configuration |

### Raw API (Fallback)
| Tool | Description |
|------|-------------|
| `jenkins_raw_api` | Make arbitrary API calls for operations not covered by other tools |

**Usage:**
```python
jenkins_raw_api(method="GET", endpoint="/job/my-job/api/json")
jenkins_raw_api(method="POST", endpoint="/job/my-job/build", server="proc")
```

**Note:** All Jenkins tools accept an optional `server` parameter to specify which Jenkins server to use. If not specified, the first configured server is used.

## Key Files

- `mcp_server.py` - Main entry point
- `jenkins_client.py` - Jenkins REST API client
- `requirements.txt` - Python dependencies
