#!/usr/bin/env python3
"""
Jenkins MCP Server - Provides Jenkins tools for Claude (read-only).

Usage:
    python mcp_server.py

Environment Variables:
    JENKINS_CONFIG - Path to .env file (default: ~/.config/jenkins-mcp/.env)
"""

import traceback
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from jenkins_client import get_jenkins_client, get_available_jenkins_servers

# Create the MCP server
server = Server("jenkins")


# ==================== Formatters ====================

def format_job(job: dict) -> str:
    """Format Jenkins job for display."""
    output = []
    output.append(f"# {job.get('displayName', job.get('name', 'Unknown Job'))}")
    output.append("")

    color_status = {
        'blue': 'Success',
        'red': 'Failed',
        'yellow': 'Unstable',
        'grey': 'Not Built',
        'disabled': 'Disabled',
        'aborted': 'Aborted',
        'notbuilt': 'Not Built',
    }
    color = job.get('color', 'grey').replace('_anime', '')
    is_building = '_anime' in job.get('color', '')

    status = color_status.get(color, color)
    if is_building:
        status += ' (Building...)'

    output.append(f"**Status:** {status}")
    output.append(f"**URL:** {job.get('url', 'N/A')}")

    if job.get('description'):
        output.append(f"**Description:** {job.get('description')}")

    if job.get('lastBuild'):
        lb = job['lastBuild']
        output.append("")
        output.append("## Last Build")
        output.append(f"- **Number:** #{lb.get('number')}")
        output.append(f"- **URL:** {lb.get('url')}")

    if job.get('healthReport'):
        output.append("")
        output.append("## Health")
        for health in job['healthReport']:
            output.append(f"- {health.get('description', 'N/A')}")

    return '\n'.join(output)


def format_build(build: dict) -> str:
    """Format Jenkins build for display."""
    output = []
    output.append(f"# Build #{build.get('number', '?')}")
    output.append("")

    result = build.get('result', 'IN PROGRESS')
    result_emoji = {
        'SUCCESS': '[SUCCESS]',
        'FAILURE': '[FAILURE]',
        'UNSTABLE': '[UNSTABLE]',
        'ABORTED': '[ABORTED]',
        'IN PROGRESS': '[IN PROGRESS]',
    }

    output.append(f"**Result:** {result_emoji.get(result, '[?]')} {result}")
    output.append(f"**Building:** {'Yes' if build.get('building') else 'No'}")

    if build.get('timestamp'):
        ts = datetime.fromtimestamp(build['timestamp'] / 1000)
        output.append(f"**Started:** {ts.strftime('%Y-%m-%d %H:%M:%S')}")

    if build.get('duration'):
        duration_sec = build['duration'] / 1000
        mins, secs = divmod(int(duration_sec), 60)
        output.append(f"**Duration:** {mins}m {secs}s")

    output.append(f"**URL:** {build.get('url', 'N/A')}")

    if build.get('actions'):
        for action in build['actions']:
            if action and action.get('_class', '').endswith('ParametersAction'):
                output.append("")
                output.append("## Parameters")
                for param in action.get('parameters', []):
                    output.append(f"- **{param.get('name')}:** {param.get('value')}")

    if build.get('changeSet', {}).get('items'):
        output.append("")
        output.append("## Changes")
        for change in build['changeSet']['items'][:10]:
            msg = change.get('msg', change.get('comment', 'No message'))
            author = change.get('author', {}).get('fullName', 'Unknown')
            output.append(f"- {msg} ({author})")

    return '\n'.join(output)


def format_jobs(jobs: list) -> str:
    """Format Jenkins job list for display."""
    if not jobs:
        return "No jobs found."

    output = ["# Jenkins Jobs", ""]

    color_status = {
        'blue': '[OK]',
        'red': '[FAIL]',
        'yellow': '[WARN]',
        'grey': '[--]',
        'disabled': '[OFF]',
        'notbuilt': '[--]',
    }

    for job in jobs:
        color = job.get('color', 'grey').replace('_anime', '')
        status = color_status.get(color, '[?]')
        building = ' (building)' if '_anime' in job.get('color', '') else ''

        name = job.get('name', 'Unknown')
        last_build = job.get('lastBuild')
        build_info = f" - #{last_build['number']}" if last_build else ""

        output.append(f"- {status} **{name}**{build_info}{building}")

    return '\n'.join(output)


