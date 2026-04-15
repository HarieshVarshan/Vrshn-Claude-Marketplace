# Mira — PDK Sprint Jira Skill

## Overview

User-invocable skill (`/mira`) for managing Jira tasks in active PDK sprints via hashtag routing. Wraps the `jira-mcp` MCP tools — **requires `jira-mcp` to be installed and configured**.

## Prerequisites

- `jira-mcp` plugin installed and authenticated (`~/.config/atlassian/.env`)

## Usage

```
/mira create base jiras
/mira <description> #jira
/mira <description> #review
/mira <description> #bug
/mira <note> #chores
/mira <note> #meetings
/mira <context> #mira
```

## Hashtag Reference

| Hashtag | Action |
|---------|--------|
| `#jira` | Create Task — `component: subject` |
| `#review` | Create Task — `review: component: subject` |
| `#bug` | Create Bug |
| `#chores` | Append to sprint chores task description |
| `#meetings` | Append `[Meeting]` entry to sprint chores task |
| `#mira` | Update existing Jira (description + comment) |
| `#ocd`, `#done` | No-op |

## Key Behaviour

- All created issues are labeled `PDK_SPRINT` and moved to the active PDK sprint.
- Reference jiras (`PDK-19948` for tasks, `PDK-20159` for bugs) are used as structural guides only — fields are always populated from actual context.
- `create base jiras` bootstraps the standard chores task for a new sprint.

## Key Files

- `commands/mira.md` — full skill workflow invoked as `/mira`
