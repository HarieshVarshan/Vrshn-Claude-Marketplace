"""
Webex API client for the Cisco Webex REST API.

Covers: People, Organizations, Teams, Rooms, Messages, Memberships, Webhooks.
All endpoints use Bearer token authentication against https://webexapis.com/v1/.
"""

import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


class WebexConfig:
    """Configuration loader for Webex credentials."""

    def __init__(self, config_path: Optional[str] = None):
        # Primary: common atlassian config
        atlassian_config = os.path.expanduser('~/.config/atlassian/.env')
        # Override: service-specific config (optional)
        service_config = config_path or os.environ.get(
            'WEBEX_CONFIG',
            os.path.expanduser('~/.config/webex-mcp/.env')
        )

        if os.path.exists(atlassian_config):
            load_dotenv(atlassian_config)
        if os.path.exists(service_config):
            load_dotenv(service_config, override=True)

        self.base_url = os.environ.get('WEBEX_BASE_URL', 'https://webexapis.com').rstrip('/')
        self.access_token = os.environ.get('WEBEX_ACCESS_TOKEN', '')

        # Proxy config (optional)
        self.http_proxy = os.environ.get('HTTP_PROXY', '')
        self.https_proxy = os.environ.get('HTTPS_PROXY', '')
        self.verify_ssl = os.environ.get('VERIFY_SSL', 'true').lower() != 'false'

    def get_proxies(self) -> Optional[Dict[str, str]]:
        if self.http_proxy or self.https_proxy:
            return {'http': self.http_proxy, 'https': self.https_proxy}
        return None


