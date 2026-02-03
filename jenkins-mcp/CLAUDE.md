# Jenkins MCP Server - Quick Reference

## Overview

MCP server for Jenkins Server via REST API (read-only operations). Supports multiple Jenkins server configurations.

## Configuration

Credentials: `~/.config/jenkins-mcp/.env` (or `~/.config/atlassian/.env`)

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
| `jenkins_get_build_log` | Get build console output |

### Infrastructure
| Tool | Description |
|------|-------------|
| `jenkins_get_queue` | Get pending builds queue |
| `jenkins_get_nodes` | Get build agent status |

**Note:** All Jenkins tools accept an optional `server` parameter to specify which Jenkins server to use. If not specified, the first configured server is used.

## Key Files

- `mcp_server.py` - Main entry point
- `jenkins_client.py` - Jenkins REST API client
- `requirements.txt` - Python dependencies
