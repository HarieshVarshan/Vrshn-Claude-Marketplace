# Webex MCP Server - Quick Reference

## Overview

MCP server for Cisco Webex collaboration platform. Manage people, teams, rooms/spaces, messages, memberships, and webhooks via the Webex REST API.

## Configuration

Credentials: `~/.config/atlassian/.env` (primary) or `~/.config/webex-mcp/.env` (optional override)

Add to your `~/.config/atlassian/.env`:

```bash
# =============================================================================
# Webex credentials
# =============================================================================
WEBEX_ACCESS_TOKEN=your-webex-access-token
```

### Getting a token

1. Go to [Webex Developer Portal](https://developer.webex.com/)
2. Sign in with your Webex account
3. Navigate to "Getting Started" -> "Your Personal Access Token"
4. Copy the token (valid for 12 hours)

For long-lived tokens, use a Webex Integration or Bot token instead of a personal access token.

## Available Tools (25)

### People (3)
| Tool | Description |
|------|-------------|
| `webex_get_me` | Get current authenticated user details |
| `webex_list_people` | Search people by email or display name |
| `webex_get_person` | Get details for a specific person |

### Organizations (2)
| Tool | Description |
|------|-------------|
| `webex_list_organizations` | List organizations the user belongs to |
| `webex_get_organization` | Get organization details |

### Teams (4)
| Tool | Description |
|------|-------------|
| `webex_list_teams` | List teams the user is a member of |
| `webex_create_team` | Create a new team |
| `webex_get_team` | Get team details |
| `webex_delete_team` | Delete a team |

### Rooms (4)
| Tool | Description |
|------|-------------|
| `webex_list_rooms` | List rooms/spaces (filter by team or type) |
| `webex_create_room` | Create a new room/space |
| `webex_get_room` | Get room details |
| `webex_delete_room` | Delete a room |

### Messages (4)
| Tool | Description |
|------|-------------|
| `webex_list_messages` | List messages in a room |
| `webex_create_message` | Send message (text/markdown/HTML, to room or person) |
| `webex_get_message` | Get message details |
| `webex_delete_message` | Delete a message |

### Memberships (4)
| Tool | Description |
|------|-------------|
| `webex_list_memberships` | List room memberships |
| `webex_create_membership` | Add person to a room (by ID or email) |
| `webex_get_membership` | Get membership details |
| `webex_delete_membership` | Remove person from a room |

### Webhooks (4)
| Tool | Description |
|------|-------------|
| `webex_list_webhooks` | List webhooks |
| `webex_create_webhook` | Create webhook (resource + event + target URL) |
| `webex_get_webhook` | Get webhook details |
| `webex_delete_webhook` | Delete a webhook |

## Key Files

- `mcp_server.py` - Main entry point (25 tools)
- `webex_client.py` - Webex REST API client + config loader
- `requirements.txt` - Python dependencies
