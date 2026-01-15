# Atlassian MCP Server

A Model Context Protocol (MCP) server that provides Claude with access to Jira, Confluence, and Bitbucket. This enables Claude to search, read, create, and manage issues, pages, and pull requests directly from conversations.

## Features

### Jira Tools
- **jira_get_issue** - Get issue details by key or URL
- **jira_search** - Search issues using JQL
- **jira_create_issue** - Create new issues
- **jira_add_comment** - Add comments to issues
- **jira_transition_issue** - Change issue status

### Confluence Tools
- **confluence_get_page** - Get page content by ID or URL
- **confluence_get_page_by_title** - Get page by space and title
- **confluence_search** - Search pages using text or CQL
- **confluence_get_space_pages** - List all pages in a space

### Bitbucket Tools
- **bitbucket_get_pr** - Get pull request details
- **bitbucket_get_pr_diff** - Get PR diff/changes
- **bitbucket_list_prs** - List repository PRs
- **bitbucket_add_pr_comment** - Add comments to PRs
- **bitbucket_get_file** - Get file content from repo
- **bitbucket_list_branches** - List repository branches

## Prerequisites

1. **Python 3.10+**
2. **Atlassian Personal Access Tokens** for each service you want to use

## Installation

### 1. Create Virtual Environment

```bash
cd atlassian-mcp
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Credentials

Create `~/.config/atlassian/.env`:

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

### 4. Create Personal Access Tokens

#### Jira
1. Go to **Avatar > Profile > Personal Access Tokens**
2. Click **Create token**
3. Copy the token value

#### Confluence
1. Go to **Avatar > Settings > Personal Access Tokens**
2. Click **Create token**
3. Copy the token value

#### Bitbucket
1. Go to **Avatar > Manage Account > Personal Access Tokens**
2. Click **Create token**
3. Select **Repository Read** permission (and Write if needed)
4. Copy the token value

## Claude Integration

### Option 1: Direct MCP Registration

```bash
claude mcp add --transport stdio --scope user atlassian \
  --env ATLASSIAN_CONFIG=~/.config/atlassian/.env \
  -- python /path/to/atlassian-mcp/mcp_server.py
```

### Option 2: Using Virtual Environment

```bash
claude mcp add --transport stdio --scope user atlassian \
  --env ATLASSIAN_CONFIG=~/.config/atlassian/.env \
  -- /path/to/atlassian-mcp/venv/bin/python /path/to/atlassian-mcp/mcp_server.py
```

### Option 3: Plugin Marketplace (if using ti-claude-code-marketplace)

If you have the marketplace configured, install via:
```bash
claude plugin install atlassian-mcp
```

## Usage Examples

Once registered, you can use these tools in conversations with Claude:

### Jira Examples

```
"Get the details of PROJ-123"
"Search for all open bugs assigned to me in project MYPROJ"
"Create a new task in PROJ with summary 'Fix login issue'"
"Add a comment to PROJ-456 saying 'This is fixed in PR #789'"
"Move PROJ-123 to 'In Progress'"
```

### Confluence Examples

```
"Get the page at https://confluence.company.com/pages/viewpage.action?pageId=123456"
"Find all pages about 'deployment guide' in the DOCS space"
"List all pages in the TEAM space"
"Get the page titled 'Getting Started' in space DOCS"
```

### Bitbucket Examples

```
"Get PR #42 from project MYPROJ repo my-service"
"Show me the diff for that PR"
"List all open PRs in MYPROJ/my-service"
"Add a comment to PR #42 saying 'LGTM!'"
"Get the content of src/main.py from MYPROJ/my-service"
```

## Architecture

```
atlassian-mcp/
├── .claude-plugin/
│   └── plugin.json         # Plugin metadata
├── mcp-servers.json        # MCP server configuration
├── mcp_server.py           # Main MCP server (entry point)
├── atlassian_client.py     # API clients for Jira, Confluence, Bitbucket
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Troubleshooting

### Connection Issues

1. **Check token validity**: Tokens may expire
2. **Verify URLs**: Ensure URLs don't have trailing slashes in config
3. **Proxy settings**: If behind a corporate proxy, you may need to set HTTP_PROXY/HTTPS_PROXY

### Authentication Errors

- **Jira/Confluence**: Use Bearer token authentication
- **Bitbucket Server**: Uses Basic auth with username:token

### Debug Mode

Run the server directly to see errors:
```bash
python mcp_server.py
```

## License

MIT
