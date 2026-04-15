---
description: Smart Jira task manager for PDK sprints. Routes actions via hashtags — #jira (task), #review (review task), #bug (bug), #chores/#meetings (add to chores), #mira (update existing jira). Use `create base jiras` to bootstrap sprint chores task.
argument-hint: <description> #jira|#review|#bug|#chores|#meetings|#mira | create base jiras
---

# Mira — PDK Sprint Jira Manager

Parse `$ARGUMENTS` and route to the correct Jira operation below.

## Constants

- **Project key:** `PDK`
- **Required label for sprint visibility:** `PDK_SPRINT`
- **Reference task (for field structure):** `PDK-19948`
- **Reference bug (for field structure):** `PDK-20159`

---

## Step 0: Parse Input

1. Extract all hashtags from `$ARGUMENTS` (e.g., `#jira`, `#bug`, `#mira`, `#chores`, `#meetings`, `#review`, `#ocd`, `#done`).
2. The non-hashtag portion is the **description/context**.
3. Route to the matching mode below. If multiple hashtags are present, process each one.
4. `#ocd` and `#done` are no-ops — acknowledge them and stop.
5. **Get the current user** (once, reuse for all issue creation in this invocation):
   - `jira_get_current_user` → note the `name` (username) field.

---

## Mode A: `create base jiras`

Triggered when `$ARGUMENTS` is exactly `create base jiras` (case-insensitive).

### Steps

1. **Find the active PDK sprint:**
   - `jira_get_all_boards` with `project_key=PDK` → pick the PDK board.
   - `jira_get_board_sprints` with `board_id=<id>` and `state=active` → get current sprint name and ID.
   - If no active sprint, stop and tell the user.

2. **Create the chores task:**
   - `jira_create_issue` with:
     - `project_key`: `PDK`
     - `issue_type`: `Task`
     - `summary`: `{sprint_name}: chores, meetings and miscs`
     - `labels`: `["PDK_SPRINT"]`
     - `assignee`: current user (from Step 0)
   - Do **not** blindly copy fields from the reference jira — populate only what makes sense.

3. **Add to active sprint:**
   - `jira_move_issues_to_sprint` with the new issue key and the active sprint ID.

4. **Report:** Show the created issue key and Jira URL.

---

## Mode B: `#jira` — Create a Task

### Input format
The description should contain a component and subject, e.g.:
- `MCUPSDK j722s promotion logic integration <url> #jira`
- `UART driver refactor #jira`

### Steps

1. **Parse the description:**
   - Extract **component** (the first word or explicit `component:` prefix if present).
   - Extract **subject** (the rest of the description, optionally including a URL).
   - Form the summary: `<component>: <subject>`

2. **Find the active PDK sprint** (same as Mode A, Step 1).

3. **Get reference task for field hints** (optional — use to understand standard priority/component setup):
   - `jira_get_issue` with `PDK-19948`

4. **Create the task:**
   - `jira_create_issue` with:
     - `project_key`: `PDK`
     - `issue_type`: `Task`
     - `summary`: `<component>: <subject>`
     - `description`: Contextual description built from the input (include URLs, PR links, or any extra context found in the description).
     - `labels`: `["PDK_SPRINT"]`
     - `assignee`: current user (from Step 0)
     - `components`: Set to `[<component>]` if the component matches a known PDK component. If unsure, leave blank — do not guess.
   - Update fields based on context. Do **not** blindly clone the reference jira.

5. **Add to active sprint:**
   - `jira_move_issues_to_sprint` with the new issue key and active sprint ID.

6. **Report:** Show the created issue key and Jira URL.

---

## Mode C: `#review` — Create a Review Task

Same as Mode B (`#jira`) with one difference:
- Prefix the summary with `review: ` → `review: <component>: <subject>`

---

## Mode D: `#bug` — Create a Bug

### Steps

1. **Parse the description** for component, subject, and any reproduction steps or context.

2. **Find the active PDK sprint** (same as Mode A, Step 1).

3. **Get reference bug for field hints:**
   - `jira_get_issue` with `PDK-20159`

