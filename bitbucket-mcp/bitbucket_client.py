"""
Bitbucket API client for Bitbucket Server/Data Center.
Supports Basic authentication with username:token.
"""

import os
import re
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv


class BitbucketConfig:
    """Configuration loader for Bitbucket credentials."""

    def __init__(self, config_path: Optional[str] = None):
        # Primary: common atlassian config
        atlassian_config = os.path.expanduser('~/.config/atlassian/.env')
        # Override: service-specific config (optional)
        service_config = config_path or os.environ.get(
            'BITBUCKET_CONFIG',
            os.path.expanduser('~/.config/bitbucket-mcp/.env')
        )

        # Load atlassian config first, then override with service-specific if exists
        if os.path.exists(atlassian_config):
            load_dotenv(atlassian_config)
        if os.path.exists(service_config):
            load_dotenv(service_config, override=True)

        # Bitbucket config
        self.bitbucket_url = os.environ.get('BITBUCKET_URL', '').rstrip('/')
        self.bitbucket_username = os.environ.get('BITBUCKET_USERNAME', '')
        self.bitbucket_token = os.environ.get('BITBUCKET_TOKEN', '')

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


class BitbucketClient:
    """Client for Bitbucket Server REST API v1.0."""

    def __init__(self, config: BitbucketConfig):
        self.base_url = config.bitbucket_url
        self.username = config.bitbucket_username
        self.token = config.bitbucket_token
        self.session = requests.Session()
        self.session.auth = (self.username, self.token)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.session.verify = config.verify_ssl
        if not config.should_bypass_proxy(self.base_url):
            proxies = config.get_proxies()
            if proxies:
                self.session.proxies.update(proxies)

    def _parse_pr_url(self, url_or_parts: str) -> tuple:
        """Parse PR URL to extract project, repo, and PR ID."""
        if '/pull-requests/' in url_or_parts:
            match = re.search(r'/projects/([^/]+)/repos/([^/]+)/pull-requests/(\d+)', url_or_parts)
            if match:
                return match.group(1), match.group(2), match.group(3)
        return None, None, None

    # ==================== Pull Requests ====================

    def get_pull_request(self, project: str, repo: str, pr_id: int) -> Dict[str, Any]:
        """Get a pull request by project, repo, and PR ID."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_pull_request_by_url(self, pr_url: str) -> Dict[str, Any]:
        """Get a pull request by its full URL."""
        project, repo, pr_id = self._parse_pr_url(pr_url)
        if not all([project, repo, pr_id]):
            raise ValueError(f"Could not parse PR URL: {pr_url}")
        return self.get_pull_request(project, repo, int(pr_id))

    def list_pull_requests(self, project: str, repo: str, state: str = "OPEN",
                           limit: int = 25) -> Dict[str, Any]:
        """List pull requests for a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests"
        params = {'state': state, 'limit': limit}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_pr_diff(self, project: str, repo: str, pr_id: int, context_lines: int = 10) -> Dict[str, Any]:
        """Get the diff for a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/diff"
        params = {'contextLines': context_lines}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_pr_commits(self, project: str, repo: str, pr_id: int, limit: int = 25) -> Dict[str, Any]:
        """Get commits in a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/commits"
        params = {'limit': limit}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_pr_activities(self, project: str, repo: str, pr_id: int, limit: int = 25) -> Dict[str, Any]:
        """Get activities/comments on a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/activities"
        params = {'limit': limit}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def add_pr_comment(self, project: str, repo: str, pr_id: int, comment: str,
                       file_path: str = None, line: int = None) -> Dict[str, Any]:
        """Add a comment to a pull request (general or inline)."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/comments"
        payload: Dict[str, Any] = {'text': comment}
        if file_path and line:
            payload['anchor'] = {
                'path': file_path,
                'line': line,
                'lineType': 'ADDED'
            }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def approve_pr(self, project: str, repo: str, pr_id: int) -> Dict[str, Any]:
        """Approve a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/approve"
        response = self.session.post(url)
        response.raise_for_status()
        return response.json()

    def unapprove_pr(self, project: str, repo: str, pr_id: int) -> None:
        """Remove approval from a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/approve"
        response = self.session.delete(url)
        response.raise_for_status()

    def merge_pr(self, project: str, repo: str, pr_id: int, version: int = None) -> Dict[str, Any]:
        """Merge a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/merge"
        params = {}
        if version is not None:
            params['version'] = version
        response = self.session.post(url, params=params)
        response.raise_for_status()
        return response.json()

    def decline_pr(self, project: str, repo: str, pr_id: int, version: int = None) -> Dict[str, Any]:
        """Decline a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/decline"
        params = {}
        if version is not None:
            params['version'] = version
        response = self.session.post(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Repositories ====================

    def get_repos(self, project: str, limit: int = 25) -> Dict[str, Any]:
        """List repositories in a project."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos"
        params = {'limit': limit}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_repo(self, project: str, repo: str) -> Dict[str, Any]:
        """Get repository details."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ==================== Branches ====================

    def get_branches(self, project: str, repo: str, filter_text: str = None,
                     limit: int = 25) -> Dict[str, Any]:
        """Get branches in a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/branches"
        params: Dict[str, Any] = {'limit': limit}
        if filter_text:
            params['filterText'] = filter_text
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_default_branch(self, project: str, repo: str) -> Dict[str, Any]:
        """Get the default branch of a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/branches/default"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ==================== Tags ====================

    def get_tags(self, project: str, repo: str, filter_text: str = None,
                 limit: int = 25) -> Dict[str, Any]:
        """Get tags in a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/tags"
        params: Dict[str, Any] = {'limit': limit}
        if filter_text:
            params['filterText'] = filter_text
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Commits ====================

    def get_commits(self, project: str, repo: str, until: str = None,
                    since: str = None, limit: int = 25) -> Dict[str, Any]:
        """Get commits in a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/commits"
        params: Dict[str, Any] = {'limit': limit}
        if until:
            params['until'] = until
        if since:
            params['since'] = since
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_commit(self, project: str, repo: str, commit_id: str) -> Dict[str, Any]:
        """Get a specific commit."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/commits/{commit_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_commit_diff(self, project: str, repo: str, commit_id: str,
                        context_lines: int = 10) -> Dict[str, Any]:
        """Get diff for a commit."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/commits/{commit_id}/diff"
        params = {'contextLines': context_lines}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Files ====================

    def get_file_content(self, project: str, repo: str, file_path: str,
                         ref: str = None) -> Dict[str, Any]:
        """Get file content from a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/browse/{file_path}"
        params = {}
        if ref:
            params['at'] = ref
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def browse_directory(self, project: str, repo: str, path: str = "",
                         ref: str = None, limit: int = 100) -> Dict[str, Any]:
        """Browse directory contents."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/browse/{path}"
        params: Dict[str, Any] = {'limit': limit}
        if ref:
            params['at'] = ref
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Projects ====================

    def get_all_projects(self, limit: int = 25) -> Dict[str, Any]:
        """List all projects."""
        url = f"{self.base_url}/rest/api/1.0/projects"
        params = {'limit': limit}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_project(self, project_key: str) -> Dict[str, Any]:
        """Get project details."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project_key}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ==================== Raw API ====================

    def raw_api(self, method: str, endpoint: str,
                body: Dict[str, Any] = None,
                params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make a raw API call to Bitbucket.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/rest/api/1.0/projects/PROJ/repos')
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
_config: Optional[BitbucketConfig] = None
_client: Optional[BitbucketClient] = None


def get_config() -> BitbucketConfig:
    """Get or create the global config."""
    global _config
    if _config is None:
        _config = BitbucketConfig()
    return _config


def get_bitbucket_client() -> BitbucketClient:
    """Get or create the Bitbucket client."""
    global _client
    if _client is None:
        _client = BitbucketClient(get_config())
    return _client
