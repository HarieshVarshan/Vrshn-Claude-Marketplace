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

    # ==================== Build Details ====================

    def list_builds(self, job_name: str, limit: int = 25) -> List[Dict[str, Any]]:
        """List builds for a job."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/api/json"
        params = {
            "tree": f"builds[number,result,timestamp,duration,building]{{0,{limit}}}"
        }
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('builds', [])

    def get_build_test_results(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """Get test results for a build."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/{build_number}/testReport/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_build_artifacts(self, job_name: str, build_number: int) -> List[Dict[str, Any]]:
        """List artifacts from a build."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/{build_number}/api/json"
        params = {"tree": "artifacts[fileName,relativePath,displayPath]"}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('artifacts', [])

    def download_artifact(self, job_name: str, build_number: int,
                          artifact_path: str, download_path: str) -> str:
        """Download an artifact from a build."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/{build_number}/artifact/{artifact_path}"
        response = self.session.get(url, stream=True)
        response.raise_for_status()

        with open(download_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return download_path

    # ==================== Views ====================

    def list_views(self) -> List[Dict[str, Any]]:
        """List all views."""
        url = f"{self.base_url}/api/json"
        params = {"tree": "views[name,url,description]"}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('views', [])

    def get_view(self, view_name: str) -> Dict[str, Any]:
        """Get jobs in a specific view."""
        url = f"{self.base_url}/view/{view_name}/api/json"
        params = {"tree": "name,description,jobs[name,color,url,lastBuild[number,result]]"}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    # ==================== Nodes ====================

    def get_node_details(self, node_name: str) -> Dict[str, Any]:
        """Get detailed info about a specific node."""
        # Master node has special path
        if node_name.lower() in ('master', 'built-in node', '(master)'):
            node_path = "(master)"
        else:
            node_path = node_name

        url = f"{self.base_url}/computer/{node_path}/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ==================== System Info ====================

    def get_server_info(self) -> Dict[str, Any]:
        """Get Jenkins server information."""
        url = f"{self.base_url}/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_system_info(self) -> Dict[str, Any]:
        """Get Jenkins system information including version."""
        # Get version from response headers
        url = f"{self.base_url}/api/json"
        response = self.session.get(url)
        response.raise_for_status()

        info = response.json()
        info['jenkinsVersion'] = response.headers.get('X-Jenkins', 'Unknown')
        return info

    def get_plugins(self) -> List[Dict[str, Any]]:
        """List installed plugins."""
        url = f"{self.base_url}/pluginManager/api/json"
        params = {"tree": "plugins[shortName,longName,version,active,enabled,hasUpdate]",
                  "depth": 1}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('plugins', [])

    def get_credentials_list(self, domain: str = "_") -> List[Dict[str, Any]]:
        """List credential IDs (metadata only, not secrets)."""
        url = f"{self.base_url}/credentials/store/system/domain/{domain}/api/json"
        params = {"tree": "credentials[id,displayName,description,typeName]"}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('credentials', [])

    # ==================== Build Operations (Write) ====================

    def trigger_build(self, job_name: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Trigger a build for a job."""
        job_path = self._get_job_path(job_name)

        if parameters:
            url = f"{self.base_url}/job/{job_path}/buildWithParameters"
            response = self.session.post(url, params=parameters)
        else:
            url = f"{self.base_url}/job/{job_path}/build"
            response = self.session.post(url)

        response.raise_for_status()

        # Get queue item URL from Location header
        queue_url = response.headers.get('Location', '')
        return {
            'status': 'triggered',
            'queue_url': queue_url,
            'queue_item': queue_url.split('/')[-2] if queue_url else None
        }

    def stop_build(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """Stop/abort a running build."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/{build_number}/stop"
        response = self.session.post(url)
        response.raise_for_status()
        return {'status': 'stopped', 'job': job_name, 'build': build_number}

    # ==================== Job Operations (Write) ====================

    def enable_job(self, job_name: str) -> Dict[str, Any]:
        """Enable a disabled job."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/enable"
        response = self.session.post(url)
        response.raise_for_status()
        return {'status': 'enabled', 'job': job_name}

    def disable_job(self, job_name: str) -> Dict[str, Any]:
        """Disable a job."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/disable"
        response = self.session.post(url)
        response.raise_for_status()
        return {'status': 'disabled', 'job': job_name}

    def delete_job(self, job_name: str) -> Dict[str, Any]:
        """Delete a job."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/doDelete"
        response = self.session.post(url)
        response.raise_for_status()
        return {'status': 'deleted', 'job': job_name}

    def create_job(self, job_name: str, config_xml: str, folder: str = None) -> Dict[str, Any]:
        """Create a new job from XML config."""
        if folder:
            folder_path = self._get_job_path(folder)
            url = f"{self.base_url}/job/{folder_path}/createItem"
        else:
            url = f"{self.base_url}/createItem"

        headers = {'Content-Type': 'application/xml'}
        params = {'name': job_name}
        response = self.session.post(url, data=config_xml, headers=headers, params=params)
        response.raise_for_status()
        return {'status': 'created', 'job': job_name}

    def copy_job(self, source_job: str, new_job_name: str, folder: str = None) -> Dict[str, Any]:
        """Copy an existing job."""
        if folder:
            folder_path = self._get_job_path(folder)
            url = f"{self.base_url}/job/{folder_path}/createItem"
        else:
            url = f"{self.base_url}/createItem"

        params = {
            'name': new_job_name,
            'mode': 'copy',
            'from': source_job
        }
        response = self.session.post(url, params=params)
        response.raise_for_status()
        return {'status': 'copied', 'source': source_job, 'new_job': new_job_name}

    def update_job_config(self, job_name: str, config_xml: str) -> Dict[str, Any]:
        """Update job configuration."""
        job_path = self._get_job_path(job_name)
        url = f"{self.base_url}/job/{job_path}/config.xml"
        headers = {'Content-Type': 'application/xml'}
        response = self.session.post(url, data=config_xml, headers=headers)
        response.raise_for_status()
        return {'status': 'updated', 'job': job_name}

    # ==================== Raw API ====================

    def raw_api(self, method: str, endpoint: str,
                body: Dict[str, Any] = None,
                params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make a raw API call to Jenkins.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/job/my-job/api/json')
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
