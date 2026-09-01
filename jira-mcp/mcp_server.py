#!/usr/bin/env python3
"""
Jira MCP Server - Provides comprehensive Jira tools for Claude.

Usage:
    python mcp_server.py

Environment Variables:
    JIRA_CONFIG - Path to .env file with credentials (default: ~/.config/jira-mcp/.env)

The .env file should contain:
    JIRA_URL, JIRA_USERNAME, JIRA_TOKEN
"""

import traceback
from typing import Any, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from jira_client import get_jira_client

# Create the MCP server
server = Server("jira")


# ==================== Formatters ====================

def format_issue(issue: dict) -> str:
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
    else:
        output.append("**Assignee:** Unassigned")

    if fields.get('reporter'):
        output.append(f"**Reporter:** {fields['reporter'].get('displayName', 'Unknown')}")

    output.append(f"**Created:** {fields.get('created', 'Unknown')}")
    output.append(f"**Updated:** {fields.get('updated', 'Unknown')}")

    if fields.get('labels'):
        output.append(f"**Labels:** {', '.join(fields['labels'])}")

    if fields.get('components'):
        components = [c.get('name', '') for c in fields['components']]
        output.append(f"**Components:** {', '.join(components)}")

    if fields.get('fixVersions'):
        versions = [v.get('name', '') for v in fields['fixVersions']]
        output.append(f"**Fix Versions:** {', '.join(versions)}")

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


def format_issues_list(issues: List[dict]) -> str:
    """Format a list of issues for display."""
    output = [f"Found {len(issues)} issues:\n"]
    for issue in issues:
        fields = issue.get('fields', {})
        key = issue.get('key')
        summary = fields.get('summary', 'No summary')
        status = fields.get('status', {}).get('name', 'Unknown')
        assignee = fields.get('assignee', {})
        assignee_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
        priority = fields.get('priority', {})
        priority_name = priority.get('name', '-') if priority else '-'
        output.append(f"- **{key}**: {summary} [{status}] ({priority_name}) - {assignee_name}")
    return '\n'.join(output)


def format_projects(projects: List[dict]) -> str:
    """Format projects list."""
    output = [f"# Projects ({len(projects)} found)\n"]
    for proj in projects:
        output.append(f"- **{proj.get('key')}**: {proj.get('name', 'Unknown')}")
        if proj.get('projectCategory'):
            output.append(f"  Category: {proj['projectCategory'].get('name', 'N/A')}")
    return '\n'.join(output)


def format_users(users: List[dict]) -> str:
    """Format users list."""
    output = [f"# Users ({len(users)} found)\n"]
    for user in users:
        output.append(f"- **{user.get('name', 'Unknown')}**: {user.get('displayName', 'N/A')} ({user.get('emailAddress', 'N/A')})")
    return '\n'.join(output)


def format_boards(boards: dict) -> str:
    """Format boards list."""
    values = boards.get('values', [])
    output = [f"# Agile Boards ({len(values)} found)\n"]
    for board in values:
        board_type = board.get('type', 'unknown')
        output.append(f"- **{board.get('id')}**: {board.get('name', 'Unknown')} ({board_type})")
    return '\n'.join(output)


def format_sprints(sprints: dict) -> str:
    """Format sprints list."""
    values = sprints.get('values', [])
    output = [f"# Sprints ({len(values)} found)\n"]
    for sprint in values:
        state = sprint.get('state', 'unknown')
        output.append(f"- **{sprint.get('id')}**: {sprint.get('name', 'Unknown')} [{state}]")
        if sprint.get('goal'):
            output.append(f"  Goal: {sprint['goal']}")
    return '\n'.join(output)


