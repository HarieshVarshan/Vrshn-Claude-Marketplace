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

### /capture Command

```
/capture                    # Capture all knowledge from conversation
/capture CSIRX debugging    # Focus on CSIRX debugging knowledge
/capture DMA architecture   # Focus on DMA architecture
```

The command extracts knowledge, searches the vault, and either handles simple additions directly or launches the full knowledge-sync agent for complex operations.

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

The vault path is configured in the command and agent files:

```
/home/harieshvarshan/vrshn_obsidian/
```

To use with a different vault, update the path in:
- `commands/capture.md`
- `references/vault-conventions.md`
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
│   └── plugin.json                  # Plugin manifest
├── commands/
│   └── capture.md                   # /capture — entry point, simple captures
├── references/
│   └── vault-conventions.md         # Tag taxonomy, naming, hub structure
├── agents/
│   └── knowledge-sync.md            # 10-step Knowledge PR workflow
├── CLAUDE.md                        # Plugin development guide
└── README.md                        # This file
```
