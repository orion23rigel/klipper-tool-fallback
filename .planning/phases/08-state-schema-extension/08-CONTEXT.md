# Phase 08: State Schema Extension - Context

**Gathered:** 2026-06-28
**Status:** Ready for planning

## Phase Boundary

This phase extends the persistent state schema with backward-compatible user-defined backup fields so the extension can store and restore mappings without breaking existing state files. It adds `user_defined_backup` to `ToolState` and `user_defined_backups` to `FallbackState`, bumps the schema version, and implements migration for existing state files.

**Scope anchor:** Schema extension only. No commands, no detection, no prompt flow, no routing changes.

## Requirements (locked via REQUIREMENTS.md)

**4 requirements are locked.** See REQUIREMENTS.md for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read REQUIREMENTS.md before planning or implementing.

**In scope (from REQUIREMENTS.md):**
- STATE-01: `ToolState` includes optional `user_defined_backup` field defaulting to `None`
- STATE-02: `FallbackState` includes optional `user_defined_backups` dict field defaulting to `{}`
- STATE-03: `StateStore.load_reconciled()` handles state files lacking `user_defined_backups`
- STATE-04: `StateStore.save()` persists `user_defined_backups` to JSON state file

**Out of scope (from REQUIREMENTS.md):**
- User commands (Phase 9)
- Undefined tool detection (Phase 10)
- User prompt flow (Phase 11)
- Fallback integration and observability (Phase 12)

## Implementation Decisions

### Schema Storage Design
- **D-01:** `user_defined_backups` is stored as a top-level dict on `FallbackState` (e.g., `{"T0": "T1"}`) — this is the canonical source of truth
- **D-02:** `ToolState.user_defined_backup` is a single optional string defaulting to `None` — a derived convenience accessor that reads from the parent `FallbackState.user_defined_backups[logical_tool]`
- **Rationale:** Matches STATE-02's wording ("optional `user_defined_backups` dict field") and STATE-01's singular wording ("optional `user_defined_backup` field"). Keeps the data model clean with one source of truth.

### Schema Version
- **D-03:** Bump schema version from 1 to 2
- **D-04:** `FallbackState.from_dict()` accepts both version 1 and version 2 — for v1 files, `user_defined_backups` is initialized to `{}`
- **Rationale:** Explicit version bump signals a schema change and makes migration visible. `from_dict` validation checks `version in (1, 2)` and fills in the missing field.

### User-Defined Backup Semantics
- **D-05:** User-defined backups take precedence over configured backups during routing resolution
- **D-06:** When no user-defined backup exists for a tool, configured backups serve as the fallback (handled in Phase 12's `resolve_backup_graph()`)
- **Rationale:** The phase's purpose is to let users explicitly define a backup for a non-existent tool. Their choice should be authoritative. Configured backups provide the default when no user override exists.

### Data Model
- **D-07:** `ToolState.user_defined_backup` is a single string (not a list) — one user-defined backup per logical tool
- **D-08:** `FallbackState.user_defined_backups` is a dict mapping logical tool names (str) to single backup tool names (str or None)
- **Rationale:** Simplest model satisfying all 4 STATE requirements. Single backup per tool is sufficient for the undefined-tool flow (Phase 10-11).

### Migration Strategy
- **D-09:** Migration is implicit during `from_dict()` — no separate migration step or version upgrade write
- **D-10:** Existing v1 state files load successfully with `user_defined_backups = {}` and remain on disk unchanged
- **Rationale:** Minimal risk. No need to rewrite existing files. The field is optional everywhere.

### Serialization
- **D-11:** `to_dict()` always includes `user_defined_backups` in the serialized output (even when empty `{}`)
- **D-12:** `sort_keys=True` is preserved in `StateStore.save()` — `user_defined_backups` keys are sorted alphabetically
- **Rationale:** Consistent with existing serialization patterns. Ensures deterministic output.

### Validation
- **D-13:** `user_defined_backups` values must be valid tool names (matching `TOOL_NAME_RE`) or `None`
- **D-14:** Self-references and unknown tool references in `user_defined_backups` are rejected by `StateStore.save()` or during `reconcile()`
- **Rationale:** Consistent with existing backup validation rules. Prevents corrupted state.

### the agent's Discretion
- **D-15:** Exact placement of `user_defined_backups` in `to_dict()` output (key ordering) — as long as `sort_keys=True` is used, order is deterministic
- **D-16:** Whether `reconcile()` should propagate user-defined backups into new tools added during reconciliation (agent should default to inheriting from config)

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### State Schema
- `klippy/extras/tool_fallback_state.py` — Current implementation of `ToolState`, `FallbackState`, `StateStore`, and all persistence logic
- `klippy/extras/tool_fallback_config.py` — ToolConfig dataclass (referenced by state tests)
- `klippy/extras/tool_fallback.py` — `resolve_backup_graph()` and routing logic (for Phase 12 integration context)

### Requirements
- `.planning/REQUIREMENTS.md` — v1.2 requirements, including STATE-01 through STATE-04

### Tests
- `tests/test_tool_fallback_state.py` — Existing state tests (555 lines) — new tests must follow these patterns

### Design
- `.planning/DESIGN.md` — Design document with state schema example and semantics

### Prior Phase Context
- `.planning/ROADMAP.md` — Phase 8 goal and dependencies

## Existing Code Insights

### Reusable Assets
- `StateStore` class (`klippy/extras/tool_fallback_state.py:289`) — Atomic write, fsync, and load logic. New persistence code should use this class.
- `FallbackState.from_dict()` (`klippy/extras/tool_fallback_state.py:42`) — Parsing/validation pattern for backward-compatible schema loading
- `_require_fields()` and `_require_tool_name()` (`klippy/extras/tool_fallback_state.py:367, 387`) — Validation helpers to reuse
- `MappingProxyType` — Used for immutable tool/mapping views; should be preserved for `user_defined_backups`

### Established Patterns
- **Frozen dataclasses:** `ToolState` and `FallbackState` are frozen — all mutations return new instances via `with_*` methods
- **Immutable views:** `MappingProxyType` wraps tools and mappings — `user_defined_backups` should follow the same pattern
- **Atomic writes:** `StateStore._atomic_write()` uses tempfile + fsync + os.replace — new save logic must use this
- **Strict parsing:** `from_dict()` rejects unknown fields, duplicate keys, and invalid types — new fields must fit this model
- **Canonical ordering:** `_canonical()` sorts tools and mappings by tool number — `user_defined_backups` should be sorted by key in `to_dict()`

### Integration Points
- `klippy/extras/tool_fallback.py` — `resolve_backup_graph()` will need to consider `user_defined_backups` (Phase 12)
- `klippy/extras/tool_fallback_config.py` — `ToolConfig` provides the configured backup lists that serve as defaults

## Specific Ideas

No specific requirements — open to standard approaches.

## Deferred Ideas

None — discussion stayed within phase scope

---

*Phase: 08-State Schema Extension*
*Context gathered: 2026-06-28*