# ==================== Tool Definitions ====================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Jira tools."""
    return [
        # ========== Issues ==========
        Tool(
            name="jira_get_issue",
            description="Get a Jira issue by key (e.g., PROJ-123) or URL. Returns full issue details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key (e.g., PROJ-123) or full Jira URL"}
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="jira_search",
            description="Search Jira issues using JQL. Examples: 'project = PROJ AND status = Open', 'assignee = currentUser()'",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {"type": "string", "description": "JQL query string"},
                    "max_results": {"type": "integer", "description": "Maximum results (default: 50)", "default": 50}
                },
                "required": ["jql"]
            }
        ),
        Tool(
            name="jira_create_issue",
            description="Create a new Jira issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string", "description": "Project key (e.g., PROJ)"},
                    "summary": {"type": "string", "description": "Issue summary/title"},
                    "issue_type": {"type": "string", "description": "Issue type (Task, Bug, Story, etc.)", "default": "Task"},
                    "description": {"type": "string", "description": "Issue description"},
                    "priority": {"type": "string", "description": "Priority (High, Medium, Low, etc.)"},
                    "assignee": {"type": "string", "description": "Assignee username"},
                    "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels"},
                    "components": {"type": "array", "items": {"type": "string"}, "description": "Component names"},
                    "fix_versions": {"type": "array", "items": {"type": "string"}, "description": "Fix version names"},
                    "affects_versions": {"type": "array", "items": {"type": "string"}, "description": "Affects Version/s — the version(s) where the bug was found"},
                    "custom_fields": {"type": "object", "description": "Arbitrary custom fields as a flat key→value dict. Scalar values are sent as-is; use nested objects (e.g. {\"value\": \"foo\"}) for select/option fields. Example: {\"customfield_10302\": {\"value\": \"S2-Major\"}, \"customfield_12300\": \"steps text\"}"}
                },
                "required": ["project_key", "summary"]
            }
        ),
        Tool(
            name="jira_update_issue",
            description="Update a Jira issue's fields.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"},
                    "summary": {"type": "string", "description": "New summary"},
                    "description": {"type": "string", "description": "New description"},
                    "priority": {"type": "string", "description": "New priority"},
                    "assignee": {"type": "string", "description": "New assignee username"},
                    "labels": {"type": "array", "items": {"type": "string"}, "description": "New labels (replaces existing)"}
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="jira_delete_issue",
            description="Delete a Jira issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"},
                    "delete_subtasks": {"type": "boolean", "description": "Also delete subtasks", "default": False}
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="jira_assign_issue",
            description="Assign or unassign a Jira issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"},
                    "assignee": {"type": "string", "description": "Username to assign (omit or null to unassign)"}
                },
                "required": ["issue_key"]
            }
        ),

        # ========== Transitions ==========
        Tool(
            name="jira_get_transitions",
            description="Get available transitions for an issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"}
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="jira_transition_issue",
            description="Transition an issue to a new status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"},
                    "transition": {"type": "string", "description": "Transition name or ID"},
                    "comment": {"type": "string", "description": "Optional comment to add"},
                    "resolution": {"type": "string", "description": "Resolution name (if resolving)"}
                },
                "required": ["issue_key", "transition"]
            }
        ),

        # ========== Comments ==========
        Tool(
            name="jira_add_comment",
            description="Add a comment to a Jira issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"},
                    "comment": {"type": "string", "description": "Comment text"}
                },
                "required": ["issue_key", "comment"]
            }
        ),
        Tool(
            name="jira_get_comments",
            description="Get all comments for an issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"}
                },
                "required": ["issue_key"]
            }
        ),

        # ========== Worklog ==========
        Tool(
            name="jira_add_worklog",
            description="Log work on an issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"},
                    "time_spent": {"type": "string", "description": "Time spent (e.g., '2h 30m', '1d')"},
                    "comment": {"type": "string", "description": "Work description"},
                    "started": {"type": "string", "description": "Start time (ISO format)"}
                },
                "required": ["issue_key", "time_spent"]
            }
        ),
        Tool(
            name="jira_get_worklogs",
            description="Get work logs for an issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"}
                },
                "required": ["issue_key"]
            }
        ),

        # ========== Issue Links ==========
        Tool(
            name="jira_link_issues",
            description="Link two issues together.",
            inputSchema={
                "type": "object",
                "properties": {
                    "inward_issue": {"type": "string", "description": "Inward issue key (e.g., is blocked by)"},
                    "outward_issue": {"type": "string", "description": "Outward issue key (e.g., blocks)"},
                    "link_type": {"type": "string", "description": "Link type (Blocks, Relates, Duplicates, etc.)", "default": "Relates"}
                },
                "required": ["inward_issue", "outward_issue"]
            }
        ),
        Tool(
            name="jira_get_link_types",
            description="Get all available issue link types.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),

        # ========== Watchers ==========
        Tool(
            name="jira_get_watchers",
            description="Get watchers for an issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"}
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="jira_add_watcher",
            description="Add a watcher to an issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"},
                    "username": {"type": "string", "description": "Username to add as watcher"}
                },
                "required": ["issue_key", "username"]
            }
        ),
        Tool(
            name="jira_remove_watcher",
            description="Remove a watcher from an issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string", "description": "Issue key or URL"},
                    "username": {"type": "string", "description": "Username to remove"}
                },
                "required": ["issue_key", "username"]
            }
        ),

        # ========== Projects ==========
        Tool(
            name="jira_get_all_projects",
            description="List all Jira projects.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="jira_get_project",
            description="Get project details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string", "description": "Project key"}
                },
                "required": ["project_key"]
            }
        ),
        Tool(
            name="jira_get_project_components",
            description="Get components for a project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string", "description": "Project key"}
                },
                "required": ["project_key"]
            }
        ),
        Tool(
            name="jira_create_component",
            description="Create a project component.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string", "description": "Project key"},
                    "name": {"type": "string", "description": "Component name"},
                    "description": {"type": "string", "description": "Component description"},
                    "lead": {"type": "string", "description": "Component lead username"}
                },
                "required": ["project_key", "name"]
            }
        ),
        Tool(
            name="jira_get_project_versions",
            description="Get versions for a project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string", "description": "Project key"}
                },
                "required": ["project_key"]
            }
        ),
        Tool(
            name="jira_create_version",
            description="Create a project version.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string", "description": "Project key"},
                    "name": {"type": "string", "description": "Version name"},
                    "description": {"type": "string", "description": "Version description"},
                    "release_date": {"type": "string", "description": "Release date (YYYY-MM-DD)"},
                    "released": {"type": "boolean", "description": "Is released", "default": False}
                },
                "required": ["project_key", "name"]
            }
        ),
        Tool(
            name="jira_get_project_statuses",
            description="Get statuses available in a project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string", "description": "Project key"}
                },
                "required": ["project_key"]
            }
        ),

        # ========== Users ==========
        Tool(
            name="jira_get_user",
            description="Get user by username.",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username"}
                },
                "required": ["username"]
            }
        ),
        Tool(
            name="jira_search_users",
            description="Search for users.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="jira_find_assignable_users",
            description="Find users assignable to a project or issue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string", "description": "Project key"},
                    "issue_key": {"type": "string", "description": "Issue key"},
                    "query": {"type": "string", "description": "Username query"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": []
            }
        ),
        Tool(
            name="jira_get_current_user",
            description="Get the currently authenticated user.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),

        # ========== Groups ==========
        Tool(
            name="jira_get_all_groups",
            description="List all groups.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="jira_get_group_members",
            description="Get members of a group.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_name": {"type": "string", "description": "Group name"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["group_name"]
            }
        ),
        Tool(
            name="jira_add_user_to_group",
            description="Add a user to a group.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_name": {"type": "string", "description": "Group name"},
                    "username": {"type": "string", "description": "Username to add"}
                },
                "required": ["group_name", "username"]
            }
        ),
        Tool(
            name="jira_remove_user_from_group",
            description="Remove a user from a group.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_name": {"type": "string", "description": "Group name"},
                    "username": {"type": "string", "description": "Username to remove"}
                },
                "required": ["group_name", "username"]
            }
        ),

        # ========== Boards ==========
        Tool(
            name="jira_get_all_boards",
            description="List all agile boards.",
            inputSchema={
                "type": "object",
                "properties": {
                    "board_type": {"type": "string", "description": "Filter by type (scrum, kanban)"},
                    "name": {"type": "string", "description": "Filter by name"},
                    "project_key": {"type": "string", "description": "Filter by project"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": []
            }
        ),
        Tool(
            name="jira_get_board",
            description="Get board details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "board_id": {"type": "integer", "description": "Board ID"}
                },
                "required": ["board_id"]
            }
        ),
        Tool(
            name="jira_get_board_sprints",
            description="Get sprints for a board.",
            inputSchema={
                "type": "object",
                "properties": {
                    "board_id": {"type": "integer", "description": "Board ID"},
                    "state": {"type": "string", "description": "Filter by state (active, closed, future)"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["board_id"]
            }
        ),
        Tool(
            name="jira_get_board_backlog",
            description="Get backlog issues for a board.",
            inputSchema={
                "type": "object",
                "properties": {
                    "board_id": {"type": "integer", "description": "Board ID"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["board_id"]
            }
        ),

        # ========== Sprints ==========
        Tool(
            name="jira_get_sprint",
            description="Get sprint details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sprint_id": {"type": "integer", "description": "Sprint ID"}
                },
                "required": ["sprint_id"]
            }
        ),
        Tool(
            name="jira_create_sprint",
            description="Create a new sprint.",
            inputSchema={
                "type": "object",
                "properties": {
                    "board_id": {"type": "integer", "description": "Board ID"},
                    "name": {"type": "string", "description": "Sprint name"},
                    "start_date": {"type": "string", "description": "Start date (ISO format)"},
                    "end_date": {"type": "string", "description": "End date (ISO format)"},
                    "goal": {"type": "string", "description": "Sprint goal"}
                },
                "required": ["board_id", "name"]
            }
        ),
        Tool(
            name="jira_update_sprint",
            description="Update a sprint.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sprint_id": {"type": "integer", "description": "Sprint ID"},
                    "name": {"type": "string", "description": "New name"},
                    "state": {"type": "string", "description": "New state (active, closed)"},
                    "start_date": {"type": "string", "description": "New start date"},
                    "end_date": {"type": "string", "description": "New end date"},
                    "goal": {"type": "string", "description": "New goal"}
                },
                "required": ["sprint_id"]
            }
        ),
        Tool(
            name="jira_get_sprint_issues",
            description="Get issues in a sprint.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sprint_id": {"type": "integer", "description": "Sprint ID"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["sprint_id"]
            }
        ),
        Tool(
            name="jira_move_issues_to_sprint",
            description="Move issues to a sprint.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sprint_id": {"type": "integer", "description": "Sprint ID"},
                    "issue_keys": {"type": "array", "items": {"type": "string"}, "description": "Issue keys to move"}
                },
                "required": ["sprint_id", "issue_keys"]
            }
        ),
        Tool(
            name="jira_move_issues_to_backlog",
            description="Move issues to backlog.",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_keys": {"type": "array", "items": {"type": "string"}, "description": "Issue keys to move"}
                },
                "required": ["issue_keys"]
            }
        ),

        # ========== Epics ==========
        Tool(
            name="jira_get_epic",
            description="Get epic details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "epic_key": {"type": "string", "description": "Epic issue key"}
                },
                "required": ["epic_key"]
            }
        ),
        Tool(
            name="jira_get_epic_issues",
            description="Get issues in an epic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "epic_key": {"type": "string", "description": "Epic issue key"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": ["epic_key"]
            }
        ),
        Tool(
            name="jira_move_issues_to_epic",
            description="Move issues to an epic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "epic_key": {"type": "string", "description": "Epic issue key"},
                    "issue_keys": {"type": "array", "items": {"type": "string"}, "description": "Issue keys to move"}
                },
                "required": ["epic_key", "issue_keys"]
            }
        ),

        # ========== Filters ==========
        Tool(
            name="jira_get_filter",
            description="Get a filter by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_id": {"type": "string", "description": "Filter ID"}
                },
                "required": ["filter_id"]
            }
        ),
        Tool(
            name="jira_get_favorite_filters",
            description="Get user's favorite filters.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="jira_search_filters",
            description="Search for filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_name": {"type": "string", "description": "Filter name to search"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": []
            }
        ),
        Tool(
            name="jira_create_filter",
            description="Create a new filter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Filter name"},
                    "jql": {"type": "string", "description": "JQL query"},
                    "description": {"type": "string", "description": "Filter description"},
                    "favourite": {"type": "boolean", "description": "Add to favourites", "default": False}
                },
                "required": ["name", "jql"]
            }
        ),
        Tool(
            name="jira_delete_filter",
            description="Delete a filter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_id": {"type": "string", "description": "Filter ID"}
                },
                "required": ["filter_id"]
            }
        ),

        # ========== Dashboards ==========
        Tool(
            name="jira_get_all_dashboards",
            description="List all dashboards.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Max results", "default": 50}
                },
                "required": []
            }
        ),
        Tool(
            name="jira_get_dashboard",
            description="Get dashboard by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dashboard_id": {"type": "string", "description": "Dashboard ID"}
                },
                "required": ["dashboard_id"]
            }
        ),

        # ========== Administration ==========
        Tool(
            name="jira_get_server_info",
            description="Get Jira server information.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="jira_get_all_fields",
            description="Get all fields (including custom fields).",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="jira_get_all_issue_types",
            description="Get all issue types.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="jira_get_all_priorities",
            description="Get all priorities.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="jira_get_all_statuses",
            description="Get all statuses.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="jira_get_all_resolutions",
            description="Get all resolutions.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),

        # ========== Raw API ==========
        Tool(
            name="jira_raw_api",
            description="Make a raw API call to Jira. Use this for operations not covered by other tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method (GET, POST, PUT, DELETE)"},
                    "endpoint": {"type": "string", "description": "API endpoint (e.g., '/rest/api/2/issue/PROJ-123')"},
                    "body": {"type": "object", "description": "Request body for POST/PUT requests"},
                    "params": {"type": "object", "description": "Query parameters"}
                },
                "required": ["method", "endpoint"]
            }
        ),
    ]


