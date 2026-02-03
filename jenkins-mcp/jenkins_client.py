"""
Jenkins API client for Jenkins Server.
Supports Basic authentication with username:api-token.
Supports multiple server configurations.
"""

import os
import requests
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv


class JenkinsConfig:
    """Configuration loader for Jenkins credentials."""

    def __init__(self, config_path: Optional[str] = None):
        # Primary: common atlassian config
        atlassian_config = os.path.expanduser('~/.config/atlassian/.env')
        # Override: service-specific config (optional)
        service_config = config_path or os.environ.get(
            'JENKINS_CONFIG',
            os.path.expanduser('~/.config/jenkins-mcp/.env')
        )

        # Load atlassian config first, then override with service-specific if exists
        if os.path.exists(atlassian_config):
            load_dotenv(atlassian_config)
        if os.path.exists(service_config):
            load_dotenv(service_config, override=True)

        # Proxy config (optional)
        self.http_proxy = os.environ.get('HTTP_PROXY', '')
        self.https_proxy = os.environ.get('HTTPS_PROXY', '')
        self.no_proxy = os.environ.get('NO_PROXY', 'localhost,127.0.0.1')

        # SSL verification
        self.verify_ssl = os.environ.get('VERIFY_SSL', 'true').lower() != 'false'

        # Jenkins config - supports multiple servers
        self.jenkins_servers: Dict[str, Dict[str, str]] = {}

        # Check for multi-server config
        jenkins_server_names = os.environ.get('JENKINS_SERVERS', '')
        if jenkins_server_names:
            for server_name in jenkins_server_names.split(','):
                server_name = server_name.strip().lower()
                if server_name:
                    prefix = f'JENKINS_{server_name.upper()}_'
                    url = os.environ.get(f'{prefix}URL', '').rstrip('/')
                    if url:
                        self.jenkins_servers[server_name] = {
                            'url': url,
                            'username': os.environ.get(f'{prefix}USERNAME', ''),
                            'token': os.environ.get(f'{prefix}TOKEN', '')
                        }

        # Fallback to legacy single server config
        legacy_url = os.environ.get('JENKINS_URL', '').rstrip('/')
        if legacy_url and not self.jenkins_servers:
            self.jenkins_servers['default'] = {
                'url': legacy_url,
                'username': os.environ.get('JENKINS_USERNAME', ''),
                'token': os.environ.get('JENKINS_TOKEN', '')
            }

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