def format_queue(queue: list) -> str:
    """Format Jenkins queue for display."""
    if not queue:
        return "Build queue is empty."

    output = ["# Build Queue", ""]

    for item in queue:
        task = item.get('task', {})
        output.append(f"- **{task.get('name', 'Unknown')}**")
        if item.get('why'):
            output.append(f"  - Waiting: {item['why']}")
        if item.get('inQueueSince'):
            ts = datetime.fromtimestamp(item['inQueueSince'] / 1000)
            output.append(f"  - Queued since: {ts.strftime('%Y-%m-%d %H:%M:%S')}")

    return '\n'.join(output)


def format_nodes(nodes: list) -> str:
    """Format Jenkins nodes for display."""
    if not nodes:
        return "No nodes found."

    output = ["# Jenkins Nodes", ""]

    for node in nodes:
        name = node.get('displayName', 'Unknown')
        offline = node.get('offline', False)
        status = '[OFFLINE]' if offline else '[ONLINE]'

        output.append(f"## {name}")
        output.append(f"- **Status:** {status}")

        if node.get('offlineCauseReason'):
            output.append(f"- **Offline Reason:** {node['offlineCauseReason']}")

        executors = node.get('numExecutors', 0)
        output.append(f"- **Executors:** {executors}")
        output.append("")

    return '\n'.join(output)


