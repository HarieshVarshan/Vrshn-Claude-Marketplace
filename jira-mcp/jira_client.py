"""
Jira API client for Jira Data Center/Server.
Supports Bearer/Basic token authentication.
"""

import os
import re
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv


class JiraConfig:
    """Configuration loader for Jira credentials."""

    def __init__(self, config_path: Optional[str] = None):
        # Primary: common atlassian config
        atlassian_config = os.path.expanduser('~/.config/atlassian/.env')
        # Override: service-specific config (optional)
        service_config = config_path or os.environ.get(
            'JIRA_CONFIG',
            os.path.expanduser('~/.config/jira-mcp/.env')
        )

        # Load atlassian config first, then override with service-specific if exists
        if os.path.exists(atlassian_config):
            load_dotenv(atlassian_config)
        if os.path.exists(service_config):
            load_dotenv(service_config, override=True)

        # Jira config
        self.jira_url = os.environ.get('JIRA_URL', '').rstrip('/')
        self.jira_username = os.environ.get('JIRA_USERNAME', '')
        self.jira_token = os.environ.get('JIRA_TOKEN', '')

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
                if hostname.endswith(no_proxy) or hostname == no_proxy[1:]:
                    return True
            elif hostname == no_proxy or hostname.endswith('.' + no_proxy):
                return True
        return False


