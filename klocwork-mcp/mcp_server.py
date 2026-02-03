#!/usr/bin/env python3
"""
Klocwork MCP Server

MCP server for Klocwork project management operations.
Supports project creation, configuration import, module replication,
and permission management.
"""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)

from klocwork_client import KlocworkClient

# Load environment variables
# Primary: shared atlassian config location
# Secondary: klocwork-mcp specific config
primary_env = Path.home() / ".config" / "atlassian" / ".env"
secondary_env = Path.home() / ".config" / "klocwork-mcp" / ".env"

if primary_env.exists():
    load_dotenv(primary_env)
if secondary_env.exists():
    load_dotenv(secondary_env, override=True)

# Initialize the MCP server
server = Server("klocwork-mcp")

def get_client(server: str = None) -> KlocworkClient:
    """Get a Klocwork client for the specified server."""
    return KlocworkClient(server=server)


def format_result(result: dict, title: str = None) -> str:
    """Format a result dictionary as markdown."""
    lines = []

    if title:
        lines.append(f"## {title}")
        lines.append("")

    if result.get("success"):
        lines.append("✓ **Success**")
    elif "error" in result:
        lines.append(f"✗ **Error:** {result['error']}")

    if result.get("output"):
        lines.append("")
        lines.append("### Output")
        lines.append("```")
        lines.append(result["output"])
        lines.append("```")

    if result.get("project_url"):
        lines.append("")
        lines.append(f"**Project URL:** {result['project_url']}")

    if result.get("config_import"):
        import_result = result["config_import"]
        lines.append("")
        lines.append("### Configuration Import")
        if import_result.get("success"):
            lines.append("✓ Configuration imported successfully")
        else:
            lines.append(f"✗ Import failed: {import_result.get('error', 'Unknown error')}")

    if result.get("warning"):
        lines.append("")
        lines.append(f"⚠ **Warning:** {result['warning']}")

    return "\n".join(lines)


