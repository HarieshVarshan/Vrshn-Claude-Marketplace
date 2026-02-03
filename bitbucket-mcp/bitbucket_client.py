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

    def create_pr(self, project: str, repo: str, title: str, from_branch: str,
                  to_branch: str, description: str = None,
                  reviewers: List[str] = None) -> Dict[str, Any]:
        """Create a new pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests"
        payload: Dict[str, Any] = {
            'title': title,
            'fromRef': {'id': f'refs/heads/{from_branch}'},
            'toRef': {'id': f'refs/heads/{to_branch}'}
        }
        if description:
            payload['description'] = description
        if reviewers:
            payload['reviewers'] = [{'user': {'name': r}} for r in reviewers]
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def update_pr(self, project: str, repo: str, pr_id: int, title: str = None,
                  description: str = None, version: int = None) -> Dict[str, Any]:
        """Update a pull request title/description."""
        # First get current PR to get version
        if version is None:
            current = self.get_pull_request(project, repo, pr_id)
            version = current.get('version', 0)

        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}"
        payload: Dict[str, Any] = {'version': version}
        if title:
            payload['title'] = title
        if description is not None:
            payload['description'] = description
        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def reopen_pr(self, project: str, repo: str, pr_id: int, version: int = None) -> Dict[str, Any]:
        """Reopen a declined pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/reopen"
        params = {}
        if version is not None:
            params['version'] = version
        response = self.session.post(url, params=params)
        response.raise_for_status()
        return response.json()

    def add_pr_reviewer(self, project: str, repo: str, pr_id: int, username: str) -> Dict[str, Any]:
        """Add a reviewer to a pull request."""
        # Get current PR state
        current = self.get_pull_request(project, repo, pr_id)
        version = current.get('version', 0)
        reviewers = current.get('reviewers', [])
        reviewers.append({'user': {'name': username}})

        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}"
        payload = {
            'version': version,
            'reviewers': reviewers
        }
        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def remove_pr_reviewer(self, project: str, repo: str, pr_id: int, username: str) -> Dict[str, Any]:
        """Remove a reviewer from a pull request."""
        # Get current PR state
        current = self.get_pull_request(project, repo, pr_id)
        version = current.get('version', 0)
        reviewers = [r for r in current.get('reviewers', [])
                     if r.get('user', {}).get('name') != username]

        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}"
        payload = {
            'version': version,
            'reviewers': reviewers
        }
        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_pr_tasks(self, project: str, repo: str, pr_id: int) -> Dict[str, Any]:
        """Get tasks on a pull request."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/tasks"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def add_pr_task(self, project: str, repo: str, pr_id: int, comment_id: int,
                    task_text: str) -> Dict[str, Any]:
        """Add a task to a PR comment."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/comments/{comment_id}/tasks"
        payload = {'text': task_text}
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def update_pr_task(self, project: str, repo: str, pr_id: int, task_id: int,
                       state: str) -> Dict[str, Any]:
        """Update task status (OPEN or RESOLVED)."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/tasks/{task_id}"
        payload = {'state': state}
        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_pr_merge_status(self, project: str, repo: str, pr_id: int) -> Dict[str, Any]:
        """Check if PR can be merged."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests/{pr_id}/merge"
        response = self.session.get(url)
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

    def create_repo(self, project: str, name: str, description: str = None,
                    public: bool = False) -> Dict[str, Any]:
        """Create a new repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos"
        payload: Dict[str, Any] = {
            'name': name,
            'public': public
        }
        if description:
            payload['description'] = description
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def delete_repo(self, project: str, repo: str) -> Dict[str, Any]:
        """Delete a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}"
        response = self.session.delete(url)
        response.raise_for_status()
        return {'status': 'deleted', 'repository': repo}

    def fork_repo(self, project: str, repo: str, target_project: str = None,
                  name: str = None) -> Dict[str, Any]:
        """Fork a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}"
        payload: Dict[str, Any] = {}
        if target_project:
            payload['project'] = {'key': target_project}
        if name:
            payload['name'] = name
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_repo_webhooks(self, project: str, repo: str) -> Dict[str, Any]:
        """List repository webhooks."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/webhooks"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def create_webhook(self, project: str, repo: str, name: str, url: str,
                       events: List[str], active: bool = True) -> Dict[str, Any]:
        """Create a repository webhook."""
        api_url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/webhooks"
        payload = {
            'name': name,
            'url': url,
            'events': events,
            'active': active,
            'configuration': {'secret': ''}
        }
        response = self.session.post(api_url, json=payload)
        response.raise_for_status()
        return response.json()

    def delete_webhook(self, project: str, repo: str, webhook_id: int) -> Dict[str, Any]:
        """Delete a repository webhook."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/webhooks/{webhook_id}"
        response = self.session.delete(url)
        response.raise_for_status()
        return {'status': 'deleted', 'webhook_id': webhook_id}

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

    def create_branch(self, project: str, repo: str, branch_name: str,
                      start_point: str) -> Dict[str, Any]:
        """Create a new branch."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/branches"
        payload = {
            'name': branch_name,
            'startPoint': start_point
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def delete_branch(self, project: str, repo: str, branch_name: str) -> Dict[str, Any]:
        """Delete a branch."""
        url = f"{self.base_url}/rest/branch-utils/1.0/projects/{project}/repos/{repo}/branches"
        payload = {'name': f'refs/heads/{branch_name}'}
        response = self.session.delete(url, json=payload)
        response.raise_for_status()
        return {'status': 'deleted', 'branch': branch_name}

    def set_default_branch(self, project: str, repo: str, branch_name: str) -> Dict[str, Any]:
        """Set the default branch of a repository."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/branches/default"
        payload = {'id': f'refs/heads/{branch_name}'}
        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return {'status': 'updated', 'default_branch': branch_name}

    def compare_branches(self, project: str, repo: str, from_branch: str,
                         to_branch: str, limit: int = 25) -> Dict[str, Any]:
        """Compare two branches (get commits between them)."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/compare/commits"
        params = {
            'from': from_branch,
            'to': to_branch,
            'limit': limit
        }
        response = self.session.get(url, params=params)
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

    def create_tag(self, project: str, repo: str, tag_name: str,
                   start_point: str, message: str = None) -> Dict[str, Any]:
        """Create a new tag."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/tags"
        payload: Dict[str, Any] = {
            'name': tag_name,
            'startPoint': start_point
        }
        if message:
            payload['message'] = message
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def delete_tag(self, project: str, repo: str, tag_name: str) -> Dict[str, Any]:
        """Delete a tag."""
        url = f"{self.base_url}/rest/git/1.0/projects/{project}/repos/{repo}/tags/{tag_name}"
        response = self.session.delete(url)
        response.raise_for_status()
        return {'status': 'deleted', 'tag': tag_name}

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

    def create_project(self, key: str, name: str, description: str = None) -> Dict[str, Any]:
        """Create a new project."""
        url = f"{self.base_url}/rest/api/1.0/projects"
        payload: Dict[str, Any] = {
            'key': key,
            'name': name
        }
        if description:
            payload['description'] = description
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def update_project(self, project_key: str, name: str = None,
                       description: str = None) -> Dict[str, Any]:
        """Update project details."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project_key}"
        payload: Dict[str, Any] = {}
        if name:
            payload['name'] = name
        if description is not None:
            payload['description'] = description
        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def delete_project(self, project_key: str) -> Dict[str, Any]:
        """Delete a project."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project_key}"
        response = self.session.delete(url)
        response.raise_for_status()
        return {'status': 'deleted', 'project': project_key}

    # ==================== Build Status ====================

    def get_commit_build_status(self, commit_id: str) -> Dict[str, Any]:
        """Get CI build status for a commit."""
        url = f"{self.base_url}/rest/build-status/1.0/commits/{commit_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def set_commit_build_status(self, commit_id: str, state: str, key: str,
                                 url: str, name: str = None,
                                 description: str = None) -> Dict[str, Any]:
        """Set build status for a commit."""
        api_url = f"{self.base_url}/rest/build-status/1.0/commits/{commit_id}"
        payload: Dict[str, Any] = {
            'state': state,  # SUCCESSFUL, FAILED, INPROGRESS
            'key': key,
            'url': url
        }
        if name:
            payload['name'] = name
        if description:
            payload['description'] = description
        response = self.session.post(api_url, json=payload)
        response.raise_for_status()
        return {'status': 'updated', 'commit': commit_id, 'state': state}

    # ==================== Permissions ====================

    def get_repo_permissions(self, project: str, repo: str) -> Dict[str, Any]:
        """Get repository user/group permissions."""
        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/permissions/users"
        users_response = self.session.get(url)
        users_response.raise_for_status()

        url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/permissions/groups"
        groups_response = self.session.get(url)
        groups_response.raise_for_status()

        return {
            'users': users_response.json().get('values', []),
            'groups': groups_response.json().get('values', [])
        }

    def grant_repo_permission(self, project: str, repo: str, permission: str,
                               user: str = None, group: str = None) -> Dict[str, Any]:
        """Grant repository access to user or group."""
        if user:
            url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/permissions/users"
            params = {'name': user, 'permission': permission}
        elif group:
            url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/permissions/groups"
            params = {'name': group, 'permission': permission}
        else:
            raise ValueError("Either user or group must be specified")

        response = self.session.put(url, params=params)
        response.raise_for_status()
        return {'status': 'granted', 'permission': permission, 'user': user, 'group': group}

    def revoke_repo_permission(self, project: str, repo: str,
                                user: str = None, group: str = None) -> Dict[str, Any]:
        """Revoke repository access from user or group."""
        if user:
            url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/permissions/users"
            params = {'name': user}
        elif group:
            url = f"{self.base_url}/rest/api/1.0/projects/{project}/repos/{repo}/permissions/groups"
            params = {'name': group}
        else:
            raise ValueError("Either user or group must be specified")

        response = self.session.delete(url, params=params)
        response.raise_for_status()
        return {'status': 'revoked', 'user': user, 'group': group}

    # ==================== Users ====================

    def search_users(self, filter_text: str, limit: int = 25) -> Dict[str, Any]:
        """Search for Bitbucket users."""
        url = f"{self.base_url}/rest/api/1.0/users"
        params = {'filter': filter_text, 'limit': limit}
        response = self.session.get(url, params=params)
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
