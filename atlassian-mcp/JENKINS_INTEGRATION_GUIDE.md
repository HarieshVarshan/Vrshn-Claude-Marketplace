# Adding Jenkins Support to Atlassian MCP Server

This guide outlines the steps and information needed to add Jenkins server integration to the existing MCP server.

## Overview

Yes, it is absolutely possible to add Jenkins support! This integration is **read-only** by design - it allows viewing job status, build information, logs, and configurations, but cannot trigger builds or modify settings.

The current project follows a clean architecture pattern that makes it straightforward to add new integrations. You'll need to:

1. Provide Jenkins credentials and configuration
2. Implement a `JenkinsClient` class
3. Register Jenkins tools in the MCP server
4. Add formatting functions for responses

---

## What You Need to Provide

### 1. Jenkins Server Configuration

Add these environment variables to `~/.config/atlassian/.env`:

```bash
# Jenkins Configuration
JENKINS_URL=https://jenkins.example.com
JENKINS_USERNAME=your-username
JENKINS_TOKEN=your-api-token
```

### 2. How to Generate a Jenkins API Token

1. Log in to your Jenkins server
2. Click your username (top-right corner)
3. Go to **Configure** → **API Token**
4. Click **Add new Token**
5. Give it a name and click **Generate**
6. Copy the token immediately (it won't be shown again)

### 3. Required Permissions

Your Jenkins user should have permissions to:
- View jobs and builds (Read permission)
- View build logs
- Access pipeline information
- **Read job configuration** (ExtendedRead or Configure permission for `jenkins_get_job_config`)

> **Note:** This integration is read-only. No write or trigger permissions are required.

---

## Suggested Jenkins Tools to Implement

Based on common use cases, here are recommended tools:

| Tool | Description | Jenkins API Endpoint |
|------|-------------|---------------------|
| `jenkins_get_job` | Get job details and status | `/job/{name}/api/json` |
| `jenkins_get_build` | Get specific build info | `/job/{name}/{number}/api/json` |
| `jenkins_get_last_build` | Get last build for a job | `/job/{name}/lastBuild/api/json` |
| `jenkins_list_jobs` | List all jobs | `/api/json?tree=jobs[name,color,url]` |
| `jenkins_get_build_log` | Get console output | `/job/{name}/{number}/consoleText` |
| `jenkins_get_queue` | Get build queue | `/queue/api/json` |
| `jenkins_get_node_status` | Get agent/node status | `/computer/api/json` |
| `jenkins_get_job_config` | Get job XML configuration | `/job/{name}/config.xml` |

---

## Implementation Steps

### Step 1: Update Configuration (`atlassian_client.py`)

Add Jenkins configuration to the `AtlassianConfig` class:

```python
# Add to AtlassianConfig.__init__():
self.jenkins_url = os.environ.get('JENKINS_URL', '').rstrip('/')
self.jenkins_username = os.environ.get('JENKINS_USERNAME', '')
self.jenkins_token = os.environ.get('JENKINS_TOKEN', '')
```

### Step 2: Create JenkinsClient Class (`atlassian_client.py`)

```python
class JenkinsClient:
    """Jenkins REST API client."""

    def __init__(self, config: AtlassianConfig):
        self.base_url = config.jenkins_url
        self.session = requests.Session()
        # Jenkins uses Basic Auth with username:api-token
        self.session.auth = (config.jenkins_username, config.jenkins_token)

        if not config.verify_ssl:
            self.session.verify = False

        if config.proxies:
            self.session.proxies = config.proxies

    def get_job(self, job_name: str) -> Dict[str, Any]:
        """Get job details by name."""
        # Handle folder paths (e.g., "folder/subfolder/job")
        job_path = '/job/'.join(job_name.split('/'))
        url = f"{self.base_url}/job/{job_path}/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_build(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """Get specific build information."""
        job_path = '/job/'.join(job_name.split('/'))
        url = f"{self.base_url}/job/{job_path}/{build_number}/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_last_build(self, job_name: str) -> Dict[str, Any]:
        """Get the last build for a job."""
        job_path = '/job/'.join(job_name.split('/'))
        url = f"{self.base_url}/job/{job_path}/lastBuild/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def list_jobs(self, folder: str = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally within a folder."""
        if folder:
            folder_path = '/job/'.join(folder.split('/'))
            url = f"{self.base_url}/job/{folder_path}/api/json"
        else:
            url = f"{self.base_url}/api/json"

        params = {"tree": "jobs[name,color,url,lastBuild[number,result,timestamp]]"}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('jobs', [])

    def get_build_log(self, job_name: str, build_number: int) -> str:
        """Get console output for a build."""
        job_path = '/job/'.join(job_name.split('/'))
        url = f"{self.base_url}/job/{job_path}/{build_number}/consoleText"
        response = self.session.get(url)
        response.raise_for_status()
        return response.text

    def get_queue(self) -> List[Dict[str, Any]]:
        """Get the build queue."""
        url = f"{self.base_url}/queue/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('items', [])

    def get_nodes(self) -> List[Dict[str, Any]]:
        """Get all build agents/nodes."""
        url = f"{self.base_url}/computer/api/json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('computer', [])

    def get_job_config(self, job_name: str) -> str:
        """Get job XML configuration."""
        job_path = '/job/'.join(job_name.split('/'))
        url = f"{self.base_url}/job/{job_path}/config.xml"
        response = self.session.get(url)
        response.raise_for_status()
        return response.text

    def get_job_config_parsed(self, job_name: str) -> Dict[str, Any]:
        """Get job configuration as parsed dictionary with key settings."""
        import xml.etree.ElementTree as ET

        xml_config = self.get_job_config(job_name)
        root = ET.fromstring(xml_config)

        config = {
            'job_type': root.tag,
            'description': '',
            'disabled': False,
            'triggers': [],
            'scm': None,
            'builders': [],
            'publishers': [],
            'parameters': [],
            'raw_xml': xml_config
        }

        # Description
        desc = root.find('description')
        if desc is not None and desc.text:
            config['description'] = desc.text

        # Disabled status
        disabled = root.find('disabled')
        if disabled is not None:
            config['disabled'] = disabled.text.lower() == 'true'

        # Build triggers
        triggers = root.find('triggers')
        if triggers is not None:
            for trigger in triggers:
                trigger_info = {'type': trigger.tag}
                spec = trigger.find('spec')
                if spec is not None and spec.text:
                    trigger_info['schedule'] = spec.text
                config['triggers'].append(trigger_info)

        # SCM configuration
        scm = root.find('scm')
        if scm is not None:
            scm_class = scm.get('class', '')
            config['scm'] = {'type': scm_class}

            # Git specific
            if 'git' in scm_class.lower():
                user_remote = scm.find('.//userRemoteConfigs/hudson.plugins.git.UserRemoteConfig')
                if user_remote is not None:
                    url_elem = user_remote.find('url')
                    if url_elem is not None:
                        config['scm']['url'] = url_elem.text

                branches = scm.findall('.//branches/hudson.plugins.git.BranchSpec/name')
                if branches:
                    config['scm']['branches'] = [b.text for b in branches if b.text]

        # Build parameters
        props = root.find('properties')
        if props is not None:
            params_def = props.find('.//hudson.model.ParametersDefinitionProperty/parameterDefinitions')
            if params_def is not None:
                for param in params_def:
                    param_info = {
                        'type': param.tag.split('.')[-1],
                        'name': '',
                        'description': '',
                        'default': ''
                    }
                    name = param.find('name')
                    if name is not None:
                        param_info['name'] = name.text
                    desc = param.find('description')
                    if desc is not None and desc.text:
                        param_info['description'] = desc.text
                    default = param.find('defaultValue')
                    if default is not None and default.text:
                        param_info['default'] = default.text
                    config['parameters'].append(param_info)

        # Builders (build steps)
        builders = root.find('builders')
        if builders is not None:
            for builder in builders:
                builder_info = {'type': builder.tag.split('.')[-1]}
                # Shell command
                command = builder.find('command')
                if command is not None and command.text:
                    builder_info['command'] = command.text[:500]  # Truncate long commands
                config['builders'].append(builder_info)

        # Pipeline definition (for pipeline jobs)
        definition = root.find('definition')
        if definition is not None:
            def_class = definition.get('class', '')
            config['pipeline'] = {'type': def_class}
            script = definition.find('script')
            if script is not None and script.text:
                config['pipeline']['script'] = script.text

        # Publishers (post-build actions)
        publishers = root.find('publishers')
        if publishers is not None:
            for publisher in publishers:
                config['publishers'].append({'type': publisher.tag.split('.')[-1]})

        return config
```

### Step 3: Add Client Singleton

```python
# Add at module level in atlassian_client.py:
_jenkins_client: Optional[JenkinsClient] = None

def get_jenkins_client() -> JenkinsClient:
    """Get or create Jenkins client singleton."""
    global _jenkins_client
    if _jenkins_client is None:
        config = get_config()
        if not config.jenkins_url:
            raise ValueError("Jenkins URL not configured. Set JENKINS_URL environment variable.")
        _jenkins_client = JenkinsClient(config)
    return _jenkins_client
```

### Step 4: Register Tools (`mcp_server.py`)

Add to the `list_tools()` function:

```python
# Jenkins Tools
Tool(
    name="jenkins_get_job",
    description="Get Jenkins job details including status, last build info, and configuration.",
    inputSchema={
        "type": "object",
        "properties": {
            "job_name": {
                "type": "string",
                "description": "Job name (use folder/job for jobs in folders)"
            }
        },
        "required": ["job_name"]
    }
),
Tool(
    name="jenkins_get_build",
    description="Get details for a specific Jenkins build.",
    inputSchema={
        "type": "object",
        "properties": {
            "job_name": {"type": "string", "description": "Job name"},
            "build_number": {"type": "integer", "description": "Build number"}
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
            "job_name": {"type": "string", "description": "Job name"},
            "build_number": {"type": "integer", "description": "Build number"}
        },
        "required": ["job_name", "build_number"]
    }
),
Tool(
    name="jenkins_get_queue",
    description="Get the Jenkins build queue showing pending builds.",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": []
    }
),
Tool(
    name="jenkins_get_nodes",
    description="Get status of Jenkins build agents/nodes.",
    inputSchema={
        "type": "object",
        "properties": {},
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
            }
        },
        "required": ["job_name"]
    }
),
```

### Step 5: Add Tool Handlers (`mcp_server.py`)

Add to the `call_tool()` function:

```python
# Jenkins handlers
elif name == "jenkins_get_job":
    client = get_jenkins_client()
    job = client.get_job(arguments["job_name"])
    result = format_jenkins_job(job)

elif name == "jenkins_get_build":
    client = get_jenkins_client()
    build = client.get_build(arguments["job_name"], arguments["build_number"])
    result = format_jenkins_build(build)

elif name == "jenkins_list_jobs":
    client = get_jenkins_client()
    jobs = client.list_jobs(arguments.get("folder"))
    result = format_jenkins_jobs(jobs)

elif name == "jenkins_get_build_log":
    client = get_jenkins_client()
    log = client.get_build_log(arguments["job_name"], arguments["build_number"])
    # Truncate very long logs
    if len(log) > 50000:
        log = log[-50000:] + "\n\n... (truncated, showing last 50000 characters)"
    result = f"# Build Log: {arguments['job_name']} #{arguments['build_number']}\n\n```\n{log}\n```"

elif name == "jenkins_get_queue":
    client = get_jenkins_client()
    queue = client.get_queue()
    result = format_jenkins_queue(queue)

elif name == "jenkins_get_nodes":
    client = get_jenkins_client()
    nodes = client.get_nodes()
    result = format_jenkins_nodes(nodes)

elif name == "jenkins_get_job_config":
    client = get_jenkins_client()
    if arguments.get("raw_xml"):
        xml_config = client.get_job_config(arguments["job_name"])
        result = f"# Job Configuration: {arguments['job_name']}\n\n```xml\n{xml_config}\n```"
    else:
        config = client.get_job_config_parsed(arguments["job_name"])
        result = format_jenkins_job_config(config, arguments["job_name"])
```

### Step 6: Add Formatting Functions (`mcp_server.py`)

```python
def format_jenkins_job(job: dict) -> str:
    """Format Jenkins job for display."""
    output = []
    output.append(f"# {job.get('displayName', job.get('name', 'Unknown Job'))}")
    output.append("")

    # Status color mapping
    color_status = {
        'blue': '✓ Success',
        'red': '✗ Failed',
        'yellow': '⚠ Unstable',
        'grey': '○ Not Built',
        'disabled': '⊘ Disabled',
        'aborted': '⊗ Aborted',
        'notbuilt': '○ Not Built',
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
    output = []
    output.append(f"# Build #{build.get('number', '?')}")
    output.append("")

    result = build.get('result', 'IN PROGRESS')
    result_emoji = {
        'SUCCESS': '✓',
        'FAILURE': '✗',
        'UNSTABLE': '⚠',
        'ABORTED': '⊗',
        'IN PROGRESS': '⟳',
    }

    output.append(f"**Result:** {result_emoji.get(result, '?')} {result}")
    output.append(f"**Building:** {'Yes' if build.get('building') else 'No'}")

    if build.get('timestamp'):
        from datetime import datetime
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
            if action.get('_class', '').endswith('ParametersAction'):
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

    color_emoji = {
        'blue': '✓',
        'red': '✗',
        'yellow': '⚠',
        'grey': '○',
        'disabled': '⊘',
        'notbuilt': '○',
    }

    for job in jobs:
        color = job.get('color', 'grey').replace('_anime', '')
        emoji = color_emoji.get(color, '?')
        building = ' (building)' if '_anime' in job.get('color', '') else ''

        name = job.get('name', 'Unknown')
        last_build = job.get('lastBuild')
        build_info = f" - #{last_build['number']}" if last_build else ""

        output.append(f"- {emoji} **{name}**{build_info}{building}")

    return '\n'.join(output)


def format_jenkins_queue(queue: list) -> str:
    """Format Jenkins queue for display."""
    if not queue:
        return "Build queue is empty."

    output = ["# Build Queue", ""]

    for item in queue:
        task = item.get('task', {})
        output.append(f"- **{task.get('name', 'Unknown')}**")
        if item.get('why'):
            output.append(f"  - Waiting: {item['why']}")
        if item.get('inQueueSince'):
            from datetime import datetime
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
        status = '🔴 Offline' if offline else '🟢 Online'

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
        output.append("**Status:** ⊘ Disabled")
    else:
        output.append("**Status:** ✓ Enabled")

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
```

---

## Update CLAUDE.md Quick Reference

Add this section to `CLAUDE.md`:

```markdown
### Jenkins (Read-Only)
| Tool | Description |
|------|-------------|
| `jenkins_get_job` | Get job details and status |
| `jenkins_get_build` | Get specific build information |
| `jenkins_list_jobs` | List all jobs (optionally in a folder) |
| `jenkins_get_build_log` | Get build console output |
| `jenkins_get_queue` | Get pending builds queue |
| `jenkins_get_nodes` | Get build agent status |
| `jenkins_get_job_config` | Get job configuration (SCM, triggers, parameters, build steps) |
```

---

## Testing the Integration

1. **Set up credentials:**
   ```bash
   echo "JENKINS_URL=https://your-jenkins-server.com" >> ~/.config/atlassian/.env
   echo "JENKINS_USERNAME=your-username" >> ~/.config/atlassian/.env
   echo "JENKINS_TOKEN=your-api-token" >> ~/.config/atlassian/.env
   ```

2. **Test basic connectivity:**
   ```python
   # Quick test script
   from atlassian_client import get_jenkins_client

   client = get_jenkins_client()
   jobs = client.list_jobs()
   print(f"Found {len(jobs)} jobs")
   ```

3. **Test via Claude:**
   - "List all Jenkins jobs"
   - "Get the status of the 'my-pipeline' job"
   - "Show the last build log for 'my-app'"
   - "Show me the configuration for the 'my-pipeline' job"
   - "What triggers are configured for the 'build-app' job?"

---

## Security Considerations

1. **API Token Scope:** Create a dedicated Jenkins user with read-only permissions
2. **Token Storage:** Keep credentials in `~/.config/atlassian/.env` with restricted file permissions (`chmod 600`)
3. **Read-Only Design:** This integration only supports read operations - no builds can be triggered or configurations modified
4. **SSL Verification:** Keep `VERIFY_SSL=true` in production environments

---

## Optional: Pipeline-Specific Tools

If you use Jenkins Pipelines extensively, consider adding:

| Tool | Description | API Endpoint |
|------|-------------|--------------|
| `jenkins_get_pipeline_stages` | Get pipeline stage status | `/job/{name}/{build}/wfapi/describe` |
| `jenkins_replay_build` | Replay a build with modifications | `/job/{name}/{build}/replay` |

---

## Files to Modify Summary

| File | Changes |
|------|---------|
| `atlassian_client.py` | Add `JenkinsClient` class and config |
| `mcp_server.py` | Add tools and handlers |
| `CLAUDE.md` | Add Jenkins quick reference |
| `~/.config/atlassian/.env` | Add Jenkins credentials |

---

## Questions?

If you need help with the implementation or have questions about specific Jenkins features, let me know!
