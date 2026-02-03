"""
Confluence API client for Confluence Data Center/Server.
Supports Bearer/Basic token authentication.
"""

import os
import re
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv


class ConfluenceConfig:
    """Configuration loader for Confluence credentials."""

    def __init__(self, config_path: Optional[str] = None):
        # Primary: common atlassian config
        atlassian_config = os.path.expanduser('~/.config/atlassian/.env')
        # Override: service-specific config (optional)
        service_config = config_path or os.environ.get(
            'CONFLUENCE_CONFIG',
            os.path.expanduser('~/.config/confluence-mcp/.env')
        )

        # Load atlassian config first, then override with service-specific if exists
        if os.path.exists(atlassian_config):
            load_dotenv(atlassian_config)
        if os.path.exists(service_config):
            load_dotenv(service_config, override=True)

        # Confluence config
        self.confluence_url = os.environ.get('CONFLUENCE_URL', '').rstrip('/')
        self.confluence_username = os.environ.get('CONFLUENCE_USERNAME', '')
        self.confluence_token = os.environ.get('CONFLUENCE_TOKEN', '')

        # Proxy config (optional)
        self.http_proxy = os.environ.get('HTTP_PROXY', '')
        self.https_proxy = os.environ.get('HTTPS_PROXY', '')
        self.no_proxy = os.environ.get('NO_PROXY', 'localhost,127.0.0.1')

        # SSL verification
        self.verify_ssl = os.environ.get('VERIFY_SSL', 'true').lower() != 'false'

    def get_proxies(self) -> Optional[Dict[str, str]]:
        """Get proxy configuration if set."""
        if self.http_proxy or self.https_proxy:
            return {
                'http': self.http_proxy,
                'https': self.https_proxy
            }
        return None

    def should_bypass_proxy(self, url: str) -> bool:
        """Check if URL should bypass proxy based on NO_PROXY."""
        from urllib.parse import urlparse
        if not self.no_proxy:
            return False
        hostname = urlparse(url).hostname or ''
        no_proxy_list = [x.strip() for x in self.no_proxy.split(',')]
        for no_proxy in no_proxy_list:
            if no_proxy.startswith('.'):
                if hostname.endswith(no_proxy) or hostname == no_proxy[1:]:
                    return True
            elif hostname == no_proxy or hostname.endswith('.' + no_proxy):
                return True
        return False