class JenkinsClient:
    """Client for Jenkins REST API (read-only operations)."""

    def __init__(self, config: JenkinsConfig, server_name: Optional[str] = None):
        """
        Initialize Jenkins client.

        Args:
            config: JenkinsConfig instance
            server_name: Name of the Jenkins server (e.g., 'proc', 'epsw').
                        If None, uses first available or 'default'.
        """
        self.server_name = server_name

        # Get server config
        if server_name and server_name in config.jenkins_servers:
            server_config = config.jenkins_servers[server_name]
        elif config.jenkins_servers:
            first_server = next(iter(config.jenkins_servers))
            server_config = config.jenkins_servers[first_server]
            self.server_name = first_server
        else:
            raise ValueError("No Jenkins servers configured")

        self.base_url = server_config['url']
        self.session = requests.Session()
        self.session.auth = (server_config['username'], server_config['token'])
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.session.verify = config.verify_ssl
        if not config.should_bypass_proxy(self.base_url):
            proxies = config.get_proxies()
            if proxies:
                self.session.proxies.update(proxies)

    def _get_job_path(self, job_name: str) -> str:
        """Convert job name with folders to URL path."""
        return '/job/'.join(job_name.split('/'))

    # ==================== Jobs ====================

    def get_job(self, job_name: str) -> Dict[str, Any]:
        """Get job details by name."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def list_jobs(self, folder: str = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally within a folder."""
        if folder:
            folder_path = self._get_job_path(folder)
            url = f"{self.base_url}/job/{folder_path}/api/json"
        else:
            url = f"{self.base_url}/api/json"

        params = {"tree": "jobs[name,color,url,lastBuild[number,result,timestamp]]"}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('jobs', [])

    # ==================== Builds ====================

    def get_build(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """Get specific build information."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/{build_number}/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_last_build(self, job_name: str) -> Dict[str, Any]:
        """Get the last build for a job."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/lastBuild/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_build_log(self, job_name: str, build_number: int) -> str:
        """Get console output for a build."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/{build_number}/consoleText"
        response = self.session.get(url)
        response.raise_for_status()
        return response.text

    # ==================== Queue ====================

    def get_queue(self) -> List[Dict[str, Any]]:
        """Get the build queue."""
        url = f"{self.base_url}/queue/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('items', [])

    # ==================== Nodes ====================

    def get_nodes(self) -> List[Dict[str, Any]]:
        """Get all build agents/nodes."""
        url = f"{self.base_url}/computer/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('computer', [])

    # ==================== Job Configuration ====================

    def get_job_config(self, job_name: str) -> str:
        """Get job XML configuration."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/config.xml"
        response = self.session.get(url)
        response.raise_for_status()
        return response.text

    def get_job_config_parsed(self, job_name: str) -> Dict[str, Any]:
        """Get job configuration as parsed dictionary with key settings."""
        xml_config = self.get_job_config(job_name)
        root = ET.fromstring(xml_config)

        config: Dict[str, Any] = {
            'job_type': root.tag,
            'description': '',
            'disabled': False,
            'triggers': [],
            'scm': None,
            'builders': [],
            'publishers': [],
            'parameters': [],
            'raw_xml': xml_config
        }

        # Description
        desc = root.find('description')
        if desc is not None and desc.text:
            config['description'] = desc.text

        # Disabled status
        disabled = root.find('disabled')
        if disabled is not None and disabled.text:
            config['disabled'] = disabled.text.lower() == 'true'

        # Build triggers
        triggers = root.find('triggers')
        if triggers is not None:
            for trigger in triggers:
                trigger_info: Dict[str, Any] = {'type': trigger.tag}
                spec = trigger.find('spec')
                if spec is not None and spec.text:
                    trigger_info['schedule'] = spec.text
                config['triggers'].append(trigger_info)

        # SCM configuration
        scm = root.find('scm')
        if scm is not None:
            scm_class = scm.get('class', '')
            config['scm'] = {'type': scm_class}

            if 'git' in scm_class.lower():
                user_remote = scm.find('.//userRemoteConfigs/hudson.plugins.git.UserRemoteConfig')
                if user_remote is not None:
                    url_elem = user_remote.find('url')
                    if url_elem is not None and url_elem.text:
                        config['scm']['url'] = url_elem.text

                branches = scm.findall('.//branches/hudson.plugins.git.BranchSpec/name')
                if branches:
                    config['scm']['branches'] = [b.text for b in branches if b.text]

        # Build parameters
        props = root.find('properties')
        if props is not None:
            params_def = props.find('.//hudson.model.ParametersDefinitionProperty/parameterDefinitions')
            if params_def is not None:
                for param in params_def:
                    param_info: Dict[str, Any] = {
                        'type': param.tag.split('.')[-1],
                        'name': '',
                        'description': '',
                        'default': ''
                    }
                    name_elem = param.find('name')
                    if name_elem is not None and name_elem.text:
                        param_info['name'] = name_elem.text
                    desc_elem = param.find('description')
                    if desc_elem is not None and desc_elem.text:
                        param_info['description'] = desc_elem.text
                    default = param.find('defaultValue')
                    if default is not None and default.text:
                        param_info['default'] = default.text
                    config['parameters'].append(param_info)

        # Builders (build steps)
        builders = root.find('builders')
        if builders is not None:
            for builder in builders:
                builder_info: Dict[str, Any] = {'type': builder.tag.split('.')[-1]}
                command = builder.find('command')
                if command is not None and command.text:
                    builder_info['command'] = command.text[:500]
                config['builders'].append(builder_info)

        # Pipeline definition
        definition = root.find('definition')
        if definition is not None:
            def_class = definition.get('class', '')
            config['pipeline'] = {'type': def_class}
            script = definition.find('script')
            if script is not None and script.text:
                config['pipeline']['script'] = script.text

        # Publishers
        publishers = root.find('publishers')
        if publishers is not None:
            for publisher in publishers:
                config['publishers'].append({'type': publisher.tag.split('.')[-1]})

        return config

    # ==================== Server Info ====================

    def get_server_info(self) -> Dict[str, Any]:
        """Get Jenkins server information."""
        url = f"{self.base_url}/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()


# Singleton instances
_config: Optional[JenkinsConfig] = None
_clients: Dict[str, JenkinsClient] = {}


def get_config() -> JenkinsConfig:
    """Get or create the global config."""
    global _config
    if _config is None:
        _config = JenkinsConfig()
    return _config


def get_jenkins_client(server: Optional[str] = None) -> JenkinsClient:
    """
    Get or create a Jenkins client for the specified server.

    Args:
        server: Name of the Jenkins server (e.g., 'proc', 'epsw').
                If None, uses first available server.
    """
    global _clients
    config = get_config()

    if not config.jenkins_servers:
        raise ValueError(
            "No Jenkins servers configured. Set JENKINS_SERVERS and corresponding "
            "JENKINS_<NAME>_URL/USERNAME/TOKEN environment variables."
        )

    # Normalize server name
    if server:
        server = server.lower()
    else:
        server = next(iter(config.jenkins_servers))

    if server not in config.jenkins_servers:
        available = ', '.join(config.jenkins_servers.keys())
        raise ValueError(f"Unknown Jenkins server '{server}'. Available servers: {available}")

    if server not in _clients:
        _clients[server] = JenkinsClient(config, server)

    return _clients[server]


def get_available_jenkins_servers() -> List[str]:
    """Get list of available Jenkins server names."""
    config = get_config()
    return list(config.jenkins_servers.keys())
