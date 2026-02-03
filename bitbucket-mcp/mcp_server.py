#!/usr/bin/env python3
"""
Bitbucket MCP Server - Provides Bitbucket Server tools for Claude.

Usage:
    python mcp_server.py

Environment Variables:
    BITBUCKET_CONFIG - Path to .env file (default: ~/.config/bitbucket-mcp/.env)
"""

import traceback
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from bitbucket_client import get_bitbucket_client

# Create the MCP server
server = Server("bitbucket")


def format_pr(pr: dict) -> str:
    """Format a pull request for display."""
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


def format_pr_list(prs: list) -> str:
    """Format a list of pull requests."""
    output = [f"# Pull Requests ({len(prs)} found)\n"]
    for pr in prs:
        pr_id = pr.get('id')
        title = pr.get('title', 'Untitled')
        author = pr.get('author', {}).get('user', {}).get('displayName', 'Unknown')
        state = pr.get('state', 'Unknown')
        output.append(f"- **#{pr_id}**: {title} [{state}] by {author}")
    return '\n'.join(output)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Bitbucket tools."""
    return [
        # ========== Pull Requests ==========
        Tool(
            name="bitbucket_get_pr",
            description="Get a pull request by URL or project/repo/PR ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pr_url": {"type": "string", "description": "Full PR URL"},
                    "project": {"type": "string", "description": "Project key (if not using URL)"},
                    "repo": {"type": "string", "description": "Repository slug (if not using URL)"},
                    "pr_id": {"type": "integer", "description": "PR ID (if not using URL)"}
                },
                "required": []
            }
        ),
        Tool(
            name="bitbucket_list_prs",
            description="List pull requests for a repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "state": {"type": "string", "description": "PR state: OPEN, MERGED, DECLINED, ALL", "default": "OPEN"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["project", "repo"]
            }
        ),
        Tool(
            name="bitbucket_get_pr_diff",
            description="Get the diff for a pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "pr_id": {"type": "integer", "description": "PR ID"},
                    "context_lines": {"type": "integer", "description": "Lines of context", "default": 10}
                },
                "required": ["project", "repo", "pr_id"]
            }
        ),
        Tool(
            name="bitbucket_get_pr_commits",
            description="Get commits in a pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "pr_id": {"type": "integer", "description": "PR ID"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["project", "repo", "pr_id"]
            }
        ),
        Tool(
            name="bitbucket_get_pr_activities",
            description="Get activities/comments on a pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "pr_id": {"type": "integer", "description": "PR ID"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["project", "repo", "pr_id"]
            }
        ),
        Tool(
            name="bitbucket_add_pr_comment",
            description="Add a comment to a pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "pr_id": {"type": "integer", "description": "PR ID"},
                    "comment": {"type": "string", "description": "Comment text"},
                    "file_path": {"type": "string", "description": "File path for inline comment"},
                    "line": {"type": "integer", "description": "Line number for inline comment"}
                },
                "required": ["project", "repo", "pr_id", "comment"]
            }
        ),
        Tool(
            name="bitbucket_approve_pr",
            description="Approve a pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "pr_id": {"type": "integer", "description": "PR ID"}
                },
                "required": ["project", "repo", "pr_id"]
            }
        ),
        Tool(
            name="bitbucket_unapprove_pr",
            description="Remove approval from a pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "pr_id": {"type": "integer", "description": "PR ID"}
                },
                "required": ["project", "repo", "pr_id"]
            }
        ),
        Tool(
            name="bitbucket_merge_pr",
            description="Merge a pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "pr_id": {"type": "integer", "description": "PR ID"}
                },
                "required": ["project", "repo", "pr_id"]
            }
        ),
        Tool(
            name="bitbucket_decline_pr",
            description="Decline a pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "pr_id": {"type": "integer", "description": "PR ID"}
                },
                "required": ["project", "repo", "pr_id"]
            }
        ),

        # ========== Repositories ==========
        Tool(
            name="bitbucket_get_repos",
            description="List repositories in a project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["project"]
            }
        ),
        Tool(
            name="bitbucket_get_repo",
            description="Get repository details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"}
                },
                "required": ["project", "repo"]
            }
        ),

        # ========== Branches ==========
        Tool(
            name="bitbucket_list_branches",
            description="List branches in a repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "filter": {"type": "string", "description": "Filter by name"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["project", "repo"]
            }
        ),
        Tool(
            name="bitbucket_get_default_branch",
            description="Get the default branch of a repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"}
                },
                "required": ["project", "repo"]
            }
        ),

        # ========== Tags ==========
        Tool(
            name="bitbucket_list_tags",
            description="List tags in a repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "filter": {"type": "string", "description": "Filter by name"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["project", "repo"]
            }
        ),

        # ========== Commits ==========
        Tool(
            name="bitbucket_list_commits",
            description="List commits in a repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "until": {"type": "string", "description": "Commit/branch to list until"},
                    "since": {"type": "string", "description": "Commit/branch to list since"},
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": ["project", "repo"]
            }
        ),
        Tool(
            name="bitbucket_get_commit",
            description="Get a specific commit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "commit_id": {"type": "string", "description": "Commit hash"}
                },
                "required": ["project", "repo", "commit_id"]
            }
        ),
        Tool(
            name="bitbucket_get_commit_diff",
            description="Get diff for a commit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "commit_id": {"type": "string", "description": "Commit hash"},
                    "context_lines": {"type": "integer", "description": "Lines of context", "default": 10}
                },
                "required": ["project", "repo", "commit_id"]
            }
        ),

        # ========== Files ==========
        Tool(
            name="bitbucket_get_file",
            description="Get file content from a repository.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "file_path": {"type": "string", "description": "Path to file"},
                    "ref": {"type": "string", "description": "Branch, tag, or commit"}
                },
                "required": ["project", "repo", "file_path"]
            }
        ),
        Tool(
            name="bitbucket_browse",
            description="Browse directory contents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project key"},
                    "repo": {"type": "string", "description": "Repository slug"},
                    "path": {"type": "string", "description": "Directory path", "default": ""},
                    "ref": {"type": "string", "description": "Branch, tag, or commit"},
                    "limit": {"type": "integer", "description": "Max results", "default": 100}
                },
                "required": ["project", "repo"]
            }
        ),

        # ========== Projects ==========
        Tool(
            name="bitbucket_get_all_projects",
            description="List all Bitbucket projects.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results", "default": 25}
                },
                "required": []
            }
        ),
        Tool(
            name="bitbucket_get_project",
            description="Get project details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string", "description": "Project key"}
                },
                "required": ["project_key"]
            }
        ),

        # ========== Raw API ==========
        Tool(
            name="bitbucket_raw_api",
            description="Make a raw API call to Bitbucket. Use this for operations not covered by other tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method (GET, POST, PUT, DELETE)"},
                    "endpoint": {"type": "string", "description": "API endpoint (e.g., '/rest/api/1.0/projects/PROJ/repos')"},
                    "body": {"type": "object", "description": "Request body for POST/PUT requests"},
                    "params": {"type": "object", "description": "Query parameters"}
                },
                "required": ["method", "endpoint"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        client = get_bitbucket_client()
        result = ""

        # ========== Pull Requests ==========
        if name == "bitbucket_get_pr":
            if arguments.get("pr_url"):
                pr = client.get_pull_request_by_url(arguments["pr_url"])
            else:
                pr = client.get_pull_request(arguments["project"], arguments["repo"], arguments["pr_id"])
            result = format_pr(pr)

        elif name == "bitbucket_list_prs":
            response = client.list_pull_requests(
                arguments["project"], arguments["repo"],
                state=arguments.get("state", "OPEN"),
                limit=arguments.get("limit", 25)
            )
            result = format_pr_list(response.get('values', []))

        elif name == "bitbucket_get_pr_diff":
            diff = client.get_pr_diff(
                arguments["project"], arguments["repo"], arguments["pr_id"],
                context_lines=arguments.get("context_lines", 10)
            )
            output = ["# Pull Request Diff\n"]
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

        elif name == "bitbucket_get_pr_commits":
            commits = client.get_pr_commits(
                arguments["project"], arguments["repo"], arguments["pr_id"],
                limit=arguments.get("limit", 25)
            )
            output = [f"# PR Commits ({len(commits.get('values', []))} found)\n"]
            for c in commits.get('values', []):
                sha = c.get('id', '')[:8]
                msg = c.get('message', 'No message').split('\n')[0]
                author = c.get('author', {}).get('name', 'Unknown')
                output.append(f"- **{sha}**: {msg} ({author})")
            result = '\n'.join(output)

        elif name == "bitbucket_get_pr_activities":
            activities = client.get_pr_activities(
                arguments["project"], arguments["repo"], arguments["pr_id"],
                limit=arguments.get("limit", 25)
            )
            output = [f"# PR Activities ({len(activities.get('values', []))} found)\n"]
            for a in activities.get('values', []):
                action = a.get('action', 'UNKNOWN')
                user = a.get('user', {}).get('displayName', 'Unknown')
                if a.get('comment'):
                    text = a['comment'].get('text', '')[:100]
                    output.append(f"- **{action}** by {user}: {text}...")
                else:
                    output.append(f"- **{action}** by {user}")
            result = '\n'.join(output)

        elif name == "bitbucket_add_pr_comment":
            client.add_pr_comment(
                arguments["project"], arguments["repo"], arguments["pr_id"],
                arguments["comment"],
                file_path=arguments.get("file_path"),
                line=arguments.get("line")
            )
            result = f"Comment added to PR #{arguments['pr_id']}"

        elif name == "bitbucket_approve_pr":
            client.approve_pr(arguments["project"], arguments["repo"], arguments["pr_id"])
            result = f"Approved PR #{arguments['pr_id']}"

        elif name == "bitbucket_unapprove_pr":
            client.unapprove_pr(arguments["project"], arguments["repo"], arguments["pr_id"])
            result = f"Removed approval from PR #{arguments['pr_id']}"

        elif name == "bitbucket_merge_pr":
            client.merge_pr(arguments["project"], arguments["repo"], arguments["pr_id"])
            result = f"Merged PR #{arguments['pr_id']}"

        elif name == "bitbucket_decline_pr":
            client.decline_pr(arguments["project"], arguments["repo"], arguments["pr_id"])
            result = f"Declined PR #{arguments['pr_id']}"

        # ========== Repositories ==========
        elif name == "bitbucket_get_repos":
            repos = client.get_repos(arguments["project"], arguments.get("limit", 25))
            output = [f"# Repositories ({len(repos.get('values', []))} found)\n"]
            for r in repos.get('values', []):
                output.append(f"- **{r.get('slug')}**: {r.get('name', 'N/A')}")
            result = '\n'.join(output)

        elif name == "bitbucket_get_repo":
            repo = client.get_repo(arguments["project"], arguments["repo"])
            output = [f"# Repository: {repo.get('name', 'Unknown')}"]
            output.append(f"**Slug:** {repo.get('slug')}")
            output.append(f"**Project:** {repo.get('project', {}).get('key', 'N/A')}")
            output.append(f"**Public:** {repo.get('public', False)}")
            result = '\n'.join(output)

        # ========== Branches ==========
        elif name == "bitbucket_list_branches":
            branches = client.get_branches(
                arguments["project"], arguments["repo"],
                filter_text=arguments.get("filter"),
                limit=arguments.get("limit", 25)
            )
            output = [f"# Branches ({len(branches.get('values', []))} found)\n"]
            for b in branches.get('values', []):
                default = " (default)" if b.get('isDefault') else ""
                output.append(f"- {b.get('displayId', 'Unknown')}{default}")
            result = '\n'.join(output)

        elif name == "bitbucket_get_default_branch":
            branch = client.get_default_branch(arguments["project"], arguments["repo"])
            result = f"Default branch: **{branch.get('displayId', 'Unknown')}**"

        # ========== Tags ==========
        elif name == "bitbucket_list_tags":
            tags = client.get_tags(
                arguments["project"], arguments["repo"],
                filter_text=arguments.get("filter"),
                limit=arguments.get("limit", 25)
            )
            output = [f"# Tags ({len(tags.get('values', []))} found)\n"]
            for t in tags.get('values', []):
                output.append(f"- {t.get('displayId', 'Unknown')}")
            result = '\n'.join(output)

        # ========== Commits ==========
        elif name == "bitbucket_list_commits":
            commits = client.get_commits(
                arguments["project"], arguments["repo"],
                until=arguments.get("until"),
                since=arguments.get("since"),
                limit=arguments.get("limit", 25)
            )
            output = [f"# Commits ({len(commits.get('values', []))} found)\n"]
            for c in commits.get('values', []):
                sha = c.get('id', '')[:8]
                msg = c.get('message', 'No message').split('\n')[0]
                author = c.get('author', {}).get('name', 'Unknown')
                output.append(f"- **{sha}**: {msg} ({author})")
            result = '\n'.join(output)

        elif name == "bitbucket_get_commit":
            commit = client.get_commit(arguments["project"], arguments["repo"], arguments["commit_id"])
            output = [f"# Commit: {commit.get('id', 'Unknown')[:8]}"]
            output.append(f"**Message:** {commit.get('message', 'N/A')}")
            output.append(f"**Author:** {commit.get('author', {}).get('name', 'Unknown')}")
            output.append(f"**Date:** {commit.get('authorTimestamp', 'N/A')}")
            result = '\n'.join(output)

        elif name == "bitbucket_get_commit_diff":
            diff = client.get_commit_diff(
                arguments["project"], arguments["repo"], arguments["commit_id"],
                context_lines=arguments.get("context_lines", 10)
            )
            output = ["# Commit Diff\n"]
            for diff_entry in diff.get('diffs', []):
                source = diff_entry.get('source', {}).get('toString', 'New file')
                dest = diff_entry.get('destination', {}).get('toString', 'Deleted')
                output.append(f"\n### {source} -> {dest}")
            result = '\n'.join(output)

        # ========== Files ==========
        elif name == "bitbucket_get_file":
            response = client.get_file_content(
                arguments["project"], arguments["repo"], arguments["file_path"],
                ref=arguments.get("ref")
            )
            lines = response.get('lines', [])
            content = '\n'.join(line.get('text', '') for line in lines)
            result = f"## {arguments['file_path']}\n\n```\n{content}\n```"

        elif name == "bitbucket_browse":
            response = client.browse_directory(
                arguments["project"], arguments["repo"],
                path=arguments.get("path", ""),
                ref=arguments.get("ref"),
                limit=arguments.get("limit", 100)
            )
            children = response.get('children', {}).get('values', [])
            output = [f"# Directory: {arguments.get('path', '/')}\n"]
            for child in children:
                path = child.get('path', {})
                name = path.get('name', 'Unknown')
                is_dir = child.get('type') == 'DIRECTORY'
                prefix = "[DIR]" if is_dir else "[FILE]"
                output.append(f"- {prefix} {name}")
            result = '\n'.join(output)

        # ========== Projects ==========
        elif name == "bitbucket_get_all_projects":
            projects = client.get_all_projects(arguments.get("limit", 25))
            output = [f"# Projects ({len(projects.get('values', []))} found)\n"]
            for p in projects.get('values', []):
                output.append(f"- **{p.get('key')}**: {p.get('name', 'Unknown')}")
            result = '\n'.join(output)

        elif name == "bitbucket_get_project":
            project = client.get_project(arguments["project_key"])
            output = [f"# Project: {project.get('name', 'Unknown')}"]
            output.append(f"**Key:** {project.get('key')}")
            output.append(f"**Description:** {project.get('description', 'N/A')}")
            output.append(f"**Public:** {project.get('public', False)}")
            result = '\n'.join(output)

        # ========== Raw API ==========
        elif name == "bitbucket_raw_api":
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
