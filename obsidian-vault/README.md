# obsidian-vault

Capture knowledge from Claude Code sessions into your Obsidian vault. Searches for existing notes, deduplicates, proposes changes for your review, and maintains cross-links and tags.

## What It Does

- Extracts valuable knowledge from your conversation (concepts, insights, debug findings, corrections)
- Searches the vault for related existing notes before creating new ones
- Proposes changes as "Knowledge PRs" — you review and approve before anything is written
- Preserves each note's existing style (or proposes refactoring messy notes)
- Maintains cross-links between related notes using `[[wiki-links]]`
- Updates hub/MOC files when new notes are created
- Evaluates whether accumulated knowledge is paper-worthy

## How to Use

### Natural Language (Auto-Trigger)

Say any of these during a conversation:

```
"add this to obsidian"
"save to vault"
"capture this"
"update my notes"
"sync to obsidian"
```

The skill auto-triggers, extracts knowledge, searches the vault, and either handles simple additions directly or launches the full sync workflow.

### /capture Command

```
/capture                    # Capture all knowledge from conversation
/capture CSIRX debugging    # Focus on CSIRX debugging knowledge
/capture DMA architecture   # Focus on DMA architecture
```

### Full Vault Sync

For reorganizing notes, syncing a long session, or working across multiple notes:

```
"do a full vault sync"
"reorganize my DMA notes"
```

This launches the knowledge-sync agent with the full 10-step workflow.

## How It Works

1. **Extract** — Analyzes the conversation for capturable knowledge
2. **Search** — Uses Glob/Grep to find related existing notes in the vault
3. **Classify** — Simple addition or complex sync?
4. **Preview** — Shows exactly what will be written (Knowledge PR format)
5. **Approve** — You review and approve/edit/reject each change
6. **Write** — Applies approved changes using Edit/Write tools
7. **Link** — Updates cross-links and hub files
8. **Report** — Summary of everything that was synced

Nothing is written without your explicit approval.

## Configuration

The vault path is configured in the skill and agent files:

```
/home/harieshvarshan/vrshn_obsidian/
```

To use with a different vault, update the path in:
- `skills/context-capture/SKILL.md`
- `skills/context-capture/references/vault-conventions.md`
- `agents/knowledge-sync.md`

## Installation

### From marketplace
```bash
claude plugin install obsidian-vault@vrshn-claude-marketplace
```

### Development
```bash
claude --plugin-dir /path/to/obsidian-vault
```

## Prerequisites

- Claude Code CLI
- An Obsidian vault accessible via absolute path
- Optional: `excalidraw-mcp` plugin for diagram creation on a live canvas

## Project Structure

```
obsidian-vault/
├── .claude-plugin/
│   └── plugin.json                        # Plugin manifest
├── commands/
│   └── capture.md                         # /capture slash command
├── skills/
│   └── context-capture/
│       ├── SKILL.md                       # Auto-trigger entry point
│       └── references/
│           └── vault-conventions.md       # Tag taxonomy, naming, hub structure
├── agents/
│   └── knowledge-sync.md                  # 10-step Knowledge PR workflow
├── CLAUDE.md                              # Plugin development guide
└── README.md                              # This file
```
