# Jira Head Start

Nightly analysis agent + local dashboard for open Jira tickets.

## What It Does

For each open ticket assigned to you it:
1. Fetches full Jira context (description, all comments, linked issues)
2. Searches local code repos (`~/ti/`) for relevant files
3. Reads related Confluence pages and PDS documents
4. Checks Bitbucket for related PRs
5. Checks Jenkins if it's a CI/pipeline ticket
6. Writes a rich markdown analysis to `~/.local/share/jira-headstart/<KEY>/analysis.md`

**Read-only — never touches Jira, code, or any external system.**

## Quick Start

### 1. Install server dependencies

```bash
mkdir -p ~/.local/share/jira-mcp-headstart/venv
python -m venv ~/.local/share/jira-mcp-headstart/venv
~/.local/share/jira-mcp-headstart/venv/bin/pip install -r \
  /path/to/skills/jira-headstart/server/requirements.txt
```

### 2. Start the dashboard

```bash
cd skills/jira-headstart/server
python server.py          # http://localhost:7337
python server.py --port 8080  # custom port
```

### 3. Run the analysis agent

In Claude Code:
```
run the jira-headstart agent
```

Or for a single ticket:
```
run jira-headstart for PDK-19948
```

### 4. Set up nightly cron (TODO — not yet working)

```bash
# NOTE: Disabled — claude --print doesn't load MCP servers in non-interactive mode.
# Needs investigation before enabling.
#
# crontab -e
# 30 22 * * * claude --print "run the jira-headstart agent" >> ~/.local/share/jira-headstart/cron.log 2>&1
```

## Dashboard Features

- **Filter tabs**: All Open / External Bugs / Internal Bugs
- **Analysis badges**: ✓ analyzed / stale / – (not yet analyzed)
- **Universal search**: search Jira beyond your current filter (Enter key)
- **Markdown rendering**: full rendered analysis with syntax highlighting
- **Open in Jira**: direct link from every ticket

## Output Layout

```
~/.local/share/jira-headstart/
├── index.json          ← analysis registry (key → metadata)
└── <KEY>/
    └── analysis.md     ← rich analysis for that ticket
```

## Analysis Agent

The agent is defined in `agents/jira-headstart.md`. It is invoked via Claude Code
with full access to all configured MCP tools.

### Context sources used per ticket

| Source | What it provides |
|--------|-----------------|
| Jira MCP | Full description, all comments, linked issues |
| Local repos (`~/ti/`) | Relevant source files, README context |
| Confluence MCP | Design documents, specs |
| PDS MCP | SoC/IP specification documents |
| Bitbucket MCP | Related PRs, code review context |
| Jenkins MCP | CI job configs and build logs (for pipeline tickets) |

### Repo mapping

The agent maps ticket signals to local repo paths:

| Signal | Local repo |
|--------|-----------|
| `pdk`, `tda4`, `jacinto` | `~/ti/PROCESSOR_SDK/pdk/` |
| `mcu_sdk`, `tda5`, `tda54`, `hal` | `~/ti/PROCESSOR_SDK/repo_mcu_sdk/` |
| `mcu_plus`, `j722s`, `k3` | `~/ti/PROCESSOR_SDK_MCU/j722s/` |
| `csirx`, `vision`, `tiovx` | `~/ti/PROCESSOR_SDK_VISION/` |
| `cd-sync`, `promotion`, `ci` | `~/ti/SITMPUSW/cd-sync/` |
| `sysfw`, `sciclient` | `~/ti/SYSFW/` |

## Key Files

| File | Purpose |
|------|---------|
| `agents/jira-headstart.md` | Analysis agent workflow |
| `server/server.py` | Flask dashboard server |
| `server/index.html` | Dashboard UI (single-file, vanilla JS + Tailwind) |
| `server/requirements.txt` | Python dependencies |
