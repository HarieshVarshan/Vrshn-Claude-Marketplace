"""
Error classification, user-friendly messages, and daily JSON log files.

Classifies HTTP and connection errors into categories with actionable suggestions.
Logs errors to ~/.config/confluence-mcp/logs/error-log-YYYY-MM-DD.json (JSON Lines format).
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests


LOG_DIR = os.path.expanduser('~/.config/confluence-mcp/logs')


class ConfluenceError:
    """Structured error with category, message, and actionable suggestion."""

    def __init__(self, tool_name: str, status_code: Optional[int],
                 message: str, category: str, suggestion: str):
        self.tool_name = tool_name
        self.status_code = status_code
        self.message = message
        self.category = category
        self.suggestion = suggestion
        self.timestamp = datetime.now(timezone.utc).isoformat() + 'Z'

    def format_for_user(self) -> str:
        """Return a Markdown-formatted error message for MCP tool output."""
        parts = [f"**Error** ({self.category})"]
        if self.status_code:
            parts[0] += f" [{self.status_code}]"
        parts.append(f"\n{self.message}")
        parts.append(f"\n**Suggestion:** {self.suggestion}")
        return '\n'.join(parts)

    def to_dict(self) -> dict:
        """Serialize for JSON logging."""
        return {
            'timestamp': self.timestamp,
            'tool_name': self.tool_name,
            'status_code': self.status_code,
            'message': self.message,
            'category': self.category,
            'suggestion': self.suggestion,
        }


def classify_error(tool_name: str, exception: Exception) -> ConfluenceError:
    """Map an exception to a structured ConfluenceError with actionable suggestion."""

    if isinstance(exception, requests.exceptions.HTTPError):
        response = exception.response
        status = response.status_code if response is not None else None
        body = ''
        try:
            body = response.text[:500] if response is not None else ''
        except Exception:
            pass

        if status == 401:
            return ConfluenceError(
                tool_name, status,
                f"Authentication failed: {body}",
                'auth',
                'Your API token may have expired. Regenerate it in Confluence and update ~/.config/atlassian/.env'
            )
        elif status == 403:
            return ConfluenceError(
                tool_name, status,
                f"Permission denied: {body}",
                'permission',
                'You lack permissions for this operation. Contact your Confluence admin to grant access.'
            )
        elif status == 404:
            return ConfluenceError(
                tool_name, status,
                f"Resource not found: {body}",
                'not_found',
                'Verify the page ID, space key, or URL is correct and that the content exists.'
            )
        elif status == 409:
            return ConfluenceError(
                tool_name, status,
                f"Conflict: {body}",
                'conflict',
                'The page was modified by another user. Reload and retry with the latest version number.'
            )
        elif status and 500 <= status < 600:
            return ConfluenceError(
                tool_name, status,
                f"Server error: {body}",
                'server',
                'Confluence server is having a temporary issue. Wait a moment and retry.'
            )
        else:
            return ConfluenceError(
                tool_name, status,
                f"HTTP error: {body}",
                'http',
                'Check the Confluence server status and your request parameters.'
            )

    elif isinstance(exception, requests.exceptions.ConnectionError):
        return ConfluenceError(
            tool_name, None,
            f"Connection failed: {exception}",
            'network',
            'Cannot reach the Confluence server. Check CONFLUENCE_URL in your config and your network connection.'
        )

    elif isinstance(exception, requests.exceptions.Timeout):
        return ConfluenceError(
            tool_name, None,
            f"Request timed out: {exception}",
            'network',
            'The request timed out. The server may be overloaded; try again later.'
        )

    else:
        return ConfluenceError(
            tool_name, None,
            str(exception),
            'unknown',
            'An unexpected error occurred. Check the error log for details.'
        )


def log_error(error: ConfluenceError) -> None:
    """Append error to daily JSON Lines log file."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        log_path = os.path.join(LOG_DIR, f'error-log-{date_str}.json')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error.to_dict()) + '\n')
    except Exception:
        pass  # Never let logging break the main flow


def cleanup_old_logs(max_age_days: int = 30) -> None:
    """Remove log files older than max_age_days. Safe to call on startup."""
    try:
        if not os.path.isdir(LOG_DIR):
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        for entry in os.scandir(LOG_DIR):
            if entry.is_file() and entry.name.startswith('error-log-') and entry.name.endswith('.json'):
                # Extract date from filename: error-log-YYYY-MM-DD.json
                date_part = entry.name[len('error-log-'):-len('.json')]
                try:
                    file_date = datetime.strptime(date_part, '%Y-%m-%d')
                    if file_date < cutoff:
                        os.remove(entry.path)
                except ValueError:
                    pass
    except Exception:
        pass  # Never let cleanup break startup
