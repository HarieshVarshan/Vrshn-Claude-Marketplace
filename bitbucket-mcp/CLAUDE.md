# Bitbucket MCP Server - Quick Reference

## Overview

MCP server for Bitbucket Server/Data Center via REST API.

## Configuration

Credentials: `~/.config/atlassian/.env` (primary) or `~/.config/bitbucket-mcp/.env` (optional override)

```bash
BITBUCKET_URL=https://bitbucket.example.com
BITBUCKET_USERNAME=username
BITBUCKET_TOKEN=your-api-token
```

## Available Tools

### Pull Requests
| Tool | Description |
|------|-------------|
| `bitbucket_get_pr` | Get PR by URL or project/repo/ID |
| `bitbucket_list_prs` | List PRs for a repository |
| `bitbucket_get_pr_diff` | Get PR diff/changes |
| `bitbucket_get_pr_commits` | Get PR commits |
| `bitbucket_get_pr_activities` | Get PR activities/comments |
| `bitbucket_add_pr_comment` | Add comment to PR |
| `bitbucket_approve_pr` | Approve PR |
| `bitbucket_unapprove_pr` | Remove approval |
| `bitbucket_merge_pr` | Merge PR |
| `bitbucket_decline_pr` | Decline PR |

### Repositories
| Tool | Description |
|------|-------------|
| `bitbucket_get_repos` | List repos in project |
| `bitbucket_get_repo` | Get repo details |

### Branches
| Tool | Description |
|------|-------------|
| `bitbucket_list_branches` | List branches |
| `bitbucket_get_default_branch` | Get default branch |

### Tags
| Tool | Description |
|------|-------------|
| `bitbucket_list_tags` | List tags |

### Commits
| Tool | Description |
|------|-------------|
| `bitbucket_list_commits` | List commits |
| `bitbucket_get_commit` | Get commit details |
| `bitbucket_get_commit_diff` | Get commit diff |

### Files
| Tool | Description |
|------|-------------|
| `bitbucket_get_file` | Get file content |
| `bitbucket_browse` | Browse directory |

### Projects
| Tool | Description |
|------|-------------|
| `bitbucket_get_all_projects` | List all projects |
| `bitbucket_get_project` | Get project details |

### Raw API (Fallback)
| Tool | Description |
|------|-------------|
| `bitbucket_raw_api` | Make arbitrary API calls for operations not covered by other tools |

**Usage:**
```python
bitbucket_raw_api(method="GET", endpoint="/rest/api/1.0/projects/PROJ/repos")
bitbucket_raw_api(method="POST", endpoint="/rest/api/1.0/projects", body={"key": "NEW", ...})
```

## URL Parsing

The tools automatically parse URLs:
- `https://bitbucket.example.com/projects/PROJ/repos/my-repo/pull-requests/42` -> extracts project, repo, PR ID

## Key Files

- `mcp_server.py` - Main entry point
- `bitbucket_client.py` - Bitbucket REST API client
- `requirements.txt` - Python dependencies