def format_job_config(config: dict, job_name: str) -> str:
    """Format Jenkins job configuration for display."""
    output = []
    output.append(f"# Job Configuration: {job_name}")
    output.append("")

    job_type_map = {
        'project': 'Freestyle Project',
        'flow-definition': 'Pipeline',
        'maven2-moduleset': 'Maven Project',
        'matrix-project': 'Multi-configuration Project',
    }
    job_type = config.get('job_type', 'Unknown')
    friendly_type = job_type_map.get(job_type, job_type)
    output.append(f"**Job Type:** {friendly_type}")

    if config.get('disabled'):
        output.append("**Status:** Disabled")
    else:
        output.append("**Status:** Enabled")

    if config.get('description'):
        output.append(f"**Description:** {config['description']}")

    if config.get('parameters'):
        output.append("")
        output.append("## Build Parameters")
        for param in config['parameters']:
            param_type = param.get('type', 'Unknown').replace('ParameterDefinition', '')
            output.append(f"- **{param.get('name', 'unnamed')}** ({param_type})")
            if param.get('description'):
                output.append(f"  - Description: {param['description']}")
            if param.get('default'):
                output.append(f"  - Default: `{param['default']}`")

    if config.get('scm'):
        output.append("")
        output.append("## Source Code Management")
        scm = config['scm']
        scm_type = scm.get('type', '').split('.')[-1]
        output.append(f"**Type:** {scm_type}")
        if scm.get('url'):
            output.append(f"**Repository:** {scm['url']}")
        if scm.get('branches'):
            output.append(f"**Branches:** {', '.join(scm['branches'])}")

    if config.get('triggers'):
        output.append("")
        output.append("## Build Triggers")
        trigger_names = {
            'SCMTrigger': 'Poll SCM',
            'TimerTrigger': 'Build periodically',
            'GitHubPushTrigger': 'GitHub hook trigger',
        }
        for trigger in config['triggers']:
            trigger_type = trigger.get('type', '').split('.')[-1]
            friendly_name = trigger_names.get(trigger_type, trigger_type)
            output.append(f"- **{friendly_name}**")
            if trigger.get('schedule'):
                output.append(f"  - Schedule: `{trigger['schedule']}`")

    if config.get('builders'):
        output.append("")
        output.append("## Build Steps")
        builder_names = {
            'Shell': 'Execute shell',
            'BatchFile': 'Execute Windows batch command',
        }
        for i, builder in enumerate(config['builders'], 1):
            builder_type = builder.get('type', 'Unknown')
            friendly_name = builder_names.get(builder_type, builder_type)
            output.append(f"{i}. **{friendly_name}**")
            if builder.get('command'):
                cmd_preview = builder['command'][:200]
                if len(builder['command']) > 200:
                    cmd_preview += '...'
                output.append(f"   ```bash\n   {cmd_preview}\n   ```")

    if config.get('pipeline'):
        output.append("")
        output.append("## Pipeline Definition")
        pipeline = config['pipeline']
        if 'CpsFlowDefinition' in pipeline.get('type', ''):
            output.append("**Type:** Pipeline script (inline)")
        elif 'CpsScmFlowDefinition' in pipeline.get('type', ''):
            output.append("**Type:** Pipeline script from SCM")
        if pipeline.get('script'):
            script_preview = pipeline['script'][:500]
            if len(pipeline['script']) > 500:
                script_preview += '\n// ... (truncated)'
            output.append(f"```groovy\n{script_preview}\n```")

    return '\n'.join(output)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Jenkins tools."""
    return [
        Tool(
            name="jenkins_list_servers",
            description="List available Jenkins servers that are configured.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="jenkins_get_job",
            description="Get Jenkins job details including status, last build info, and health report.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name (use folder/job for jobs in folders)"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name"]
            }
        ),
        Tool(
            name="jenkins_list_jobs",
            description="List Jenkins jobs. Optionally specify a folder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Folder path (optional)"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": []
            }
        ),
        Tool(
            name="jenkins_get_build",
            description="Get details for a specific Jenkins build.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "build_number": {"type": "integer", "description": "Build number"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name", "build_number"]
            }
        ),
        Tool(
            name="jenkins_get_build_log",
            description="Get console output/log for a Jenkins build.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "build_number": {"type": "integer", "description": "Build number"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name", "build_number"]
            }
        ),
        Tool(
            name="jenkins_get_queue",
            description="Get the Jenkins build queue showing pending builds.",
            inputSchema={
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": []
            }
        ),
        Tool(
            name="jenkins_get_nodes",
            description="Get status of Jenkins build agents/nodes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": []
            }
        ),
        Tool(
            name="jenkins_get_job_config",
            description="Get Jenkins job configuration (SCM, triggers, parameters, build steps).",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "raw_xml": {"type": "boolean", "description": "Return raw XML config", "default": False},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        result = ""

        if name == "jenkins_list_servers":
            servers = get_available_jenkins_servers()
            if servers:
                output = ["# Available Jenkins Servers", ""]
                for srv in servers:
                    output.append(f"- **{srv}**")
                output.append("")
                output.append("Use the `server` parameter to specify which server to query.")
                result = '\n'.join(output)
            else:
                result = "No Jenkins servers configured."

        elif name == "jenkins_get_job":
            client = get_jenkins_client(arguments.get("server"))
            job = client.get_job(arguments["job_name"])
            result = format_job(job)

        elif name == "jenkins_list_jobs":
            client = get_jenkins_client(arguments.get("server"))
            jobs = client.list_jobs(arguments.get("folder"))
            result = format_jobs(jobs)

        elif name == "jenkins_get_build":
            client = get_jenkins_client(arguments.get("server"))
            build = client.get_build(arguments["job_name"], arguments["build_number"])
            result = format_build(build)

        elif name == "jenkins_get_build_log":
            client = get_jenkins_client(arguments.get("server"))
            log = client.get_build_log(arguments["job_name"], arguments["build_number"])
            if len(log) > 50000:
                log = log[-50000:]
                log = "... (truncated, showing last 50000 characters)\n\n" + log
            result = f"# Build Log: {arguments['job_name']} #{arguments['build_number']}\n\n```\n{log}\n```"

        elif name == "jenkins_get_queue":
            client = get_jenkins_client(arguments.get("server"))
            queue = client.get_queue()
            result = format_queue(queue)

        elif name == "jenkins_get_nodes":
            client = get_jenkins_client(arguments.get("server"))
            nodes = client.get_nodes()
            result = format_nodes(nodes)

        elif name == "jenkins_get_job_config":
            client = get_jenkins_client(arguments.get("server"))
            if arguments.get("raw_xml"):
                xml_config = client.get_job_config(arguments["job_name"])
                result = f"# Job Configuration: {arguments['job_name']}\n\n```xml\n{xml_config}\n```"
            else:
                config = client.get_job_config_parsed(arguments["job_name"])
                result = format_job_config(config, arguments["job_name"])

        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        error_msg = f"Error executing {name}: {str(e)}\n{traceback.format_exc()}"
        return [TextContent(type="text", text=error_msg)]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
