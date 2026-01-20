#!/usr/bin/env python3
"""
Atlassian MCP Server - Provides Jira, Confluence, and Bitbucket tools for Claude.

Usage:
    python mcp_server.py

Environment Variables:
    ATLASSIAN_CONFIG - Path to .env file with credentials (default: ~/.config/atlassian/.env)

The .env file should contain:
    JIRA_URL, JIRA_USERNAME, JIRA_TOKEN
    CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_TOKEN
    BITBUCKET_URL, BITBUCKET_USERNAME, BITBUCKET_TOKEN
"""

import json
import sys
import traceback
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from atlassian_client import (
    get_jira_client,
    get_confluence_client,
    get_bitbucket_client,
    get_jenkins_client,
    get_available_jenkins_servers
)

# Create the MCP server
server = Server("atlassian")


def format_jira_issue(issue: dict) -> str:
    """Format a Jira issue for display."""
    fields = issue.get('fields', {})
    rendered = issue.get('renderedFields', {})

    output = []
    output.append(f"# {issue.get('key')}: {fields.get('summary', 'No summary')}")
    output.append("")
    output.append(f"**Status:** {fields.get('status', {}).get('name', 'Unknown')}")
    output.append(f"**Type:** {fields.get('issuetype', {}).get('name', 'Unknown')}")

    if fields.get('priority'):
        output.append(f"**Priority:** {fields['priority'].get('name', 'Unknown')}")

    if fields.get('assignee'):
        output.append(f"**Assignee:** {fields['assignee'].get('displayName', 'Unassigned')}")

    if fields.get('reporter'):
        output.append(f"**Reporter:** {fields['reporter'].get('displayName', 'Unknown')}")

    output.append(f"**Created:** {fields.get('created', 'Unknown')}")
    output.append(f"**Updated:** {fields.get('updated', 'Unknown')}")

    if fields.get('labels'):
        output.append(f"**Labels:** {', '.join(fields['labels'])}")

    output.append("")
    output.append("## Description")
    desc = rendered.get('description') or fields.get('description') or 'No description'
    output.append(desc)

    # Include comments if available
    if fields.get('comment', {}).get('comments'):
        output.append("")
        output.append("## Comments")
        for comment in fields['comment']['comments']:
            author = comment.get('author', {}).get('displayName', 'Unknown')
            created = comment.get('created', '')
            body = comment.get('body', '')
            output.append(f"\n**{author}** ({created}):")
            output.append(body)

    return '\n'.join(output)


def format_confluence_page(page: dict) -> str:
    """Format a Confluence page for display."""
    output = []
    output.append(f"# {page.get('title', 'Untitled')}")
    output.append("")
    output.append(f"**ID:** {page.get('id')}")
    output.append(f"**Space:** {page.get('space', {}).get('key', 'Unknown')}")

    version = page.get('version', {})
    output.append(f"**Version:** {version.get('number', 'Unknown')}")
    output.append(f"**Last Modified:** {version.get('when', 'Unknown')}")
    if version.get('by'):
        output.append(f"**Modified By:** {version['by'].get('displayName', 'Unknown')}")

    output.append("")
    output.append("## Content")
    body = page.get('body', {})
    content = body.get('view', {}).get('value') or body.get('storage', {}).get('value') or 'No content'
    output.append(content)

    return '\n'.join(output)


def format_bitbucket_pr(pr: dict) -> str:
    """Format a Bitbucket pull request for display."""
    output = []
    output.append(f"# PR #{pr.get('id')}: {pr.get('title', 'Untitled')}")
    output.append("")
    output.append(f"**State:** {pr.get('state', 'Unknown')}")
    output.append(f"**Author:** {pr.get('author', {}).get('user', {}).get('displayName', 'Unknown')}")

    from_ref = pr.get('fromRef', {})
    to_ref = pr.get('toRef', {})
    output.append(f"**From:** {from_ref.get('displayId', 'Unknown')}")
    output.append(f"**To:** {to_ref.get('displayId', 'Unknown')}")

    output.append(f"**Created:** {pr.get('createdDate', 'Unknown')}")
    output.append(f"**Updated:** {pr.get('updatedDate', 'Unknown')}")

    if pr.get('reviewers'):
        reviewers = [r.get('user', {}).get('displayName', 'Unknown') for r in pr['reviewers']]
        output.append(f"**Reviewers:** {', '.join(reviewers)}")

    if pr.get('description'):
        output.append("")
        output.append("## Description")
        output.append(pr['description'])

    return '\n'.join(output)


