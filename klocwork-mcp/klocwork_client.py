"""
Klocwork API client for project management operations.

Uses kwadmin CLI tool and Klocwork Web API for administrative operations.
Requires:
- kwadmin in PATH (from Klocwork installation)
- Credentials configured in ~/.config/atlassian/.env
"""

import os
import subprocess
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
from typing import Dict, Any, List, Optional


# Default server configuration
DEFAULT_KLOCWORK_URL = "https://klocworkweb.india.ti.com:8095"
DEFAULT_SERVER = "india"


def get_server_config(server_name: str = None) -> Dict[str, str]:
    """
    Get Klocwork server configuration from environment variables.

    Supports multi-server configuration:
        KLOCWORK_SERVERS=india,stage
        KLOCWORK_INDIA_URL=https://klocworkweb.india.ti.com:8095
        KLOCWORK_INDIA_USERNAME=username
        KLOCWORK_INDIA_TOKEN=token

    Or single server (legacy):
        KLOCWORK_URL=https://...
        KLOCWORK_USERNAME=username
        KLOCWORK_TOKEN=token
    """
    server_name = server_name or os.environ.get("KLOCWORK_DEFAULT_SERVER", DEFAULT_SERVER)

    # Check for multi-server configuration
    server_list = os.environ.get("KLOCWORK_SERVERS", "")
    if server_list and server_name.lower() in [s.strip().lower() for s in server_list.split(",")]:
        upper_name = server_name.upper()
        return {
            "url": os.environ.get(f"KLOCWORK_{upper_name}_URL", "").rstrip("/"),
            "username": os.environ.get(f"KLOCWORK_{upper_name}_USERNAME", ""),
            "token": os.environ.get(f"KLOCWORK_{upper_name}_TOKEN", "")
        }

    # Fallback to single server configuration
    return {
        "url": os.environ.get("KLOCWORK_URL", DEFAULT_KLOCWORK_URL).rstrip("/"),
        "username": os.environ.get("KLOCWORK_USERNAME", ""),
        "token": os.environ.get("KLOCWORK_TOKEN", "")
    }


def list_configured_servers() -> List[Dict[str, str]]:
    """List all configured Klocwork servers."""
    servers = []
    server_list = os.environ.get("KLOCWORK_SERVERS", "")

    if server_list:
        for server_name in server_list.split(","):
            server_name = server_name.strip()
            upper_name = server_name.upper()
            url = os.environ.get(f"KLOCWORK_{upper_name}_URL", "")
            if url:
                servers.append({
                    "name": server_name,
                    "url": url.rstrip("/"),
                    "username": os.environ.get(f"KLOCWORK_{upper_name}_USERNAME", "")
                })
    elif os.environ.get("KLOCWORK_URL"):
        servers.append({
            "name": "default",
            "url": os.environ.get("KLOCWORK_URL", "").rstrip("/"),
            "username": os.environ.get("KLOCWORK_USERNAME", "")
        })

    return servers


