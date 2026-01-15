# Vrshn Claude Marketplace

A collection of MCP (Model Context Protocol) server plugins for Claude Code.

## Available Plugins

| Plugin | Description |
|--------|-------------|
| [atlassian-mcp](./atlassian-mcp/) | Jira, Confluence, and Bitbucket integration - search, read, create, and manage issues, pages, and pull requests |
| [talk2docs](./talk2docs/) | Local document semantic search using ChromaDB and Ollama embeddings |

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

If you already have other settings in the file, just add the `marketplaces` array alongside them.

### Step 2: Clone the Repository

```bash
git clone ssh://git@bitbucket.itg.ti.com/vrshn/vrshn-claude-marketplace.git
cd vrshn-claude-marketplace
```

### Step 3: Install a Plugin

Choose which plugin to install and follow the setup instructions below.

---

## Plugin Setup Instructions

### Atlassian MCP Setup

This plugin provides tools for Jira, Confluence, and Bitbucket.

#### 1. Install Dependencies

```bash
cd atlassian-mcp
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

#### 2. Configure Credentials

Create the credentials file:

```bash
mkdir -p ~/.config/atlassian
chmod 700 ~/.config/atlassian

cat > ~/.config/atlassian/.env << 'EOF'
# Jira credentials
JIRA_URL=https://jira.your-company.com
JIRA_USERNAME=your_username
JIRA_TOKEN=your_personal_access_token

# Confluence credentials
CONFLUENCE_URL=https://confluence.your-company.com
CONFLUENCE_USERNAME=your_username
CONFLUENCE_TOKEN=your_personal_access_token

# Bitbucket credentials
BITBUCKET_URL=https://bitbucket.your-company.com
BITBUCKET_USERNAME=your_username
BITBUCKET_TOKEN=your_personal_access_token
EOF

chmod 600 ~/.config/atlassian/.env
```

#### 3. Get Personal Access Tokens

**Jira:**
1. Go to Avatar > Profile > Personal Access Tokens
2. Click "Create token"
3. Copy the token value

**Confluence:**
1. Go to Avatar > Settings > Personal Access Tokens
2. Click "Create token"
3. Copy the token value

**Bitbucket:**
1. Go to Avatar > Manage Account > Personal Access Tokens
2. Click "Create token"
3. Select "Repository Read" permission (and Write if needed)
4. Copy the token value

#### 4. Register with Claude Code

```bash
# Make sure you're in the atlassian-mcp directory with venv activated
claude mcp add --transport stdio --scope user atlassian \
  --env ATLASSIAN_CONFIG=~/.config/atlassian/.env \
  -- $(pwd)/venv/bin/python $(pwd)/mcp_server.py
```

#### 5. Verify Installation

Restart Claude Code and try:
- "Get issue PROJ-123 from Jira"
- "Search for open bugs assigned to me"
- "Get the latest PR in my-project/my-repo"

---

### Talk2Docs Setup

This plugin provides semantic search across local documents.

#### 1. Install Ollama

```bash
# Install Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the embedding model
ollama pull nomic-embed-text

# Start Ollama service
ollama serve
```

#### 2. Install Dependencies

```bash
cd talk2docs
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. Index Your Documents

```bash
# Index a folder of documents
python index.py /path/to/your/documents

# Index specific files
python index.py file1.pdf file2.docx

# Force re-index existing documents
python index.py --force /path/to/documents

# Filter by extension
python index.py /path/to/documents --ext pdf docx

# Use parallel processing for faster indexing
python index.py /path/to/documents -p 4 -w 8
```

#### 4. Register with Claude Code

```bash
# Make sure you're in the talk2docs directory with venv activated
claude mcp add --transport stdio --scope user ldoc-search \
  --env CHROMA_DB_PATH=$(pwd)/chroma_db \
  --env OLLAMA_MODEL=nomic-embed-text \
  -- $(pwd)/venv/bin/python $(pwd)/mcp_server.py
```

#### 5. Verify Installation

Restart Claude Code and try:
- "Search my documents for deployment guide"
- "List all indexed documents"
- "Get index statistics"

---

## Managing MCP Servers

```bash
# List registered MCP servers
claude mcp list

# Remove an MCP server
claude mcp remove atlassian
claude mcp remove ldoc-search

# Check MCP server status
claude mcp status
```

## Plugin Details

### Atlassian MCP Tools

**Jira:**
- `jira_get_issue` - Get issue details by key or URL
- `jira_search` - Search issues using JQL
- `jira_create_issue` - Create new issues
- `jira_add_comment` - Add comments to issues
- `jira_transition_issue` - Change issue status

**Confluence:**
- `confluence_get_page` - Get page content by ID or URL
- `confluence_get_page_by_title` - Get page by space and title
- `confluence_search` - Search pages using CQL
- `confluence_get_space_pages` - List pages in a space

**Bitbucket:**
- `bitbucket_get_pr` - Get pull request details
- `bitbucket_get_pr_diff` - Get PR code changes
- `bitbucket_list_prs` - List repository PRs
- `bitbucket_add_pr_comment` - Comment on PRs
- `bitbucket_get_file` - Get file content from repo
- `bitbucket_list_branches` - List repository branches

### Talk2Docs Tools

- `search_pdfs` - Semantic search across indexed documents
- `list_indexed_documents` - List all indexed documents with chunk counts
- `get_index_stats` - Get index statistics

**Supported Formats:** PDF, DOCX, XLSX, PPTX, ODT, ODS, ODP, TXT, MD, HTML, CSV, JSON, XML

---

## Troubleshooting

### MCP Server Not Responding

1. Check if the server is registered: `claude mcp list`
2. Test the server directly: `python mcp_server.py` (should sit quietly if working)
3. Check for error messages in Claude Code output

### Atlassian Authentication Errors

1. Verify token hasn't expired
2. Check URLs don't have trailing slashes
3. Ensure correct permissions on token

### Talk2Docs Search Returns No Results

1. Verify documents are indexed: `python manage_index.py list`
2. Check Ollama is running: `curl http://localhost:11434/api/tags`
3. Try re-indexing: `python index.py --force /path/to/docs`

---

## Creating Your Own Plugin

Each plugin follows this structure:

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json       # Plugin metadata
├── mcp-servers.json      # MCP server configuration
├── mcp_server.py         # MCP server implementation
├── requirements.txt      # Python dependencies
└── README.md             # Plugin documentation
```

**plugin.json format:**
```json
{
    "name": "plugin-name",
    "description": "What your plugin does",
    "version": "1.0.0",
    "author": {
        "name": "Your Name",
        "email": "your@email.com"
    },
    "mcpServers": "./mcp-servers.json"
}
```

**mcp-servers.json format:**
```json
{
    "mcpServers": {
        "server-name": {
            "type": "stdio",
            "command": "python",
            "args": ["${CLAUDE_PLUGIN_ROOT}/mcp_server.py"],
            "env": {}
        }
    }
}
```

## License

MIT
