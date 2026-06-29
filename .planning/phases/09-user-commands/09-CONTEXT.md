# Phase 09: User Commands - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

## Phase Boundary

This phase provides operators with G-code commands to define, remove, and list backup-tool mappings at runtime. It implements three commands: `DEFINE_TOOL_BACKUP`, `UNDEFINE_TOOL_BACKUP`, and `SHOW_TOOL_BACKUPS`. These commands write to the `user_defined_backups` dict introduced in Phase 8 and persist via `StateStore.save()`.

**Scope anchor:** Three G-code commands only. No detection logic (Phase 10), no prompt flow (Phase 11), no routing integration (Phase 12).

## Requirements (locked via REQUIREMENTS.md)

**8 requirements are locked.** See REQUIREMENTS.md for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read REQUIREMENTS.md before planning or implementing.

**In scope (from REQUIREMENTS.md):**
- CMD-01: `DEFINE_TOOL_BACKUP <logical> <backup>` defines a backup mapping and persists immediately
- CMD-02: `DEFINE_TOOL_BACKUP` validates that the backup tool is configured (exists in `self.config.tools`)
- CMD-03: `DEFINE_TOOL_BACKUP` rejects during an active workflow transition
- CMD-04: `DEFINE_TOOL_BACKUP` persists the mapping via `StateStore.save()`
- CMD-05: `UNDEFINE_TOOL_BACKUP <logical>` removes a user-defined backup mapping and persists
- CMD-06: `UNDEFINE_TOOL_BACKUP` validates the mapping exists before removing
- CMD-07: `SHOW_TOOL_BACKUPS` lists all user-defined backup mappings
- CMD-08: `SHOW_TOOL_BACKUPS` displays both configured and user-defined backup mappings

**Out of scope (from REQUIREMENTS.md):**
- Undefined tool detection (Phase 10)
- User prompt flow (Phase 11)
- Fallback integration and observability (Phase 12)

## Implementation Decisions

### Command Registration
- **D-01:** Commands follow the existing `cmd_COMMAND_NAME(self, gcmd)` pattern registered via `self.gcode.register_command()` — same pattern as `cmd_SET_TOOL_BACKUPS`, `cmd_REMAP_TOOL`, etc.
- **D-02:** Command names are uppercase with underscores: `DEFINE_TOOL_BACKUP`, `UNDEFINE_TOOL_BACKUP`, `SHOW_TOOL_BACKUPS` — matching the REQUIREMENTS.md naming exactly.
- **D-03:** Each command gets a `desc` parameter in `register_command()` matching the style of existing commands (short human-readable description).

### Parameter Handling
- **D-04:** `DEFINE_TOOL_BACKUP` takes two positional parameters: `<logical>` and `<backup>` — retrieved via `gcmd.get("LOGICAL")` and `gcmd.get("BACKUP")` (Klipper convention uses uppercase parameter names).
- **D-05:** `UNDEFINE_TOOL_BACKUP` takes one positional parameter: `<logical>` — retrieved via `gcmd.get("LOGICAL")`.
- **D-06:** `SHOW_TOOL_BACKUPS` takes no parameters.

