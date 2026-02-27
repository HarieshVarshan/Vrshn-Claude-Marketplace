# Vault Conventions Reference

Loaded on-demand by the context-capture skill and knowledge-sync agent. This is the single source of truth for vault structure, naming, tagging, and linking rules.

**Vault path:** `/home/harieshvarshan/vrshn_obsidian/`

---

## Tag Taxonomy

Tags are inline at the bottom of notes (no YAML frontmatter). Always adopt existing tags exactly as spelled — case matters.

### Domain Tags
| Tag | Usage |
|-----|-------|
| `#csi` | Camera Serial Interface — CSIRX, CSITX, DPHY |
| `#dma` | DMA subsystem — UDMA, BCDMA, PktDMA, DRU |
| `#dru` | Data Routing Unit (subset of DMA) |
| `#cicd` | Jenkins CI/CD, build pipelines |
| `#safety` | Functional safety, FFI, TUV SUD |
| `#ai` | AI/ML topics |
| `#financial-planning` | Personal finance umbrella |
| `#investment` | Investment-specific |
| `#insurance` | Insurance notes |
| `#fixed-income` | Bonds, FDs |
| `#equity` | Stock market |
| `#credit-cards` | Credit card strategy |
| `#retirement` | Retirement planning |
| `#rewards` | Credit card rewards |
| `#hal` | Hardware Abstraction Layer |
| `#coding` | General programming |

### Platform Tags
| Tag | Usage |
|-----|-------|
| `#tda4` | TDA4 / J721E platform |
| `#tda5` | TDA5 platform |
| `#jacinto` | Jacinto family (broader) |
| `#j722s` | J722S platform |

### Content Type Tags
| Tag | Usage |
|-----|-------|
| `#concept` | Conceptual explanation notes |
| `#howto` | Step-by-step guides |
| `#ticket` | JIRA ticket reference notes |
| `#debug` | Debug sessions and findings |
| `#moc` | Map of Content (hub notes) |
| `#docs` | Documentation references |
| `#query` | Research questions |
| `#task` | Task-related notes |

### Status Tags
| Tag | Usage |
|-----|-------|
| `#brb` | Paused but returning as high priority |
| `#under5` | Quick tasks under 5 minutes |
| `#under15` | Tasks under 15 minutes |
| `#wip` | Work in progress |
| `#high` | High priority |
| `#stub` | Placeholder note needing expansion |
| `#todo` | Pending action items |
| `#implemented` | Completed implementation |
| `#skipped` | Skipped/deferred |
| `#paper-candidate` | Potential publishable paper topic |

### Tagging Rules
- Every note should have at least one domain tag and one content type tag
- 3-6 tags per note is typical; more than 8 suggests the note should be split
- Tags go at the bottom of the note, on their own line, space-separated
- Never create a new tag variant if one exists (use `#tda4` not `#TDA4` — check existing casing)
- `#debug` content goes into the relevant concept note, not a separate debug diary

---

## Naming Conventions

Notes use **Title Case with spaces**. Acronyms stay uppercase.

| Pattern | Example |
|---------|---------|
| Concept notes | `Understanding CSIRX.md`, `Data Movement Architecture DMA.md` |
| Platform-specific | `TDA4 CSIRX Cadence IP.md`, `TDA54 DMA Arch Discussion.md` |
| Ticket references | `PDK-13532 CSIRX to CSITX loopback Application fails.md` |
| Debug sessions | `CSIRX Stream FIFO Overflow.md` |
| Hub/MOC notes | `00 CSI Hub.md`, `00 DMA Hub.md` |
| Training notes | `CSIRX Module Training Notes.md`, `KT with Lohith for DMA.md` |
| Discussion notes | `Discussion with Cadence.md`, `DMA DM Discussions.md` |

**Rules:**
- Capitalize major words; lowercase articles/prepositions unless starting the title
- Preserve uppercase acronyms: UDMA, CSI, DMA, TDA4, PSI-L
- Use spaces, not hyphens or underscores
- Parenthetical qualifiers for disambiguation: `UDMA Notes (TDA4).md`
- Hub files prefixed with `00 ` and suffixed with `Hub`

---

## File Locations

| Content | Location |
|---------|----------|
| All concept notes | Vault root (`/home/harieshvarshan/vrshn_obsidian/`) |
| Hub / MOC notes | Vault root, prefixed `00 ` |
| Task tracking | `daily logger.md`, `today.md`, `todo.md`, `Tasks.md`, `ocd tasks.md` |
| Excalidraw drawings | `excalidraw/` |
| Attachments/media | `attachments/` |
| Paper candidates | `papers/` (create if needed) |
| Goldfish session docs | `docs/goldfish_docs/` |
| Quick capture | `thoughts.md` |
| TI process notes | `TICA.md` |

**Flat vault rule:** All concept notes live at the vault root. Never create subfolders for organizing topics — use tags and `[[wiki-links]]` instead. The only subfolders are `excalidraw/`, `attachments/`, `papers/`, and `docs/`.

---

## Hub Files

Hub files (prefixed `00 `) are Maps of Content. Their standard section structure:

| Hub | Sections |
|-----|----------|
| `00 CSI Hub.md` | Core Concepts, Platform-Specific (TDA4/TDA5/TDA54), Training & Learning, Safety & Compliance, DPHY, Debug & Analysis, DMA Integration, JIRA Tickets, Miscellaneous, Dataview |
| `00 DMA Hub.md` | Core Concepts, Platform-Specific (TDA4/TDA54/TDA5/J722S), DRU, Safety & FFI, Training & Knowledge Transfer, Integration, Debug & Issues, Dataview |
| `00 CICD Hub.md` | CI/CD related notes |
| `00 Finance Hub.md` | Personal finance notes |
| `00 TI Hub.md` | General TI platform notes |
| `00 Tasks.md` | Task aggregation |

When creating a new note that fits under a hub, add a `[[wiki-link]]` to it in the appropriate hub section.

---

## Cross-Linking Rules

- Use Obsidian `[[wiki-link]]` syntax: `[[Note Name]]` or `[[Note Name|display text]]`
- Inline wiki-links in body text where concepts are mentioned
- Optionally add a `## Related` section at the bottom for broader connections
- Check for existing links before adding duplicates (use `Grep("\\[\\[Note Name\\]\\]", path=VAULT_PATH)`)
- Broken links are OK — Obsidian shows them as unresolved and they become valid when the target note is created
- Excalidraw embeds use `![[excalidraw/diagram_name.excalidraw]]`

---

## Formatting Rules

- **No YAML frontmatter** — the vault doesn't use it. Tags go inline at the bottom of notes
- Preserve existing markdown formatting when editing
- Notes are concise references, not elaborate documents — capture what's essential for future reference
- Headings use `#` / `##` / `###` hierarchy
- Horizontal rules (`---`) separate major sections in hub files
- Dataview queries use fenced code blocks with `dataview` language
- Mermaid diagrams use fenced code blocks with `mermaid` language (Obsidian renders natively)
