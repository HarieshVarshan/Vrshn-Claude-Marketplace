#!/usr/bin/env python3
"""
Webex MCP Server - Provides Cisco Webex tools for Claude.

Usage:
    python mcp_server.py

Environment Variables:
    WEBEX_CONFIG - Path to .env file (default: ~/.config/atlassian/.env)
"""

import traceback
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from webex_client import get_webex_client

server = Server("webex")


# ==================== Formatters ====================

def _format_person(p: dict) -> str:
    output = [f"# {p.get('displayName', 'Unknown')}"]
    output.append(f"**ID:** `{p.get('id', 'N/A')}`")
    emails = p.get('emails', [])
    if emails:
        output.append(f"**Email:** {', '.join(emails)}")
    output.append(f"**Org ID:** `{p.get('orgId', 'N/A')}`")
    output.append(f"**Status:** {p.get('status', 'N/A')}")
    output.append(f"**Type:** {p.get('type', 'N/A')}")
    if p.get('created'):
        output.append(f"**Created:** {p['created']}")
    if p.get('lastActivity'):
        output.append(f"**Last Activity:** {p['lastActivity']}")
    return '\n'.join(output)


def _format_person_short(p: dict) -> str:
    email = p.get('emails', ['N/A'])[0] if p.get('emails') else 'N/A'
    return f"- **{p.get('displayName', 'Unknown')}** ({email}) `{p.get('id', '')}`"


def _format_org(o: dict) -> str:
    output = [f"# {o.get('displayName', 'Unknown')}"]
    output.append(f"**ID:** `{o.get('id', 'N/A')}`")
    output.append(f"**Created:** {o.get('created', 'N/A')}")
    return '\n'.join(output)


def _format_team(t: dict) -> str:
    output = [f"# {t.get('name', 'Unknown')}"]
    output.append(f"**ID:** `{t.get('id', 'N/A')}`")
    if t.get('description'):
        output.append(f"**Description:** {t['description']}")
    output.append(f"**Created:** {t.get('created', 'N/A')}")
    return '\n'.join(output)


def _format_room(r: dict) -> str:
    output = [f"# {r.get('title', 'Untitled')}"]
    output.append(f"**ID:** `{r.get('id', 'N/A')}`")
    output.append(f"**Type:** {r.get('type', 'N/A')}")
    if r.get('teamId'):
        output.append(f"**Team ID:** `{r['teamId']}`")
    output.append(f"**Created:** {r.get('created', 'N/A')}")
    if r.get('lastActivity'):
        output.append(f"**Last Activity:** {r['lastActivity']}")
    output.append(f"**Locked:** {r.get('isLocked', False)}")
    return '\n'.join(output)


def _format_message(m: dict) -> str:
    output = [f"# Message"]
    output.append(f"**ID:** `{m.get('id', 'N/A')}`")
    output.append(f"**Room ID:** `{m.get('roomId', 'N/A')}`")
    output.append(f"**Person:** {m.get('personEmail', 'N/A')}")
    output.append(f"**Created:** {m.get('created', 'N/A')}")
    if m.get('markdown'):
        output.append(f"\n## Content (Markdown)\n{m['markdown']}")
    elif m.get('html'):
        output.append(f"\n## Content (HTML)\n{m['html']}")
    elif m.get('text'):
        output.append(f"\n## Content\n{m['text']}")
    if m.get('files'):
        output.append(f"\n**Files:** {len(m['files'])} attached")
    return '\n'.join(output)


def _format_membership(mb: dict) -> str:
    output = [f"# Membership"]
    output.append(f"**ID:** `{mb.get('id', 'N/A')}`")
    output.append(f"**Room ID:** `{mb.get('roomId', 'N/A')}`")
    output.append(f"**Person:** {mb.get('personDisplayName', 'N/A')} ({mb.get('personEmail', 'N/A')})")
    output.append(f"**Moderator:** {mb.get('isModerator', False)}")
    output.append(f"**Created:** {mb.get('created', 'N/A')}")
    return '\n'.join(output)


def _format_webhook(w: dict) -> str:
    output = [f"# {w.get('name', 'Untitled Webhook')}"]
    output.append(f"**ID:** `{w.get('id', 'N/A')}`")
    output.append(f"**Target URL:** {w.get('targetUrl', 'N/A')}")
    output.append(f"**Resource:** {w.get('resource', 'N/A')}")
    output.append(f"**Event:** {w.get('event', 'N/A')}")
    if w.get('filter'):
        output.append(f"**Filter:** {w['filter']}")
    output.append(f"**Status:** {w.get('status', 'N/A')}")
    output.append(f"**Created:** {w.get('created', 'N/A')}")
    return '\n'.join(output)


