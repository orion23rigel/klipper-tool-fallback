# Phase 10: Undefined Tool Detection - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

## Phase Boundary

This phase detects when G-code references a tool number not configured on the printer and triggers the undefined-tool flow. It implements a wrapper G-code command `_TOOL_FALLBACK_TN` that intercepts tool selection requests, checks if the tool is configured, and either delegates to existing routing or triggers the undefined-tool flow.

**Scope anchor:** Detection logic only. No prompt flow (Phase 11), no routing integration (Phase 12). The undefined-tool flow trigger is a state change + log event that Phase 11 will respond to.

## Requirements (locked via REQUIREMENTS.md)

**4 requirements are locked.** See REQUIREMENTS.md for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read REQUIREMENTS.md before planning or implementing.

**In scope (from REQUIREMENTS.md):**
- DETECT-01: Wrapper command `_TOOL_FALLBACK_TN` parses tool number from G-code parameters
- DETECT-02: `_TOOL_FALLBACK_TN` checks if tool is configured in `self.config.tools`
- DETECT-03: If configured, delegates to existing `_route_logical` path
- DETECT-04: If NOT configured, triggers the undefined-tool flow

**Out of scope (from REQUIREMENTS.md):**
- User commands (Phase 9) — already implemented
- User prompt flow (Phase 11) — Phase 10 triggers, Phase 11 responds
- Fallback integration and observability (Phase 12)

## Implementation Decisions

### Wrapper Command Design
- **D-01:** The wrapper command is `_TOOL_FALLBACK_TN` (underscore prefix = internal/private command, consistent with Klipper conventions for internal commands like `_TOOL_FALLBACK_NOTIFY`, `_TOOL_FALLBACK_PURGE`).
- **D-02:** The command parses the tool number from the `T` parameter: `gcmd.get("T")` — this is the standard Klipper tool selection parameter.
- **D-03:** The command is registered in `__init__` alongside other internal commands, with `desc="_TOOL_FALLBACK_TN wrapper for tool selection"` (or similar).

### Tool Number Validation
- **D-04:** Tool number validation uses `TOOL_NAME_RE` from `tool_fallback_config` — same regex used everywhere for tool name validation.
- **D-05:** Invalid tool number format → `gcmd.error("Tool number must be in format Tn where n is a non-negative integer")`.
- **D-06:** If the T parameter is missing entirely → `gcmd.error("_TOOL_FALLBACK_TN requires a T parameter")`.

### Routing Delegation
- **D-07:** When the tool IS configured, delegation goes to `self._route_logical(logical_tool, gcmd)` — the EXISTING routing method. This preserves all existing behavior (mapping lookup, physical selection, purge, etc.) for known tools.
- **D-08:** The wrapper does NOT replace existing logical tool handlers (T0, T1, etc.). Instead, it is a separate command that macros/users call. The existing tool handlers remain unchanged.
- **D-09:** The wrapper should log when delegation occurs — `self.gcode.respond_info("Tool Tn is configured; routing normally")` — for operator visibility.

### Undefined Tool Flow Trigger
- **D-10:** When the tool is NOT configured, the undefined-tool flow is triggered by:
  1. Logging the event: `self.gcode.respond_info("Tool Tn is not configured on this printer")`
  2. Setting a state flag or raising a specific exception that Phase 11's prompt flow can detect
  3. The trigger mechanism should be a new `_workflow_checkpoint` with `source="undefined_tool"` and `stage="tool_not_configured"` — reusing the existing checkpoint infrastructure
- **D-11:** The undefined-tool trigger does NOT pause the print by itself — Phase 11's prompt flow handles pausing (PROMPT-01). Phase 10 just detects and signals.
- **D-12:** Detection events are logged via `self.gcode.respond_info()` which feeds Klipper's log system — satisfies DETECT-04.

### Integration with Existing Architecture
- **D-13:** The wrapper command is a standalone G-code handler — it does NOT monkey-patch existing tool handlers (per PROJECT.md scope boundary: "wrapper command, not monkey-patching").
- **D-14:** The wrapper should be documented in examples as the recommended entry point for tool selection when undefined-tool detection is desired.
- **D-15:** The `_route_logical` method signature is `_route_logical(self, logical_tool, gcmd)` — the wrapper calls this directly for configured tools.

### Error Handling
- **D-16:** If `self.config` is None (routing not initialized) → `gcmd.error("Tool fallback routing is not initialized")` — same guard as existing commands.
- **D-17:** The wrapper does NOT call `_guard_workflow_operation()` — tool selection should work even during a workflow (the undefined-tool case is itself part of a workflow).

### the agent's Discretion
- **D-18:** How the "undefined tool" signal is communicated to Phase 11 — options: checkpoint-based (preferred, consistent with existing architecture), state flag, or exception. The checkpoint approach is most consistent with the existing `_workflow_checkpoint` pattern.
- **D-19:** Whether to include the tool number in the info message or use a specific error code
- **D-20:** Whether the wrapper should also accept a `BACKUP` parameter to pre-specify a backup tool

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source Code
- `klippy/extras/tool_fallback.py` — Main extension class, `_route_logical()` method, `_workflow_checkpoint` infrastructure, `WorkflowCheckpoint` dataclass
- `klippy/extras/tool_fallback_config.py` — `TOOL_NAME_RE` pattern for tool name validation
- `klippy/extras/tool_fallback_state.py` — `FallbackState` with `user_defined_backups` (for Phase 12 integration context)

### Requirements
- `.planning/REQUIREMENTS.md` — v1.2 requirements, DETECT-01 through DETECT-04

### Prior Phase Context
- `.planning/phases/09-user-commands/09-CONTEXT.md` — Phase 9 decisions, command patterns
- `.planning/phases/08-state-schema-extension/08-CONTEXT.md` — Phase 8 state schema decisions

### Design
- `.planning/ROADMAP.md` — Phase 10 goal, dependencies, and success criteria

## Existing Code Insights

### Reusable Assets
- `_route_logical(self, logical_tool, gcmd)` (`tool_fallback.py:462`) — Existing routing method; wrapper delegates here for configured tools
- `WorkflowCheckpoint` dataclass (`tool_fallback.py:45`) — Used for workflow state tracking; new checkpoint source "undefined_tool"
- `self.gcode.respond_info()` — Klipper log/info output; used for detection logging
- `self.gcode.error()` — G-code error raising; used for validation failures

### Established Patterns
- **Wrapper command:** Internal commands use underscore prefix (`_TOOL_FALLBACK_NOTIFY`, `_TOOL_FALLBACK_PURGE`)
- **Parameter parsing:** `gcmd.get("PARAM")` for strings, validated against `TOOL_NAME_RE`
- **Workflow checkpoints:** Source + stage + generation pattern; new source types follow same structure
- **Delegation pattern:** Wrapper checks condition, then delegates to existing method or triggers new flow

### Integration Points
- `self.config.tools` — Configured tool names for existence check
- `self._route_logical()` — Existing routing for configured tools
- `self._workflow_checkpoint` — State tracking for undefined-tool flow trigger
- `self.gcode.respond_info()` — Klipper logging for detection events

## Specific Ideas

No specific requirements — open to standard approaches consistent with existing architecture.

## Deferred Ideas

None — discussion stayed within phase scope

---

*Phase: 10-Undefined Tool Detection*
*Context gathered: 2026-06-29*
