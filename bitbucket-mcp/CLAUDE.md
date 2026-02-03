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
| `bitbucket_create_pr` | Create a new pull request |
| `bitbucket_update_pr` | Update PR title/description |
| `bitbucket_reopen_pr` | Reopen a declined PR |
| `bitbucket_add_pr_reviewer` | Add reviewer to PR |
| `bitbucket_remove_pr_reviewer` | Remove reviewer from PR |
| `bitbucket_get_pr_tasks` | Get tasks on a PR |
| `bitbucket_add_pr_task` | Add task to a PR comment |
| `bitbucket_update_pr_task` | Mark task complete/incomplete |
| `bitbucket_get_pr_merge_status` | Check if PR is mergeable |

### Repositories
| Tool | Description |
|------|-------------|
| `bitbucket_get_repos` | List repos in project |
| `bitbucket_get_repo` | Get repo details |
| `bitbucket_create_repo` | Create a new repository |
| `bitbucket_delete_repo` | Delete a repository |
| `bitbucket_fork_repo` | Fork a repository |
| `bitbucket_get_repo_webhooks` | List repository webhooks |
| `bitbucket_create_webhook` | Create a webhook |
| `bitbucket_delete_webhook` | Delete a webhook |

### Branches
| Tool | Description |
|------|-------------|
| `bitbucket_list_branches` | List branches |
| `bitbucket_get_default_branch` | Get default branch |
| `bitbucket_create_branch` | Create a new branch |
| `bitbucket_delete_branch` | Delete a branch |
| `bitbucket_set_default_branch` | Set default branch |
| `bitbucket_compare_branches` | Compare two branches |

### Tags
| Tool | Description |
|------|-------------|
| `bitbucket_list_tags` | List tags |
| `bitbucket_create_tag` | Create a new tag |
| `bitbucket_delete_tag` | Delete a tag |

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
| `bitbucket_create_project` | Create a new project |
| `bitbucket_update_project` | Update project details |
| `bitbucket_delete_project` | Delete a project |

### Build Status
| Tool | Description |
|------|-------------|
| `bitbucket_get_commit_build_status` | Get CI build status for a commit |
| `bitbucket_set_commit_build_status` | Set build status for a commit |

### Permissions
| Tool | Description |
|------|-------------|
| `bitbucket_get_repo_permissions` | Get repository user/group permissions |
| `bitbucket_grant_repo_permission` | Grant repo access to user/group |
| `bitbucket_revoke_repo_permission` | Revoke repo access |

### Users
| Tool | Description |
|------|-------------|
| `bitbucket_search_users` | Search for users |

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