def format_jenkins_job(job: dict) -> str:
    """Format Jenkins job for display."""
    output = []
    output.append(f"# {job.get('displayName', job.get('name', 'Unknown Job'))}")
    output.append("")

    # Status color mapping
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

    # Last build info
    if job.get('lastBuild'):
        lb = job['lastBuild']
        output.append("")
        output.append("## Last Build")
        output.append(f"- **Number:** #{lb.get('number')}")
        output.append(f"- **URL:** {lb.get('url')}")

    # Health report
    if job.get('healthReport'):
        output.append("")
        output.append("## Health")
        for health in job['healthReport']:
            output.append(f"- {health.get('description', 'N/A')}")

    return '\n'.join(output)


def format_jenkins_build(build: dict) -> str:
    """Format Jenkins build for display."""
    from datetime import datetime

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

    # Parameters
    if build.get('actions'):
        for action in build['actions']:
            if action and action.get('_class', '').endswith('ParametersAction'):
                output.append("")
                output.append("## Parameters")
                for param in action.get('parameters', []):
                    output.append(f"- **{param.get('name')}:** {param.get('value')}")

    # Changes
    if build.get('changeSet', {}).get('items'):
        output.append("")
        output.append("## Changes")
        for change in build['changeSet']['items'][:10]:
            msg = change.get('msg', change.get('comment', 'No message'))
            author = change.get('author', {}).get('fullName', 'Unknown')
            output.append(f"- {msg} ({author})")

    return '\n'.join(output)


def format_jenkins_jobs(jobs: list) -> str:
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


def format_jenkins_queue(queue: list) -> str:
    """Format Jenkins queue for display."""
    from datetime import datetime

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


def format_jenkins_nodes(nodes: list) -> str:
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