# ==================== Tool Definitions ====================

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ========== People ==========
        Tool(
            name="webex_get_me",
            description="Get the current authenticated Webex user's details.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="webex_list_people",
            description="Search for Webex people by email or display name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Email address to search for"},
                    "display_name": {"type": "string", "description": "Display name to search for"},
                    "max": {"type": "integer", "description": "Maximum results (default: 100)"}
                },
                "required": []
            }
        ),
        Tool(
            name="webex_get_person",
            description="Get details for a specific Webex person by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "person_id": {"type": "string", "description": "Person ID"}
                },
                "required": ["person_id"]
            }
        ),

        # ========== Organizations ==========
        Tool(
            name="webex_list_organizations",
            description="List Webex organizations the user belongs to.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="webex_get_organization",
            description="Get details for a specific Webex organization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "org_id": {"type": "string", "description": "Organization ID"}
                },
                "required": ["org_id"]
            }
        ),

        # ========== Teams ==========
        Tool(
            name="webex_list_teams",
            description="List Webex teams the user is a member of.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max": {"type": "integer", "description": "Maximum results (default: 100)"}
                },
                "required": []
            }
        ),
        Tool(
            name="webex_create_team",
            description="Create a new Webex team.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Team name"},
                    "description": {"type": "string", "description": "Team description"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="webex_get_team",
            description="Get details for a specific Webex team.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {"type": "string", "description": "Team ID"}
                },
                "required": ["team_id"]
            }
        ),
        Tool(
            name="webex_delete_team",
            description="Delete a Webex team.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {"type": "string", "description": "Team ID"}
                },
                "required": ["team_id"]
            }
        ),

        # ========== Rooms ==========
        Tool(
            name="webex_list_rooms",
            description="List Webex rooms/spaces the user is a member of.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {"type": "string", "description": "Filter by team ID"},
                    "type": {"type": "string", "description": "Filter by type: 'direct' or 'group'"},
                    "max": {"type": "integer", "description": "Maximum results (default: 100)"}
                },
                "required": []
            }
        ),
        Tool(
            name="webex_create_room",
            description="Create a new Webex room/space.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Room title"},
                    "team_id": {"type": "string", "description": "Team ID to associate with"}
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="webex_get_room",
            description="Get details for a specific Webex room.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {"type": "string", "description": "Room ID"}
                },
                "required": ["room_id"]
            }
        ),
        Tool(
            name="webex_delete_room",
            description="Delete a Webex room.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {"type": "string", "description": "Room ID"}
                },
                "required": ["room_id"]
            }
        ),

        # ========== Messages ==========
        Tool(
            name="webex_list_messages",
            description="List messages in a Webex room.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {"type": "string", "description": "Room ID"},
                    "max": {"type": "integer", "description": "Maximum results (default: 50)"},
                    "before": {"type": "string", "description": "List messages before this date (ISO 8601)"},
                    "before_message": {"type": "string", "description": "List messages before this message ID"}
                },
                "required": ["room_id"]
            }
        ),
        Tool(
            name="webex_create_message",
            description="Send a Webex message to a room or person. Specify roomId OR toPersonId/toPersonEmail. Provide text, markdown, or html content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {"type": "string", "description": "Room ID (for room messages)"},
                    "to_person_id": {"type": "string", "description": "Person ID (for direct messages)"},
                    "to_person_email": {"type": "string", "description": "Person email (for direct messages)"},
                    "text": {"type": "string", "description": "Plain text content"},
                    "markdown": {"type": "string", "description": "Markdown content"},
                    "html": {"type": "string", "description": "HTML content"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "Array of file URLs to attach"}
                },
                "required": []
            }
        ),
        Tool(
            name="webex_get_message",
            description="Get details for a specific Webex message.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Message ID"}
                },
                "required": ["message_id"]
            }
        ),
        Tool(
            name="webex_delete_message",
            description="Delete a Webex message.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Message ID"}
                },
                "required": ["message_id"]
            }
        ),

        # ========== Memberships ==========
        Tool(
            name="webex_list_memberships",
            description="List Webex room memberships. Filter by room, person, or email.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {"type": "string", "description": "Filter by room ID"},
                    "person_id": {"type": "string", "description": "Filter by person ID"},
                    "person_email": {"type": "string", "description": "Filter by person email"},
                    "max": {"type": "integer", "description": "Maximum results (default: 100)"}
                },
                "required": []
            }
        ),
        Tool(
            name="webex_create_membership",
            description="Add a person to a Webex room. Specify personId OR personEmail.",
            inputSchema={
                "type": "object",
                "properties": {
                    "room_id": {"type": "string", "description": "Room ID"},
                    "person_id": {"type": "string", "description": "Person ID to add"},
                    "person_email": {"type": "string", "description": "Person email to add"},
                    "is_moderator": {"type": "boolean", "description": "Make them a moderator (default: false)"}
                },
                "required": ["room_id"]
            }
        ),
        Tool(
            name="webex_get_membership",
            description="Get details for a specific Webex room membership.",
            inputSchema={
                "type": "object",
                "properties": {
                    "membership_id": {"type": "string", "description": "Membership ID"}
                },
                "required": ["membership_id"]
            }
        ),
        Tool(
            name="webex_delete_membership",
            description="Remove a person from a Webex room.",
            inputSchema={
                "type": "object",
                "properties": {
                    "membership_id": {"type": "string", "description": "Membership ID"}
                },
                "required": ["membership_id"]
            }
        ),

        # ========== Webhooks ==========
        Tool(
            name="webex_list_webhooks",
            description="List Webex webhooks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max": {"type": "integer", "description": "Maximum results (default: 100)"}
                },
                "required": []
            }
        ),
        Tool(
            name="webex_create_webhook",
            description="Create a new Webex webhook for real-time event notifications.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Webhook name"},
                    "target_url": {"type": "string", "description": "URL to send events to"},
                    "resource": {"type": "string", "description": "Resource type: messages, memberships, rooms, meetings, recordings, attachmentActions"},
                    "event": {"type": "string", "description": "Event type: created, updated, deleted, started, ended"},
                    "filter": {"type": "string", "description": "Filter expression (e.g. roomId=...)"},
                    "secret": {"type": "string", "description": "Secret for signature validation"}
                },
                "required": ["name", "target_url", "resource", "event"]
            }
        ),
        Tool(
            name="webex_get_webhook",
            description="Get details for a specific Webex webhook.",
            inputSchema={
                "type": "object",
                "properties": {
                    "webhook_id": {"type": "string", "description": "Webhook ID"}
                },
                "required": ["webhook_id"]
            }
        ),
        Tool(
            name="webex_delete_webhook",
            description="Delete a Webex webhook.",
            inputSchema={
                "type": "object",
                "properties": {
                    "webhook_id": {"type": "string", "description": "Webhook ID"}
                },
                "required": ["webhook_id"]
            }
        ),
    ]


