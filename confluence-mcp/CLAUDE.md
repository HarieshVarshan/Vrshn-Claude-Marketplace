# Confluence MCP Server - Quick Reference

## Overview

MCP server for Confluence Data Center/Server via REST API.

## Configuration

Credentials: `~/.config/confluence-mcp/.env` (or `~/.config/atlassian/.env`)

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
| `confluence_get_page_attachments` | Get page attachments |

### History
| Tool | Description |
|------|-------------|
| `confluence_get_page_history` | Get version history |

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
