# obsidian-vault Plugin

Capture knowledge from Claude sessions into an Obsidian vault with intelligent search, deduplication, cross-linking, and paper candidate tracking.

## Architecture

**No MCP server.** Claude's native file tools (Glob, Grep, Read, Write, Edit) access the vault directly via absolute paths.

```
User runs /capture [topic]
        |
        v
   Command (commands/capture.md)
   Extracts knowledge -> searches vault -> classifies complexity
        |
        +-- Simple (1-3 bullet append) --> Command handles directly
        |
        +-- Complex (multi-note, refactor) --> Launches knowledge-sync agent
                                                (agents/knowledge-sync.md)
```

## Files

| File | Purpose |
|------|---------|
| `.claude-plugin/plugin.json` | Plugin manifest |
| `commands/capture.md` | `/capture [topic]` — entry point, handles extract/search/classify and simple captures |
| `references/vault-conventions.md` | Tag taxonomy, naming rules, hub structure, file locations |
| `agents/knowledge-sync.md` | Full 10-step Knowledge PR workflow for complex syncs |

## Testing

```bash
# Run with plugin-dir flag
claude --plugin-dir /home/harieshvarshan/foss_repo/Personal/Vrshn-Claude-Marketplace/obsidian-vault

# Or install from marketplace
claude plugin install obsidian-vault@vrshn-claude-marketplace
```

Test scenarios:
- Run `/capture` — should invoke the capture command
- Run `/capture DMA architecture` — should focus on DMA knowledge
- Test from a non-vault directory (e.g., a TI SDK codebase)
- Verify vault search finds existing notes
- Verify preview is shown before any writes

## Key Design Decisions

1. **No MCP server**: Every tool the old `mcp_server.py` provided is a thin wrapper around Claude's native tools. `obsidian_search_vault` = `Grep` + `Glob`. `obsidian_read_note` = `Read`. No point wrapping native tools.

2. **Command + Agent split**: Simple captures (1-3 bullets) don't need the full 10-step workflow. The `/capture` command handles these directly. Complex captures launch the knowledge-sync agent.

3. **Knowledge PR format preserved**: The review-before-write pattern from the previous version works well. Style-preserving and refactor modes, paper candidates, and diagram proposals are all kept.

4. **No YAML frontmatter**: The vault uses inline tags at the bottom of notes. The agent respects this.

5. **Vault conventions as reference file**: Tag taxonomy, naming rules, and hub structure are in a separate file loaded on-demand, keeping the command and agent files focused on workflow.
