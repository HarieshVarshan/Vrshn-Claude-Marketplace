# Vrshn Claude Marketplace

A collection of MCP (Model Context Protocol) server plugins for Claude Code.

## Available Plugins

### MCP Server Plugins

| Plugin | Tools | Description |
|--------|-------|-------------|
| [jira-mcp](./jira-mcp/) | 40+ | Jira Data Center - issues, projects, sprints, boards, epics, workflows |
| [confluence-mcp](./confluence-mcp/) | 41 | Confluence Data Center - pages (Markdown-native), spaces, attachments, search, watch |
| [bitbucket-mcp](./bitbucket-mcp/) | 55+ | Bitbucket Server - PRs, repos, branches, tags, commits, permissions |
| [jenkins-mcp](./jenkins-mcp/) | 25+ | Jenkins CI/CD - jobs, builds, nodes, artifacts, views, credentials |
| [klocwork-mcp](./klocwork-mcp/) | 20+ | Klocwork static analysis - projects, issues, modules, builds, users |
| [email-mcp](./email-mcp/) | 8 | Email via IMAP/SMTP - send, read, search, delete, move, folders, attachments |
| [webex-mcp](./webex-mcp/) | 25 | Cisco Webex - people, teams, rooms, messages, memberships, webhooks |
| [excalidraw-mcp](./excalidraw-mcp/) | 15+ | Excalidraw diagrams - create, edit, manage with live canvas |
| [talk2docs](./talk2docs/) | 3 | Local document semantic search using ChromaDB and Ollama embeddings |

### Agent / Command Plugins (no MCP server)

| Plugin | Description |
|--------|-------------|
| [sprint-report-gen](./sprint-report-gen/) | Agent that generates sprint status reports from Jira comments |
| [obsidian-vault](./obsidian-vault/) | Capture knowledge from Claude sessions into Obsidian vault |

### Skills

| Skill | Command | Description |
|-------|---------|-------------|
| [mira](./skills/mira/) | `/mira` | Smart Jira task manager for PDK sprints — hashtag-routed issue creation (#jira, #review, #bug, #chores, #meetings, #mira) |
| [jira-headstart](./skills/jira-headstart/) | agent | Nightly deep-analysis of open Jira tickets — Jira + Bitbucket + Confluence + PDS + local repos → local markdown + dashboard at :7337 |

## Quick Start

### Step 1: Add This Marketplace to Claude Code

Open or create `~/.claude/settings.json` and add the marketplace configuration:

```json
{
  "marketplaces": [
    {
      "name": "Vrshn Marketplace",
      "url": "https://bitbucket.itg.ti.com/projects/vrshn/repos/vrshn-claude-marketplace/raw/.claude-plugin/marketplace.json?at=refs/heads/master"
    }
  ]
}
```

### Step 2: Clone the Repository

```bash
git clone ssh://git@bitbucket.itg.ti.com/vrshn/vrshn-claude-marketplace.git
cd vrshn-claude-marketplace
```

### Step 3: Install a Plugin

Each Python MCP plugin follows the same setup pattern:

```bash
# Create a venv in the standard location
mkdir -p ~/.local/share/<plugin-name>
python -m venv ~/.local/share/<plugin-name>/venv

# Install dependencies
~/.local/share/<plugin-name>/venv/bin/pip install -r <plugin-name>/requirements.txt
```

Replace `<plugin-name>` with the plugin directory name (e.g., `jira-mcp`, `email-mcp`, `webex-mcp`).

## Configuration

Most plugins read credentials from `~/.config/atlassian/.env`:

```bash
mkdir -p ~/.config/atlassian
chmod 700 ~/.config/atlassian

cat > ~/.config/atlassian/.env << 'EOF'
# Jira
JIRA_URL=https://jira.your-company.com
JIRA_USERNAME=your_username
JIRA_TOKEN=your_personal_access_token

# Confluence
CONFLUENCE_URL=https://confluence.your-company.com
CONFLUENCE_USERNAME=your_username
CONFLUENCE_TOKEN=your_personal_access_token

# Bitbucket
BITBUCKET_URL=https://bitbucket.your-company.com
BITBUCKET_USERNAME=your_username
BITBUCKET_TOKEN=your_personal_access_token

# Jenkins
JENKINS_SERVERS=server1
JENKINS_SERVER1_URL=https://jenkins.your-company.com
JENKINS_SERVER1_USERNAME=your_username
JENKINS_SERVER1_TOKEN=your_api_token

# Email (IMAP/SMTP)
EMAIL_USER=your-email@company.com
EMAIL_PASSWORD=your-password
IMAP_HOST=imap.company.com
IMAP_PORT=993
IMAP_SECURE=true
SMTP_HOST=smtp.company.com
SMTP_PORT=587
SMTP_STARTTLS=true

# Webex
WEBEX_ACCESS_TOKEN=your-webex-token

# Optional: proxy settings
# HTTP_PROXY=http://proxy.company.com:8080
# HTTPS_PROXY=https://proxy.company.com:8080
# VERIFY_SSL=true
EOF

chmod 600 ~/.config/atlassian/.env
```

Each plugin also supports an override file at `~/.config/<plugin-name>/.env` if you need plugin-specific settings.

See each plugin's `CLAUDE.md` for detailed configuration.

## Managing MCP Servers

```bash
# List registered MCP servers
claude mcp list

# Remove an MCP server
claude mcp remove <server-name>

# Check MCP server status
claude mcp status
```

## Creating Your Own Plugin

Each plugin follows this structure:

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json       # Plugin metadata
├── mcp-servers.json      # MCP server configuration
├── mcp_server.py         # MCP server implementation
├── <service>_client.py   # API client + config loader
├── requirements.txt      # Python dependencies
└── CLAUDE.md             # Quick reference for Claude
```

## License

MIT
