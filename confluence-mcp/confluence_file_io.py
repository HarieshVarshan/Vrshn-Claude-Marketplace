"""
File I/O helpers for reading/saving Confluence page content to local filesystem.

Supports:
- Reading Markdown content from a file for page creation/updates
- Saving a page as a Markdown file with YAML-like front matter
- Saving a page to a directory structure (index.md + attachments/)
"""

import os
import re
from typing import Optional


def sanitize_filename(name: str) -> str:
    """Clean a string for use as a filename. Replaces unsafe characters with hyphens."""
    name = re.sub(r'[<>:"/\\|?*]', '-', name)
    name = re.sub(r'\s+', '-', name)
    name = re.sub(r'-+', '-', name)
    return name.strip('-')[:200]


def read_content_from_file(file_path: str) -> str:
    """Read content from a local file.

    Args:
        file_path: Path to the file (supports ~ expansion)

    Returns:
        File contents as a string

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file is not readable
    """
    expanded = os.path.expanduser(file_path)
    resolved = os.path.abspath(expanded)
    with open(resolved, 'r', encoding='utf-8') as f:
        return f.read()


def save_page_to_file(file_path: str, title: str, markdown_content: str,
                       metadata: Optional[dict] = None) -> str:
    """Save page content as a Markdown file with front matter.

    Args:
        file_path: Destination file path (supports ~ expansion)
        title: Page title
        markdown_content: Page content in Markdown format
        metadata: Optional dict with page_id, space, version, url

    Returns:
        Absolute path of the saved file
    """
    expanded = os.path.expanduser(file_path)
    resolved = os.path.abspath(expanded)

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(resolved), exist_ok=True)

    lines = []
    lines.append('---')
    lines.append(f'title: "{title}"')
    if metadata:
        if metadata.get('page_id'):
            lines.append(f'page_id: "{metadata["page_id"]}"')
        if metadata.get('space'):
            lines.append(f'space: "{metadata["space"]}"')
        if metadata.get('version'):
            lines.append(f'version: {metadata["version"]}')
        if metadata.get('url'):
            lines.append(f'url: "{metadata["url"]}"')
        if metadata.get('last_modified'):
            lines.append(f'last_modified: "{metadata["last_modified"]}"')
    lines.append('---')
    lines.append('')
    lines.append(markdown_content)

    with open(resolved, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return resolved


def save_page_to_directory(dir_path: str, title: str, markdown_content: str,
                            metadata: Optional[dict] = None) -> str:
    """Save page content as index.md in a directory, with attachments/ subdir.

    Args:
        dir_path: Destination directory path (supports ~ expansion)
        title: Page title (used for directory name if dir_path is a parent)
        markdown_content: Page content in Markdown format
        metadata: Optional dict with page_id, space, version, url

    Returns:
        Absolute path of the saved index.md file
    """
    expanded = os.path.expanduser(dir_path)
    resolved = os.path.abspath(expanded)

    # Create directory structure
    os.makedirs(resolved, exist_ok=True)
    os.makedirs(os.path.join(resolved, 'attachments'), exist_ok=True)

    # Save content as index.md
    index_path = os.path.join(resolved, 'index.md')
    return save_page_to_file(index_path, title, markdown_content, metadata)
