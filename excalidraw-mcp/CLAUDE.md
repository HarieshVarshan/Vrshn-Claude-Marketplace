# Excalidraw MCP Server - Quick Reference

## Overview

MCP server for Excalidraw with a live canvas, WebSocket sync, and 26 tools for diagram management.

## Prerequisites

- Node.js >= 18
- Canvas server running at `http://localhost:3000`

### Setup

```bash
cd excalidraw-mcp
npm ci
npm run build
```

Start the canvas server (separate terminal):
```bash
HOST=0.0.0.0 PORT=3000 npm run canvas
```

Open `http://localhost:3000` in a browser.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EXPRESS_SERVER_URL` | URL of the canvas server | `http://localhost:3000` |
| `ENABLE_CANVAS_SYNC` | Enable real-time canvas sync | `true` |

## Available Tools (26)

### Element CRUD
| Tool | Description |
|------|-------------|
| `create_element` | Create a new element |
| `get_element` | Get element by ID |
| `update_element` | Update an existing element |
| `delete_element` | Delete an element |
| `query_elements` | Query elements with filters |
| `batch_create_elements` | Create multiple elements at once |
| `duplicate_elements` | Duplicate elements |

### Layout
| Tool | Description |
|------|-------------|
| `align_elements` | Align elements |
| `distribute_elements` | Distribute elements evenly |
| `group_elements` | Group elements |
| `ungroup_elements` | Ungroup elements |
| `lock_elements` | Lock elements |
| `unlock_elements` | Unlock elements |

### Scene Awareness
| Tool | Description |
|------|-------------|
| `describe_scene` | Get structured text description of the canvas |
| `get_canvas_screenshot` | Get a screenshot of the canvas |

### File I/O
| Tool | Description |
|------|-------------|
| `export_scene` | Export scene as .excalidraw JSON |
| `import_scene` | Import a .excalidraw JSON scene |
| `export_to_image` | Export canvas to image |
| `export_to_excalidraw_url` | Generate a shareable Excalidraw URL |
| `create_from_mermaid` | Create diagram from Mermaid syntax |

### State Management
| Tool | Description |
|------|-------------|
| `clear_canvas` | Clear all elements |
| `snapshot_scene` | Save a named snapshot |
| `restore_snapshot` | Restore a named snapshot |

### Viewport
| Tool | Description |
|------|-------------|
| `set_viewport` | Control zoom and scroll position |

### Design Guide
| Tool | Description |
|------|-------------|
| `read_diagram_guide` | Get best-practice design guide |

### Resources
| Tool | Description |
|------|-------------|
| `get_resource` | Get a resource |

## Key Files

- `src/index.ts` - MCP server entry point (stdio transport)
- `src/server.ts` - Canvas server (Express + WebSocket)
- `src/types.ts` - Type definitions
- `skills/excalidraw-skill/` - Agent skill with helper scripts
