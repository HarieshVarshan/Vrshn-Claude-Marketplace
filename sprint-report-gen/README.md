# sprint-report-gen

A Claude agent that generates a concise sprint status report by reading the latest Jira comment on each ticket in the active sprint.

## What It Does

1. Finds the active sprint for a given Jira project
2. Fetches all tickets in the sprint
3. Reads the most recent comment on each ticket
4. Classifies each ticket's status (Completed, In Progress, Blocked, On Hold, Needs Review, No Update)
5. Produces a report with sprint progress metrics, a table of tickets needing attention (completed tickets are excluded from the table), and actionable insights

## Output

The agent produces three outputs every time it runs:

1. **On-screen report** -- displayed directly in the conversation with metrics, ticket table, and insights
2. **Confluence page update** -- publishes an expandable macro to the sprint tracking page with sprint metrics and the ticket table (completed tickets excluded). Each sprint gets its own expandable section, latest on top.
3. **Excel file** -- `sprint-report-{sprint}-{date}.xlsx` with two sheets: Sprint Progress (metrics) and All Tickets (full breakdown with color-coded status)

## Prerequisites

- The **jira-mcp** plugin must be installed and configured (provides the Jira tools this agent uses)
- The **confluence-mcp** plugin must be installed and configured (for publishing reports)

## Usage

Ask Claude for a sprint report:

```
"Give me the sprint report for PROJ"
"What's the status of our current sprint?"
"Sprint report for board 142"
```

The agent will find the active sprint, read the latest comments, and produce a report like:

```
## Sprint Report: Sprint 24.1
**Board:** My Project Board | **Period:** 2026-02-10 - 2026-02-24

### Sprint Progress
| Metric | Value |
|--------|-------|
| Total Tickets | 10 |
| Completed | 4 (40%) |
| Remaining | 6 (60%) |
| Blocked | 2 (20%) |
| Sprint Health | At Risk |

### Tickets Needing Attention
| # | Key | Summary | Assignee | Status | Latest Update |
|---|-----|---------|----------|--------|---------------|
| 1 | PROJ-102 | Fix payment bug | @jane | Blocked | Waiting for DB team access |
| 2 | PROJ-103 | Update docs | @bob | No Update | — |
| ... | ... | ... | ... | ... | ... |

### Completed This Sprint (4 tickets)
PROJ-101, PROJ-105, PROJ-107, PROJ-109

### Insights
- 40% completion with 3 days remaining -- at risk of missing sprint goal
- 2 tickets blocked on external team dependencies
- PROJ-103 has no updates this sprint
```

## Project Structure

```
sprint-report-gen/
├── .claude-plugin/
│   └── plugin.json            # Plugin metadata
├── agents/
│   └── sprint-reporter.md     # Agent definition
└── README.md
```