class JiraClient:
    """Client for Jira REST API v2."""

    def __init__(self, config: JiraConfig):
        self.base_url = config.jira_url
        self.token = config.jira_token
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

    def _parse_issue_key(self, issue_key_or_url: str) -> str:
        """Extract issue key from URL or return as-is."""
        if '/' in issue_key_or_url:
            match = re.search(r'/browse/([A-Z]+-\d+)', issue_key_or_url)
            if match:
                return match.group(1)
            return issue_key_or_url.rstrip('/').split('/')[-1]
        return issue_key_or_url

    # ==================== Issues ====================

    def get_issue(self, issue_key_or_url: str, expand: str = "renderedFields,comments") -> Dict[str, Any]:
        """Get a Jira issue by key or URL."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {'expand': expand}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def search_issues(self, jql: str, max_results: int = 50,
                      fields: str = "summary,status,assignee,priority,created,updated") -> Dict[str, Any]:
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
                     assignee: str = None, labels: List[str] = None,
                     components: List[str] = None, fix_versions: List[str] = None,
                     custom_fields: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a new Jira issue."""
        url = f"{self.base_url}/rest/api/2/issue"
        fields: Dict[str, Any] = {
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
        if components:
            fields['components'] = [{'name': c} for c in components]
        if fix_versions:
            fields['fixVersions'] = [{'name': v} for v in fix_versions]
        if custom_fields:
            fields.update(custom_fields)

        response = self.session.post(url, json={'fields': fields})
        response.raise_for_status()
        return response.json()

    def update_issue(self, issue_key_or_url: str, fields: Dict[str, Any]) -> None:
        """Update an issue's fields."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        response = self.session.put(url, json={'fields': fields})
        response.raise_for_status()

    def delete_issue(self, issue_key_or_url: str, delete_subtasks: bool = False) -> None:
        """Delete an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        params = {'deleteSubtasks': str(delete_subtasks).lower()}
        response = self.session.delete(url, params=params)
        response.raise_for_status()

    def assign_issue(self, issue_key_or_url: str, assignee: str = None) -> None:
        """Assign or unassign an issue. Pass None to unassign."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/assignee"
        payload = {'name': assignee} if assignee else {'name': None}
        response = self.session.put(url, json=payload)
        response.raise_for_status()

    # ==================== Transitions ====================

    def get_transitions(self, issue_key_or_url: str) -> List[Dict[str, Any]]:
        """Get available transitions for an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/transitions"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('transitions', [])

    def transition_issue(self, issue_key_or_url: str, transition_name_or_id: str,
                         comment: str = None, resolution: str = None) -> None:
        """Transition an issue to a new status."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/transitions"

        # Check if it's an ID (numeric) or name
        if transition_name_or_id.isdigit():
            transition_id = transition_name_or_id
        else:
            # Find transition by name
            transitions = self.get_transitions(issue_key)
            transition_id = None
            for t in transitions:
                if t['name'].lower() == transition_name_or_id.lower():
                    transition_id = t['id']
                    break
            if not transition_id:
                available = [t['name'] for t in transitions]
                raise ValueError(f"Transition '{transition_name_or_id}' not found. Available: {available}")

        payload: Dict[str, Any] = {'transition': {'id': transition_id}}

        if comment:
            payload['update'] = {
                'comment': [{'add': {'body': comment}}]
            }
        if resolution:
            payload['fields'] = {'resolution': {'name': resolution}}

        response = self.session.post(url, json=payload)
        response.raise_for_status()

    # ==================== Comments ====================

    def add_comment(self, issue_key_or_url: str, comment: str) -> Dict[str, Any]:
        """Add a comment to an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/comment"
        response = self.session.post(url, json={'body': comment})
        response.raise_for_status()
        return response.json()

    def get_comments(self, issue_key_or_url: str) -> List[Dict[str, Any]]:
        """Get all comments for an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/comment"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('comments', [])

    # ==================== Worklog ====================

    def add_worklog(self, issue_key_or_url: str, time_spent: str,
                    comment: str = None, started: str = None) -> Dict[str, Any]:
        """Add worklog entry to an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/worklog"
        payload: Dict[str, Any] = {'timeSpent': time_spent}
        if comment:
            payload['comment'] = comment
        if started:
            payload['started'] = started
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_worklogs(self, issue_key_or_url: str) -> List[Dict[str, Any]]:
        """Get all worklogs for an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/worklog"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('worklogs', [])

    # ==================== Issue Links ====================

    def link_issues(self, inward_issue: str, outward_issue: str,
                    link_type: str = "Relates") -> None:
        """Link two issues together."""
        url = f"{self.base_url}/rest/api/2/issueLink"
        payload = {
            'type': {'name': link_type},
            'inwardIssue': {'key': self._parse_issue_key(inward_issue)},
            'outwardIssue': {'key': self._parse_issue_key(outward_issue)}
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()

    def get_issue_link_types(self) -> List[Dict[str, Any]]:
        """Get all available issue link types."""
        url = f"{self.base_url}/rest/api/2/issueLinkType"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('issueLinkTypes', [])

    # ==================== Watchers ====================

    def get_watchers(self, issue_key_or_url: str) -> Dict[str, Any]:
        """Get watchers for an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/watchers"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def add_watcher(self, issue_key_or_url: str, username: str) -> None:
        """Add a watcher to an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/watchers"
        response = self.session.post(url, json=username)
        response.raise_for_status()

    def remove_watcher(self, issue_key_or_url: str, username: str) -> None:
        """Remove a watcher from an issue."""
        issue_key = self._parse_issue_key(issue_key_or_url)
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}/watchers"
        params = {'username': username}
        response = self.session.delete(url, params=params)
        response.raise_for_status()

    # ==================== Projects ====================

    def get_all_projects(self) -> List[Dict[str, Any]]:
        """Get all projects."""
        url = f"{self.base_url}/rest/api/2/project"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_project(self, project_key: str) -> Dict[str, Any]:
        """Get project details."""
        url = f"{self.base_url}/rest/api/2/project/{project_key}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_project_components(self, project_key: str) -> List[Dict[str, Any]]:
        """Get project components."""
        url = f"{self.base_url}/rest/api/2/project/{project_key}/components"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def create_component(self, project_key: str, name: str,
                         description: str = None, lead: str = None) -> Dict[str, Any]:
        """Create a project component."""
        url = f"{self.base_url}/rest/api/2/component"
        payload: Dict[str, Any] = {
            'project': project_key,
            'name': name
        }
        if description:
            payload['description'] = description
        if lead:
            payload['leadUserName'] = lead
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_project_versions(self, project_key: str) -> List[Dict[str, Any]]:
        """Get project versions."""
        url = f"{self.base_url}/rest/api/2/project/{project_key}/versions"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def create_version(self, project_key: str, name: str,
                       description: str = None, release_date: str = None,
                       released: bool = False) -> Dict[str, Any]:
        """Create a project version."""
        url = f"{self.base_url}/rest/api/2/version"
        payload: Dict[str, Any] = {
            'project': project_key,
            'name': name,
            'released': released
        }
        if description:
            payload['description'] = description
        if release_date:
            payload['releaseDate'] = release_date
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_project_roles(self, project_key: str) -> Dict[str, str]:
        """Get project roles."""
        url = f"{self.base_url}/rest/api/2/project/{project_key}/role"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_project_role(self, project_key: str, role_id: str) -> Dict[str, Any]:
        """Get project role members."""
        url = f"{self.base_url}/rest/api/2/project/{project_key}/role/{role_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_project_statuses(self, project_key: str) -> List[Dict[str, Any]]:
        """Get project statuses."""
        url = f"{self.base_url}/rest/api/2/project/{project_key}/statuses"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ==================== Users ====================

    def get_user(self, username: str) -> Dict[str, Any]:
        """Get user by username."""
        url = f"{self.base_url}/rest/api/2/user"
        params = {'username': username}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def search_users(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for users."""
        url = f"{self.base_url}/rest/api/2/user/search"
        params = {'username': query, 'maxResults': max_results}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def find_assignable_users(self, project_key: str = None, issue_key: str = None,
                               query: str = None, max_results: int = 50) -> List[Dict[str, Any]]:
        """Find users assignable to a project or issue."""
        url = f"{self.base_url}/rest/api/2/user/assignable/search"
        params: Dict[str, Any] = {'maxResults': max_results}
        if project_key:
            params['project'] = project_key
        if issue_key:
            params['issueKey'] = issue_key
        if query:
            params['username'] = query
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_current_user(self) -> Dict[str, Any]:
        """Get the currently authenticated user."""
        url = f"{self.base_url}/rest/api/2/myself"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ==================== Groups ====================

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """Get all groups."""
        url = f"{self.base_url}/rest/api/2/groups/picker"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('groups', [])

    def get_group_members(self, group_name: str, max_results: int = 50) -> Dict[str, Any]:
        """Get members of a group."""
        url = f"{self.base_url}/rest/api/2/group/member"
        params = {'groupname': group_name, 'maxResults': max_results}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def add_user_to_group(self, group_name: str, username: str) -> None:
        """Add a user to a group."""
        url = f"{self.base_url}/rest/api/2/group/user"
        params = {'groupname': group_name}
        payload = {'name': username}
        response = self.session.post(url, params=params, json=payload)
        response.raise_for_status()

    def remove_user_from_group(self, group_name: str, username: str) -> None:
        """Remove a user from a group."""
        url = f"{self.base_url}/rest/api/2/group/user"
        params = {'groupname': group_name, 'username': username}
        response = self.session.delete(url, params=params)
        response.raise_for_status()

    # ==================== Boards (Agile) ====================

    def get_all_boards(self, board_type: str = None, name: str = None,
                       project_key: str = None, max_results: int = 50) -> Dict[str, Any]:
        """Get all agile boards."""
        url = f"{self.base_url}/rest/agile/1.0/board"
        params: Dict[str, Any] = {'maxResults': max_results}
        if board_type:
            params['type'] = board_type
        if name:
            params['name'] = name
        if project_key:
            params['projectKeyOrId'] = project_key
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_board(self, board_id: int) -> Dict[str, Any]:
        """Get board details."""
        url = f"{self.base_url}/rest/agile/1.0/board/{board_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_board_sprints(self, board_id: int, state: str = None,
                          max_results: int = 50) -> Dict[str, Any]:
        """Get sprints for a board."""
        url = f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint"
        params: Dict[str, Any] = {'maxResults': max_results}
        if state:
            params['state'] = state
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_board_backlog(self, board_id: int, max_results: int = 50) -> Dict[str, Any]:
        """Get backlog issues for a board."""
        url = f"{self.base_url}/rest/agile/1.0/board/{board_id}/backlog"
        params = {'maxResults': max_results}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Sprints ====================

    def get_sprint(self, sprint_id: int) -> Dict[str, Any]:
        """Get sprint details."""
        url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def create_sprint(self, board_id: int, name: str,
                      start_date: str = None, end_date: str = None,
                      goal: str = None) -> Dict[str, Any]:
        """Create a sprint."""
        url = f"{self.base_url}/rest/agile/1.0/sprint"
        payload: Dict[str, Any] = {
            'originBoardId': board_id,
            'name': name
        }
        if start_date:
            payload['startDate'] = start_date
        if end_date:
            payload['endDate'] = end_date
        if goal:
            payload['goal'] = goal
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def update_sprint(self, sprint_id: int, name: str = None,
                      state: str = None, start_date: str = None,
                      end_date: str = None, goal: str = None) -> Dict[str, Any]:
        """Update a sprint."""
        url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}"
        payload: Dict[str, Any] = {}
        if name:
            payload['name'] = name
        if state:
            payload['state'] = state
        if start_date:
            payload['startDate'] = start_date
        if end_date:
            payload['endDate'] = end_date
        if goal:
            payload['goal'] = goal
        response = self.session.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_sprint_issues(self, sprint_id: int, max_results: int = 50) -> Dict[str, Any]:
        """Get issues in a sprint."""
        url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}/issue"
        params = {'maxResults': max_results}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def move_issues_to_sprint(self, sprint_id: int, issue_keys: List[str]) -> None:
        """Move issues to a sprint."""
        url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}/issue"
        payload = {'issues': issue_keys}
        response = self.session.post(url, json=payload)
        response.raise_for_status()

    def move_issues_to_backlog(self, issue_keys: List[str]) -> None:
        """Move issues to backlog."""
        url = f"{self.base_url}/rest/agile/1.0/backlog/issue"
        payload = {'issues': issue_keys}
        response = self.session.post(url, json=payload)
        response.raise_for_status()

    # ==================== Epics ====================

    def get_epic(self, epic_key: str) -> Dict[str, Any]:
        """Get epic details."""
        url = f"{self.base_url}/rest/agile/1.0/epic/{epic_key}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_epic_issues(self, epic_key: str, max_results: int = 50) -> Dict[str, Any]:
        """Get issues in an epic."""
        url = f"{self.base_url}/rest/agile/1.0/epic/{epic_key}/issue"
        params = {'maxResults': max_results}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def move_issues_to_epic(self, epic_key: str, issue_keys: List[str]) -> None:
        """Move issues to an epic."""
        url = f"{self.base_url}/rest/agile/1.0/epic/{epic_key}/issue"
        payload = {'issues': issue_keys}
        response = self.session.post(url, json=payload)
        response.raise_for_status()

    # ==================== Filters ====================

    def get_filter(self, filter_id: str) -> Dict[str, Any]:
        """Get filter by ID."""
        url = f"{self.base_url}/rest/api/2/filter/{filter_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_favorite_filters(self) -> List[Dict[str, Any]]:
        """Get user's favorite filters."""
        url = f"{self.base_url}/rest/api/2/filter/favourite"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def search_filters(self, filter_name: str = None, max_results: int = 50) -> Dict[str, Any]:
        """Search for filters."""
        url = f"{self.base_url}/rest/api/2/filter/search"
        params: Dict[str, Any] = {'maxResults': max_results}
        if filter_name:
            params['filterName'] = filter_name
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def create_filter(self, name: str, jql: str, description: str = None,
                      favourite: bool = False) -> Dict[str, Any]:
        """Create a filter."""
        url = f"{self.base_url}/rest/api/2/filter"
        payload: Dict[str, Any] = {
            'name': name,
            'jql': jql,
            'favourite': favourite
        }
        if description:
            payload['description'] = description
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def delete_filter(self, filter_id: str) -> None:
        """Delete a filter."""
        url = f"{self.base_url}/rest/api/2/filter/{filter_id}"
        response = self.session.delete(url)
        response.raise_for_status()

    # ==================== Dashboards ====================

    def get_all_dashboards(self, max_results: int = 50) -> Dict[str, Any]:
        """Get all dashboards."""
        url = f"{self.base_url}/rest/api/2/dashboard"
        params = {'maxResults': max_results}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """Get dashboard by ID."""
        url = f"{self.base_url}/rest/api/2/dashboard/{dashboard_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ==================== Administration ====================

    def get_server_info(self) -> Dict[str, Any]:
        """Get Jira server information."""
        url = f"{self.base_url}/rest/api/2/serverInfo"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_all_fields(self) -> List[Dict[str, Any]]:
        """Get all fields (including custom fields)."""
        url = f"{self.base_url}/rest/api/2/field"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_all_issue_types(self) -> List[Dict[str, Any]]:
        """Get all issue types."""
        url = f"{self.base_url}/rest/api/2/issuetype"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_all_priorities(self) -> List[Dict[str, Any]]:
        """Get all priorities."""
        url = f"{self.base_url}/rest/api/2/priority"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        """Get all statuses."""
        url = f"{self.base_url}/rest/api/2/status"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_all_resolutions(self) -> List[Dict[str, Any]]:
        """Get all resolutions."""
        url = f"{self.base_url}/rest/api/2/resolution"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_all_project_categories(self) -> List[Dict[str, Any]]:
        """Get all project categories."""
        url = f"{self.base_url}/rest/api/2/projectCategory"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ==================== Attachments ====================

    def get_attachment(self, attachment_id: str) -> Dict[str, Any]:
        """Get attachment metadata."""
        url = f"{self.base_url}/rest/api/2/attachment/{attachment_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def delete_attachment(self, attachment_id: str) -> None:
        """Delete an attachment."""
        url = f"{self.base_url}/rest/api/2/attachment/{attachment_id}"
        response = self.session.delete(url)
        response.raise_for_status()


# Singleton instances
_config: Optional[JiraConfig] = None
_client: Optional[JiraClient] = None


def get_config() -> JiraConfig:
    """Get or create the global config."""
    global _config
    if _config is None:
        _config = JiraConfig()
    return _config


def get_jira_client() -> JiraClient:
    """Get or create the Jira client."""
    global _client
    if _client is None:
        _client = JiraClient(get_config())
    return _client