### Validation & Guards
- **D-07:** `DEFINE_TOOL_BACKUP` uses `_require_configured_tool()` for the logical tool parameter (ensures it's a configured tool).
- **D-08:** `DEFINE_TOOL_BACKUP` validates the backup tool is also configured — reuses `_require_configured_tool()` or inline check against `self.config.tools`.
- **D-09:** `DEFINE_TOOL_BACKUP` rejects self-references (logical == backup) — consistent with D-14 from Phase 8 and existing backup validation.
- **D-10:** `DEFINE_TOOL_BACKUP` uses `_guard_workflow_operation(gcmd.error, "tool backup definition")` to reject during active workflow — same guard used by `cmd_REMAP_TOOL` and `cmd_SET_TOOL_BACKUPS`.
- **D-11:** `UNDEFINE_TOOL_BACKUP` also uses `_guard_workflow_operation()` for consistency — even though CMD-05/06 don't explicitly require it, the pattern from existing commands (SET_TOOL_BACKUPS, REMAP_TOOL) applies workflow guards to all mutation operations.
- **D-12:** `SHOW_TOOL_BACKUPS` does NOT need workflow guards — it's a read-only operation.
- **D-13:** Both `DEFINE_TOOL_BACKUP` and `UNDEFINE_TOOL_BACKUP` use `_guard_notification_operation()` — consistent with existing backup/mapping commands.

### Persistence
- **D-14:** Persistence uses `_persist_state()` which calls `StateStore.save()` — same pattern as `cmd_REMAP_TOOL` and `cmd_SET_TOOL_BACKUPS`.
- **D-15:** State mutation uses `FallbackState` methods — likely `with_user_defined_backup(logical, backup)` for define and `with_user_defined_backup(logical, None)` for undefine (or a `clear_user_defined_backup(logical)` method). The planner should design the exact state mutation API.
- **D-16:** No-op detection: if the state doesn't change (e.g., defining the same mapping that already exists), respond with "unchanged: no write" — same pattern as `_apply_immediate_backup_operation`.

### Error Messages
- **D-17:** Validation errors use `gcmd.error()` with descriptive messages — matching Klipper conventions and the style of existing commands.
- **D-18:** Success messages use `gcmd.respond_info()` with human-readable output showing what was changed.
- **D-19:** `UNDEFINE_TOOL_BACKUP` error when mapping doesn't exist: "No user-defined backup for tool Tn" — clear, specific.

### SHOW_TOOL_BACKUPS Output
- **D-20:** Output format: human-readable multi-line list, not JSON. Format:
  ```
  User-defined backups:
    T0 -> T1
    T2 -> T3
  (empty if none)
  ```
- **D-21:** `SHOW_TOOL_BACKUPS` shows only user-defined backups (from `self.state.user_defined_backups`), not configured backups — the "both" in CMD-08 means showing user-defined alongside a note about configured backups being separate, not merging them into one display.

### Integration with Phase 8 State Schema
- **D-22:** User-defined backups are stored in `self.state.user_defined_backups` as a `MappingProxyType` dict (from Phase 8 D-01).
- **D-23:** The state mutation must return a new `FallbackState` instance (frozen dataclass pattern) — not mutate in place.
- **D-24:** The planner should add a `with_user_defined_backup(logical, backup)` method to `FallbackState` if not already present in Phase 8 (Phase 8 added the field but may not have added mutation methods).

### the agent's Discretion
- **D-25:** Exact error message wording — as long as they're clear and consistent with existing command error messages
- **D-26:** Whether to add a `RESET_TOOL_BACKUPS` (clear all user-defined) command — not in requirements, but consistent with existing patterns. If added, note as scope expansion.
- **D-27:** Whether `SHOW_TOOL_BACKUPS` includes configured backup policies alongside user-defined — the requirements say "both" which could mean merged view or separate sections

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source Code
- `klippy/extras/tool_fallback.py` — Main extension class with existing command implementations (cmd_SET_TOOL_BACKUPS, cmd_REMAP_TOOL, cmd_SHOW_TOOL_FALLBACK_STATE, etc.) — the primary file for implementing new commands
- `klippy/extras/tool_fallback_state.py` — `FallbackState` dataclass with `user_defined_backups` field, `StateStore` for persistence — new state mutation methods may be needed
- `klippy/extras/tool_fallback_config.py` — `TOOL_NAME_RE` pattern, `ToolConfig` — for validation

### Requirements
- `.planning/REQUIREMENTS.md` — v1.2 requirements, CMD-01 through CMD-08

### Prior Phase Context
- `.planning/phases/08-state-schema-extension/08-CONTEXT.md` — Phase 8 decisions, including `user_defined_backups` schema design
- `.planning/phases/08-state-schema-extension/08-SUMMARY.md` — Phase 8 implementation details, affected test files

### Tests
- `tests/test_tool_fallback_extension.py` — Existing command tests (cmd_SET_TOOL_BACKUPS, cmd_REMAP_TOOL patterns)
- `tests/test_tool_fallback_state.py` — State mutation tests (with_mapping, with_backups patterns)

### Design
- `.planning/ROADMAP.md` — Phase 9 goal, dependencies, and success criteria

## Existing Code Insights

### Reusable Assets
- `_require_configured_tool(self, gcmd, parameter)` (`tool_fallback.py:1731`) — Validates tool name is configured; reuse for both logical and backup parameters
- `_guard_workflow_operation(self, error_factory, operation)` (`tool_fallback.py:1306`) — Rejects during active workflow; reuse for DEFINE and UNDEFINE
- `_guard_notification_operation(self, error_factory)` (`tool_fallback.py:1315`) — Rejects during notification; reuse for DEFINE and UNDEFINE
- `_persist_state(self, candidate)` (`tool_fallback.py:512`) — Atomic state persistence; reuse for all mutation commands
- `StateStore.save()` (`tool_fallback_state.py:396`) — Validates and persists state; called via `_persist_state`

### Established Patterns
- **Command registration:** `self.gcode.register_command("CMD_NAME", self.cmd_CMD_NAME, desc="...")` in `__init__`
- **Command handler signature:** `def cmd_CMD_NAME(self, gcmd):` — receives gcode command object
- **Parameter retrieval:** `gcmd.get("PARAM")` for strings, `gcmd.get_int("PARAM", minval=0, maxval=1)` for booleans
- **Error handling:** `raise gcmd.error("message")` for validation failures
- **Success feedback:** `gcmd.respond_info("message")` for informational messages
- **No-op detection:** Compare `candidate is self.state` before persisting — avoids unnecessary disk writes
- **Frozen dataclass mutations:** All state methods return new instances — never mutate in place

### Integration Points
- `self.state.user_defined_backups` — The `MappingProxyType` dict to read/write (via state mutation methods)
- `self.config.tools` — Configured tool names for validation
- `self._state_store` — The `StateStore` instance for persistence

## Specific Ideas

No specific requirements — open to standard approaches consistent with existing command patterns.

## Deferred Ideas

None — discussion stayed within phase scope

---

*Phase: 09-User Commands*
*Context gathered: 2026-06-29*