# ==================== Tool Handlers ====================

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        client = get_webex_client()
        result = ""

        # ========== People ==========
        if name == "webex_get_me":
            person = client.get_me()
            result = _format_person(person)

        elif name == "webex_list_people":
            people = client.list_people(
                email=arguments.get("email"),
                display_name=arguments.get("display_name"),
                max_results=arguments.get("max", 100),
            )
            output = [f"# People ({len(people)} found)\n"]
            for p in people:
                output.append(_format_person_short(p))
            result = '\n'.join(output)

        elif name == "webex_get_person":
            person = client.get_person(arguments["person_id"])
            result = _format_person(person)

        # ========== Organizations ==========
        elif name == "webex_list_organizations":
            orgs = client.list_organizations()
            output = [f"# Organizations ({len(orgs)} found)\n"]
            for o in orgs:
                output.append(f"- **{o.get('displayName', 'Unknown')}** `{o.get('id', '')}`")
            result = '\n'.join(output)

        elif name == "webex_get_organization":
            org = client.get_organization(arguments["org_id"])
            result = _format_org(org)

        # ========== Teams ==========
        elif name == "webex_list_teams":
            teams = client.list_teams(arguments.get("max", 100))
            output = [f"# Teams ({len(teams)} found)\n"]
            for t in teams:
                desc = f" - {t['description']}" if t.get('description') else ""
                output.append(f"- **{t.get('name', 'Unknown')}**{desc} `{t.get('id', '')}`")
            result = '\n'.join(output)

        elif name == "webex_create_team":
            team = client.create_team(
                name=arguments["name"],
                description=arguments.get("description"),
            )
            result = f"Team created.\n\n{_format_team(team)}"

        elif name == "webex_get_team":
            team = client.get_team(arguments["team_id"])
            result = _format_team(team)

        elif name == "webex_delete_team":
            client.delete_team(arguments["team_id"])
            result = f"Team `{arguments['team_id']}` deleted."

        # ========== Rooms ==========
        elif name == "webex_list_rooms":
            rooms = client.list_rooms(
                team_id=arguments.get("team_id"),
                room_type=arguments.get("type"),
                max_results=arguments.get("max", 100),
            )
            output = [f"# Rooms ({len(rooms)} found)\n"]
            for r in rooms:
                rtype = f" [{r.get('type', '')}]" if r.get('type') else ""
                output.append(f"- **{r.get('title', 'Untitled')}**{rtype} `{r.get('id', '')}`")
            result = '\n'.join(output)

        elif name == "webex_create_room":
            room = client.create_room(
                title=arguments["title"],
                team_id=arguments.get("team_id"),
            )
            result = f"Room created.\n\n{_format_room(room)}"

        elif name == "webex_get_room":
            room = client.get_room(arguments["room_id"])
            result = _format_room(room)

        elif name == "webex_delete_room":
            client.delete_room(arguments["room_id"])
            result = f"Room `{arguments['room_id']}` deleted."

        # ========== Messages ==========
        elif name == "webex_list_messages":
            messages = client.list_messages(
                room_id=arguments["room_id"],
                max_results=arguments.get("max", 50),
                before=arguments.get("before"),
                before_message=arguments.get("before_message"),
            )
            output = [f"# Messages ({len(messages)} found)\n"]
            for m in messages:
                sender = m.get('personEmail', 'Unknown')
                created = m.get('created', '')[:19]
                text = (m.get('text') or m.get('markdown') or '(no text)')[:120]
                output.append(f"- **{sender}** ({created}): {text}")
                output.append(f"  ID: `{m.get('id', '')}`")
            result = '\n'.join(output)

        elif name == "webex_create_message":
            msg = client.create_message(
                room_id=arguments.get("room_id"),
                to_person_id=arguments.get("to_person_id"),
                to_person_email=arguments.get("to_person_email"),
                text=arguments.get("text"),
                markdown=arguments.get("markdown"),
                html=arguments.get("html"),
                files=arguments.get("files"),
            )
            result = f"Message sent.\n\n{_format_message(msg)}"

        elif name == "webex_get_message":
            msg = client.get_message(arguments["message_id"])
            result = _format_message(msg)

        elif name == "webex_delete_message":
            client.delete_message(arguments["message_id"])
            result = f"Message `{arguments['message_id']}` deleted."

        # ========== Memberships ==========
        elif name == "webex_list_memberships":
            memberships = client.list_memberships(
                room_id=arguments.get("room_id"),
                person_id=arguments.get("person_id"),
                person_email=arguments.get("person_email"),
                max_results=arguments.get("max", 100),
            )
            output = [f"# Memberships ({len(memberships)} found)\n"]
            for mb in memberships:
                mod = " [Moderator]" if mb.get('isModerator') else ""
                output.append(f"- **{mb.get('personDisplayName', 'Unknown')}** ({mb.get('personEmail', 'N/A')}){mod}")
                output.append(f"  ID: `{mb.get('id', '')}`")
            result = '\n'.join(output)

        elif name == "webex_create_membership":
            mb = client.create_membership(
                room_id=arguments["room_id"],
                person_id=arguments.get("person_id"),
                person_email=arguments.get("person_email"),
                is_moderator=arguments.get("is_moderator", False),
            )
            result = f"Membership created.\n\n{_format_membership(mb)}"

        elif name == "webex_get_membership":
            mb = client.get_membership(arguments["membership_id"])
            result = _format_membership(mb)

        elif name == "webex_delete_membership":
            client.delete_membership(arguments["membership_id"])
            result = f"Membership `{arguments['membership_id']}` removed."

        # ========== Webhooks ==========
        elif name == "webex_list_webhooks":
            webhooks = client.list_webhooks(arguments.get("max", 100))
            output = [f"# Webhooks ({len(webhooks)} found)\n"]
            for w in webhooks:
                output.append(f"- **{w.get('name', 'Untitled')}** ({w.get('resource', '')}/{w.get('event', '')}) [{w.get('status', '')}]")
                output.append(f"  ID: `{w.get('id', '')}`")
            result = '\n'.join(output)

        elif name == "webex_create_webhook":
            wh = client.create_webhook(
                name=arguments["name"],
                target_url=arguments["target_url"],
                resource=arguments["resource"],
                event=arguments["event"],
                filter_expr=arguments.get("filter"),
                secret=arguments.get("secret"),
            )
            result = f"Webhook created.\n\n{_format_webhook(wh)}"

        elif name == "webex_get_webhook":
            wh = client.get_webhook(arguments["webhook_id"])
            result = _format_webhook(wh)

        elif name == "webex_delete_webhook":
            client.delete_webhook(arguments["webhook_id"])
            result = f"Webhook `{arguments['webhook_id']}` deleted."

        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        error_msg = f"**Error** in `{name}`: {str(e)}\n\n<details><summary>Traceback</summary>\n\n```\n{traceback.format_exc()}\n```\n</details>"
        return [TextContent(type="text", text=error_msg)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