class KlocworkClient:
    """Client for Klocwork administrative operations."""

    def __init__(self, server: str = None):
        """
        Initialize Klocwork client.

        Args:
            server: Server name ('india' or 'stage'). Defaults to KLOCWORK_DEFAULT_SERVER.
        """
        self.server_name = server or os.environ.get("KLOCWORK_DEFAULT_SERVER", DEFAULT_SERVER)
        config = get_server_config(self.server_name)

        self.base_url = config["url"]
        self.username = config["username"]
        self.token = config["token"]

        # Create SSL context that doesn't verify certificates (for internal servers)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def _run_kwadmin(self, command: str, args: List[str],
                     capture_output: bool = True) -> Dict[str, Any]:
        """
        Run a kwadmin command.

        Args:
            command: The kwadmin subcommand (e.g., 'create-project')
            args: Additional arguments for the command
            capture_output: Whether to capture and return output

        Returns:
            Dict with 'success', 'output', and optionally 'error' keys
        """
        cmd = ["kwadmin", "--url", self.base_url, command] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "output": result.stdout.strip() if result.stdout else "",
                    "command": " ".join(cmd)
                }
            else:
                return {
                    "success": False,
                    "output": result.stdout.strip() if result.stdout else "",
                    "error": result.stderr.strip() if result.stderr else f"Command failed with exit code {result.returncode}",
                    "command": " ".join(cmd)
                }

        except FileNotFoundError:
            return {
                "success": False,
                "error": "kwadmin not found. Please ensure Klocwork is installed and kwadmin is in your PATH.",
                "command": " ".join(cmd)
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timed out after 5 minutes",
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": " ".join(cmd)
            }

    def _api_request(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make a request to the Klocwork Web API.

        Args:
            action: The API action name
            params: Additional parameters for the request

        Returns:
            API response as dictionary
        """
        if not self.token:
            return {"error": "No Klocwork token configured. Set KLOCWORK_TOKEN or KLOCWORK_<SERVER>_TOKEN in ~/.config/atlassian/.env"}

        if not self.username:
            return {"error": "No Klocwork username configured. Set KLOCWORK_USERNAME or KLOCWORK_<SERVER>_USERNAME in ~/.config/atlassian/.env"}

        url = f"{self.base_url}/review/api"

        data = {
            "action": action,
            "user": self.username,
            "ltoken": self.token
        }
        if params:
            data.update(params)

        encoded_data = urllib.parse.urlencode(data).encode('utf-8')

        try:
            request = urllib.request.Request(url, data=encoded_data, method='POST')
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urllib.request.urlopen(request, context=self.ssl_context, timeout=60) as response:
                result = response.read().decode('utf-8')
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return {"response": result}

        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            return {"error": f"URL Error: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # Project Operations
    # =========================================================================

    def list_projects(self) -> Dict[str, Any]:
        """List all projects on the Klocwork server."""
        return self._run_kwadmin("list-projects", [])

    def create_project(self, project_name: str,
                       reference_project: str = None) -> Dict[str, Any]:
        """
        Create a new Klocwork project.

        Args:
            project_name: Name for the new project
            reference_project: Optional reference project to copy configuration from

        Returns:
            Result dictionary with success status and details
        """
        # First create the project
        result = self._run_kwadmin("create-project", [project_name])

        if not result.get("success"):
            return result

        project_url = f"{self.base_url}/review/insight-review.html#goto:project={project_name}"
        result["project_url"] = project_url
        result["project_name"] = project_name

        # If reference project specified, import its configuration
        if reference_project:
            import_result = self.import_config(reference_project, project_name)
            result["config_import"] = import_result

            if not import_result.get("success"):
                result["warning"] = "Project created but config import failed"

        return result

    def delete_project(self, project_name: str) -> Dict[str, Any]:
        """
        Delete a Klocwork project.

        Args:
            project_name: Name of the project to delete

        Returns:
            Result dictionary with success status
        """
        return self._run_kwadmin("delete-project", [project_name])

    def get_project_info(self, project_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a project.

        Args:
            project_name: Name of the project

        Returns:
            Project information
        """
        return self._api_request("project_info", {"project": project_name})

    # =========================================================================
    # Configuration Operations
    # =========================================================================

    def import_config(self, source_project: str, target_project: str) -> Dict[str, Any]:
        """
        Import configuration from one project to another.

        This copies all configuration including:
        - Checker settings
        - Ignore lists
        - Taxonomies
        - Custom checkers

        Args:
            source_project: Project to copy configuration from
            target_project: Project to copy configuration to

        Returns:
            Result dictionary with success status
        """
        return self._run_kwadmin("import-config", [source_project, target_project])

    def export_config(self, project_name: str, output_file: str) -> Dict[str, Any]:
        """
        Export project configuration to a file.

        Args:
            project_name: Project to export configuration from
            output_file: Path to save the configuration

        Returns:
            Result dictionary with success status
        """
        return self._run_kwadmin("export-config", [project_name, output_file])

    def load_config(self, project_name: str, config_file: str) -> Dict[str, Any]:
        """
        Load configuration from a file into a project.

        Args:
            project_name: Project to load configuration into
            config_file: Path to the configuration file

        Returns:
            Result dictionary with success status
        """
        return self._run_kwadmin("load-config", [project_name, config_file])

    # =========================================================================
    # Module Operations
    # =========================================================================

    def list_modules(self, project_name: str) -> Dict[str, Any]:
        """
        List all modules in a project.

        Args:
            project_name: Project to list modules from

        Returns:
            List of modules
        """
        return self._run_kwadmin("list-modules", [project_name])

    def create_module(self, project_name: str, module_name: str,
                      paths: List[str] = None) -> Dict[str, Any]:
        """
        Create a new module in a project.

        Args:
            project_name: Project to create module in
            module_name: Name for the new module
            paths: Optional list of file paths to include in the module

        Returns:
            Result dictionary with success status
        """
        args = [project_name, module_name]
        if paths:
            args.extend(paths)
        return self._run_kwadmin("create-module", args)

    def delete_module(self, project_name: str, module_name: str) -> Dict[str, Any]:
        """
        Delete a module from a project.

        Args:
            project_name: Project containing the module
            module_name: Name of the module to delete

        Returns:
            Result dictionary with success status
        """
        return self._run_kwadmin("delete-module", [project_name, module_name])

    def replicate_modules(self, source_project: str,
                          target_project: str) -> Dict[str, Any]:
        """
        Replicate all modules from one project to another.

        Args:
            source_project: Project to copy modules from
            target_project: Project to copy modules to

        Returns:
            Result dictionary with details of replicated modules
        """
        # First get modules from source
        source_modules = self.list_modules(source_project)

        if not source_modules.get("success"):
            return {
                "success": False,
                "error": f"Failed to list modules from {source_project}: {source_modules.get('error')}"
            }

        # Parse module list from output
        modules_output = source_modules.get("output", "")
        modules = [m.strip() for m in modules_output.split("\n") if m.strip()]

        if not modules:
            return {
                "success": True,
                "message": f"No modules found in {source_project}",
                "modules_copied": 0
            }

        # Copy each module (we need to get module details and recreate)
        results = []
        for module in modules:
            # Get module details from source
            module_info = self._run_kwadmin("get-module", [source_project, module])

            # Create module in target
            create_result = self._run_kwadmin("create-module", [target_project, module])
            results.append({
                "module": module,
                "success": create_result.get("success", False),
                "error": create_result.get("error") if not create_result.get("success") else None
            })

        successful = sum(1 for r in results if r["success"])

        return {
            "success": successful > 0,
            "source_project": source_project,
            "target_project": target_project,
            "modules_found": len(modules),
            "modules_copied": successful,
            "results": results
        }

    # =========================================================================
    # Permission Operations
    # =========================================================================

    def list_users(self, project_name: str) -> Dict[str, Any]:
        """
        List users with access to a project.

        Args:
            project_name: Project to list users for

        Returns:
            List of users and their roles
        """
        return self._run_kwadmin("list-users", [project_name])

    def add_user(self, project_name: str, username: str,
                 role: str = "user") -> Dict[str, Any]:
        """
        Add a user to a project with specified role.

        Args:
            project_name: Project to add user to
            username: Username to add
            role: Role to assign ('admin', 'user', 'viewer')

        Returns:
            Result dictionary with success status
        """
        return self._run_kwadmin("add-user", [project_name, username, "--role", role])

    def remove_user(self, project_name: str, username: str) -> Dict[str, Any]:
        """
        Remove a user from a project.

        Args:
            project_name: Project to remove user from
            username: Username to remove

        Returns:
            Result dictionary with success status
        """
        return self._run_kwadmin("remove-user", [project_name, username])

    def set_user_role(self, project_name: str, username: str,
                      role: str) -> Dict[str, Any]:
        """
        Change a user's role on a project.

        Args:
            project_name: Project to modify
            username: Username to change
            role: New role ('admin', 'user', 'viewer')

        Returns:
            Result dictionary with success status
        """
        return self._run_kwadmin("set-user-role", [project_name, username, role])

    # =========================================================================
    # Build Operations
    # =========================================================================

    def list_builds(self, project_name: str, limit: int = 10) -> Dict[str, Any]:
        """
        List recent builds for a project.

        Args:
            project_name: Project to list builds for
            limit: Maximum number of builds to return

        Returns:
            List of builds
        """
        return self._run_kwadmin("list-builds", [project_name, "--limit", str(limit)])

    def get_build_info(self, project_name: str, build_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific build.

        Args:
            project_name: Project containing the build
            build_id: Build ID to get info for

        Returns:
            Build information
        """
        return self._run_kwadmin("get-build", [project_name, build_id])

    # =========================================================================
    # Issues/Defects Operations
    # =========================================================================

    def search_issues(self, project_name: str, query: str = None,
                      status: str = None, severity: str = None,
                      limit: int = 100) -> Dict[str, Any]:
        """
        Search for issues in a project.

        Args:
            project_name: Project to search
            query: Search query string
            status: Filter by status (e.g., 'Analyze', 'Fix', 'Ignore')
            severity: Filter by severity (e.g., 'Critical', 'Error', 'Warning')
            limit: Maximum number of results

        Returns:
            List of matching issues
        """
        params = {
            "project": project_name,
            "limit": str(limit)
        }
        if query:
            params["query"] = query
        if status:
            params["status"] = status
        if severity:
            params["severity"] = severity

        return self._api_request("search", params)

    def get_issue(self, project_name: str, issue_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific issue.

        Args:
            project_name: Project containing the issue
            issue_id: Issue ID

        Returns:
            Issue details
        """
        return self._api_request("issue_details", {
            "project": project_name,
            "id": issue_id
        })

    def update_issue_status(self, project_name: str, issue_id: str,
                            status: str, comment: str = None) -> Dict[str, Any]:
        """
        Update the status of an issue.

        Args:
            project_name: Project containing the issue
            issue_id: Issue ID to update
            status: New status ('Analyze', 'Fix', 'Ignore', 'Not a Problem', 'Defer')
            comment: Optional comment explaining the status change

        Returns:
            Result dictionary with success status
        """
        params = {
            "project": project_name,
            "id": issue_id,
            "status": status
        }
        if comment:
            params["comment"] = comment

        return self._api_request("update_status", params)

    # =========================================================================
    # Server Operations
    # =========================================================================

    def get_server_info(self) -> Dict[str, Any]:
        """Get information about the Klocwork server."""
        return self._run_kwadmin("version", [])

    def get_config(self) -> Dict[str, Any]:
        """Get current Klocwork configuration."""
        return {
            "server": self.server_name,
            "url": self.base_url,
            "username": self.username,
            "token_configured": bool(self.token)
        }

    def list_servers(self) -> Dict[str, Any]:
        """List all configured Klocwork servers."""
        servers = list_configured_servers()
        default = os.environ.get("KLOCWORK_DEFAULT_SERVER", DEFAULT_SERVER)
        return {
            "servers": servers,
            "default_server": default,
            "current_server": self.server_name
        }
