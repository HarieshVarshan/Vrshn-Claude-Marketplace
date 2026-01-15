"""
Atlassian API clients for Jira, Confluence, and Bitbucket.
Supports TI internal instances with Bearer/Basic token authentication.
"""

import os
import re
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv


class AtlassianConfig:
    """Configuration loader for Atlassian credentials."""

    def __init__(self, config_path: Optional[str] = None):
        config_path = config_path or os.environ.get(
            'ATLASSIAN_CONFIG',
            os.path.expanduser('~/.config/atlassian/.env')
        )
        if os.path.exists(config_path):
            load_dotenv(config_path)

        # Jira config
        self.jira_url = os.environ.get('JIRA_URL', '').rstrip('/')
        self.jira_username = os.environ.get('JIRA_USERNAME', '')
        self.jira_token = os.environ.get('JIRA_TOKEN', '')

        # Confluence config
        self.confluence_url = os.environ.get('CONFLUENCE_URL', '').rstrip('/')
        self.confluence_username = os.environ.get('CONFLUENCE_USERNAME', '')
        self.confluence_token = os.environ.get('CONFLUENCE_TOKEN', '')

        # Bitbucket config
        self.bitbucket_url = os.environ.get('BITBUCKET_URL', '').rstrip('/')
        self.bitbucket_username = os.environ.get('BITBUCKET_USERNAME', '')
        self.bitbucket_token = os.environ.get('BITBUCKET_TOKEN', '')

        # Proxy config (optional)
        self.http_proxy = os.environ.get('HTTP_PROXY', '')
        self.https_proxy = os.environ.get('HTTPS_PROXY', '')
        self.no_proxy = os.environ.get('NO_PROXY', 'localhost,127.0.0.1')

        # SSL verification (can be disabled for internal certs)
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
                # Domain suffix match (e.g., .ti.com)
                if hostname.endswith(no_proxy) or hostname == no_proxy[1:]:
                    return True
            elif hostname == no_proxy or hostname.endswith('.' + no_proxy):
                return True
        return False


