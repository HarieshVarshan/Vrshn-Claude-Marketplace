# Expert Agents Strategy

A strategy document for creating specialized document search agents for different IP modules, platforms, and devices.

---

## Table of Contents

1. [Current State](#current-state)
2. [Problem Statement](#problem-statement)
3. [Proposed Solution](#proposed-solution)
4. [Document Organization Analysis](#document-organization-analysis)
5. [Tagging Strategy](#tagging-strategy)
6. [Migration Plan](#migration-plan)
7. [MCP Server Changes](#mcp-server-changes)
8. [Usage Examples](#usage-examples)
9. [Team Workflow](#team-workflow)
10. [Future Enhancements](#future-enhancements)

---

## Current State

### Document Location
```
/home/harieshvarshan/vrshn_obsidian/docs/specifications/
```

### Document Statistics
| Format | Count |
|--------|-------|
| PDF | 71 |
| XLSX | 26 |
| DOCX | 18 |
| DOC (legacy) | 15 |
| PPTX | 7 |
| **Total** | **137** |

### Current Index
- Single ChromaDB database at `./chroma_db/`
- Documents indexed with basic metadata: `source`, `file_path`, `file_type`, `chunk_index`
- No module/platform/device tagging
- Single MCP server exposing: `search_pdfs`, `list_indexed_documents`, `get_index_stats`

### Current Limitations
1. Cannot filter searches by platform (tda4, tda5, sitara)
2. Cannot filter by device (j721e, j721s2, am62l)
3. Cannot filter by module (csi, navss, dru)
4. Search results mix all documents together
5. No way to create "expert" agents for specific domains

---

## Problem Statement

### Team Needs
1. **Focused searches** - Search only within relevant documents
2. **Expert agents** - Create specialists for DMA, IPC, CSI, etc.
3. **Cross-module queries** - "How does DMA interact with CSI?"
4. **Platform-specific answers** - "How is this different in TDA5 vs TDA4?"
5. **No re-indexing** - Already spent 3-4 hours indexing

### Why Separate Databases Won't Work
| Issue | Impact |
|-------|--------|
| Must know which expert to ask | User friction |
| Can't answer cross-module questions | Limited usefulness |
| Multiple MCP servers to maintain | Operational overhead |
| Duplicate docs spanning modules | Inconsistency |

---

## Proposed Solution

### Architecture: Single DB with Smart Metadata

```
┌─────────────────────────────────────────────────────────────┐
│                      ChromaDB                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Document Chunks with Rich Metadata                  │    │
│  │                                                      │    │
│  │  chunk_1: {                                         │    │
│  │    source: "SPRUIL_TRM.pdf",                        │    │
│  │    platform: "tda4",                                │    │
│  │    device: "j721e",                                 │    │
│  │    module: "trm",                                   │    │
│  │    doc_type: "trm",                                 │    │
│  │    ...                                              │    │
│  │  }                                                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                          ↓                                   │
│              Single MCP Server                               │
│     search(query, platform?, device?, module?)              │
└─────────────────────────────────────────────────────────────┘
```

### Benefits
| Benefit | Description |
|---------|-------------|
| Zero friction | Ask anything, system finds relevant docs |
| Cross-module queries | "How does DMA work with CSI?" works |
| Single source of truth | One DB to maintain, backup, share |
| Results show context | "This is from TDA4 J721E TRM" |
| Easy to scale | Add new modules = just index with tags |
| No re-indexing | Metadata update only |

---

## Document Organization Analysis

### Folder Structure
```
specifications/
├── general_spec/                    ← Platform: general
│   ├── fvid2_spec/                  ← Module: fvid2
│   └── serdes_spec/                 ← Module: serdes
│
├── sitara_spec/                     ← Platform: sitara
│   ├── am62l_spec/                  ← Device: am62l
│   │   └── am62l_trm/               ← Doc Type: trm
│   └── am62x_spec/                  ← Device: am62x
│       └── am62x_trm/               ← Doc Type: trm
│
├── tda4_spec/                       ← Platform: tda4
│   ├── j721e_spec/                  ← Device: j721e
│   │   ├── j721e_safety_manual/     ← Doc Type: safety_manual
│   │   └── j721e_ti_com/
│   │       ├── j721e_datasheet/     ← Doc Type: datasheet
│   │       ├── j721e_errata/        ← Doc Type: errata
│   │       └── j721e_trm/           ← Doc Type: trm
│   ├── j721s2_spec/                 ← Device: j721s2
│   ├── j722s_spec/                  ← Device: j722s
│   ├── j784s4_spec/                 ← Device: j784s4
│   ├── tda4_cadence_spec/           ← Module: cadence
│   │   ├── tda4_cadence_csirx_spec/ ← Sub-module: csirx
│   │   ├── tda4_cadence_csitx_spec/ ← Sub-module: csitx
│   │   ├── tda4_cadence_dphyrx_spec/← Sub-module: dphyrx
│   │   └── tda4_cadence_dphytx_spec/← Sub-module: dphytx
│   ├── tda4_csi_spec/               ← Module: csi
│   ├── tda4_navss_spec/             ← Module: navss
│   ├── tda4_phy_spec/               ← Module: phy
│   ├── tda4_prd/                    ← Doc Type: prd
│   └── tda4_sdl_spec/               ← Module: sdl
│
└── tda5_spec/                       ← Platform: tda5
    ├── tda54_analytics_spec/        ← Module: analytics
    ├── tda54_csi_spec/              ← Module: csi
    ├── tda54_dru_spec/              ← Module: dru
    ├── tda54_general/               ← Module: general
    ├── tda54_navss_spec/            ← Module: navss
    ├── tda54_prd/                   ← Doc Type: prd
    ├── tda54_soc_spec/              ← Module: soc
    └── tda54_synopsys/              ← Module: synopsys
```

### Detected Platforms
| Platform | Description |
|----------|-------------|
| `general` | Common/shared specifications |
| `sitara` | Sitara processor family |
| `tda4` | TDA4 family (Jacinto 7) |
| `tda5` | TDA5 family (next gen) |

### Detected Devices
| Device | Platform | Description |
|--------|----------|-------------|
| `am62l` | sitara | AM62L processor |
| `am62x` | sitara | AM62X processor |
| `j721e` | tda4 | J721E / TDA4VM |
| `j721s2` | tda4 | J721S2 / TDA4VE |
| `j722s` | tda4 | J722S |
| `j784s4` | tda4 | J784S4 / AM69A |

### Detected Modules
| Module | Platforms | Description |
|--------|-----------|-------------|
| `csi` | tda4, tda5 | Camera Serial Interface |
| `navss` | tda4, tda5 | Navigator Subsystem |
| `dru` | tda5 | Data Routing Unit |
| `cadence` | tda4 | Cadence IP specs |
| `sdl` | tda4 | Safety Diagnostic Library |
| `phy` | tda4 | PHY specifications |
| `serdes` | general | SerDes specifications |
| `fvid2` | general | FVID2 framework |
| `synopsys` | tda5 | Synopsys IP specs |
| `analytics` | tda5 | Analytics subsystem |

### Detected Document Types
| Doc Type | Description |
|----------|-------------|
| `trm` | Technical Reference Manual |
| `datasheet` | Device datasheet |
| `errata` | Known issues/errata |
| `safety_manual` | Safety documentation |
| `prd` | Product Requirements Document |

---

## Tagging Strategy

### Metadata Fields to Add

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `platform` | string | Top-level platform | `tda4`, `tda5`, `sitara` |
| `device` | string | Specific device | `j721e`, `am62l` |
| `module` | string | IP module/subsystem | `csi`, `navss`, `dru` |
| `doc_type` | string | Document category | `trm`, `errata`, `datasheet` |

### Extraction Rules

```python
# Path: /specifications/tda4_spec/j721e_spec/j721e_ti_com/j721e_trm/file.pdf

# Rule 1: Platform from first _spec folder
platform = "tda4"  # from "tda4_spec"

# Rule 2: Device from device pattern (j7xxx, amXXx)
device = "j721e"   # from "j721e_spec"

# Rule 3: Module from module folders
module = "trm"     # from "j721e_trm" or specific module folders

# Rule 4: Doc type from deepest folder or filename patterns
doc_type = "trm"   # from folder name containing trm/datasheet/errata/etc
```

### Extraction Logic Pseudocode

```python
def extract_tags(file_path):
    parts = file_path.split('/')
    tags = {
        'platform': None,
        'device': None,
        'module': None,
        'doc_type': None
    }

    for part in parts:
        # Platform detection
        if part in ['general_spec', 'sitara_spec', 'tda4_spec', 'tda5_spec']:
            tags['platform'] = part.replace('_spec', '')

        # Device detection (j7xxx, amXXx patterns)
        if re.match(r'j7\d+[a-z]*_spec', part):
            tags['device'] = part.replace('_spec', '')
        elif re.match(r'am\d+[a-z]*_spec', part):
            tags['device'] = part.replace('_spec', '')

        # Module detection
        module_patterns = ['csi', 'navss', 'dru', 'cadence', 'sdl', 'phy',
                          'serdes', 'fvid2', 'synopsys', 'analytics', 'soc']
        for mod in module_patterns:
            if mod in part.lower():
                tags['module'] = mod

        # Doc type detection
        doc_types = ['trm', 'datasheet', 'errata', 'safety_manual', 'prd']
        for dt in doc_types:
            if dt in part.lower():
                tags['doc_type'] = dt

    return tags
```

### Example Extractions

| File Path | platform | device | module | doc_type |
|-----------|----------|--------|--------|----------|
| `tda4_spec/j721e_spec/.../j721e_trm/SPRUIL_TRM.pdf` | tda4 | j721e | - | trm |
| `tda4_spec/tda4_cadence_spec/tda4_cadence_csirx_spec/...` | tda4 | - | cadence, csirx | - |
| `tda5_spec/tda54_navss_spec/navss512.doc` | tda5 | - | navss | - |
| `sitara_spec/am62l_spec/am62l_trm/datasheet.pdf` | sitara | am62l | - | trm |
| `general_spec/serdes_spec/ds90ub960.pdf` | general | - | serdes | - |

---

## Migration Plan

### Overview
| Step | Description | Time | Re-index? |
|------|-------------|------|-----------|
| 1 | Create migration script | 10 min | No |
| 2 | Backup existing database | 1 min | No |
| 3 | Run migration (metadata update) | 2-5 min | No |
| 4 | Verify migration | 2 min | No |
| 5 | Update MCP server | 15 min | No |
| 6 | Test filtered searches | 5 min | No |
| **Total** | | **~35 min** | **No** |

### Step 1: Migration Script

Create `migrate_add_tags.py`:
- Read all documents from ChromaDB
- Extract tags from `file_path` metadata
- Update metadata in-place using `collection.update()`
- No re-embedding required

### Step 2: Backup

```bash
cp -r chroma_db/ chroma_db_backup_$(date +%Y%m%d)/
```

### Step 3: Run Migration

```bash
python migrate_add_tags.py
```

Expected output:
```
Reading existing documents...
Found 137 documents, ~5000 chunks

Extracting tags from file paths...
  tda4: 85 documents
  tda5: 32 documents
  sitara: 12 documents
  general: 8 documents

Updating metadata...
  Updated 5000/5000 chunks

Migration complete!
```

### Step 4: Verify

```bash
python manage_index.py stats
# Should show new metadata fields
```

### Step 5: Update MCP Server

Modify `mcp_server.py` to add filtered search:
- Add optional `platform`, `device`, `module` parameters to search
- Update tool descriptions

### Step 6: Test

```bash
# Test in Claude
"Search for DMA in tda4 platform"
"What does j721e TRM say about interrupts?"
"Search navss module across all platforms"
```

---

## MCP Server Changes

### Current Tools
```python
search_pdfs(query, num_results)
list_indexed_documents()
get_index_stats()
```

### Proposed Tools

```python
# Enhanced search with filters
search(
    query: str,
    num_results: int = 5,
    platform: str = None,    # Filter: tda4, tda5, sitara, general
    device: str = None,      # Filter: j721e, j721s2, am62l, etc.
    module: str = None       # Filter: csi, navss, dru, etc.
)

# List with grouping
list_indexed_documents(
    group_by: str = None     # Group by: platform, device, module
)

# Enhanced stats
get_index_stats()            # Now includes tag distribution

# New: List available filters
list_filters()               # Returns available platforms, devices, modules
```

### Search Filter Logic

```python
def search(query, num_results=5, platform=None, device=None, module=None):
    # Build where clause
    where = {}
    if platform:
        where["platform"] = platform
    if device:
        where["device"] = device
    if module:
        where["module"] = module

    # Query with filters
    results = collection.query(
        query_embeddings=[embed(query)],
        n_results=num_results,
        where=where if where else None
    )
    return results
```

---

## Usage Examples

### Basic Search (No Filter)
```
User: "How to configure DMA channels?"
→ Searches all documents
→ Returns results from TDA4, TDA5, Sitara mixed
→ Results show which platform/device each came from
```

### Platform-Filtered Search
```
User: "Search in tda4 for CSI configuration"
→ Filters to platform=tda4
→ Returns only TDA4 family results
```

### Device-Filtered Search
```
User: "What does j721e documentation say about power management?"
→ Filters to device=j721e
→ Returns only J721E specific results
```

### Module-Filtered Search
```
User: "Search navss module for interrupt routing"
→ Filters to module=navss
→ Returns NAVSS docs from all platforms
```

### Cross-Platform Comparison
```
User: "Compare CSI implementation between tda4 and tda5"
→ Two searches: platform=tda4, module=csi AND platform=tda5, module=csi
→ Returns comparison-ready results
```

### Combined Filters
```
User: "Search tda4 j721e device for CSI errata"
→ Filters: platform=tda4, device=j721e, module=csi
→ Highly focused results
```

---

## Team Workflow

### For Team Members (End Users)

**No change required.** They just ask questions:

```
"How do I configure DMA?"                    → Works (all docs)
"Show me TDA4 CSI register map"              → Works (filtered)
"What's different between J721E and J721S2?" → Works (comparison)
```

### For Team Lead (You)

**Indexing new documents:**
```bash
# New docs automatically get tagged based on folder location
python index.py /path/to/new/docs/tda5_spec/tda54_newmodule/

# Tags extracted automatically from path
```

**Checking index health:**
```bash
python manage_index.py stats
# Shows distribution by platform, device, module
```

**Sharing with team:**
- Single database to backup/share
- Single MCP server configuration
- No per-module setup required

---

## Future Enhancements

### Phase 2: Smart Query Routing
```
User query → LLM classifier → Auto-detect relevant filters → Filtered search
```

### Phase 3: Cross-Reference Detection
```
"DMA chapter references CSI" → Automatic cross-module linking
```

### Phase 4: Version Tracking
```
Track document versions, show when specs were updated
```

### Phase 5: Team Analytics
```
- Most searched modules
- Query patterns
- Missing documentation gaps
```

---

## Summary

| Aspect | Current | Proposed |
|--------|---------|----------|
| Database | Single, no tags | Single, rich tags |
| Search | All-or-nothing | Filterable |
| MCP Tools | 3 basic | 4 enhanced |
| Re-indexing | - | Not required |
| Migration time | - | ~35 minutes |
| Team friction | High | Zero |

### Next Steps

1. Review and approve this strategy
2. Create migration script
3. Run migration
4. Update MCP server
5. Test with team
6. Document new capabilities

---

## Approval

- [ ] Strategy reviewed
- [ ] Migration plan approved
- [ ] Ready to implement
