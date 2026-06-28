# Architecture Research: Non-existent Tool Fallback

**Researched:** 2026-06-27
**Scope:** v1.2 — architecture changes for detecting undefined tools and user-prompted backup

## Existing Architecture Summary

The extension has three main files:

| File | Responsibility |
|---|---|
| `tool_fallback.py` | Main `ToolFallback` class: G-code command handlers, routing, fallback resolution, workflow state |
| `tool_fallback_config.py` | Configuration parsing: global config + per-tool config, tool name validation |
| `tool_fallback_state.py` | State schema: `ToolState`, `ToolFallbackState`, `StateStore` (JSON persistence) |

Key architectural patterns:
- **Fail-closed safety:** All Tn interception goes through `_route_logical` which checks workflow state
- **Backup graph resolution:** `resolve_backup_graph()` traverses configured backup lists depth-first
- **State persistence:** `StateStore` loads/reconciles/saves JSON state file
- **Workflow-aware:** Transitions respect pause/resume ownership and checkpoint stages

## New Components

### 1. Undefined Tool Detection Layer

**Location:** `tool_fallback.py`, new method `_install_default_handler()`

**Approach (recommended):** Register a wrapper G-code command `_TOOL_FALLBACK_TN` that the user's macros call instead of raw `Tn`. This command:
1. Parses the tool number from the G-code parameter
2. Checks if the tool is configured (`tool in self.config.tools`)
3. If configured: delegates to existing routing
4. If NOT configured: triggers the undefined-tool flow (pause + prompt)

This avoids monkey-patching Klipper internals and is version-stable.

**Alternative (less preferred):** Wrap Klipper's `gcode.register_command()` to intercept all Tn commands before the extension's logical handlers, checking for unconfigured tools first. This is more transparent to users but riskier.

### 2. User Prompt Flow

**Location:** `tool_fallback.py`, new methods:
- `_handle_undefined_tool(logical_tool, gcmd)` — entry point when undefined tool detected
- `_await_user_backup_definition(logical_tool)` — pause and wait for user command
- `_on_user_backup_defined(logical_tool, backup_tool)` — callback when user defines backup

**Flow:**
1. Detect undefined tool → call `_handle_undefined_tool`
2. Pause print (reuse existing `pause_gcode` mechanism)
3. Send console message: "Tool Tn not defined. Define a backup tool: `DEFINE_TOOL_BACKUP Tn Tm`"
4. Wait for user to submit `DEFINE_TOOL_BACKUP` command
5. On receive: persist mapping, apply backup, resume print

### 3. State Schema Extension

**Location:** `tool_fallback_state.py`

Add to `ToolState` dataclass:
```python
user_defined_backup: object = None  # logical tool name or None
```

Add to `ToolFallbackState` dataclass:
```python
user_defined_backups: object = None  # dict: logical_tool -> physical_tool
```

Update `load_reconciled()` to merge user-defined backups with configured state.

### 4. New G-code Commands

| Command | Handler | Location |
|---|---|---|
| `DEFINE_TOOL_BACKUP` | `cmd_DEFINE_TOOL_BACKUP` | `tool_fallback.py` |
| `UNDEFINE_TOOL_BACKUP` | `cmd_UNDEFINE_TOOL_BACKUP` | `tool_fallback.py` |
| `SHOW_TOOL_BACKUPS` | `cmd_SHOW_TOOL_BACKUPS` | `tool_fallback.py` |

## Modified Components

### `tool_fallback.py` — `resolve_backup_graph()`

Extend to accept an optional `user_defined_backups` dict. When resolving a failed tool, first check configured backups, then check user-defined backup for the failed tool.

### `tool_fallback.py` — `_route_logical()`

No changes needed — the routing already uses `state.mappings` which will include user-defined mappings after reconciliation.

### `tool_fallback_config.py`

No changes needed — user-defined backups are runtime-only, not config-time.

## Data Flow Changes

```
Before (v1.0/v1.1):
  G-code Tn → _route_logical → state.mappings[Tn] → _select_physical

After (v1.2):
  G-code Tn → _TOOL_FALLBACK_TN → is_tool_configured(Tn)?
    YES → _route_logical → state.mappings[Tn] → _select_physical
    NO  → _handle_undefined_tool → pause → prompt → await DEFINE_TOOL_BACKUP
          → persist(user_defined_backup) → reconcile state → _route_logical
          → state.mappings[Tn] → _select_physical
```

## Suggested Build Order

1. **State schema extension** (tool_fallback_state.py) — foundation, no dependencies
2. **DEFINE_TOOL_BACKUP / UNDEFINE_TOOL_BACKUP commands** — core user interaction
3. **User-defined backup reconciliation** in `load_reconciled()` — merges runtime data
4. **Undefined tool detection layer** (_TOOL_FALLBACK_TN wrapper) — detection entry point
5. **User prompt flow** (_handle_undefined_tool, _await_user_backup_definition) — complete flow
6. **SHOW_TOOL_BACKUPS** — observability (can be done earlier but benefits from having other pieces)

## Integration Risks

- **State migration:** Existing state files won't have `user_defined_backups` field. `load_reconciled()` must handle missing keys gracefully.
- **Prompt timing:** The pause/resume cycle for user prompts must not interfere with existing workflow checkpoints.
- **G-code wrapper adoption:** Users must update their macros/slicers to call `_TOOL_FALLBACK_TN` instead of raw `Tn`. Documentation and examples must cover this.