class JiraClient:
    """Client for Jira REST API v2."""

    def __init__(self, config: AtlassianConfig):
        self.base_url = config.jira_url
        self.token = config.jira_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.session.verify = config.verify_ssl
        # Only set proxies if URL should not bypass proxy
        if not config.should_bypass_proxy(self.base_url):
            proxies = config.get_proxies()
            if proxies:
                self.session.proxies.update(proxies)

    def _parse_issue_key(self, issue_key_or_url: str) -> str:
        """Extract issue key from URL or return as-is."""
        # Handle URLs like https://jira.itg.ti.com/browse/PROJ-123
        if '/' in issue_key_or_url:
            match = re.search(r'/browse/([A-Z]+-\d+)', issue_key_or_url)
            if match:
                return match.group(1)
            # Try to get last path segment
            return issue_key_or_url.rstrip('/').split('/')[-1]
        return issue_key_or_url

    def get_issue(self, issue_key_or_url: str, expand: str = "renderedFields,comments") -> Dict[str, Any]:
        """Get a Jira issue by key or URL."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {'expand': expand}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def search_issues(self, jql: str, max_results: int = 50, fields: str = "summary,status,assignee,priority,created,updated") -> Dict[str, Any]:
        """Search for issues using JQL."""
        url = f"{self.base_url}/rest/api/2/search"
        payload = {
            'jql': jql,
            'maxResults': max_results,
            'fields': fields.split(',')
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def create_issue(self, project_key: str, summary: str, issue_type: str = "Task",
                     description: str = "", priority: str = None,
                     assignee: str = None, labels: List[str] = None) -> Dict[str, Any]:
        """Create a new Jira issue."""
        url = f"{self.base_url}/rest/api/2/issue"
        fields = {
            'project': {'key': project_key},
            'summary': summary,
            'issuetype': {'name': issue_type},
            'description': description
        }
        if priority:
            fields['priority'] = {'name': priority}
        if assignee:
            fields['assignee'] = {'name': assignee}
        if labels:
            fields['labels'] = labels

        response = self.session.post(url, json={'fields': fields})
        response.raise_for_status()
        return response.json()

    def add_comment(self, issue_key_or_url: str, comment: str) -> Dict[str, Any]:
        """Add a comment to an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/comment"
        response = self.session.post(url, json={'body': comment})
        response.raise_for_status()
        return response.json()

    def update_issue(self, issue_key_or_url: str, fields: Dict[str, Any]) -> None:
        """Update an issue's fields."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        response = self.session.put(url, json={'fields': fields})
        response.raise_for_status()

    def transition_issue(self, issue_key_or_url: str, transition_name: str) -> None:
        """Transition an issue to a new status."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        # First get available transitions
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/transitions"
        response = self.session.get(url)
        response.raise_for_status()
        transitions = response.json().get('transitions', [])

        # Find matching transition
        transition_id = None
        for t in transitions:
            if t['name'].lower() == transition_name.lower():
                transition_id = t['id']
                break

        if not transition_id:
            available = [t['name'] for t in transitions]
            raise ValueError(f"Transition '{transition_name}' not found. Available: {available}")

        # Execute transition
        response = self.session.post(url, json={'transition': {'id': transition_id}})
        response.raise_for_status()

    def get_transitions(self, issue_key_or_url: str) -> List[Dict[str, Any]]:
        """Get available transitions for an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/transitions"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('transitions', [])


class ConfluenceClient:
    """Client for Confluence REST API."""

    def __init__(self, config: AtlassianConfig):
        self.base_url = config.confluence_url
        self.token = config.confluence_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.session.verify = config.verify_ssl
        # Only set proxies if URL should not bypass proxy
        if not config.should_bypass_proxy(self.base_url):
            proxies = config.get_proxies()
            if proxies:
                self.session.proxies.update(proxies)

    def _parse_page_id(self, page_id_or_url: str) -> str:
        """Extract page ID from URL or return as-is."""
        # Handle URLs like https://confluence.itg.ti.com/pages/viewpage.action?pageId=123456
        if 'pageId=' in page_id_or_url:
            match = re.search(r'pageId=(\d+)', page_id_or_url)
            if match:
                return match.group(1)
        # Handle /display/SPACE/Page+Title URLs - need to resolve via API
        if '/display/' in page_id_or_url:
            match = re.search(r'/display/([^/]+)/(.+)', page_id_or_url)
            if match:
                space_key = match.group(1)
                title = match.group(2).replace('+', ' ').replace('%20', ' ')
                page = self.get_page_by_title(space_key, title)
                if page and 'results' in page and page['results']:
                    return page['results'][0]['id']
        # If it's just digits, return as-is
        if page_id_or_url.isdigit():
            return page_id_or_url
        return page_id_or_url

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

    def get_page_children(self, page_id_or_url: str, limit: int = 25) -> Dict[str, Any]:
        """Get child pages of a page."""
        page_id = self._parse_page_id(page_id_or_url)
        url = f"{self.base_url}/rest/api/content/{page_id}/child/page"
        params = {'limit': limit, 'expand': 'version'}
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


class BitbucketClient:
    """Client for Bitbucket Server REST API v1.0."""

    def __init__(self, config: AtlassianConfig):
        self.base_url = config.bitbucket_url
        self.username = config.bitbucket_username
        self.token = config.bitbucket_token
        self.session = requests.Session()
        # Bitbucket Server uses Basic auth with username:token
        self.session.auth = (self.username, self.token)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.session.verify = config.verify_ssl
        # Only set proxies if URL should not bypass proxy
        if not config.should_bypass_proxy(self.base_url):
            proxies = config.get_proxies()
            if proxies:
                self.session.proxies.update(proxies)

    def _parse_pr_url(self, url_or_parts: str) -> tuple:
        """Parse PR URL to extract project, repo, and PR ID."""
        # Handle URLs like https://bitbucket.itg.ti.com/projects/PROJ/repos/repo-name/pull-requests/123
        if '/pull-requests/' in url_or_parts:
            match = re.search(r'/projects/([^/]+)/repos/([^/]+)/pull-requests/(\d+)', url_or_parts)
            if match:
                return match.group(1), match.group(2), match.group(3)
        return None, None, None

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

    def get_pr_diff(self, project: str, repo: str, pr_id: int, context_lines: int = 10) -> str:
        """Get the diff for a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/diff"
        params = {'contextLines': context_lines}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_pr_comments(self, project: str, repo: str, pr_id: int) -> Dict[str, Any]:
        """Get comments on a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/activities"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def list_pull_requests(self, project: str, repo: str, state: str = "OPEN",
                           limit: int = 25) -> Dict[str, Any]:
        """List pull requests for a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests"
        params = {'state': state, 'limit': limit}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def add_pr_comment(self, project: str, repo: str, pr_id: int, comment: str,
                       file_path: str = None, line: int = None) -> Dict[str, Any]:
        """Add a comment to a pull request (general or inline)."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/comments"
        payload = {'text': comment}
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

    def get_repo_branches(self, project: str, repo: str, filter_text: str = None,
                          limit: int = 25) -> Dict[str, Any]:
        """Get branches in a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/branches"
        params = {'limit': limit}
        if filter_text:
            params['filterText'] = filter_text
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

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


# Singleton instances
_config = None
_jira_client = None
_confluence_client = None
_bitbucket_client = None


def get_config() -> AtlassianConfig:
    """Get or create the global config."""
    global _config
    if _config is None:
        _config = AtlassianConfig()
    return _config


def get_jira_client() -> JiraClient:
    """Get or create the Jira client."""
    global _jira_client
    if _jira_client is None:
        _jira_client = JiraClient(get_config())
    return _jira_client


def get_confluence_client() -> ConfluenceClient:
    """Get or create the Confluence client."""
    global _confluence_client
    if _confluence_client is None:
        _confluence_client = ConfluenceClient(get_config())
    return _confluence_client


def get_bitbucket_client() -> BitbucketClient:
    """Get or create the Bitbucket client."""
    global _bitbucket_client
    if _bitbucket_client is None:
        _bitbucket_client = BitbucketClient(get_config())
    return _bitbucket_client