class ConfluenceClient:
    """Client for Confluence REST API."""

    def __init__(self, config: ConfluenceConfig):
        self.base_url = config.confluence_url
        self.token = config.confluence_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.session.verify = config.verify_ssl
        if not config.should_bypass_proxy(self.base_url):
            proxies = config.get_proxies()
            if proxies:
                self.session.proxies.update(proxies)

    def _parse_page_id(self, page_id_or_url: str) -> str:
        """Extract page ID from URL or return as-is."""
        if 'pageId=' in page_id_or_url:
            match = re.search(r'pageId=(\d+)', page_id_or_url)
            if match:
                return match.group(1)
        if '/display/' in page_id_or_url:
            match = re.search(r'/display/([^/]+)/(.+)', page_id_or_url)
            if match:
                space_key = match.group(1)
                title = match.group(2).replace('+', ' ').replace('%20', ' ')
                page = self.get_page_by_title(space_key, title)
                if page and 'results' in page and page['results']:
                    return page['results'][0]['id']
        if page_id_or_url.isdigit():
            return page_id_or_url
        return page_id_or_url

    # ==================== Pages ====================

    def get_page(self, page_id_or_url: str, expand: str = "body.storage,body.view,version,space") -> Dict[str, Any]:
        """Get a Confluence page by ID or URL."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}"
        params = {'expand': expand}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_page_by_title(self, space_key: str, title: str) -> Dict[str, Any]:
        """Get a page by space key and title."""
        url = f"{self.base_url}/rest/api/content"
        params = {
            'spaceKey': space_key,
            'title': title,
            'expand': 'body.storage,version,space'
        }
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def create_page(self, space_key: str, title: str, content: str,
                    parent_id: str = None) -> Dict[str, Any]:
        """Create a new Confluence page."""
        url = f"{self.base_url}/rest/api/content"
        payload: Dict[str, Any] = {
            'type': 'page',
            'title': title,
            'space': {'key': space_key},
            'body': {
                'storage': {
                    'value': content,
                    'representation': 'storage'
                }
            }
        }
        if parent_id:
            payload['ancestors'] = [{'id': parent_id}]

        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def update_page(self, page_id: str, title: str, content: str,
                    version_number: int = None) -> Dict[str, Any]:
        """Update an existing Confluence page."""
        if version_number is None:
            current_page = self.get_page(page_id)
            version_number = current_page.get('version', {}).get('number', 1)

        url = f"{self.base_url}/rest/api/content/{page_id}"
        payload = {
            'type': 'page',
            'title': title,
            'body': {
                'storage': {
                    'value': content,
                    'representation': 'storage'
                }
            },
            'version': {
                'number': version_number + 1
            }
        }

        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def delete_page(self, page_id_or_url: str) -> None:
        """Delete a Confluence page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}"
        response = self.session.delete(url)
        response.raise_for_status()

    def get_page_children(self, page_id_or_url: str, limit: int = 25) -> Dict[str, Any]:
        """Get child pages of a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/child/page"
        params = {'limit': limit, 'expand': 'version'}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_page_ancestors(self, page_id_or_url: str) -> List[Dict[str, Any]]:
        """Get ancestors (parent hierarchy) of a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}"
        params = {'expand': 'ancestors'}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('ancestors', [])

    # ==================== Search ====================

    def search_pages(self, cql: str, limit: int = 25) -> Dict[str, Any]:
        """Search pages using CQL (Confluence Query Language)."""
        url = f"{self.base_url}/rest/api/content/search"
        params = {
            'cql': cql,
            'limit': limit,
            'expand': 'space,version'
        }
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def search_content(self, query: str, space_key: str = None, limit: int = 25) -> Dict[str, Any]:
        """Search content using simple text query."""
        cql = f'text ~ "{query}"'
        if space_key:
            cql += f' AND space = "{space_key}"'
        return self.search_pages(cql, limit)

    # ==================== Spaces ====================

    def get_all_spaces(self, limit: int = 50) -> Dict[str, Any]:
        """Get all spaces."""
        url = f"{self.base_url}/rest/api/space"
        params = {'limit': limit, 'expand': 'description.plain'}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_space(self, space_key: str) -> Dict[str, Any]:
        """Get space details."""
        url = f"{self.base_url}/rest/api/space/{space_key}"
        params = {'expand': 'description.plain,homepage'}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_space_pages(self, space_key: str, limit: int = 50) -> Dict[str, Any]:
        """Get all pages in a space."""
        url = f"{self.base_url}/rest/api/content"
        params = {
            'spaceKey': space_key,
            'type': 'page',
            'limit': limit,
            'expand': 'version'
        }
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Comments ====================

    def add_comment(self, page_id: str, comment: str) -> Dict[str, Any]:
        """Add a comment to a Confluence page."""
        url = f"{self.base_url}/rest/api/content"
        payload = {
            'type': 'comment',
            'container': {'id': page_id, 'type': 'page'},
            'body': {
                'storage': {
                    'value': comment,
                    'representation': 'storage'
                }
            }
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_page_comments(self, page_id_or_url: str, limit: int = 25) -> Dict[str, Any]:
        """Get comments for a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/child/comment"
        params = {'limit': limit, 'expand': 'body.storage'}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Labels ====================

    def get_page_labels(self, page_id_or_url: str) -> List[Dict[str, Any]]:
        """Get labels for a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/label"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('results', [])

    def add_page_label(self, page_id_or_url: str, label: str) -> Dict[str, Any]:
        """Add a label to a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/label"
        payload = [{'name': label}]
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def remove_page_label(self, page_id_or_url: str, label: str) -> None:
        """Remove a label from a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/label/{label}"
        response = self.session.delete(url)
        response.raise_for_status()

    # ==================== Attachments ====================

    def get_page_attachments(self, page_id_or_url: str, limit: int = 25) -> Dict[str, Any]:
        """Get attachments for a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/child/attachment"
        params = {'limit': limit}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== History ====================

    def get_page_history(self, page_id_or_url: str) -> Dict[str, Any]:
        """Get page version history."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/history"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def list_page_versions(self, page_id_or_url: str, limit: int = 25) -> Dict[str, Any]:
        """List all versions of a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/version"
        params = {'limit': limit, 'expand': 'content'}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_page_version(self, page_id_or_url: str, version_number: int) -> Dict[str, Any]:
        """Get a specific version of a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/version/{version_number}"
        params = {'expand': 'content.body.storage'}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Page Operations ====================

    def move_page(self, page_id_or_url: str, target_space_key: str = None,
                  target_parent_id: str = None) -> Dict[str, Any]:
        """Move a page to a different location or space."""
        page_id = self._parse_page_id(page_id_or_url)
        current_page = self.get_page(page_id)
        current_version = current_page.get('version', {}).get('number', 1)

        url = f"{self.base_url}/rest/api/content/{page_id}"
        payload: Dict[str, Any] = {
            'type': 'page',
            'title': current_page.get('title'),
            'version': {'number': current_version + 1}
        }

        if target_space_key:
            payload['space'] = {'key': target_space_key}

        if target_parent_id:
            payload['ancestors'] = [{'id': target_parent_id}]

        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def copy_page(self, page_id_or_url: str, destination_space_key: str = None,
                  destination_parent_id: str = None, new_title: str = None,
                  copy_labels: bool = True, copy_attachments: bool = False) -> Dict[str, Any]:
        """Copy a page to a new location."""
        page_id = self._parse_page_id(page_id_or_url)
        source_page = self.get_page(page_id)

        space_key = destination_space_key or source_page.get('space', {}).get('key')
        title = new_title or f"Copy of {source_page.get('title')}"
        content = source_page.get('body', {}).get('storage', {}).get('value', '')

        # Create the copy
        new_page = self.create_page(space_key, title, content, destination_parent_id)

        # Copy labels if requested
        if copy_labels:
            labels = self.get_page_labels(page_id)
            for label in labels:
                try:
                    self.add_page_label(new_page['id'], label.get('name'))
                except Exception:
                    pass  # Ignore label copy failures

        return new_page

    def get_page_descendants(self, page_id_or_url: str, limit: int = 100) -> Dict[str, Any]:
        """Get all descendant pages (recursive children)."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/descendant/page"
        params = {'limit': limit, 'expand': 'version'}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Space Management ====================

    def create_space(self, space_key: str, name: str, description: str = None) -> Dict[str, Any]:
        """Create a new space."""
        url = f"{self.base_url}/rest/api/space"
        payload: Dict[str, Any] = {
            'key': space_key,
            'name': name
        }
        if description:
            payload['description'] = {
                'plain': {'value': description, 'representation': 'plain'}
            }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def update_space(self, space_key: str, name: str = None, description: str = None) -> Dict[str, Any]:
        """Update a space's name or description."""
        url = f"{self.base_url}/rest/api/space/{space_key}"
        payload: Dict[str, Any] = {}
        if name:
            payload['name'] = name
        if description:
            payload['description'] = {
                'plain': {'value': description, 'representation': 'plain'}
            }
        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def delete_space(self, space_key: str) -> None:
        """Delete a space."""
        url = f"{self.base_url}/rest/api/space/{space_key}"
        response = self.session.delete(url)
        response.raise_for_status()

    # ==================== Attachment Management ====================

    def get_attachment(self, attachment_id: str) -> Dict[str, Any]:
        """Get attachment metadata."""
        url = f"{self.base_url}/rest/api/content/{attachment_id}"
        params = {'expand': 'version,container'}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def upload_attachment(self, page_id_or_url: str, file_path: str,
                          comment: str = None) -> Dict[str, Any]:
        """Upload an attachment to a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/child/attachment"

        # Need to use multipart/form-data for file upload
        headers = {
            'X-Atlassian-Token': 'nocheck',
            'Authorization': f'Bearer {self.token}'
        }

        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {}
            if comment:
                data['comment'] = comment

            # Remove Content-Type header for multipart
            session_headers = dict(self.session.headers)
            session_headers.pop('Content-Type', None)
            session_headers.update(headers)

            response = requests.post(url, files=files, data=data,
                                     headers=session_headers,
                                     verify=self.session.verify)

        response.raise_for_status()
        return response.json()

    def download_attachment(self, attachment_id: str, download_path: str) -> str:
        """Download an attachment to local filesystem."""
        attachment = self.get_attachment(attachment_id)
        download_url = attachment.get('_links', {}).get('download', '')

        if not download_url:
            raise ValueError("No download URL found for attachment")

        full_url = f"{self.base_url}{download_url}"
        response = self.session.get(full_url, stream=True)
        response.raise_for_status()

        with open(download_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return download_path

    def delete_attachment(self, attachment_id: str) -> None:
        """Delete an attachment."""
        url = f"{self.base_url}/rest/api/content/{attachment_id}"
        response = self.session.delete(url)
        response.raise_for_status()

    # ==================== Page Restrictions ====================

    def get_page_restrictions(self, page_id_or_url: str) -> Dict[str, Any]:
        """Get view/edit restrictions for a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/restriction"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def set_page_restrictions(self, page_id_or_url: str, operation: str,
                               users: List[str] = None,
                               groups: List[str] = None) -> Dict[str, Any]:
        """Set view/edit restrictions for a page.

        Args:
            page_id_or_url: Page ID or URL
            operation: 'read' for view restrictions, 'update' for edit restrictions
            users: List of usernames to grant access
            groups: List of group names to grant access
        """
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/restriction"

        restrictions = []
        if users:
            for user in users:
                restrictions.append({
                    'operation': operation,
                    'restrictions': {
                        'user': [{'type': 'known', 'username': user}]
                    }
                })
        if groups:
            for group in groups:
                restrictions.append({
                    'operation': operation,
                    'restrictions': {
                        'group': [{'type': 'group', 'name': group}]
                    }
                })

        response = self.session.put(url, json=restrictions)
        response.raise_for_status()
        return response.json()

    def remove_page_restrictions(self, page_id_or_url: str) -> None:
        """Remove all restrictions from a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/restriction"
        response = self.session.delete(url)
        response.raise_for_status()

    # ==================== Users ====================

    def search_users(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search for Confluence users."""
        url = f"{self.base_url}/rest/api/search/user"
        params = {'cql': f'user.fullname ~ "{query}" OR user.username ~ "{query}"', 'limit': limit}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('results', [])

    def get_current_user(self) -> Dict[str, Any]:
        """Get the currently authenticated user."""
        url = f"{self.base_url}/rest/api/user/current"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ==================== Raw API ====================

    def raw_api(self, method: str, endpoint: str,
                body: Dict[str, Any] = None,
                params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make a raw API call to Confluence.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/rest/api/content/123456')
            body: Request body for POST/PUT requests
            params: Query parameters

        Returns:
            Response JSON or {'status': 'success'} for no-content responses
        """
        url = f"{self.base_url}{endpoint}"
        method = method.upper()

        if method == 'GET':
            response = self.session.get(url, params=params)
        elif method == 'POST':
            response = self.session.post(url, json=body, params=params)
        elif method == 'PUT':
            response = self.session.put(url, json=body, params=params)
        elif method == 'DELETE':
            response = self.session.delete(url, params=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()

        if response.status_code == 204 or not response.content:
            return {'status': 'success', 'status_code': response.status_code}

        try:
            return response.json()
        except ValueError:
            return {'status': 'success', 'content': response.text}


# Singleton instances
_config: Optional[ConfluenceConfig] = None
_client: Optional[ConfluenceClient] = None


def get_config() -> ConfluenceConfig:
    """Get or create the global config."""
    global _config
    if _config is None:
        _config = ConfluenceConfig()
    return _config


def get_confluence_client() -> ConfluenceClient:
    """Get or create the Confluence client."""
    global _client
    if _client is None:
        _client = ConfluenceClient(get_config())
    return _client
