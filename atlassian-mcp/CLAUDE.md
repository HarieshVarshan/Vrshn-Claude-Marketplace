# Atlassian MCP Server - Quick Reference

## Overview

This MCP server provides tools for interacting with Jira, Confluence, Bitbucket, and Jenkins from Claude conversations.

## Available Tools

### Jira
| Tool | Description |
|------|-------------|
| `jira_get_issue` | Get issue by key (PROJ-123) or URL |
| `jira_search` | Search with JQL (e.g., `project = PROJ AND status = Open`) |
| `jira_create_issue` | Create new issue |
| `jira_add_comment` | Add comment to issue |
| `jira_transition_issue` | Change issue status |
| `jira_update_issue` | Update issue fields (summary, description, assignee, priority, labels) |

### Confluence
| Tool | Description |
|------|-------------|
| `confluence_get_page` | Get page by ID or URL |
| `confluence_get_page_by_title` | Get page by space + title |
| `confluence_search` | Search with text or CQL |
| `confluence_get_space_pages` | List pages in space |
| `confluence_create_page` | Create a new page |
| `confluence_update_page` | Update page content |
| `confluence_add_comment` | Add comment to a page |

### Bitbucket
| Tool | Description |
|------|-------------|
| `bitbucket_get_pr` | Get PR details |
| `bitbucket_get_pr_diff` | Get PR code changes |
| `bitbucket_list_prs` | List repository PRs |
| `bitbucket_add_pr_comment` | Comment on PR |
| `bitbucket_get_file` | Get file from repo |
| `bitbucket_list_branches` | List branches |

### Jenkins (Read-Only)
| Tool | Description |
|------|-------------|
| `jenkins_list_servers` | List available configured Jenkins servers |
| `jenkins_get_job` | Get job details and status |
| `jenkins_get_build` | Get specific build information |
| `jenkins_list_jobs` | List all jobs (optionally in a folder) |
| `jenkins_get_build_log` | Get build console output |
| `jenkins_get_queue` | Get pending builds queue |
| `jenkins_get_nodes` | Get build agent status |
| `jenkins_get_job_config` | Get job configuration (SCM, triggers, parameters, build steps) |

**Note:** All Jenkins tools accept an optional `server` parameter to specify which Jenkins server to use (e.g., `server: "proc"` or `server: "epsw"`). If not specified, the first configured server is used.

## URL Parsing

The tools automatically parse URLs:

- **Jira**: `https://jira.example.com/browse/PROJ-123` -> extracts `PROJ-123`
- **Confluence**: `https://confluence.example.com/pages/viewpage.action?pageId=123456` -> extracts `123456`
- **Bitbucket**: `https://bitbucket.example.com/projects/PROJ/repos/my-repo/pull-requests/42` -> extracts project, repo, PR ID

## JQL Quick Reference

```jql
# Find issues
project = PROJ
assignee = currentUser()
status = "In Progress"
status in (Open, "In Progress")
text ~ "search term"

# Combine with AND/OR
project = PROJ AND status = Open
assignee = currentUser() OR reporter = currentUser()

# Order results
project = PROJ ORDER BY created DESC
```

## CQL Quick Reference (Confluence)

```cql
# Search text
text ~ "search term"

# Filter by space
space = DOCS
space IN (DOCS, TEAM)

# By title
title ~ "guide"

# Combined
text ~ "deployment" AND space = DOCS
```

## Configuration

Credentials: `~/.config/atlassian/.env`

```bash
JIRA_URL=https://jira.example.com
JIRA_USERNAME=username
JIRA_TOKEN=token

CONFLUENCE_URL=https://confluence.example.com
CONFLUENCE_USERNAME=username
CONFLUENCE_TOKEN=token

BITBUCKET_URL=https://bitbucket.example.com
BITBUCKET_USERNAME=username
BITBUCKET_TOKEN=token
```

### Jenkins Configuration

**Single server (legacy):**
```bash
JENKINS_URL=https://jenkins.example.com
JENKINS_USERNAME=username
JENKINS_TOKEN=api-token
```

**Multiple servers:**
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

## Key Files

- `mcp_server.py` - Main entry point, defines MCP tools
- `atlassian_client.py` - API clients for all four services (Jira, Confluence, Bitbucket, Jenkins)
- `requirements.txt` - Python dependencies (mcp, requests, python-dotenv)
