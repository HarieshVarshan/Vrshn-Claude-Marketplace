---
description: Capture knowledge from current conversation into Obsidian vault
argument-hint: [optional topic or scope]
allowed-tools: Read, Write, Edit, Glob, Grep, Task
---

# Obsidian Capture

Capture knowledge from this conversation into the Obsidian vault.

**Focus:** $ARGUMENTS
**Vault path:** `/home/harieshvarshan/vrshn_obsidian/`

If no topic is specified, analyze the full conversation and identify all capturable knowledge.

---

## Phase 1: Extract Knowledge

Analyze the conversation and extract capturable knowledge. Look for:

1. **Key concepts** — named entities, protocols, hardware blocks, algorithms, tools, libraries
2. **New insights** — facts, clarifications, or understanding gained during discussion
3. **Debug findings** — problems, root causes, fixes discovered
4. **Corrections** — earlier misunderstandings that were corrected
5. **How-tos** — step-by-step procedures or workflows figured out
6. **Tasks/decisions** — action items or decisions made

For each piece of knowledge, determine:
- A short descriptive label
- Which existing note it might belong to (guess from topic)
- Relevant tags (consult `references/vault-conventions.md` in the plugin directory if unsure about tag taxonomy)

Skip trivial or ephemeral content — only capture what has future reference value. Notes are concise references, not transcripts.

## Phase 2: Search the Vault

For each extracted concept, search for existing notes using native tools:

**Filename search:**
```
Glob("*{keyword}*.md", path="/home/harieshvarshan/vrshn_obsidian/")
```

**Heading search:**
```
Grep("^#{1,3}.*{keyword}", path="/home/harieshvarshan/vrshn_obsidian/", glob="*.md", output_mode="content")
```

**Content search (for unique terms):**
```
Grep("{unique_term}", path="/home/harieshvarshan/vrshn_obsidian/", glob="*.md", output_mode="files_with_matches")
```

**Tag search:**
```
Grep("#{tag_name}", path="/home/harieshvarshan/vrshn_obsidian/", glob="*.md", output_mode="files_with_matches")
```

**Backlink search:**
```
Grep("\\[\\[{Note Name}\\]\\]", path="/home/harieshvarshan/vrshn_obsidian/", glob="*.md")
```

Search broadly: try the concept name, abbreviations, full forms, and related terms. Cast a wide net before concluding a concept is new.

## Phase 3: Classify Complexity

Based on extraction and search results, classify the capture:

**Simple capture** (handle directly):
- A single note needs a focused change (append, edit, correct, or create)
- The change is straightforward and self-contained

**Complex capture** (delegate to knowledge-sync agent):
- Multiple notes need updating
- Existing note is messy and needs refactoring alongside new content
- Cross-linking across 3+ notes
- Paper candidate evaluation needed
- Diagram creation (Mermaid or Excalidraw)
- User asks for a full vault sync or reorganization

## Phase 4: Execute

### Simple Capture Path

1. **Read** the target note (if modifying an existing note). Understand its structure, style, and existing content.

2. **Determine the right operation.** This is NOT always appending — understand the context and choose accordingly:
   - **Append** — new information that extends what's already there (new bullet, new section)
   - **Edit inline** — existing content is incomplete, outdated, or slightly wrong and needs updating in place
   - **Correct** — the conversation revealed a misunderstanding captured in the note; fix it
   - **Integrate** — the new knowledge fits naturally within an existing section rather than tacked on at the end
   - **Replace section** — a section is outdated and the conversation produced a better version
   - **New note** — the topic doesn't exist in the vault yet
   - **Add cross-links/tags** — the note exists and is fine, just needs linking or tagging

3. **Show preview** to the user. Present exactly what will change:

   ```
   ## Proposed change: {Note Name}.md

   **Operation:** {Append / Edit / Correct / Integrate / Replace section / New note}
   **Why:** {brief reason — e.g., "conversation clarified that X actually works differently"}

   {Show the specific change — diff-style for edits/corrections, full content for new notes}

   Tags to add: #tag1, #tag2 (if any)
   Cross-links to add: [[Note A]], [[Note B]] (if any)

   Approve? (yes / edit / reject)
   ```

4. **Wait for explicit approval.** Never write without it.

5. **Apply** the approved change using the appropriate tool:
   - Inline edits, corrections, integrations: use `Edit` with precise old_string/new_string
   - New notes: use `Write` to create the file
   - Tag/link additions: use `Edit`
   - Hub updates: use `Edit` to add the link in the appropriate hub section

6. **Confirm** what was written.

### Complex Capture Path

Launch the knowledge-sync agent:

```
Task(
  subagent_type="general-purpose",
  description="Knowledge sync to Obsidian vault",
  prompt="You are the knowledge-sync agent. Read and follow the workflow defined in
  /home/harieshvarshan/foss_repo/Personal/Vrshn-Claude-Marketplace/obsidian-vault/agents/knowledge-sync.md exactly.

  Context from the conversation that needs to be synced:
  {summarize the extracted knowledge here}

  The user has approved launching the full sync workflow. Begin at Step 1 (Scope Selection)."
)
```

Include a summary of extracted knowledge in the prompt so the agent has context.

---

## Important Rules

- **NEVER** write to the vault without showing the user exactly what will be written and getting approval
- **NEVER** silently drop knowledge — if you extracted it, it goes somewhere or the user explicitly rejects it
- **Preserve wiki-link syntax** `[[Note Name]]` in all edits
- **Match existing style** — read the target note first, match its tone/format/depth
- **Flat vault** — all concept notes at vault root, never create subfolders (except `papers/`, `excalidraw/`, `attachments/`, `docs/`)
- **Title Case naming** — `UDMA Completion Interrupts.md` not `udma-completion-interrupts.md`
- **Inline tags at bottom** — no YAML frontmatter
- **Adopt existing tags** — search the vault's tag taxonomy before creating new tags
- Notes are concise references, not elaborate documents — capture what's essential for future use
- Don't create notes for trivial or ephemeral content
- If a relevant note exists, integrate knowledge into it (edit, correct, append, etc.) rather than creating a duplicate note
