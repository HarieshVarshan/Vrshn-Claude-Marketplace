# Email MCP Server - Quick Reference

## Overview

MCP server for email management via IMAP/SMTP. Send, read, search, delete, move emails, manage folders, and download attachments.

## Configuration

Credentials: `~/.config/atlassian/.env` (primary) or `~/.config/email-mcp/.env` (optional override)

Add the following to your `~/.config/atlassian/.env`:

```bash
# =============================================================================
# Email credentials
# =============================================================================
EMAIL_USER=your-email@example.com
EMAIL_PASSWORD=your-password

IMAP_HOST=imap.example.com
IMAP_PORT=993
IMAP_SECURE=true

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_STARTTLS=true
```

### TI servers

```bash
EMAIL_USER=a0513924@ti.com
EMAIL_PASSWORD=your-password
IMAP_HOST=email.ti.com
IMAP_PORT=993
IMAP_SECURE=true
SMTP_HOST=smtp.mail.ti.com
SMTP_PORT=25
SMTP_SECURE=false
SMTP_STARTTLS=false
```

### Gmail

```bash
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_SECURE=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true
```

### Outlook/Office365

```bash
IMAP_HOST=outlook.office365.com
IMAP_PORT=993
IMAP_SECURE=true
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_STARTTLS=true
```

## Available Tools (8)

### Email Operations
| Tool | Description |
|------|-------------|
| `email_send` | Send email with optional attachments (CC, BCC, HTML support) |
| `email_get` | Get full email details by UID (headers, body, attachment list) |
| `email_list` | List emails from a folder with pagination and unread filter |
| `email_search` | Search emails by query, sender, subject, date range |
| `email_delete` | Delete emails (move to trash or permanently) |
| `email_move` | Move emails between folders |

### Folder & Attachment Operations
| Tool | Description |
|------|-------------|
| `email_get_folders` | List all available email folders |
| `email_download_attachment` | Download attachment(s) to local filesystem or as base64 |

## Email Identifiers

| Field | Type | Use For |
|-------|------|---------|
| `uid` | integer | All operations (`email_get`, `email_delete`, `email_move`, `email_download_attachment`) |
| `messageId` | string | Reference/threading only - do NOT use for IMAP operations |

## Key Files

- `mcp_server.py` - Main entry point (8 tools)
- `email_client.py` - IMAP/SMTP client + config loader
- `requirements.txt` - Python dependencies
