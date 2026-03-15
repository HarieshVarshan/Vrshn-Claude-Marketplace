# Confluence MCP Server - Quick Reference

## Overview

MCP server for Confluence Data Center/Server via REST API. Supports Markdown content (auto-converted to/from Confluence XHTML), `cfl://` URL schemes for Confluence-specific elements, file I/O, watch operations, and structured error handling.

## Configuration

Credentials: `~/.config/atlassian/.env` (primary) or `~/.config/confluence-mcp/.env` (optional override)

```bash
CONFLUENCE_URL=https://confluence.example.com
CONFLUENCE_USERNAME=username
CONFLUENCE_TOKEN=your-api-token
```

## Markdown Content Support

Content is now **Markdown-native**:
- **Reading pages:** XHTML content is auto-converted to Markdown in tool output
- **Creating/updating pages:** Provide content as Markdown (auto-detected and converted to XHTML) or raw XHTML (passed through unchanged)
- **Detection:** Content starting with `<p`, `<h1`, `<div`, `<table`, `<ac:`, `<ri:` is treated as XHTML; everything else is parsed as Markdown

## `cfl://` URL Scheme

Use special `cfl://` URLs in Markdown content for Confluence-specific elements:

| Pattern | Description | Confluence Output |
|---------|-------------|------------------|
| `[Name](cfl://user/username)` | User mention | `<ac:link><ri:user>` |
| `[Title](cfl://page/SPACE/Title)` | Page link | `<ac:link><ri:page>` |
| `[Display](cfl://date/YYYY-MM-DD)` | Date | `<time datetime>` |
| `[Text](cfl://status/Color/Text)` | Status macro | Status lozenge |
| `[KEY-123](cfl://jira/KEY-123)` | Jira issue | Jira issue macro |
| `![alt](cfl://image/file.png?width=200)` | Attached image | `<ac:image><ri:attachment>` |
| `[Name](cfl://attachment/file.pdf)` | Attachment link | `<ac:link><ri:attachment>` |

## Available Tools

### Pages
| Tool | Description |
|------|-------------|
| `confluence_get_page` | Get page by ID or URL (returns Markdown, supports `save_to_file` / `save_to_dir`) |
| `confluence_get_page_by_title` | Get page by space + title (returns Markdown, supports `save_to_file` / `save_to_dir`) |
| `confluence_create_page` | Create page from Markdown/XHTML content or `file_path` |
| `confluence_update_page` | Update page from Markdown/XHTML content or `file_path` |
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

### Watch
| Tool | Description |
|------|-------------|
| `confluence_is_watching_content` | Check if you're watching a page/content |
| `confluence_watch_content` | Start watching a page/content |
| `confluence_unwatch_content` | Stop watching a page/content |
| `confluence_watch_space` | Start watching a space |
| `confluence_unwatch_space` | Stop watching a space |

### Raw API (Fallback)
| Tool | Description |
|------|-------------|
| `confluence_raw_api` | Make arbitrary API calls for operations not covered by other tools |

**Usage:**
```python
confluence_raw_api(method="GET", endpoint="/rest/api/content/123456")
confluence_raw_api(method="POST", endpoint="/rest/api/content", body={"type": "page", ...})
```

## File I/O Parameters

**Reading pages to local files:**
```python
# Save as single Markdown file with YAML front matter
confluence_get_page(page_id="123456", save_to_file="~/docs/my-page.md")

# Save as directory with index.md + attachments/
confluence_get_page(page_id="123456", save_to_dir="~/docs/my-page/")
```

**Creating/updating from local files:**
```python
# Read content from file instead of inline
confluence_create_page(space_key="DOCS", title="New Page", file_path="~/docs/content.md")
confluence_update_page(page_id="123456", title="Updated", file_path="~/docs/content.md")
```

## Error Handling

Errors are classified with actionable suggestions:
- **401 (auth):** Token expiration guidance
- **403 (permission):** Contact admin suggestion
- **404 (not_found):** Verify ID/URL guidance
- **409 (conflict):** Version conflict resolution
- **5xx (server):** Retry suggestion
- **Connection/Timeout:** Network troubleshooting

Error logs: `~/.config/confluence-mcp/logs/error-log-YYYY-MM-DD.json` (auto-cleaned after 30 days)

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

- `mcp_server.py` - Main entry point (41 tools)
- `confluence_client.py` - Confluence REST API client
- `confluence_converter.py` - Markdown <-> XHTML converter with `cfl://` support
- `confluence_file_io.py` - File read/save helpers
- `confluence_errors.py` - Error classification and logging
- `requirements.txt` - Python dependencies
