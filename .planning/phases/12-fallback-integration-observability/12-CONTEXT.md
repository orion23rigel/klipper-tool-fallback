# Phase 12: Fallback Integration & Observability - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

## Phase Boundary

This phase merges user-defined backups into the routing resolution pipeline and exposes runtime state for operator visibility. It modifies `resolve_backup_graph()` to consider user-defined backups, ensures they flow through existing safety checkpoints, updates `SHOW_TOOL_FALLBACK_STATE` to display them, and logs undefined tool detection events.

**Scope anchor:** Routing integration + observability. No new commands (Phase 9), no detection (Phase 10), no prompt flow (Phase 11).

## Requirements (locked via REQUIREMENTS.md)

**6 requirements are locked.** See REQUIREMENTS.md for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read REQUIREMENTS.md before planning or implementing.

**In scope (from REQUIREMENTS.md):**
- FALLBACK-01: `resolve_backup_graph()` considers user-defined backups alongside configured backups
- FALLBACK-02: User-defined backups applied through existing `_select_and_conditionally_purge()` path
- FALLBACK-03: All fail-closed safety checkpoints respected when applying user-defined backups
- FALLBACK-04: `SHOW_TOOL_FALLBACK_STATE` includes user-defined backup mappings in output
- OBSERVE-01: Undefined tool detection events visible in Klipper's log system
- OBSERVE-02: (Note: OBSERVE-01 and OBSERVE-02 are listed in ROADMAP but the REQUIREMENTS.md shows OBSERVE-01 and OBSERVE-02 — both about logging/visibility)

**Out of scope (from REQUIREMENTS.md):**
- User commands (Phase 9) — already implemented
- Undefined tool detection (Phase 10) — already implemented
- User prompt flow (Phase 11) — already implemented

## Implementation Decisions

### resolve_backup_graph() Integration
- **D-01:** `resolve_backup_graph()` is modified to prepend user-defined backups to the backup list before graph traversal. When resolving for a failed tool, if `state.user_defined_backups[logical_tool]` is not None, that tool is tried FIRST before the configured backup chain.
- **D-02:** The user-defined backup is a single tool (not a list), so it's tried as the first candidate. If it fails (unloaded, failed, etc.), the configured backup chain from `state.tools[failed_tool].backups` is tried next.
- **D-03:** The modification is in the caller of `resolve_backup_graph()` — likely in `_on_confirmed_runout()` or a new helper that builds the effective backup list. The core `resolve_backup_graph()` function itself is NOT modified to avoid breaking its pure-function contract.
- **D-04:** User-defined backups are only considered for the SPECIFIC logical tool that failed — not as a global override for all tools.

### Safety Checkpoint Compliance
- **D-05:** User-defined backups flow through the EXISTING `_select_and_conditionally_purge()` path — no separate fast path. This means they get the same purge, preheat, and safety checkpoint treatment as configured backups.
- **D-06:** Fail-closed safety is preserved: if the user-defined backup tool is unloaded, failed, or has unknown sensor authority, the configured backup chain is used instead.
- **D-07:** The user-defined backup is validated at routing time (not just at definition time) — consistent with Phase 8's `_validate_user_defined_backups()` which validates at save time.

### SHOW_TOOL_FALLBACK_STATE Updates
- **D-08:** `get_status()` (which powers `SHOW_TOOL_FALLBACK_STATE`) adds a `user_defined_backups` key to the output snapshot — same format as the state file: `{"T0": "T1", "T2": null}`.
- **D-09:** The output is appended to the existing status snapshot alongside `mappings`, `configuration`, `active_logical_tool`, etc.

### Undefined Tool Detection Logging
- **D-10:** Phase 10's `_TOOL_FALLBACK_TN` already logs via `self.gcode.respond_info()` — this feeds Klipper's log system. No additional logging needed unless Phase 10's implementation is insufficient.
- **D-11:** If Phase 10's detection logging is adequate (respond_info → Klipper log), OBSERVE-02 is satisfied by existing code. Phase 12 verifies this.

### State Reconciliation
- **D-12:** `FallbackState.reconcile()` already filters `user_defined_backups` for removed tools (from Phase 8). No changes needed.
- **D-13:** `SHOW_TOOL_FALLBACK_STATE` output should distinguish between user-defined backups and configured backups — the `user_defined_backups` key in the snapshot makes this clear.

### the agent's Discretion
- **D-14:** Exact location where user-defined backups are injected into the backup resolution — could be in `resolve_backup_graph()` itself (modifying the visited tool's effective backup list) or in the caller (`_on_confirmed_runout`). Caller-side injection is cleaner.
- **D-15:** Whether to add a `user_defined_backup` field to the `GraphResolution` output for observability
- **D-16:** Whether undefined tool detection events should also trigger notifications (like FALLBACK_SUCCESS/FALLBACK_FAILURE) or just logging

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source Code
- `klippy/extras/tool_fallback.py` — `resolve_backup_graph()` function (line 106), `_on_confirmed_runout()` (line 950), `_select_and_conditionally_purge()` (line 476), `get_status()` (line 257), `_finalize_fallback_success()` (line 607)
- `klippy/extras/tool_fallback_state.py` — `FallbackState.reconcile()` (line 165), `FallbackState.to_dict()` (line 148), `user_defined_backups` field
- `klippy/extras/tool_fallback_config.py` — `TOOL_NAME_RE`, `GlobalConfig`

### Requirements
- `.planning/REQUIREMENTS.md` — v1.2 requirements, FALLBACK-01 through FALLBACK-04, OBSERVE-01 through OBSERVE-02

### Prior Phase Context
- `.planning/phases/11-user-prompt-flow/11-CONTEXT.md` — Phase 11 prompt flow design
- `.planning/phases/10-undefined-tool-detection/10-CONTEXT.md` — Phase 10 detection design
- `.planning/phases/09-user-commands/09-CONTEXT.md` — Phase 9 command patterns
- `.planning/phases/08-state-schema-extension/08-CONTEXT.md` — Phase 8 state schema

### Design
- `.planning/ROADMAP.md` — Phase 12 goal, dependencies, and success criteria

## Existing Code Insights

### Reusable Assets
- `resolve_backup_graph(state, failed_tool, unknown_authority=())` (`tool_fallback.py:106`) — Core backup resolution function; needs user-defined backup integration
- `_select_and_conditionally_purge()` (`tool_fallback.py:476`) — Existing path that user-defined backups must flow through
- `get_status()` (`tool_fallback.py:257`) — Status snapshot for SHOW commands; needs user_defined_backups key
- `FallbackState.to_dict()` (`tool_fallback_state.py:148`) — Serialization; already includes user_defined_backups

### Established Patterns
- **Graph traversal:** DFS with evaluated/looped/unloaded tracking — user-defined backup is a first-try candidate
- **Fail-closed:** Unknown/failed tools skipped in graph traversal — user-defined backup subject to same rules
- **Status snapshots:** Dict with sorted keys via `to_dict()` — user_defined_backups included naturally

### Integration Points
- `_on_confirmed_runout()` — Where backup resolution happens; user-defined backups injected here
- `get_status()` — Where observability output is built
- `resolve_backup_graph()` — Core resolution function

## Specific Ideas

No specific requirements — open to standard approaches consistent with existing architecture.

## Deferred Ideas

None — discussion stayed within phase scope

---

*Phase: 12-Fallback Integration & Observability*
*Context gathered: 2026-06-29*