class WebexClient:
    """Client for the Cisco Webex REST API."""

    def __init__(self, config: WebexConfig):
        self.base_url = config.base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {config.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        self.session.verify = config.verify_ssl
        proxies = config.get_proxies()
        if proxies:
            self.session.proxies.update(proxies)

    def _url(self, path: str) -> str:
        return f"{self.base_url}/v1{path}"

    def _get(self, path: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        response = self.session.get(self._url(path), params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(self._url(path), json=payload)
        response.raise_for_status()
        return response.json()

    def _delete(self, path: str) -> None:
        response = self.session.delete(self._url(path))
        response.raise_for_status()

    # ==================== People ====================

    def get_me(self) -> Dict[str, Any]:
        """Get the current authenticated user's details."""
        return self._get('/people/me')

    def list_people(self, email: str = None, display_name: str = None,
                    max_results: int = 100) -> List[Dict[str, Any]]:
        """Search for people by email or display name."""
        params: Dict[str, Any] = {'max': max_results}
        if email:
            params['email'] = email
        if display_name:
            params['displayName'] = display_name
        return self._get('/people', params).get('items', [])

    def get_person(self, person_id: str) -> Dict[str, Any]:
        """Get details for a specific person."""
        return self._get(f'/people/{person_id}')

    # ==================== Organizations ====================

    def list_organizations(self) -> List[Dict[str, Any]]:
        """List organizations the user belongs to."""
        return self._get('/organizations').get('items', [])

    def get_organization(self, org_id: str) -> Dict[str, Any]:
        """Get details for a specific organization."""
        return self._get(f'/organizations/{org_id}')

    # ==================== Teams ====================

    def list_teams(self, max_results: int = 100) -> List[Dict[str, Any]]:
        """List teams the user is a member of."""
        return self._get('/teams', {'max': max_results}).get('items', [])

    def create_team(self, name: str, description: str = None) -> Dict[str, Any]:
        """Create a new team."""
        payload: Dict[str, Any] = {'name': name}
        if description:
            payload['description'] = description
        return self._post('/teams', payload)

    def get_team(self, team_id: str) -> Dict[str, Any]:
        """Get details for a specific team."""
        return self._get(f'/teams/{team_id}')

    def delete_team(self, team_id: str) -> None:
        """Delete a team."""
        self._delete(f'/teams/{team_id}')

    # ==================== Rooms ====================

    def list_rooms(self, team_id: str = None, room_type: str = None,
                   max_results: int = 100) -> List[Dict[str, Any]]:
        """List rooms/spaces the user is a member of."""
        params: Dict[str, Any] = {'max': max_results}
        if team_id:
            params['teamId'] = team_id
        if room_type:
            params['type'] = room_type
        return self._get('/rooms', params).get('items', [])

    def create_room(self, title: str, team_id: str = None) -> Dict[str, Any]:
        """Create a new room/space."""
        payload: Dict[str, Any] = {'title': title}
        if team_id:
            payload['teamId'] = team_id
        return self._post('/rooms', payload)

    def get_room(self, room_id: str) -> Dict[str, Any]:
        """Get details for a specific room."""
        return self._get(f'/rooms/{room_id}')

    def delete_room(self, room_id: str) -> None:
        """Delete a room."""
        self._delete(f'/rooms/{room_id}')

    # ==================== Messages ====================

    def list_messages(self, room_id: str, max_results: int = 50,
                      before: str = None, before_message: str = None) -> List[Dict[str, Any]]:
        """List messages in a room."""
        params: Dict[str, Any] = {'roomId': room_id, 'max': max_results}
        if before:
            params['before'] = before
        if before_message:
            params['beforeMessage'] = before_message
        return self._get('/messages', params).get('items', [])

    def create_message(self, room_id: str = None, to_person_id: str = None,
                       to_person_email: str = None, text: str = None,
                       markdown: str = None, html: str = None,
                       files: List[str] = None) -> Dict[str, Any]:
        """Send a message to a room or person.

        Must specify either roomId OR (toPersonId / toPersonEmail).
        Must specify at least one of: text, markdown, html, files.
        """
        payload: Dict[str, Any] = {}
        if room_id:
            payload['roomId'] = room_id
        if to_person_id:
            payload['toPersonId'] = to_person_id
        if to_person_email:
            payload['toPersonEmail'] = to_person_email
        if text:
            payload['text'] = text
        if markdown:
            payload['markdown'] = markdown
        if html:
            payload['html'] = html
        if files:
            payload['files'] = files
        return self._post('/messages', payload)

    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Get details for a specific message."""
        return self._get(f'/messages/{message_id}')

    def delete_message(self, message_id: str) -> None:
        """Delete a message."""
        self._delete(f'/messages/{message_id}')

    # ==================== Memberships ====================

    def list_memberships(self, room_id: str = None, person_id: str = None,
                         person_email: str = None,
                         max_results: int = 100) -> List[Dict[str, Any]]:
        """List room memberships."""
        params: Dict[str, Any] = {'max': max_results}
        if room_id:
            params['roomId'] = room_id
        if person_id:
            params['personId'] = person_id
        if person_email:
            params['personEmail'] = person_email
        return self._get('/memberships', params).get('items', [])

    def create_membership(self, room_id: str, person_id: str = None,
                          person_email: str = None,
                          is_moderator: bool = False) -> Dict[str, Any]:
        """Add a person to a room. Specify either personId or personEmail."""
        payload: Dict[str, Any] = {'roomId': room_id, 'isModerator': is_moderator}
        if person_id:
            payload['personId'] = person_id
        if person_email:
            payload['personEmail'] = person_email
        return self._post('/memberships', payload)

    def get_membership(self, membership_id: str) -> Dict[str, Any]:
        """Get details for a specific membership."""
        return self._get(f'/memberships/{membership_id}')

    def delete_membership(self, membership_id: str) -> None:
        """Remove a person from a room."""
        self._delete(f'/memberships/{membership_id}')

    # ==================== Webhooks ====================

    def list_webhooks(self, max_results: int = 100) -> List[Dict[str, Any]]:
        """List webhooks."""
        return self._get('/webhooks', {'max': max_results}).get('items', [])

    def create_webhook(self, name: str, target_url: str, resource: str,
                       event: str, filter_expr: str = None,
                       secret: str = None) -> Dict[str, Any]:
        """Create a new webhook."""
        payload: Dict[str, Any] = {
            'name': name,
            'targetUrl': target_url,
            'resource': resource,
            'event': event,
        }
        if filter_expr:
            payload['filter'] = filter_expr
        if secret:
            payload['secret'] = secret
        return self._post('/webhooks', payload)

    def get_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Get details for a specific webhook."""
        return self._get(f'/webhooks/{webhook_id}')

    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook."""
        self._delete(f'/webhooks/{webhook_id}')


# Singleton instances
_config: Optional[WebexConfig] = None
_client: Optional[WebexClient] = None


def get_config() -> WebexConfig:
    global _config
    if _config is None:
        _config = WebexConfig()
    return _config


def get_webex_client() -> WebexClient:
    global _client
    if _client is None:
        _client = WebexClient(get_config())
    return _client