def format_jenkins_job_config(config: dict, job_name: str) -> str:
    """Format Jenkins job configuration for display."""
    output = []
    output.append(f"# Job Configuration: {job_name}")
    output.append("")

    # Job type
    job_type_map = {
        'project': 'Freestyle Project',
        'flow-definition': 'Pipeline',
        'maven2-moduleset': 'Maven Project',
        'matrix-project': 'Multi-configuration Project',
        'org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject': 'Multibranch Pipeline',
    }
    job_type = config.get('job_type', 'Unknown')
    friendly_type = job_type_map.get(job_type, job_type)
    output.append(f"**Job Type:** {friendly_type}")

    # Disabled status
    if config.get('disabled'):
        output.append("**Status:** Disabled")
    else:
        output.append("**Status:** Enabled")

    # Description
    if config.get('description'):
        output.append(f"**Description:** {config['description']}")

    # Parameters
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

    # SCM Configuration
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

    # Build Triggers
    if config.get('triggers'):
        output.append("")
        output.append("## Build Triggers")
        for trigger in config['triggers']:
            trigger_type = trigger.get('type', '').split('.')[-1]
            trigger_names = {
                'SCMTrigger': 'Poll SCM',
                'TimerTrigger': 'Build periodically',
                'GitHubPushTrigger': 'GitHub hook trigger',
                'ReverseBuildTrigger': 'Build after other projects',
            }
            friendly_name = trigger_names.get(trigger_type, trigger_type)
            output.append(f"- **{friendly_name}**")
            if trigger.get('schedule'):
                output.append(f"  - Schedule: `{trigger['schedule']}`")

    # Build Steps
    if config.get('builders'):
        output.append("")
        output.append("## Build Steps")
        for i, builder in enumerate(config['builders'], 1):
            builder_type = builder.get('type', 'Unknown')
            builder_names = {
                'Shell': 'Execute shell',
                'BatchFile': 'Execute Windows batch command',
                'Maven': 'Invoke Maven',
                'Ant': 'Invoke Ant',
                'Gradle': 'Invoke Gradle',
            }
            friendly_name = builder_names.get(builder_type, builder_type)
            output.append(f"{i}. **{friendly_name}**")
            if builder.get('command'):
                cmd_preview = builder['command'][:200]
                if len(builder['command']) > 200:
                    cmd_preview += '...'
                output.append(f"   ```bash\n   {cmd_preview}\n   ```")

    # Pipeline Script
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

    # Post-build Actions
    if config.get('publishers'):
        output.append("")
        output.append("## Post-build Actions")
        publisher_names = {
            'ArtifactArchiver': 'Archive artifacts',
            'BuildTrigger': 'Build other projects',
            'Mailer': 'E-mail notification',
            'JUnitResultArchiver': 'Publish JUnit test results',
            'HtmlPublisher': 'Publish HTML reports',
            'SlackNotifier': 'Slack notification',
        }
        for publisher in config['publishers']:
            pub_type = publisher.get('type', 'Unknown')
            friendly_name = publisher_names.get(pub_type, pub_type)
            output.append(f"- {friendly_name}")

    return '\n'.join(output)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Atlassian tools."""
    return [
        # Jira Tools
        Tool(
            name="jira_get_issue",
            description="Get a Jira issue by key (e.g., PROJ-123) or URL. Returns full issue details including description, status, assignee, and comments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key (e.g., PROJ-123) or full Jira URL"
                    }
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="jira_search",
            description="Search Jira issues using JQL (Jira Query Language). Examples: 'project = PROJ AND status = Open', 'assignee = currentUser()', 'text ~ \"search term\"'",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query string"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 25)",
                        "default": 25
                    }
                },
                "required": ["jql"]
            }
        ),
        Tool(
            name="jira_create_issue",
            description="Create a new Jira issue. Requires project key, summary, and issue type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {
                        "type": "string",
                        "description": "Project key (e.g., PROJ)"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Issue summary/title"
                    },
                    "issue_type": {
                        "type": "string",
                        "description": "Issue type (e.g., Task, Bug, Story)",
                        "default": "Task"
                    },
                    "description": {
                        "type": "string",
                        "description": "Issue description"
                    },
                    "assignee": {
                        "type": "string",
                        "description": "Assignee username"
                    },
                    "priority": {
                        "type": "string",
                        "description": "Priority (e.g., High, Medium, Low)"
                    }
                },
                "required": ["project_key", "summary"]
            }
        ),
        Tool(
            name="jira_add_comment",
            description="Add a comment to a Jira issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key or URL"
                    },
                    "comment": {
                        "type": "string",
                        "description": "Comment text"
                    }
                },
                "required": ["issue_key", "comment"]
            }
        ),
        Tool(
            name="jira_transition_issue",
            description="Transition a Jira issue to a new status (e.g., 'In Progress', 'Done').",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key or URL"
                    },
                    "transition": {
                        "type": "string",
                        "description": "Transition name (e.g., 'Start Progress', 'Resolve', 'Close')"
                    }
                },
                "required": ["issue_key", "transition"]
            }
        ),
        Tool(
            name="jira_update_issue",
            description="Update a Jira issue's fields (summary, description, assignee, priority, labels).",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Issue key or URL"
                    },
                    "summary": {
                        "type": "string",
                        "description": "New summary/title"
                    },
                    "description": {
                        "type": "string",
                        "description": "New description"
                    },
                    "assignee": {
                        "type": "string",
                        "description": "New assignee username"
                    },
                    "priority": {
                        "type": "string",
                        "description": "New priority (e.g., High, Medium, Low)"
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New labels (replaces existing labels)"
                    }
                },
                "required": ["issue_key"]
            }
        ),

        # Confluence Tools
        Tool(
            name="confluence_get_page",
            description="Get a Confluence page by ID or URL. Returns full page content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "Page ID or full Confluence URL"
                    }
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="confluence_get_page_by_title",
            description="Get a Confluence page by space key and title.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {
                        "type": "string",
                        "description": "Space key (e.g., DOCS, TEAM)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Exact page title"
                    }
                },
                "required": ["space_key", "title"]
            }
        ),
        Tool(
            name="confluence_search",
            description="Search Confluence pages using CQL or simple text. CQL examples: 'text ~ \"search term\"', 'space = DOCS AND title ~ \"guide\"'",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (text or CQL)"
                    },
                    "space_key": {
                        "type": "string",
                        "description": "Optional: limit search to a space"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default: 25)",
                        "default": 25
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="confluence_get_space_pages",
            description="List all pages in a Confluence space.",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {
                        "type": "string",
                        "description": "Space key"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default: 50)",
                        "default": 50
                    }
                },
                "required": ["space_key"]
            }
        ),
        Tool(
            name="confluence_create_page",
            description="Create a new Confluence page. Content should be in Confluence storage format (XHTML).",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {
                        "type": "string",
                        "description": "Space key where the page will be created"
                    },
                    "title": {
                        "type": "string",
                        "description": "Page title"
                    },
                    "content": {
                        "type": "string",
                        "description": "Page content in Confluence storage format (XHTML). Use <p> for paragraphs, <h1>-<h6> for headings, <ul>/<ol> for lists."
                    },
                    "parent_id": {
                        "type": "string",
                        "description": "Optional parent page ID to nest this page under"
                    }
                },
                "required": ["space_key", "title", "content"]
            }
        ),
        Tool(
            name="confluence_update_page",
            description="Update an existing Confluence page. Content should be in Confluence storage format (XHTML).",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "Page ID to update"
                    },
                    "title": {
                        "type": "string",
                        "description": "New page title"
                    },
                    "content": {
                        "type": "string",
                        "description": "New page content in Confluence storage format (XHTML)"
                    }
                },
                "required": ["page_id", "title", "content"]
            }
        ),
        Tool(
            name="confluence_add_comment",
            description="Add a comment to a Confluence page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "Page ID to comment on"
                    },
                    "comment": {
                        "type": "string",
                        "description": "Comment text (can use Confluence storage format)"
                    }
                },
                "required": ["page_id", "comment"]
            }
        ),

        # Bitbucket Tools
        Tool(
            name="bitbucket_get_pr",
            description="Get a Bitbucket pull request by URL or project/repo/PR ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pr_url": {
                        "type": "string",
                        "description": "Full PR URL or leave empty if providing project/repo/pr_id"
                    },
                    "project": {
                        "type": "string",
                        "description": "Project key (if not using URL)"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository slug (if not using URL)"
                    },
                    "pr_id": {
                        "type": "integer",
                        "description": "Pull request ID (if not using URL)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="bitbucket_get_pr_diff",
            description="Get the diff/changes for a Bitbucket pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project key"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository slug"
                    },
                    "pr_id": {
                        "type": "integer",
                        "description": "Pull request ID"
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Lines of context around changes (default: 10)",
                        "default": 10
                    }
                },
                "required": ["project", "repo", "pr_id"]
            }
        ),
        Tool(
            name="bitbucket_list_prs",
            description="List pull requests for a repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project key"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository slug"
                    },
                    "state": {
                        "type": "string",
                        "description": "PR state: OPEN, MERGED, DECLINED, ALL",
                        "default": "OPEN"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default: 25)",
                        "default": 25
                    }
                },
                "required": ["project", "repo"]
            }
        ),
        Tool(
            name="bitbucket_add_pr_comment",
            description="Add a comment to a Bitbucket pull request (general or inline on a specific file/line).",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project key"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository slug"
                    },
                    "pr_id": {
                        "type": "integer",
                        "description": "Pull request ID"
                    },
                    "comment": {
                        "type": "string",
                        "description": "Comment text"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Optional: file path for inline comment"
                    },
                    "line": {
                        "type": "integer",
                        "description": "Optional: line number for inline comment"
                    }
                },
                "required": ["project", "repo", "pr_id", "comment"]
            }
        ),
        Tool(
            name="bitbucket_get_file",
            description="Get file content from a Bitbucket repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project key"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository slug"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to file in repository"
                    },
                    "ref": {
                        "type": "string",
                        "description": "Branch, tag, or commit (default: default branch)"
                    }
                },
                "required": ["project", "repo", "file_path"]
            }
        ),
        Tool(
            name="bitbucket_list_branches",
            description="List branches in a Bitbucket repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project key"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository slug"
                    },
                    "filter": {
                        "type": "string",
                        "description": "Optional: filter branches by name"
                    }
                },
                "required": ["project", "repo"]
            }
        ),

        # Jenkins Tools (Read-Only) - supports multiple servers
        Tool(
            name="jenkins_list_servers",
            description="List available Jenkins servers that are configured.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="jenkins_get_job",
            description="Get Jenkins job details including status, last build info, and health report.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {
                        "type": "string",
                        "description": "Job name (use folder/job for jobs in folders)"
                    },
                    "server": {
                        "type": "string",
                        "description": "Jenkins server name (e.g., 'proc', 'epsw'). If not specified, uses first available."
                    }
                },
                "required": ["job_name"]
            }
        ),
        Tool(
            name="jenkins_get_build",
            description="Get details for a specific Jenkins build including result, duration, and changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {
                        "type": "string",
                        "description": "Job name"
                    },
                    "build_number": {
                        "type": "integer",
                        "description": "Build number"
                    },
                    "server": {
                        "type": "string",
                        "description": "Jenkins server name (e.g., 'proc', 'epsw'). If not specified, uses first available."
                    }
                },
                "required": ["job_name", "build_number"]
            }
        ),
        Tool(
            name="jenkins_list_jobs",
            description="List Jenkins jobs. Optionally specify a folder to list jobs within.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Optional folder path to list jobs from"
                    },
                    "server": {
                        "type": "string",
                        "description": "Jenkins server name (e.g., 'proc', 'epsw'). If not specified, uses first available."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="jenkins_get_build_log",
            description="Get console output/log for a Jenkins build.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {
                        "type": "string",
                        "description": "Job name"
                    },
                    "build_number": {
                        "type": "integer",
                        "description": "Build number"
                    },
                    "server": {
                        "type": "string",
                        "description": "Jenkins server name (e.g., 'proc', 'epsw'). If not specified, uses first available."
                    }
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
                    "server": {
                        "type": "string",
                        "description": "Jenkins server name (e.g., 'proc', 'epsw'). If not specified, uses first available."
                    }
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
                    "server": {
                        "type": "string",
                        "description": "Jenkins server name (e.g., 'proc', 'epsw'). If not specified, uses first available."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="jenkins_get_job_config",
            description="Get Jenkins job configuration settings including SCM, triggers, parameters, build steps, and post-build actions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_name": {
                        "type": "string",
                        "description": "Job name (use folder/job for jobs in folders)"
                    },
                    "raw_xml": {
                        "type": "boolean",
                        "description": "If true, return raw XML config instead of parsed summary (default: false)"
                    },
                    "server": {
                        "type": "string",
                        "description": "Jenkins server name (e.g., 'proc', 'epsw'). If not specified, uses first available."
                    }
                },
                "required": ["job_name"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        result = None

        # Jira tools
        if name == "jira_get_issue":
            client = get_jira_client()
            issue = client.get_issue(arguments["issue_key"])
            result = format_jira_issue(issue)

        elif name == "jira_search":
            client = get_jira_client()
            max_results = arguments.get("max_results", 25)
            search_result = client.search_issues(arguments["jql"], max_results=max_results)
            issues = search_result.get('issues', [])
            output = [f"Found {len(issues)} issues:\n"]
            for issue in issues:
                fields = issue.get('fields', {})
                key = issue.get('key')
                summary = fields.get('summary', 'No summary')
                status = fields.get('status', {}).get('name', 'Unknown')
                assignee = fields.get('assignee', {})
                assignee_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
                output.append(f"- **{key}**: {summary} [{status}] (Assignee: {assignee_name})")
            result = '\n'.join(output)

        elif name == "jira_create_issue":
            client = get_jira_client()
            created = client.create_issue(
                project_key=arguments["project_key"],
                summary=arguments["summary"],
                issue_type=arguments.get("issue_type", "Task"),
                description=arguments.get("description", ""),
                priority=arguments.get("priority"),
                assignee=arguments.get("assignee")
            )
            result = f"Issue created: **{created['key']}**\nURL: {client.base_url}/browse/{created['key']}"

        elif name == "jira_add_comment":
            client = get_jira_client()
            client.add_comment(arguments["issue_key"], arguments["comment"])
            result = f"Comment added to {arguments['issue_key']}"

        elif name == "jira_transition_issue":
            client = get_jira_client()
            client.transition_issue(arguments["issue_key"], arguments["transition"])
            result = f"Issue {arguments['issue_key']} transitioned to '{arguments['transition']}'"

        elif name == "jira_update_issue":
            client = get_jira_client()
            fields = {}
            if arguments.get("summary"):
                fields["summary"] = arguments["summary"]
            if arguments.get("description"):
                fields["description"] = arguments["description"]
            if arguments.get("assignee"):
                fields["assignee"] = {"name": arguments["assignee"]}
            if arguments.get("priority"):
                fields["priority"] = {"name": arguments["priority"]}
            if arguments.get("labels") is not None:
                fields["labels"] = arguments["labels"]

            if not fields:
                result = "No fields to update. Provide at least one field (summary, description, assignee, priority, labels)."
            else:
                client.update_issue(arguments["issue_key"], fields)
                updated_fields = ", ".join(fields.keys())
                result = f"Issue {arguments['issue_key']} updated. Fields changed: {updated_fields}"

        # Confluence tools
        elif name == "confluence_get_page":
            client = get_confluence_client()
            page = client.get_page(arguments["page_id"])
            result = format_confluence_page(page)

        elif name == "confluence_get_page_by_title":
            client = get_confluence_client()
            response = client.get_page_by_title(arguments["space_key"], arguments["title"])
            pages = response.get('results', [])
            if not pages:
                result = f"No page found with title '{arguments['title']}' in space '{arguments['space_key']}'"
            else:
                # Get full page with content
                page = client.get_page(pages[0]['id'])
                result = format_confluence_page(page)

        elif name == "confluence_search":
            client = get_confluence_client()
            space_key = arguments.get("space_key")
            limit = arguments.get("limit", 25)
            response = client.search_content(arguments["query"], space_key=space_key, limit=limit)
            pages = response.get('results', [])
            output = [f"Found {len(pages)} pages:\n"]
            for page in pages:
                space = page.get('space', {}).get('key', 'Unknown')
                title = page.get('title', 'Untitled')
                page_id = page.get('id')
                output.append(f"- [{space}] **{title}** (ID: {page_id})")
            result = '\n'.join(output)

        elif name == "confluence_get_space_pages":
            client = get_confluence_client()
            limit = arguments.get("limit", 50)
            response = client.get_space_pages(arguments["space_key"], limit=limit)
            pages = response.get('results', [])
            output = [f"Pages in space {arguments['space_key']} ({len(pages)} found):\n"]
            for page in pages:
                title = page.get('title', 'Untitled')
                page_id = page.get('id')
                output.append(f"- **{title}** (ID: {page_id})")
            result = '\n'.join(output)

        elif name == "confluence_create_page":
            client = get_confluence_client()
            created = client.create_page(
                space_key=arguments["space_key"],
                title=arguments["title"],
                content=arguments["content"],
                parent_id=arguments.get("parent_id")
            )
            page_id = created.get('id')
            page_url = f"{client.base_url}/pages/viewpage.action?pageId={page_id}"
            result = f"Page created: **{arguments['title']}**\nID: {page_id}\nURL: {page_url}"

        elif name == "confluence_update_page":
            client = get_confluence_client()
            updated = client.update_page(
                page_id=arguments["page_id"],
                title=arguments["title"],
                content=arguments["content"]
            )
            version = updated.get('version', {}).get('number', 'unknown')
            result = f"Page updated: **{arguments['title']}**\nID: {arguments['page_id']}\nNew version: {version}"

        elif name == "confluence_add_comment":
            client = get_confluence_client()
            client.add_comment(arguments["page_id"], arguments["comment"])
            result = f"Comment added to page {arguments['page_id']}"

        # Bitbucket tools
        elif name == "bitbucket_get_pr":
            client = get_bitbucket_client()
            if arguments.get("pr_url"):
                pr = client.get_pull_request_by_url(arguments["pr_url"])
            else:
                pr = client.get_pull_request(
                    arguments["project"],
                    arguments["repo"],
                    arguments["pr_id"]
                )
            result = format_bitbucket_pr(pr)

        elif name == "bitbucket_get_pr_diff":
            client = get_bitbucket_client()
            context = arguments.get("context_lines", 10)
            diff = client.get_pr_diff(
                arguments["project"],
                arguments["repo"],
                arguments["pr_id"],
                context_lines=context
            )
            # Format diff output
            output = ["## Pull Request Diff\n"]
            for diff_entry in diff.get('diffs', []):
                source = diff_entry.get('source', {}).get('toString', 'New file')
                dest = diff_entry.get('destination', {}).get('toString', 'Deleted')
                output.append(f"\n### {source} -> {dest}")
                for hunk in diff_entry.get('hunks', []):
                    for segment in hunk.get('segments', []):
                        seg_type = segment.get('type', 'CONTEXT')
                        prefix = ' ' if seg_type == 'CONTEXT' else ('+' if seg_type == 'ADDED' else '-')
                        for line in segment.get('lines', []):
                            output.append(f"{prefix}{line.get('line', '')}")
            result = '\n'.join(output)

        elif name == "bitbucket_list_prs":
            client = get_bitbucket_client()
            state = arguments.get("state", "OPEN")
            limit = arguments.get("limit", 25)
            response = client.list_pull_requests(
                arguments["project"],
                arguments["repo"],
                state=state,
                limit=limit
            )
            prs = response.get('values', [])
            output = [f"Pull requests ({state}) for {arguments['project']}/{arguments['repo']}:\n"]
            for pr in prs:
                pr_id = pr.get('id')
                title = pr.get('title', 'Untitled')
                author = pr.get('author', {}).get('user', {}).get('displayName', 'Unknown')
                state = pr.get('state', 'Unknown')
                output.append(f"- **#{pr_id}**: {title} [{state}] by {author}")
            result = '\n'.join(output)

        elif name == "bitbucket_add_pr_comment":
            client = get_bitbucket_client()
            client.add_pr_comment(
                arguments["project"],
                arguments["repo"],
                arguments["pr_id"],
                arguments["comment"],
                file_path=arguments.get("file_path"),
                line=arguments.get("line")
            )
            result = f"Comment added to PR #{arguments['pr_id']}"

        elif name == "bitbucket_get_file":
            client = get_bitbucket_client()
            response = client.get_file_content(
                arguments["project"],
                arguments["repo"],
                arguments["file_path"],
                ref=arguments.get("ref")
            )
            # Extract lines from response
            lines = response.get('lines', [])
            content = '\n'.join(line.get('text', '') for line in lines)
            result = f"## {arguments['file_path']}\n\n```\n{content}\n```"

        elif name == "bitbucket_list_branches":
            client = get_bitbucket_client()
            response = client.get_repo_branches(
                arguments["project"],
                arguments["repo"],
                filter_text=arguments.get("filter")
            )
            branches = response.get('values', [])
            output = [f"Branches in {arguments['project']}/{arguments['repo']}:\n"]
            for branch in branches:
                display_id = branch.get('displayId', 'Unknown')
                is_default = branch.get('isDefault', False)
                default_marker = " (default)" if is_default else ""
                output.append(f"- {display_id}{default_marker}")
            result = '\n'.join(output)

        # Jenkins tools
        elif name == "jenkins_list_servers":
            servers = get_available_jenkins_servers()
            if servers:
                output = ["# Available Jenkins Servers", ""]
                for srv in servers:
                    output.append(f"- **{srv}**")
                output.append("")
                output.append("Use the `server` parameter in other Jenkins tools to specify which server to query.")
                result = '\n'.join(output)
            else:
                result = "No Jenkins servers configured."

        elif name == "jenkins_get_job":
            server = arguments.get("server")
            client = get_jenkins_client(server)
            job = client.get_job(arguments["job_name"])
            result = format_jenkins_job(job)

        elif name == "jenkins_get_build":
            server = arguments.get("server")
            client = get_jenkins_client(server)
            build = client.get_build(arguments["job_name"], arguments["build_number"])
            result = format_jenkins_build(build)

        elif name == "jenkins_list_jobs":
            server = arguments.get("server")
            client = get_jenkins_client(server)
            jobs = client.list_jobs(arguments.get("folder"))
            result = format_jenkins_jobs(jobs)

        elif name == "jenkins_get_build_log":
            server = arguments.get("server")
            client = get_jenkins_client(server)
            log = client.get_build_log(arguments["job_name"], arguments["build_number"])
            # Truncate very long logs
            if len(log) > 50000:
                log = log[-50000:]
                log = "... (truncated, showing last 50000 characters)\n\n" + log
            result = f"# Build Log: {arguments['job_name']} #{arguments['build_number']}\n\n```\n{log}\n```"

        elif name == "jenkins_get_queue":
            server = arguments.get("server")
            client = get_jenkins_client(server)
            queue = client.get_queue()
            result = format_jenkins_queue(queue)

        elif name == "jenkins_get_nodes":
            server = arguments.get("server")
            client = get_jenkins_client(server)
            nodes = client.get_nodes()
            result = format_jenkins_nodes(nodes)

        elif name == "jenkins_get_job_config":
            server = arguments.get("server")
            client = get_jenkins_client(server)
            if arguments.get("raw_xml"):
                xml_config = client.get_job_config(arguments["job_name"])
                result = f"# Job Configuration: {arguments['job_name']}\n\n```xml\n{xml_config}\n```"
            else:
                config = client.get_job_config_parsed(arguments["job_name"])
                result = format_jenkins_job_config(config, arguments["job_name"])

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