4. **Create the bug:**
   - `jira_create_issue` with:
     - `project_key`: `PDK`
     - `issue_type`: `Bug`
     - `summary`: `<component>: <subject>` (or just `<subject>` if no component is clear)
     - `description`: Contextual description built from input (include error details, URLs, steps to reproduce if mentioned).
     - `labels`: `["PDK_SPRINT"]`
     - `assignee`: current user (from Step 0)
     - `priority`: Set based on context (Critical/High/Medium/Low). Default to `Medium` if unspecified.
   - Do **not** blindly copy fields from the reference bug.

5. **Add to active sprint:**
   - `jira_move_issues_to_sprint` with the new issue key and active sprint ID.

6. **Report:** Show the created issue key and Jira URL.

---

## Mode E: `#chores` or `#meetings` — Append to Sprint Chores Task

### Steps

1. **Find the active PDK sprint** (same as Mode A, Step 1).

2. **Find the chores task:**
   - `jira_search` with JQL: `project = PDK AND labels = PDK_SPRINT AND summary ~ "chores, meetings and miscs" AND sprint in openSprints()`
   - Take the first result. If no chores task is found, tell the user to run `/mira create base jiras` first.

3. **Get current description:**
   - `jira_get_issue` with the chores task key.
   - Note the existing description text.

4. **Append the new entry:**
   - Build updated description by appending a new bullet:
     - For `#chores`: `- <description text>`
     - For `#meetings`: `- [Meeting] <description text>`
   - `jira_update_issue` with the updated description.

5. **Report:** Confirm the chores task was updated and show the issue key.

---

## Mode F: `#mira` — Update an Existing Jira

Used when a Jira already exists and you want to add context (e.g., a PR link, status update, notes).

### Steps

1. **Find the Jira to update:**
   - Look for a Jira key (e.g., `PDK-XXXXX`) in the description.
   - Or look for a URL that includes a Jira issue key.
   - If no key is found, ask the user: "Which Jira key should I update?"

2. **Get the current issue:**
   - `jira_get_issue` with the found key.
   - Read the current summary, description, and comments.

3. **Determine what to update** based on the context provided:
   - If a **PR link** or URL is provided → add it to the description under a `## References` section.
   - If **progress notes** or status info is provided → add a comment summarizing the update.
   - If both → update description and add a comment.

4. **Apply updates:**
   - `jira_update_issue` to update description (if needed).
   - `jira_add_comment` to add a comment (if needed).

5. **Report:** Show what was updated on the issue.

---

## Mode G: `#ocd` or `#done` — No-Op

Acknowledge and stop: `Noted. No Jira action taken for #ocd/#done.`

---

## General Rules

- **Always assign to the current user** — call `jira_get_current_user` in Step 0 and pass the username as `assignee` on every `jira_create_issue` call.
- **Always add `PDK_SPRINT` to labels** so issues appear in the PDK sprint board.
- **Use `jira_move_issues_to_sprint`** after creating any issue to attach it to the active sprint.
- **Do not blindly copy fields from reference jiras** — they are structural guides only. Fill fields based on the actual context.
- **Build descriptions from context** — if a URL is provided (e.g., a PR link), include it in the Jira description.
- **Components** — only set if you can confidently identify the component from the input. Do not guess.
- **Fail fast** — if the active sprint cannot be found, stop and tell the user instead of proceeding without a sprint.
- **Be concise** when reporting — show the issue key, summary, and Jira URL. Skip verbose recaps.

---

## Examples

```
/mira create base jiras
→ Finds active PDK sprint → Creates "Sprint_25.04: chores, meetings and miscs" → Moves to sprint
```

```
/mira MCUPSDK j722s promotion logic integration https://bitbucket.itg.ti.com/projects/SITMPUSW/repos/cd-sync/pull-requests/12/overview #jira
→ Component: MCUPSDK, Subject: j722s promotion logic integration <url>
→ Creates Task "MCUPSDK: j722s promotion logic integration" with PR link in description → Moves to sprint
```

```
/mira j722s LIN driver crash on init #bug
→ Creates Bug "j722s: LIN driver crash on init" → Moves to sprint
```

```
/mira stand-up notes: discussed j722s PDK integration timeline #meetings
→ Finds chores task → Appends "- [Meeting] stand-up notes: discussed j722s PDK integration timeline" to description
```

```
/mira PDK-12345 PR merged https://bitbucket.itg.ti.com/... #mira
→ Gets PDK-12345 → Adds PR link to description → Adds comment "PR merged: <url>"
```