# ==================== Tool Handlers ====================

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        client = get_jira_client()
        result = ""

        # ========== Issues ==========
        if name == "jira_get_issue":
            issue = client.get_issue(arguments["issue_key"])
            result = format_issue(issue)

        elif name == "jira_search":
            max_results = arguments.get("max_results", 50)
            search_result = client.search_issues(arguments["jql"], max_results=max_results)
            result = format_issues_list(search_result.get('issues', []))

        elif name == "jira_create_issue":
            created = client.create_issue(
                project_key=arguments["project_key"],
                summary=arguments["summary"],
                issue_type=arguments.get("issue_type", "Task"),
                description=arguments.get("description", ""),
                priority=arguments.get("priority"),
                assignee=arguments.get("assignee"),
                labels=arguments.get("labels"),
                components=arguments.get("components"),
                fix_versions=arguments.get("fix_versions"),
                affects_versions=arguments.get("affects_versions"),
                custom_fields=arguments.get("custom_fields"),
            )
            result = f"Issue created: **{created['key']}**\nURL: {client.base_url}/browse/{created['key']}"

        elif name == "jira_update_issue":
            fields = {}
            if arguments.get("summary"):
                fields["summary"] = arguments["summary"]
            if arguments.get("description"):
                fields["description"] = arguments["description"]
            if arguments.get("priority"):
                fields["priority"] = {"name": arguments["priority"]}
            if arguments.get("assignee"):
                fields["assignee"] = {"name": arguments["assignee"]}
            if arguments.get("labels") is not None:
                fields["labels"] = arguments["labels"]

            if not fields:
                result = "No fields to update."
            else:
                client.update_issue(arguments["issue_key"], fields)
                result = f"Issue {arguments['issue_key']} updated. Fields: {', '.join(fields.keys())}"

        elif name == "jira_delete_issue":
            client.delete_issue(arguments["issue_key"], arguments.get("delete_subtasks", False))
            result = f"Issue {arguments['issue_key']} deleted."

        elif name == "jira_assign_issue":
            client.assign_issue(arguments["issue_key"], arguments.get("assignee"))
            assignee = arguments.get("assignee") or "Unassigned"
            result = f"Issue {arguments['issue_key']} assigned to {assignee}"

        # ========== Transitions ==========
        elif name == "jira_get_transitions":
            transitions = client.get_transitions(arguments["issue_key"])
            output = [f"# Available Transitions for {arguments['issue_key']}\n"]
            for t in transitions:
                output.append(f"- **{t['id']}**: {t['name']} -> {t.get('to', {}).get('name', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "jira_transition_issue":
            client.transition_issue(
                arguments["issue_key"],
                arguments["transition"],
                comment=arguments.get("comment"),
                resolution=arguments.get("resolution")
            )
            result = f"Issue {arguments['issue_key']} transitioned to '{arguments['transition']}'"

        # ========== Comments ==========
        elif name == "jira_add_comment":
            client.add_comment(arguments["issue_key"], arguments["comment"])
            result = f"Comment added to {arguments['issue_key']}"

        elif name == "jira_get_comments":
            comments = client.get_comments(arguments["issue_key"])
            output = [f"# Comments for {arguments['issue_key']} ({len(comments)} found)\n"]
            for c in comments:
                author = c.get('author', {}).get('displayName', 'Unknown')
                created = c.get('created', '')
                body = c.get('body', '')
                output.append(f"**{author}** ({created}):\n{body}\n")
            result = '\n'.join(output)

        # ========== Worklog ==========
        elif name == "jira_add_worklog":
            client.add_worklog(
                arguments["issue_key"],
                arguments["time_spent"],
                comment=arguments.get("comment"),
                started=arguments.get("started")
            )
            result = f"Worklog added to {arguments['issue_key']}: {arguments['time_spent']}"

        elif name == "jira_get_worklogs":
            worklogs = client.get_worklogs(arguments["issue_key"])
            output = [f"# Work Logs for {arguments['issue_key']} ({len(worklogs)} found)\n"]
            for w in worklogs:
                author = w.get('author', {}).get('displayName', 'Unknown')
                time_spent = w.get('timeSpent', '')
                started = w.get('started', '')
                output.append(f"- **{author}**: {time_spent} ({started})")
            result = '\n'.join(output)

        # ========== Issue Links ==========
        elif name == "jira_link_issues":
            client.link_issues(
                arguments["inward_issue"],
                arguments["outward_issue"],
                arguments.get("link_type", "Relates")
            )
            result = f"Linked {arguments['inward_issue']} -> {arguments['outward_issue']} ({arguments.get('link_type', 'Relates')})"

        elif name == "jira_get_link_types":
            link_types = client.get_issue_link_types()
            output = ["# Issue Link Types\n"]
            for lt in link_types:
                output.append(f"- **{lt['name']}**: {lt.get('inward', '')} / {lt.get('outward', '')}")
            result = '\n'.join(output)

        # ========== Watchers ==========
        elif name == "jira_get_watchers":
            watchers = client.get_watchers(arguments["issue_key"])
            output = [f"# Watchers for {arguments['issue_key']} ({watchers.get('watchCount', 0)} total)\n"]
            for w in watchers.get('watchers', []):
                output.append(f"- {w.get('displayName', w.get('name', 'Unknown'))}")
            result = '\n'.join(output)

        elif name == "jira_add_watcher":
            client.add_watcher(arguments["issue_key"], arguments["username"])
            result = f"Added {arguments['username']} as watcher to {arguments['issue_key']}"

        elif name == "jira_remove_watcher":
            client.remove_watcher(arguments["issue_key"], arguments["username"])
            result = f"Removed {arguments['username']} from watchers of {arguments['issue_key']}"

        # ========== Projects ==========
        elif name == "jira_get_all_projects":
            projects = client.get_all_projects()
            result = format_projects(projects)

        elif name == "jira_get_project":
            project = client.get_project(arguments["project_key"])
            output = [f"# Project: {project.get('name', 'Unknown')}"]
            output.append(f"**Key:** {project.get('key')}")
            output.append(f"**Lead:** {project.get('lead', {}).get('displayName', 'N/A')}")
            output.append(f"**Description:** {project.get('description', 'N/A')}")
            result = '\n'.join(output)

        elif name == "jira_get_project_components":
            components = client.get_project_components(arguments["project_key"])
            output = [f"# Components for {arguments['project_key']} ({len(components)} found)\n"]
            for c in components:
                lead = c.get('lead', {}).get('displayName', 'N/A') if c.get('lead') else 'N/A'
                output.append(f"- **{c.get('name')}**: {c.get('description', 'N/A')} (Lead: {lead})")
            result = '\n'.join(output)

        elif name == "jira_create_component":
            component = client.create_component(
                arguments["project_key"],
                arguments["name"],
                description=arguments.get("description"),
                lead=arguments.get("lead")
            )
            result = f"Component created: **{component.get('name')}** (ID: {component.get('id')})"

        elif name == "jira_get_project_versions":
            versions = client.get_project_versions(arguments["project_key"])
            output = [f"# Versions for {arguments['project_key']} ({len(versions)} found)\n"]
            for v in versions:
                released = "[Released]" if v.get('released') else "[Unreleased]"
                output.append(f"- **{v.get('name')}** {released}: {v.get('description', 'N/A')}")
            result = '\n'.join(output)

        elif name == "jira_create_version":
            version = client.create_version(
                arguments["project_key"],
                arguments["name"],
                description=arguments.get("description"),
                release_date=arguments.get("release_date"),
                released=arguments.get("released", False)
            )
            result = f"Version created: **{version.get('name')}** (ID: {version.get('id')})"

        elif name == "jira_get_project_statuses":
            statuses = client.get_project_statuses(arguments["project_key"])
            output = [f"# Statuses for {arguments['project_key']}\n"]
            for issue_type in statuses:
                output.append(f"## {issue_type.get('name', 'Unknown')}")
                for status in issue_type.get('statuses', []):
                    output.append(f"  - {status.get('name')}")
            result = '\n'.join(output)

        # ========== Users ==========
        elif name == "jira_get_user":
            user = client.get_user(arguments["username"])
            output = [f"# User: {user.get('displayName', 'Unknown')}"]
            output.append(f"**Username:** {user.get('name')}")
            output.append(f"**Email:** {user.get('emailAddress', 'N/A')}")
            output.append(f"**Active:** {user.get('active', False)}")
            result = '\n'.join(output)

        elif name == "jira_search_users":
            users = client.search_users(arguments["query"], arguments.get("max_results", 50))
            result = format_users(users)

        elif name == "jira_find_assignable_users":
            users = client.find_assignable_users(
                project_key=arguments.get("project_key"),
                issue_key=arguments.get("issue_key"),
                query=arguments.get("query"),
                max_results=arguments.get("max_results", 50)
            )
            result = format_users(users)

        elif name == "jira_get_current_user":
            user = client.get_current_user()
            output = [f"# Current User: {user.get('displayName', 'Unknown')}"]
            output.append(f"**Username:** {user.get('name')}")
            output.append(f"**Email:** {user.get('emailAddress', 'N/A')}")
            result = '\n'.join(output)

        # ========== Groups ==========
        elif name == "jira_get_all_groups":
            groups = client.get_all_groups()
            output = [f"# Groups ({len(groups)} found)\n"]
            for g in groups:
                output.append(f"- {g.get('name', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "jira_get_group_members":
            members = client.get_group_members(arguments["group_name"], arguments.get("max_results", 50))
            values = members.get('values', [])
            output = [f"# Members of {arguments['group_name']} ({len(values)} found)\n"]
            for m in values:
                output.append(f"- **{m.get('name')}**: {m.get('displayName', 'N/A')}")
            result = '\n'.join(output)

        elif name == "jira_add_user_to_group":
            client.add_user_to_group(arguments["group_name"], arguments["username"])
            result = f"Added {arguments['username']} to group {arguments['group_name']}"

        elif name == "jira_remove_user_from_group":
            client.remove_user_from_group(arguments["group_name"], arguments["username"])
            result = f"Removed {arguments['username']} from group {arguments['group_name']}"

        # ========== Boards ==========
        elif name == "jira_get_all_boards":
            boards = client.get_all_boards(
                board_type=arguments.get("board_type"),
                name=arguments.get("name"),
                project_key=arguments.get("project_key"),
                max_results=arguments.get("max_results", 50)
            )
            result = format_boards(boards)

        elif name == "jira_get_board":
            board = client.get_board(arguments["board_id"])
            output = [f"# Board: {board.get('name', 'Unknown')}"]
            output.append(f"**ID:** {board.get('id')}")
            output.append(f"**Type:** {board.get('type', 'N/A')}")
            result = '\n'.join(output)

        elif name == "jira_get_board_sprints":
            sprints = client.get_board_sprints(
                arguments["board_id"],
                state=arguments.get("state"),
                max_results=arguments.get("max_results", 50)
            )
            result = format_sprints(sprints)

        elif name == "jira_get_board_backlog":
            backlog = client.get_board_backlog(arguments["board_id"], arguments.get("max_results", 50))
            result = format_issues_list(backlog.get('issues', []))

        # ========== Sprints ==========
        elif name == "jira_get_sprint":
            sprint = client.get_sprint(arguments["sprint_id"])
            output = [f"# Sprint: {sprint.get('name', 'Unknown')}"]
            output.append(f"**ID:** {sprint.get('id')}")
            output.append(f"**State:** {sprint.get('state', 'N/A')}")
            output.append(f"**Goal:** {sprint.get('goal', 'N/A')}")
            output.append(f"**Start:** {sprint.get('startDate', 'N/A')}")
            output.append(f"**End:** {sprint.get('endDate', 'N/A')}")
            result = '\n'.join(output)

        elif name == "jira_create_sprint":
            sprint = client.create_sprint(
                arguments["board_id"],
                arguments["name"],
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
                goal=arguments.get("goal")
            )
            result = f"Sprint created: **{sprint.get('name')}** (ID: {sprint.get('id')})"

        elif name == "jira_update_sprint":
            sprint = client.update_sprint(
                arguments["sprint_id"],
                name=arguments.get("name"),
                state=arguments.get("state"),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
                goal=arguments.get("goal")
            )
            result = f"Sprint updated: **{sprint.get('name')}**"

        elif name == "jira_get_sprint_issues":
            issues = client.get_sprint_issues(arguments["sprint_id"], arguments.get("max_results", 50))
            result = format_issues_list(issues.get('issues', []))

        elif name == "jira_move_issues_to_sprint":
            client.move_issues_to_sprint(arguments["sprint_id"], arguments["issue_keys"])
            result = f"Moved {len(arguments['issue_keys'])} issues to sprint {arguments['sprint_id']}"

        elif name == "jira_move_issues_to_backlog":
            client.move_issues_to_backlog(arguments["issue_keys"])
            result = f"Moved {len(arguments['issue_keys'])} issues to backlog"

        # ========== Epics ==========
        elif name == "jira_get_epic":
            epic = client.get_epic(arguments["epic_key"])
            output = [f"# Epic: {epic.get('name', arguments['epic_key'])}"]
            output.append(f"**Key:** {epic.get('key', arguments['epic_key'])}")
            output.append(f"**Summary:** {epic.get('summary', 'N/A')}")
            output.append(f"**Done:** {epic.get('done', False)}")
            result = '\n'.join(output)

        elif name == "jira_get_epic_issues":
            issues = client.get_epic_issues(arguments["epic_key"], arguments.get("max_results", 50))
            result = format_issues_list(issues.get('issues', []))

        elif name == "jira_move_issues_to_epic":
            client.move_issues_to_epic(arguments["epic_key"], arguments["issue_keys"])
            result = f"Moved {len(arguments['issue_keys'])} issues to epic {arguments['epic_key']}"

        # ========== Filters ==========
        elif name == "jira_get_filter":
            filter_obj = client.get_filter(arguments["filter_id"])
            output = [f"# Filter: {filter_obj.get('name', 'Unknown')}"]
            output.append(f"**ID:** {filter_obj.get('id')}")
            output.append(f"**JQL:** {filter_obj.get('jql', 'N/A')}")
            output.append(f"**Owner:** {filter_obj.get('owner', {}).get('displayName', 'N/A')}")
            result = '\n'.join(output)

        elif name == "jira_get_favorite_filters":
            filters = client.get_favorite_filters()
            output = [f"# Favorite Filters ({len(filters)} found)\n"]
            for f in filters:
                output.append(f"- **{f.get('id')}**: {f.get('name', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "jira_search_filters":
            filters = client.search_filters(
                filter_name=arguments.get("filter_name"),
                max_results=arguments.get("max_results", 50)
            )
            values = filters.get('values', [])
            output = [f"# Filters ({len(values)} found)\n"]
            for f in values:
                output.append(f"- **{f.get('id')}**: {f.get('name', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "jira_create_filter":
            filter_obj = client.create_filter(
                arguments["name"],
                arguments["jql"],
                description=arguments.get("description"),
                favourite=arguments.get("favourite", False)
            )
            result = f"Filter created: **{filter_obj.get('name')}** (ID: {filter_obj.get('id')})"

        elif name == "jira_delete_filter":
            client.delete_filter(arguments["filter_id"])
            result = f"Filter {arguments['filter_id']} deleted."

        # ========== Dashboards ==========
        elif name == "jira_get_all_dashboards":
            dashboards = client.get_all_dashboards(arguments.get("max_results", 50))
            values = dashboards.get('dashboards', [])
            output = [f"# Dashboards ({len(values)} found)\n"]
            for d in values:
                output.append(f"- **{d.get('id')}**: {d.get('name', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "jira_get_dashboard":
            dashboard = client.get_dashboard(arguments["dashboard_id"])
            output = [f"# Dashboard: {dashboard.get('name', 'Unknown')}"]
            output.append(f"**ID:** {dashboard.get('id')}")
            result = '\n'.join(output)

        # ========== Administration ==========
        elif name == "jira_get_server_info":
            info = client.get_server_info()
            output = ["# Jira Server Information"]
            output.append(f"**Version:** {info.get('version', 'N/A')}")
            output.append(f"**Build:** {info.get('buildNumber', 'N/A')}")
            output.append(f"**Deployment:** {info.get('deploymentType', 'N/A')}")
            output.append(f"**Base URL:** {info.get('baseUrl', 'N/A')}")
            result = '\n'.join(output)

        elif name == "jira_get_all_fields":
            fields = client.get_all_fields()
            output = [f"# Fields ({len(fields)} found)\n"]
            for f in fields[:50]:  # Limit output
                custom = "[Custom]" if f.get('custom') else "[System]"
                output.append(f"- **{f.get('id')}**: {f.get('name', 'Unknown')} {custom}")
            if len(fields) > 50:
                output.append(f"\n... and {len(fields) - 50} more fields")
            result = '\n'.join(output)

        elif name == "jira_get_all_issue_types":
            types = client.get_all_issue_types()
            output = [f"# Issue Types ({len(types)} found)\n"]
            for t in types:
                subtask = "[Subtask]" if t.get('subtask') else ""
                output.append(f"- **{t.get('id')}**: {t.get('name', 'Unknown')} {subtask}")
            result = '\n'.join(output)

        elif name == "jira_get_all_priorities":
            priorities = client.get_all_priorities()
            output = [f"# Priorities ({len(priorities)} found)\n"]
            for p in priorities:
                output.append(f"- **{p.get('id')}**: {p.get('name', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "jira_get_all_statuses":
            statuses = client.get_all_statuses()
            output = [f"# Statuses ({len(statuses)} found)\n"]
            for s in statuses:
                category = s.get('statusCategory', {}).get('name', 'N/A')
                output.append(f"- **{s.get('id')}**: {s.get('name', 'Unknown')} ({category})")
            result = '\n'.join(output)

        elif name == "jira_get_all_resolutions":
            resolutions = client.get_all_resolutions()
            output = [f"# Resolutions ({len(resolutions)} found)\n"]
            for r in resolutions:
                output.append(f"- **{r.get('id')}**: {r.get('name', 'Unknown')}")
            result = '\n'.join(output)

        # ========== Raw API ==========
        elif name == "jira_raw_api":
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