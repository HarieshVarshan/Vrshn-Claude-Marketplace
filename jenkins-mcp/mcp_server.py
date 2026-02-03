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

        # ========== Build Details ==========
        Tool(
            name="jenkins_get_last_build",
            description="Get the most recent build for a job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name"]
            }
        ),
        Tool(
            name="jenkins_list_builds",
            description="List builds for a job with summary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "limit": {"type": "integer", "description": "Max builds to return", "default": 25},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name"]
            }
        ),
        Tool(
            name="jenkins_get_build_test_results",
            description="Get test results (JUnit) for a build.",
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
            name="jenkins_get_build_artifacts",
            description="List artifacts from a build.",
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
            name="jenkins_download_artifact",
            description="Download an artifact from a build.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "build_number": {"type": "integer", "description": "Build number"},
                    "artifact_path": {"type": "string", "description": "Relative path of artifact"},
                    "download_path": {"type": "string", "description": "Local path to save file"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name", "build_number", "artifact_path", "download_path"]
            }
        ),

        # ========== Views ==========
        Tool(
            name="jenkins_list_views",
            description="List all Jenkins views.",
            inputSchema={
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": []
            }
        ),
        Tool(
            name="jenkins_get_view",
            description="Get jobs in a specific view.",
            inputSchema={
                "type": "object",
                "properties": {
                    "view_name": {"type": "string", "description": "View name"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["view_name"]
            }
        ),

        # ========== Node Details ==========
        Tool(
            name="jenkins_get_node_details",
            description="Get detailed info about a specific node/agent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_name": {"type": "string", "description": "Node name (use 'master' for built-in node)"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["node_name"]
            }
        ),

        # ========== System Info ==========
        Tool(
            name="jenkins_get_system_info",
            description="Get Jenkins system information (version, mode, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": []
            }
        ),
        Tool(
            name="jenkins_get_plugins",
            description="List installed Jenkins plugins.",
            inputSchema={
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": []
            }
        ),
        Tool(
            name="jenkins_get_credentials_list",
            description="List credential IDs (metadata only, not secrets).",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Credential domain", "default": "_"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": []
            }
        ),

        # ========== Build Operations (Write) ==========
        Tool(
            name="jenkins_trigger_build",
            description="Trigger a build for a job (with optional parameters).",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "parameters": {"type": "object", "description": "Build parameters as key-value pairs"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name"]
            }
        ),
        Tool(
            name="jenkins_stop_build",
            description="Stop/abort a running build.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "build_number": {"type": "integer", "description": "Build number to stop"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name", "build_number"]
            }
        ),

        # ========== Job Operations (Write) ==========
        Tool(
            name="jenkins_enable_job",
            description="Enable a disabled job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name"]
            }
        ),
        Tool(
            name="jenkins_disable_job",
            description="Disable a job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name"]
            }
        ),
        Tool(
            name="jenkins_delete_job",
            description="Delete a job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name"]
            }
        ),
        Tool(
            name="jenkins_create_job",
            description="Create a new job from XML config.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Name for the new job"},
                    "config_xml": {"type": "string", "description": "Job XML configuration"},
                    "folder": {"type": "string", "description": "Folder to create job in (optional)"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name", "config_xml"]
            }
        ),
        Tool(
            name="jenkins_copy_job",
            description="Copy an existing job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_job": {"type": "string", "description": "Source job name"},
                    "new_job_name": {"type": "string", "description": "Name for the new job"},
                    "folder": {"type": "string", "description": "Folder to create job in (optional)"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["source_job", "new_job_name"]
            }
        ),
        Tool(
            name="jenkins_update_job_config",
            description="Update job XML configuration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Job name"},
                    "config_xml": {"type": "string", "description": "New job XML configuration"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["job_name", "config_xml"]
            }
        ),

        # ========== Raw API ==========
        Tool(
            name="jenkins_raw_api",
            description="Make a raw API call to Jenkins. Use this for operations not covered by other tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method (GET, POST, PUT, DELETE)"},
                    "endpoint": {"type": "string", "description": "API endpoint (e.g., '/job/my-job/api/json')"},
                    "body": {"type": "object", "description": "Request body for POST/PUT requests"},
                    "params": {"type": "object", "description": "Query parameters"},
                    "server": {"type": "string", "description": "Jenkins server name (optional)"}
                },
                "required": ["method", "endpoint"]
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

        # ========== Build Details ==========
        elif name == "jenkins_get_last_build":
            client = get_jenkins_client(arguments.get("server"))
            build = client.get_last_build(arguments["job_name"])
            result = format_build(build)

        elif name == "jenkins_list_builds":
            client = get_jenkins_client(arguments.get("server"))
            builds = client.list_builds(arguments["job_name"], arguments.get("limit", 25))
            output = [f"# Builds for {arguments['job_name']}", ""]
            result_emoji = {
                'SUCCESS': '[OK]',
                'FAILURE': '[FAIL]',
                'UNSTABLE': '[WARN]',
                'ABORTED': '[ABORT]',
                None: '[...]',
            }
            for b in builds:
                status = result_emoji.get(b.get('result'), '[?]')
                building = ' (building)' if b.get('building') else ''
                ts = ''
                if b.get('timestamp'):
                    ts = datetime.fromtimestamp(b['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M')
                output.append(f"- {status} **#{b.get('number')}** - {ts}{building}")
            result = '\n'.join(output)

        elif name == "jenkins_get_build_test_results":
            client = get_jenkins_client(arguments.get("server"))
            try:
                test_report = client.get_build_test_results(arguments["job_name"], arguments["build_number"])
                output = [f"# Test Results: {arguments['job_name']} #{arguments['build_number']}", ""]
                output.append(f"**Total:** {test_report.get('totalCount', 0)}")
                output.append(f"**Passed:** {test_report.get('passCount', 0)}")
                output.append(f"**Failed:** {test_report.get('failCount', 0)}")
                output.append(f"**Skipped:** {test_report.get('skipCount', 0)}")

                failed_tests = test_report.get('suites', [])
                failures = []
                for suite in failed_tests:
                    for case in suite.get('cases', []):
                        if case.get('status') in ('FAILED', 'REGRESSION'):
                            failures.append(f"- {case.get('className')}.{case.get('name')}")

                if failures:
                    output.append("")
                    output.append("## Failed Tests")
                    output.extend(failures[:20])
                    if len(failures) > 20:
                        output.append(f"... and {len(failures) - 20} more")

                result = '\n'.join(output)
            except Exception as e:
                if '404' in str(e):
                    result = "No test results found for this build."
                else:
                    raise

        elif name == "jenkins_get_build_artifacts":
            client = get_jenkins_client(arguments.get("server"))
            artifacts = client.get_build_artifacts(arguments["job_name"], arguments["build_number"])
            if artifacts:
                output = [f"# Artifacts: {arguments['job_name']} #{arguments['build_number']}", ""]
                for a in artifacts:
                    output.append(f"- **{a.get('fileName')}** ({a.get('relativePath')})")
                result = '\n'.join(output)
            else:
                result = "No artifacts found for this build."

        elif name == "jenkins_download_artifact":
            client = get_jenkins_client(arguments.get("server"))
            saved_path = client.download_artifact(
                arguments["job_name"],
                arguments["build_number"],
                arguments["artifact_path"],
                arguments["download_path"]
            )
            result = f"Artifact downloaded to: {saved_path}"

        # ========== Views ==========
        elif name == "jenkins_list_views":
            client = get_jenkins_client(arguments.get("server"))
            views = client.list_views()
            output = ["# Jenkins Views", ""]
            for v in views:
                desc = f" - {v.get('description')}" if v.get('description') else ""
                output.append(f"- **{v.get('name')}**{desc}")
            result = '\n'.join(output)

        elif name == "jenkins_get_view":
            client = get_jenkins_client(arguments.get("server"))
            view = client.get_view(arguments["view_name"])
            output = [f"# View: {view.get('name', arguments['view_name'])}", ""]
            if view.get('description'):
                output.append(f"**Description:** {view.get('description')}")
                output.append("")
            jobs = view.get('jobs', [])
            output.append(f"## Jobs ({len(jobs)})")
            result = '\n'.join(output) + '\n' + format_jobs(jobs)

        # ========== Node Details ==========
        elif name == "jenkins_get_node_details":
            client = get_jenkins_client(arguments.get("server"))
            node = client.get_node_details(arguments["node_name"])
            output = [f"# Node: {node.get('displayName', arguments['node_name'])}", ""]
            output.append(f"**Status:** {'OFFLINE' if node.get('offline') else 'ONLINE'}")
            output.append(f"**Executors:** {node.get('numExecutors', 0)}")

            if node.get('offlineCauseReason'):
                output.append(f"**Offline Reason:** {node.get('offlineCauseReason')}")

            if node.get('monitorData'):
                output.append("")
                output.append("## Monitor Data")
                monitor = node.get('monitorData', {})
                if monitor.get('hudson.node_monitors.DiskSpaceMonitor'):
                    disk = monitor['hudson.node_monitors.DiskSpaceMonitor']
                    if disk:
                        size_gb = disk.get('size', 0) / (1024**3)
                        output.append(f"- **Disk Space:** {size_gb:.1f} GB")
                if monitor.get('hudson.node_monitors.ResponseTimeMonitor'):
                    rt = monitor['hudson.node_monitors.ResponseTimeMonitor']
                    if rt:
                        output.append(f"- **Response Time:** {rt.get('average', 0)}ms")

            result = '\n'.join(output)

        # ========== System Info ==========
        elif name == "jenkins_get_system_info":
            client = get_jenkins_client(arguments.get("server"))
            info = client.get_system_info()
            output = ["# Jenkins System Info", ""]
            output.append(f"**Version:** {info.get('jenkinsVersion', 'Unknown')}")
            output.append(f"**Mode:** {info.get('mode', 'Unknown')}")
            output.append(f"**URL:** {info.get('url', 'Unknown')}")
            if info.get('useSecurity'):
                output.append("**Security:** Enabled")
            output.append(f"**Executors:** {info.get('numExecutors', 0)}")
            result = '\n'.join(output)

        elif name == "jenkins_get_plugins":
            client = get_jenkins_client(arguments.get("server"))
            plugins = client.get_plugins()
            output = [f"# Installed Plugins ({len(plugins)})", ""]
            for p in plugins:
                status = "[ON]" if p.get('active') and p.get('enabled') else "[OFF]"
                update = " (update available)" if p.get('hasUpdate') else ""
                output.append(f"- {status} **{p.get('shortName')}** v{p.get('version')}{update}")
            result = '\n'.join(output)

        elif name == "jenkins_get_credentials_list":
            client = get_jenkins_client(arguments.get("server"))
            try:
                creds = client.get_credentials_list(arguments.get("domain", "_"))
                output = [f"# Credentials ({len(creds)})", ""]
                for c in creds:
                    output.append(f"- **{c.get('id')}** ({c.get('typeName', 'Unknown')})")
                    if c.get('description'):
                        output.append(f"  _{c.get('description')}_")
                result = '\n'.join(output)
            except Exception as e:
                if '404' in str(e):
                    result = "Credentials plugin may not be installed or accessible."
                else:
                    raise

        # ========== Build Operations (Write) ==========
        elif name == "jenkins_trigger_build":
            client = get_jenkins_client(arguments.get("server"))
            response = client.trigger_build(arguments["job_name"], arguments.get("parameters"))
            output = [f"# Build Triggered: {arguments['job_name']}", ""]
            output.append(f"**Status:** {response.get('status')}")
            if response.get('queue_item'):
                output.append(f"**Queue Item:** {response.get('queue_item')}")
            result = '\n'.join(output)

        elif name == "jenkins_stop_build":
            client = get_jenkins_client(arguments.get("server"))
            response = client.stop_build(arguments["job_name"], arguments["build_number"])
            result = f"Build #{arguments['build_number']} of **{arguments['job_name']}** has been stopped."

        # ========== Job Operations (Write) ==========
        elif name == "jenkins_enable_job":
            client = get_jenkins_client(arguments.get("server"))
            client.enable_job(arguments["job_name"])
            result = f"Job **{arguments['job_name']}** has been enabled."

        elif name == "jenkins_disable_job":
            client = get_jenkins_client(arguments.get("server"))
            client.disable_job(arguments["job_name"])
            result = f"Job **{arguments['job_name']}** has been disabled."

        elif name == "jenkins_delete_job":
            client = get_jenkins_client(arguments.get("server"))
            client.delete_job(arguments["job_name"])
            result = f"Job **{arguments['job_name']}** has been deleted."

        elif name == "jenkins_create_job":
            client = get_jenkins_client(arguments.get("server"))
            client.create_job(
                arguments["job_name"],
                arguments["config_xml"],
                arguments.get("folder")
            )
            result = f"Job **{arguments['job_name']}** has been created."

        elif name == "jenkins_copy_job":
            client = get_jenkins_client(arguments.get("server"))
            client.copy_job(
                arguments["source_job"],
                arguments["new_job_name"],
                arguments.get("folder")
            )
            result = f"Job **{arguments['source_job']}** has been copied to **{arguments['new_job_name']}**."

        elif name == "jenkins_update_job_config":
            client = get_jenkins_client(arguments.get("server"))
            client.update_job_config(arguments["job_name"], arguments["config_xml"])
            result = f"Job **{arguments['job_name']}** configuration has been updated."

        # ========== Raw API ==========
        elif name == "jenkins_raw_api":
            client = get_jenkins_client(arguments.get("server"))
            response = client.raw_api(
                method=arguments["method"],
                endpoint=arguments["endpoint"],
                body=arguments.get("body"),
                params=arguments.get("params")
            )
            import json
            result = f"# Raw API Response\n\n```json\n{json.dumps(response, indent=2)}\n```"

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
