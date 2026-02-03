# Jira MCP Server - Quick Reference

## Overview

MCP server for comprehensive Jira Data Center/Server administration via REST API.

## Configuration

Credentials: `~/.config/atlassian/.env` (primary) or `~/.config/jira-mcp/.env` (optional override)

```bash
JIRA_URL=https://jira.example.com
JIRA_USERNAME=username
JIRA_TOKEN=your-api-token
```

## Available Tools

### Issues
| Tool | Description |
|------|-------------|
| `jira_get_issue` | Get issue by key (PROJ-123) or URL |
| `jira_search` | Search using JQL |
| `jira_create_issue` | Create new issue |
| `jira_update_issue` | Update issue fields |
| `jira_delete_issue` | Delete an issue |
| `jira_assign_issue` | Assign/unassign issue |

### Transitions
| Tool | Description |
|------|-------------|
| `jira_get_transitions` | Get available transitions for an issue |
| `jira_transition_issue` | Change issue status |

### Comments
| Tool | Description |
|------|-------------|
| `jira_add_comment` | Add comment to issue |
| `jira_get_comments` | Get all comments for an issue |

### Worklog
| Tool | Description |
|------|-------------|
| `jira_add_worklog` | Log work on an issue |
| `jira_get_worklogs` | Get work logs for an issue |

### Issue Links
| Tool | Description |
|------|-------------|
| `jira_link_issues` | Link two issues together |
| `jira_get_link_types` | Get available link types |

### Watchers
| Tool | Description |
|------|-------------|
| `jira_get_watchers` | Get watchers for an issue |
| `jira_add_watcher` | Add watcher to issue |
| `jira_remove_watcher` | Remove watcher from issue |

### Projects
| Tool | Description |
|------|-------------|
| `jira_get_all_projects` | List all projects |
| `jira_get_project` | Get project details |
| `jira_get_project_components` | Get project components |
| `jira_create_component` | Create component |
| `jira_get_project_versions` | Get project versions |
| `jira_create_version` | Create version |
| `jira_get_project_statuses` | Get project statuses |

### Users
| Tool | Description |
|------|-------------|
| `jira_get_user` | Get user by username |
| `jira_search_users` | Search for users |
| `jira_find_assignable_users` | Find assignable users |
| `jira_get_current_user` | Get authenticated user |

### Groups
| Tool | Description |
|------|-------------|
| `jira_get_all_groups` | List all groups |
| `jira_get_group_members` | Get group members |
| `jira_add_user_to_group` | Add user to group |
| `jira_remove_user_from_group` | Remove user from group |

### Boards (Agile)
| Tool | Description |
|------|-------------|
| `jira_get_all_boards` | List agile boards |
| `jira_get_board` | Get board details |
| `jira_get_board_sprints` | Get board sprints |
| `jira_get_board_backlog` | Get backlog issues |

### Sprints
| Tool | Description |
|------|-------------|
| `jira_get_sprint` | Get sprint details |
| `jira_create_sprint` | Create sprint |
| `jira_update_sprint` | Update sprint |
| `jira_get_sprint_issues` | Get sprint issues |
| `jira_move_issues_to_sprint` | Move issues to sprint |
| `jira_move_issues_to_backlog` | Move issues to backlog |

### Epics
| Tool | Description |
|------|-------------|
| `jira_get_epic` | Get epic details |
| `jira_get_epic_issues` | Get issues in epic |
| `jira_move_issues_to_epic` | Move issues to epic |

### Filters
| Tool | Description |
|------|-------------|
| `jira_get_filter` | Get filter by ID |
| `jira_get_favorite_filters` | Get favorite filters |
| `jira_search_filters` | Search filters |
| `jira_create_filter` | Create filter |
| `jira_delete_filter` | Delete filter |

### Dashboards
| Tool | Description |
|------|-------------|
| `jira_get_all_dashboards` | List dashboards |
| `jira_get_dashboard` | Get dashboard details |

### Administration
| Tool | Description |
|------|-------------|
| `jira_get_server_info` | Get server information |
| `jira_get_all_fields` | Get all fields (including custom) |
| `jira_get_all_issue_types` | Get all issue types |
| `jira_get_all_priorities` | Get all priorities |
| `jira_get_all_statuses` | Get all statuses |
| `jira_get_all_resolutions` | Get all resolutions |

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

## Key Files

- `mcp_server.py` - Main entry point, defines MCP tools
- `jira_client.py` - Jira REST API client
- `requirements.txt` - Python dependencies
