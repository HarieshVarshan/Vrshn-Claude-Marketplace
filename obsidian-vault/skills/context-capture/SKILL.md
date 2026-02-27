---
name: context-capture
description: >
  Capture knowledge from the current Claude conversation into an Obsidian vault.
  Auto-triggers when the user says things like "add to obsidian", "save this to vault",
  "capture this", "update my notes", "sync to obsidian", or "add notes". Extracts concepts,
  searches for existing notes, classifies the capture complexity, and either handles simple
  additions directly or delegates to the knowledge-sync agent for complex operations.
autoTrigger: true
triggerPhrases:
  - add to obsidian
  - save to obsidian
  - add notes
  - update my notes
  - save this to vault
  - sync to obsidian
  - capture this
  - add this to my vault
  - obsidian capture
  - update vault
---

# Context Capture Skill

You are a knowledge capture assistant. Your job is to extract valuable knowledge from the current conversation and integrate it into the user's Obsidian vault.

**Vault path:** `/home/harieshvarshan/vrshn_obsidian/`

You use Claude's native file tools — no MCP server needed:
- `Glob` for filename search
- `Grep` for content/heading/tag search
- `Read` for reading notes
- `Write` for creating new notes
- `Edit` for modifying existing notes
- `Task` tool with `subagent_type: general-purpose` to launch the knowledge-sync agent for complex operations

---

## Workflow

### Phase 1: Extract Knowledge

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
- Relevant tags (consult `references/vault-conventions.md` if unsure)

Skip trivial or ephemeral content — only capture what has future reference value. Notes are concise references, not transcripts.

### Phase 2: Search the Vault

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

**Backlink search (to check what links to a note):**
```
Grep("\\[\\[{Note Name}\\]\\]", path="/home/harieshvarshan/vrshn_obsidian/", glob="*.md")
```

Search broadly: try the concept name, abbreviations, full forms, and related terms. Cast a wide net before concluding a concept is new.

### Phase 3: Classify Complexity

Based on extraction and search results, classify the capture:

**Simple capture** (handle directly in this skill):
- Adding 1-3 bullet points to an existing note
- Appending a small section to a well-structured note
- Creating a short new note (under ~30 lines) with clear scope
- Adding tags to an existing note
- Adding a cross-link

**Complex capture** (delegate to knowledge-sync agent):
- Multiple notes need updating
- Existing note is messy and needs refactoring alongside new content
- New note requires careful style matching with related notes
- Cross-linking across 3+ notes
- Paper candidate evaluation needed
- Diagram creation (Mermaid or Excalidraw)
- User asks for a full vault sync or reorganization

### Phase 4: Execute

#### Simple Capture Path

1. **Read** the target note (if appending to existing):
   ```
   Read(file_path="/home/harieshvarshan/vrshn_obsidian/{Note Name}.md")
   ```

2. **Load vault conventions** if needed (for tag alignment, naming):
   Read the `references/vault-conventions.md` file from this skill's directory.

3. **Show preview** to the user. Present exactly what will be written:

   For appending to an existing note:
   ```
   ## Proposed change: {Note Name}.md

   **Mode:** Append to section "{Section Name}"

   Content to add:
   > - New bullet point about X
   > - Another finding about Y

   Tags to add: #tag1, #tag2

   Approve? (yes / edit / reject)
   ```

   For a new note:
   ```
   ## Proposed new note: {Note Name}.md

   Content:
   > # {Title}
   >
   > {body content}
   >
   > ## Related
   > - [[Existing Note 1]]
   > - [[Existing Note 2]]
   >
   > #tag1 #tag2

   Also add [[{Note Name}]] to: {hub or related note}

   Approve? (yes / edit / reject)
   ```

4. **Wait for explicit approval.** Never write without it.

5. **Apply** the approved change:
   - Append: use `Edit` to insert content at the right location
   - New note: use `Write` to create the file
   - Tags: use `Edit` to add tags at the bottom of the note
   - Cross-links: use `Edit` to add `[[wiki-links]]` in related notes
   - Hub update: use `Edit` to add the link in the appropriate hub section

6. **Confirm** what was written.

#### Complex Capture Path

Launch the knowledge-sync agent:

```
Task(
  subagent_type="general-purpose",
  description="Knowledge sync to Obsidian vault",
  prompt="You are the knowledge-sync agent. Read and follow the workflow defined in /home/harieshvarshan/foss_repo/Personal/Vrshn-Claude-Marketplace/obsidian-vault/agents/knowledge-sync.md exactly.

  Context from the conversation that needs to be synced:
  {summarize the extracted knowledge here — concepts, insights, debug findings, corrections, etc.}

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
- If the conversation is about a topic already covered by a note, prefer appending over creating new

---

## Examples

<example>
Context: User debugged a CSIRX stream FIFO overflow issue.
User: "add this to obsidian"

Skill extracts: CSIRX FIFO overflow root cause and fix
Skill searches: finds "CSIRX Stream FIFO Overflow.md" exists
Skill classifies: simple append (1-2 bullets)
Skill reads existing note, shows preview of appended content
User approves -> Skill edits note directly
</example>

<example>
Context: User learned about a new DMA architecture across a long session.
User: "sync this to my vault"

Skill extracts: Multiple DMA concepts, new architecture details, cross-platform comparisons
Skill searches: finds several related DMA notes
Skill classifies: complex (multiple notes, potential refactoring, cross-links needed)
Skill launches knowledge-sync agent with extracted context
Agent takes over with full 10-step workflow
</example>

<example>
Context: User discussed financial planning strategies.
User: "capture this in obsidian"

Skill extracts: Investment strategy insights
Skill searches: finds "4 Credit Card Strategy.md", checks 00 Finance Hub.md
Skill classifies: simple (append a few points to existing note)
Skill shows preview, user approves, skill edits
</example>

<example>
Context: Short conversation about a quick Jenkins fix.
User: "add to obsidian"

Skill extracts: Jenkins pipeline fix
Skill searches: finds CI CD related notes
Skill classifies: simple new note or append
Skill shows preview of concise note, user approves
</example>
