---
description: Capture knowledge from current conversation into Obsidian vault
argument-hint: [optional topic or scope]
allowed-tools: Read, Write, Edit, Glob, Grep, Task
---

Capture knowledge from this conversation into the Obsidian vault.

Focus: $ARGUMENTS

Execute the context-capture workflow:
1. Analyze the conversation for capturable knowledge (focus on: $ARGUMENTS)
2. Search the vault at /home/harieshvarshan/vrshn_obsidian/ for related existing notes
3. Classify: simple addition vs complex sync
4. For simple additions: show preview, wait for approval, write
5. For complex syncs: launch the knowledge-sync agent

If no topic is specified, analyze the full conversation and identify all capturable knowledge.
