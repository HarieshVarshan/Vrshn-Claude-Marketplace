# Confluence MCP Server - Quick Reference

## Overview

MCP server for Confluence Data Center/Server via REST API.

## Configuration

Credentials: `~/.config/atlassian/.env` (primary) or `~/.config/confluence-mcp/.env` (optional override)

```bash
CONFLUENCE_URL=https://confluence.example.com
CONFLUENCE_USERNAME=username
CONFLUENCE_TOKEN=your-api-token
```

## Available Tools

### Pages
| Tool | Description |
|------|-------------|
| `confluence_get_page` | Get page by ID or URL |
| `confluence_get_page_by_title` | Get page by space + title |
| `confluence_create_page` | Create a new page |
| `confluence_update_page` | Update page content |
| `confluence_delete_page` | Delete a page |
| `confluence_get_page_children` | Get child pages |
| `confluence_get_page_ancestors` | Get parent hierarchy |
| `confluence_get_page_descendants` | Get all descendant pages (recursive) |
| `confluence_move_page` | Move page to different space/parent |
| `confluence_copy_page` | Copy page to new location |

### Search
| Tool | Description |
|------|-------------|
| `confluence_search` | Search with text or CQL |

### Spaces
| Tool | Description |
|------|-------------|
| `confluence_get_all_spaces` | List all spaces |
| `confluence_get_space` | Get space details |
| `confluence_get_space_pages` | List pages in space |
| `confluence_create_space` | Create a new space |
| `confluence_update_space` | Update space name/description |
| `confluence_delete_space` | Delete a space |

### Comments
| Tool | Description |
|------|-------------|
| `confluence_add_comment` | Add comment to page |
| `confluence_get_page_comments` | Get page comments |

### Labels
| Tool | Description |
|------|-------------|
| `confluence_get_page_labels` | Get page labels |
| `confluence_add_page_label` | Add label to page |
| `confluence_remove_page_label` | Remove label |

### Attachments
| Tool | Description |
|------|-------------|
| `confluence_get_page_attachments` | List attachments on a page |
| `confluence_get_attachment` | Get attachment metadata |
| `confluence_upload_attachment` | Upload file to page |
| `confluence_download_attachment` | Download attachment to local filesystem |
| `confluence_delete_attachment` | Delete an attachment |

### History & Versions
| Tool | Description |
|------|-------------|
| `confluence_get_page_history` | Get page history overview |
| `confluence_list_page_versions` | List all versions of a page |
| `confluence_get_page_version` | Read specific historical version content |

### Page Restrictions
| Tool | Description |
|------|-------------|
| `confluence_get_page_restrictions` | Get view/edit restrictions |
| `confluence_set_page_restrictions` | Set view/edit restrictions |
| `confluence_remove_page_restrictions` | Remove all restrictions |

### Users
| Tool | Description |
|------|-------------|
| `confluence_search_users` | Search for users |
| `confluence_get_current_user` | Get authenticated user info |

### Raw API (Fallback)
| Tool | Description |
|------|-------------|
| `confluence_raw_api` | Make arbitrary API calls for operations not covered by other tools |

**Usage:**
```python
confluence_raw_api(method="GET", endpoint="/rest/api/content/123456")
confluence_raw_api(method="POST", endpoint="/rest/api/content", body={"type": "page", ...})
```

## CQL Quick Reference

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

## Key Files

- `mcp_server.py` - Main entry point
- `confluence_client.py` - Confluence REST API client
- `requirements.txt` - Python dependencies
