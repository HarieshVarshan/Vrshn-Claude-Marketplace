#!/usr/bin/env python3
"""
Jira Head Start Dashboard Server

Serves the analysis dashboard at http://localhost:7337
- Live Jira ticket list with preset filters
- Local analysis markdown files from ~/.local/share/jira-headstart/
- Markdown rendering + analysis status badges

Usage:
    python server.py [--port 7337]

Reads credentials from ~/.config/atlassian/.env
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import requests
import urllib3
from flask import Flask, jsonify, send_from_directory, abort, Response

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
ANALYSIS_DIR = Path.home() / ".local" / "share" / "jira-headstart"
INDEX_FILE = ANALYSIS_DIR / "index.json"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENV_PATH = Path.home() / ".config" / "atlassian" / ".env"

def load_env():
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

_env = load_env()
JIRA_URL = _env.get("JIRA_URL", "").rstrip("/")
JIRA_USERNAME = _env.get("JIRA_USERNAME", "")
JIRA_TOKEN = _env.get("JIRA_TOKEN", "")

if not all([JIRA_URL, JIRA_USERNAME, JIRA_TOKEN]):
    print(f"WARNING: Missing Jira credentials in {ENV_PATH}")

# ---------------------------------------------------------------------------
# Jira client (read-only, session-pooled)
# ---------------------------------------------------------------------------
_session = requests.Session()
_session.headers["Authorization"] = f"Bearer {JIRA_TOKEN}"
_session.verify = False

MAX_RESULTS = 200

FILTERS = {
    "all_open": (
        "assignee = currentUser() AND resolution = Unresolved "
        "ORDER BY updated DESC"
    ),
    "external_bugs": (
        'issuetype = Bug AND resolution = Unresolved '
        'AND "Source of Bug" = External '
        'AND assignee in (currentUser()) '
        'ORDER BY key DESC, updated DESC'
    ),
    "internal_bugs": (
        'issuetype = Bug AND resolution = Unresolved '
        'AND "Source of Bug" = Internal '
        'AND assignee in (currentUser()) '
        'ORDER BY key DESC, updated DESC'
    ),
}


def jira_search(jql: str) -> list:
    """Run JQL and return all matching issues (paginated)."""
    issues = []
    start = 0
    while True:
        resp = _session.get(
            f"{JIRA_URL}/rest/api/2/search",
            params={
                "jql": jql,
                "maxResults": MAX_RESULTS,
                "startAt": start,
                "fields": "summary,status,priority,issuetype,project,"
                          "updated,assignee,reporter,components,labels",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        issues.extend(data.get("issues", []))
        total = data.get("total", 0)
        start += MAX_RESULTS
        if start >= total:
            break
    return issues


def normalize(raw: dict) -> dict:
    f = raw.get("fields", {})
    components = [c["name"] for c in (f.get("components") or [])]
    labels = f.get("labels") or []
    return {
        "key": raw["key"],
        "summary": f.get("summary", ""),
        "status": (f.get("status") or {}).get("name", ""),
        "priority": (f.get("priority") or {}).get("name", ""),
        "type": (f.get("issuetype") or {}).get("name", ""),
        "project": (f.get("project") or {}).get("key", ""),
        "updated": (f.get("updated") or "")[:10],
        "components": components,
        "labels": labels,
        "url": f"{JIRA_URL}/browse/{raw['key']}",
    }


# ---------------------------------------------------------------------------
# Analysis index helpers
# ---------------------------------------------------------------------------
def load_index() -> dict:
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text())
        except Exception:
            pass
    return {"lastRun": None, "tickets": {}}


def analysis_path(key: str) -> Path:
    return ANALYSIS_DIR / key / "analysis.md"


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=str(SCRIPT_DIR), static_url_path="")


@app.route("/")
def index():
    return send_from_directory(str(SCRIPT_DIR), "index.html")


@app.route("/api/issues")
def api_issues():
    """
    Returns merged ticket list for one filter with analysis status overlay.
    Query param: ?filter=all_open|external_bugs|internal_bugs  (default: all_open)
    """
    from flask import request
    filter_name = request.args.get("filter", "all_open")
    jql = FILTERS.get(filter_name, FILTERS["all_open"])

    try:
        raw_issues = jira_search(jql)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    idx = load_index()
    tickets_meta = idx.get("tickets", {})

    issues = []
    for raw in raw_issues:
        issue = normalize(raw)
        key = issue["key"]
        meta = tickets_meta.get(key, {})

        # Analysis status
        analysis_file = analysis_path(key)
        if analysis_file.exists():
            analyzed_at = meta.get("analyzedAt", "")
            issue["analyzed"] = True
            issue["analyzedAt"] = analyzed_at
            issue["contextSources"] = meta.get("contextSources", [])
            # Stale if >48h old or ticket updated after analysis
            try:
                at = datetime.fromisoformat(analyzed_at.replace(" ", "T"))
                age_h = (datetime.now() - at).total_seconds() / 3600
                issue["stale"] = age_h > 48
            except Exception:
                issue["stale"] = False
        else:
            issue["analyzed"] = False
            issue["stale"] = False

        issues.append(issue)

    return jsonify({
        "filter": filter_name,
        "total": len(issues),
        "lastRun": idx.get("lastRun"),
        "issues": issues,
    })


@app.route("/api/analysis/<key>")
def api_analysis(key: str):
    """Returns raw markdown content for a ticket's analysis."""
    # Validate key format (prevent path traversal)
    import re
    if not re.match(r'^[A-Z]+-\d+$', key):
        abort(400)

    path = analysis_path(key)
    if not path.exists():
        return jsonify({"error": f"No analysis found for {key}"}), 404

    content = path.read_text(encoding="utf-8")
    return Response(content, mimetype="text/plain; charset=utf-8")


@app.route("/api/search")
def api_search():
    """
    Universal Jira search — searches beyond the current filter.
    Query param: ?q=<text>
    """
    from flask import request
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"issues": []})

    jql = (
        f'text ~ "{q}" AND resolution = Unresolved '
        f'ORDER BY updated DESC'
    )
    try:
        raw = jira_search(jql)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({
        "query": q,
        "total": len(raw),
        "issues": [normalize(r) for r in raw[:50]],
    })


@app.route("/api/index")
def api_index():
    """Returns the full analysis index JSON."""
    return jsonify(load_index())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Jira Head Start Dashboard")
    parser.add_argument("--port", type=int, default=7337)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    print(f"Jira URL  : {JIRA_URL}")
    print(f"Username  : {JIRA_USERNAME}")
    print(f"Analysis  : {ANALYSIS_DIR}")
    print(f"Dashboard : http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