SERVER_PARAM = {
    "type": "string",
    "description": "Server name ('india' or 'stage'). Defaults to KLOCWORK_DEFAULT_SERVER."
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Klocwork tools."""
    return [
        # Server Operations
        Tool(
            name="klocwork_list_servers",
            description="List all configured Klocwork servers",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="klocwork_get_config",
            description="Get current Klocwork server configuration",
            inputSchema={
                "type": "object",
                "properties": {
                    "server": SERVER_PARAM
                },
                "required": []
            }
        ),
        Tool(
            name="klocwork_get_server_info",
            description="Get version and information about a Klocwork server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server": SERVER_PARAM
                },
                "required": []
            }
        ),

        # Project Operations
        Tool(
            name="klocwork_list_projects",
            description="List all projects on a Klocwork server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server": SERVER_PARAM
                },
                "required": []
            }
        ),
        Tool(
            name="klocwork_create_project",
            description="Create a new Klocwork project. Optionally import configuration from a reference project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name for the new project (e.g., 'OTP_KW_F29H85X')"
                    },
                    "reference_project": {
                        "type": "string",
                        "description": "Optional reference project to copy configuration from"
                    },
                    "server": SERVER_PARAM
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="klocwork_delete_project",
            description="Delete a Klocwork project. Use with caution!",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project to delete"
                    }
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="klocwork_get_project_info",
            description="Get detailed information about a Klocwork project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    }
                },
                "required": ["project_name"]
            }
        ),

        # Configuration Operations
        Tool(
            name="klocwork_import_config",
            description="Import configuration (checker settings, ignore lists, taxonomies) from one project to another",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_project": {
                        "type": "string",
                        "description": "Project to copy configuration from"
                    },
                    "target_project": {
                        "type": "string",
                        "description": "Project to copy configuration to"
                    }
                },
                "required": ["source_project", "target_project"]
            }
        ),
        Tool(
            name="klocwork_export_config",
            description="Export project configuration to a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to export configuration from"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Path to save the configuration file"
                    }
                },
                "required": ["project_name", "output_file"]
            }
        ),
        Tool(
            name="klocwork_load_config",
            description="Load configuration from a file into a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to load configuration into"
                    },
                    "config_file": {
                        "type": "string",
                        "description": "Path to the configuration file"
                    }
                },
                "required": ["project_name", "config_file"]
            }
        ),

        # Module Operations
        Tool(
            name="klocwork_list_modules",
            description="List all modules in a Klocwork project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to list modules from"
                    }
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="klocwork_create_module",
            description="Create a new module in a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to create module in"
                    },
                    "module_name": {
                        "type": "string",
                        "description": "Name for the new module"
                    },
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of file paths to include in the module"
                    }
                },
                "required": ["project_name", "module_name"]
            }
        ),
        Tool(
            name="klocwork_delete_module",
            description="Delete a module from a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project containing the module"
                    },
                    "module_name": {
                        "type": "string",
                        "description": "Name of the module to delete"
                    }
                },
                "required": ["project_name", "module_name"]
            }
        ),
        Tool(
            name="klocwork_replicate_modules",
            description="Copy all modules from one project to another",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_project": {
                        "type": "string",
                        "description": "Project to copy modules from"
                    },
                    "target_project": {
                        "type": "string",
                        "description": "Project to copy modules to"
                    }
                },
                "required": ["source_project", "target_project"]
            }
        ),

        # Permission Operations
        Tool(
            name="klocwork_list_users",
            description="List users with access to a project and their roles",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to list users for"
                    }
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="klocwork_add_user",
            description="Add a user to a project with specified role",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to add user to"
                    },
                    "username": {
                        "type": "string",
                        "description": "Username to add"
                    },
                    "role": {
                        "type": "string",
                        "description": "Role to assign ('admin', 'user', 'viewer'). Defaults to 'user'.",
                        "enum": ["admin", "user", "viewer"]
                    }
                },
                "required": ["project_name", "username"]
            }
        ),
        Tool(
            name="klocwork_remove_user",
            description="Remove a user from a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to remove user from"
                    },
                    "username": {
                        "type": "string",
                        "description": "Username to remove"
                    }
                },
                "required": ["project_name", "username"]
            }
        ),
        Tool(
            name="klocwork_set_user_role",
            description="Change a user's role on a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to modify"
                    },
                    "username": {
                        "type": "string",
                        "description": "Username to change"
                    },
                    "role": {
                        "type": "string",
                        "description": "New role ('admin', 'user', 'viewer')",
                        "enum": ["admin", "user", "viewer"]
                    }
                },
                "required": ["project_name", "username", "role"]
            }
        ),

        # Build Operations
        Tool(
            name="klocwork_list_builds",
            description="List recent builds for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to list builds for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of builds to return (default: 10)"
                    }
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="klocwork_get_build_info",
            description="Get detailed information about a specific build",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project containing the build"
                    },
                    "build_id": {
                        "type": "string",
                        "description": "Build ID to get info for"
                    }
                },
                "required": ["project_name", "build_id"]
            }
        ),

        # Issue Operations
        Tool(
            name="klocwork_search_issues",
            description="Search for issues/defects in a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project to search"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status (e.g., 'Analyze', 'Fix', 'Ignore')"
                    },
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity (e.g., 'Critical', 'Error', 'Warning')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 100)"
                    }
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="klocwork_get_issue",
            description="Get detailed information about a specific issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project containing the issue"
                    },
                    "issue_id": {
                        "type": "string",
                        "description": "Issue ID"
                    }
                },
                "required": ["project_name", "issue_id"]
            }
        ),
        Tool(
            name="klocwork_update_issue_status",
            description="Update the status of an issue (triage)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project containing the issue"
                    },
                    "issue_id": {
                        "type": "string",
                        "description": "Issue ID to update"
                    },
                    "status": {
                        "type": "string",
                        "description": "New status ('Analyze', 'Fix', 'Ignore', 'Not a Problem', 'Defer')",
                        "enum": ["Analyze", "Fix", "Ignore", "Not a Problem", "Defer"]
                    },
                    "comment": {
                        "type": "string",
                        "description": "Optional comment explaining the status change"
                    }
                },
                "required": ["project_name", "issue_id", "status"]
            }
        ),

        # Raw API (Fallback)
        Tool(
            name="klocwork_raw_kwadmin",
            description="Execute a raw kwadmin command for operations not covered by other tools",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The kwadmin subcommand to run (e.g., 'list-projects')"
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Arguments for the command"
                    }
                },
                "required": ["command"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        # Extract server parameter if provided
        server_name = arguments.pop("server", None)
        client = get_client(server_name)

        # Server Operations
        if name == "klocwork_list_servers":
            result = client.list_servers()
            lines = ["## Configured Klocwork Servers", ""]
            for srv in result.get("servers", []):
                lines.append(f"- **{srv['name']}**: {srv['url']} (user: {srv['username']})")
            lines.append("")
            lines.append(f"**Default server:** {result.get('default_server', 'N/A')}")
            lines.append(f"**Current server:** {result.get('current_server', 'N/A')}")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "klocwork_get_config":
            result = client.get_config()
            lines = ["## Klocwork Configuration", ""]
            lines.append(f"**Server:** {result['server']}")
            lines.append(f"**URL:** {result['url']}")
            lines.append(f"**Username:** {result['username']}")
            lines.append(f"**Token configured:** {'Yes' if result['token_configured'] else 'No'}")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "klocwork_get_server_info":
            result = client.get_server_info()
            return [TextContent(type="text", text=format_result(result, "Klocwork Server Info"))]

        # Project Operations
        elif name == "klocwork_list_projects":
            result = client.list_projects()
            return [TextContent(type="text", text=format_result(result, "Klocwork Projects"))]

        elif name == "klocwork_create_project":
            project_name = arguments["project_name"]
            reference_project = arguments.get("reference_project")
            result = client.create_project(project_name, reference_project)
            return [TextContent(type="text", text=format_result(result, f"Create Project: {project_name}"))]

        elif name == "klocwork_delete_project":
            project_name = arguments["project_name"]
            result = client.delete_project(project_name)
            return [TextContent(type="text", text=format_result(result, f"Delete Project: {project_name}"))]

        elif name == "klocwork_get_project_info":
            project_name = arguments["project_name"]
            result = client.get_project_info(project_name)
            text = f"## Project: {project_name}\n\n```json\n{json.dumps(result, indent=2)}\n```"
            return [TextContent(type="text", text=text)]

        # Configuration Operations
        elif name == "klocwork_import_config":
            source = arguments["source_project"]
            target = arguments["target_project"]
            result = client.import_config(source, target)
            return [TextContent(type="text", text=format_result(result, f"Import Config: {source} → {target}"))]

        elif name == "klocwork_export_config":
            project_name = arguments["project_name"]
            output_file = arguments["output_file"]
            result = client.export_config(project_name, output_file)
            return [TextContent(type="text", text=format_result(result, f"Export Config: {project_name}"))]

        elif name == "klocwork_load_config":
            project_name = arguments["project_name"]
            config_file = arguments["config_file"]
            result = client.load_config(project_name, config_file)
            return [TextContent(type="text", text=format_result(result, f"Load Config: {project_name}"))]

        # Module Operations
        elif name == "klocwork_list_modules":
            project_name = arguments["project_name"]
            result = client.list_modules(project_name)
            return [TextContent(type="text", text=format_result(result, f"Modules in {project_name}"))]

        elif name == "klocwork_create_module":
            project_name = arguments["project_name"]
            module_name = arguments["module_name"]
            paths = arguments.get("paths")
            result = client.create_module(project_name, module_name, paths)
            return [TextContent(type="text", text=format_result(result, f"Create Module: {module_name}"))]

        elif name == "klocwork_delete_module":
            project_name = arguments["project_name"]
            module_name = arguments["module_name"]
            result = client.delete_module(project_name, module_name)
            return [TextContent(type="text", text=format_result(result, f"Delete Module: {module_name}"))]

        elif name == "klocwork_replicate_modules":
            source = arguments["source_project"]
            target = arguments["target_project"]
            result = client.replicate_modules(source, target)

            lines = [f"## Replicate Modules: {source} → {target}", ""]
            if result.get("success"):
                lines.append(f"✓ **Modules copied:** {result.get('modules_copied', 0)} of {result.get('modules_found', 0)}")
            else:
                lines.append(f"✗ **Error:** {result.get('error', 'Unknown error')}")

            if result.get("results"):
                lines.append("")
                lines.append("### Details")
                for r in result["results"]:
                    status = "✓" if r["success"] else "✗"
                    error_msg = f" - {r['error']}" if r.get("error") else ""
                    lines.append(f"- {status} {r['module']}{error_msg}")

            return [TextContent(type="text", text="\n".join(lines))]

        # Permission Operations
        elif name == "klocwork_list_users":
            project_name = arguments["project_name"]
            result = client.list_users(project_name)
            return [TextContent(type="text", text=format_result(result, f"Users in {project_name}"))]

        elif name == "klocwork_add_user":
            project_name = arguments["project_name"]
            username = arguments["username"]
            role = arguments.get("role", "user")
            result = client.add_user(project_name, username, role)
            return [TextContent(type="text", text=format_result(result, f"Add User: {username} to {project_name}"))]

        elif name == "klocwork_remove_user":
            project_name = arguments["project_name"]
            username = arguments["username"]
            result = client.remove_user(project_name, username)
            return [TextContent(type="text", text=format_result(result, f"Remove User: {username}"))]

        elif name == "klocwork_set_user_role":
            project_name = arguments["project_name"]
            username = arguments["username"]
            role = arguments["role"]
            result = client.set_user_role(project_name, username, role)
            return [TextContent(type="text", text=format_result(result, f"Set Role: {username} → {role}"))]

        # Build Operations
        elif name == "klocwork_list_builds":
            project_name = arguments["project_name"]
            limit = arguments.get("limit", 10)
            result = client.list_builds(project_name, limit)
            return [TextContent(type="text", text=format_result(result, f"Builds for {project_name}"))]

        elif name == "klocwork_get_build_info":
            project_name = arguments["project_name"]
            build_id = arguments["build_id"]
            result = client.get_build_info(project_name, build_id)
            return [TextContent(type="text", text=format_result(result, f"Build {build_id}"))]

        # Issue Operations
        elif name == "klocwork_search_issues":
            project_name = arguments["project_name"]
            query = arguments.get("query")
            status = arguments.get("status")
            severity = arguments.get("severity")
            limit = arguments.get("limit", 100)
            result = client.search_issues(project_name, query, status, severity, limit)
            text = f"## Issues in {project_name}\n\n```json\n{json.dumps(result, indent=2)}\n```"
            return [TextContent(type="text", text=text)]

        elif name == "klocwork_get_issue":
            project_name = arguments["project_name"]
            issue_id = arguments["issue_id"]
            result = client.get_issue(project_name, issue_id)
            text = f"## Issue {issue_id}\n\n```json\n{json.dumps(result, indent=2)}\n```"
            return [TextContent(type="text", text=text)]

        elif name == "klocwork_update_issue_status":
            project_name = arguments["project_name"]
            issue_id = arguments["issue_id"]
            status = arguments["status"]
            comment = arguments.get("comment")
            result = client.update_issue_status(project_name, issue_id, status, comment)
            return [TextContent(type="text", text=format_result(result, f"Update Issue {issue_id}"))]

        # Raw kwadmin
        elif name == "klocwork_raw_kwadmin":
            command = arguments["command"]
            args = arguments.get("args", [])
            result = client._run_kwadmin(command, args)
            return [TextContent(type="text", text=format_result(result, f"kwadmin {command}"))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
