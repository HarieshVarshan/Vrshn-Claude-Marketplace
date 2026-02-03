"""
Klocwork API client for project management operations.

Uses kwadmin CLI tool and Klocwork Web API for administrative operations.
Requires:
- kwadmin in PATH (from Klocwork installation)
- Valid ltoken file (created via kwauth)
"""

import os
import subprocess
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
from pathlib import Path
from typing import Dict, Any, List, Optional


# Server configurations
KLOCWORK_SERVERS = {
    "dallas": "https://klocwork.itg.ti.com:8090",
    "india": "https://klocworkweb.india.ti.com:8095"
}

DEFAULT_SERVER = "dallas"


class KlocworkClient:
    """Client for Klocwork administrative operations."""

    def __init__(self, server: str = None):
        """
        Initialize Klocwork client.

        Args:
            server: Server name ('dallas' or 'india') or full URL.
                   Defaults to dallas if not specified.
        """
        self.server_name = server or DEFAULT_SERVER

        if self.server_name.startswith("http"):
            self.base_url = self.server_name.rstrip("/")
            self.server_name = "custom"
        else:
            self.base_url = KLOCWORK_SERVERS.get(
                self.server_name.lower(),
                KLOCWORK_SERVERS[DEFAULT_SERVER]
            )

        self.ltoken = self._get_ltoken()

        # Create SSL context that doesn't verify certificates (for internal servers)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def _get_ltoken(self) -> Optional[str]:
        """Get the ltoken from the user's home directory."""
        ltoken_path = Path.home() / ".klocwork" / "ltoken"
        if ltoken_path.exists():
            # ltoken file format: host;port;user;token
            with open(ltoken_path, "r") as f:
                for line in f:
                    parts = line.strip().split(";")
                    if len(parts) >= 4:
                        # Return the token part
                        return parts[3]
        return None

    def _get_ltoken_for_server(self) -> Optional[str]:
        """Get ltoken specifically for the configured server."""
        ltoken_path = Path.home() / ".klocwork" / "ltoken"
        if not ltoken_path.exists():
            return None

        # Parse server URL to get host and port
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        target_host = parsed.hostname
        target_port = str(parsed.port) if parsed.port else "8090"

        with open(ltoken_path, "r") as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) >= 4:
                    host, port, user, token = parts[0], parts[1], parts[2], parts[3]
                    if host == target_host and port == target_port:
                        return token

        # Fallback to first token if no match
        return self.ltoken

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
        token = self._get_ltoken_for_server()
        if not token:
            return {"error": "No ltoken found. Run 'kwauth --url <server_url>' to authenticate."}

        url = f"{self.base_url}/review/api"

        data = {
            "action": action,
            "user": self._get_username(),
            "ltoken": token
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

    def _get_username(self) -> Optional[str]:
        """Get username from ltoken file."""
        ltoken_path = Path.home() / ".klocwork" / "ltoken"
        if ltoken_path.exists():
            from urllib.parse import urlparse
            parsed = urlparse(self.base_url)
            target_host = parsed.hostname
            target_port = str(parsed.port) if parsed.port else "8090"

            with open(ltoken_path, "r") as f:
                for line in f:
                    parts = line.strip().split(";")
                    if len(parts) >= 4:
                        host, port, user, token = parts[0], parts[1], parts[2], parts[3]
                        if host == target_host and port == target_port:
                            return user
                # Return first user if no match
                f.seek(0)
                for line in f:
                    parts = line.strip().split(";")
                    if len(parts) >= 3:
                        return parts[2]
        return os.environ.get("USER", os.environ.get("USERNAME", "unknown"))

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

    def list_servers(self) -> Dict[str, Any]:
        """List all configured Klocwork servers."""
        return {
            "servers": [
                {"name": name, "url": url}
                for name, url in KLOCWORK_SERVERS.items()
            ],
            "current_server": {
                "name": self.server_name,
                "url": self.base_url
            }
        }
