# Phase 5: Runtime Contracts - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Add safety-neutral external notifications for terminal fallback outcomes and atomic
runtime backup-policy commands. Notifications must not affect fallback safety behavior.
Backup-policy changes affect future resolution only and do not select, remap, or
otherwise operate physical tools.

</domain>

<decisions>
## Implementation Decisions

### Notification Payload
- **D-01:** Every external event carries the compact canonical fields `EVENT`,
  `GENERATION`, `LOGICAL_TOOL`, `FAILED_TOOL`, `SELECTED_TOOL`, and `REASON_CODE`.
- **D-02:** Every canonical field is always present. An unavailable value is represented
  by the stable sentinel `n/a`.
- **D-03:** `REASON_CODE` uses specific stable codes such as `GRAPH_EXHAUSTED`,
  `HEATING_TIMEOUT`, `PURGE_FAILED`, and `RESUME_FAILED`.
- **D-04:** Unexpected failures retain a stable reason code and include a bounded,
  sanitized human-readable `REASON_DETAIL`. Detailed exception data remains local.

### Notification Outcome Timing
- **D-05:** A recoverable `HEATING_TIMEOUT` does not emit an interim external event.
  Notify only the final success or failure after guarded resume resolves the workflow.
- **D-06:** Emit `FALLBACK_FAILURE` immediately when a terminal blocked checkpoint is
  established.
- **D-07:** Emit `TRANSIENT_RECOVERY` only after the original tool's transient runout
  clears and no fallback workflow proceeds.
- **D-08:** If tool recovery completes but automatic `RESUME` fails, the final event is
  `FALLBACK_FAILURE` with `REASON_CODE=RESUME_FAILED`, not fallback success.

### Backup Mutation Availability And Queueing
- **D-09:** Operators may change backup policy while a print is printing or paused when
  no fallback workflow or route transition is active. The change affects future
  resolution only.
- **D-10:** A mutation submitted during an active fallback workflow or route transition
  is queued rather than rejected. This decision supersedes the active-workflow rejection
  recommendation in `.planning/research/SUMMARY.md`.
- **D-11:** Process queued mutations after any terminal workflow outcome, once no route
  transition is active.
- **D-12:** Process every queued command as a distinct operation in submission order,
  including multiple commands targeting the same tool.
- **D-13:** Stop queue processing at the first application failure and report both the
  failed command and all remaining unapplied commands.

### Command Feedback
- **D-14:** A successful immediate mutation reports the affected tool and complete
  canonical ordered backup list now persisted.
- **D-15:** An exact no-op explicitly reports that no write occurred and includes the
  unchanged canonical policy.
- **D-16:** A queued command immediately reports its queue position, requested operation,
  and active workflow stage.
- **D-17:** Queue processing reports the applied, no-op, or failed result of each
  processed command, followed by final queue totals.

### the agent's Discretion
- Choose the bounded encoding and maximum length for `REASON_DETAIL`.
- Define the full stable `REASON_CODE` vocabulary while preserving the examples above.
- Choose internal queue representation and reboot/shutdown handling, provided no queued
  command can alter an active workflow and all visible queue behavior follows D-10
  through D-17.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone Contract
- `.planning/ROADMAP.md` — Phase boundary, success criteria, and milestone sequencing.
- `.planning/REQUIREMENTS.md` — Observable Phase 5 notification and backup-policy
  requirements. `BACKUP-04` contains the discussion-approved queueing contract.
- `.planning/research/SUMMARY.md` — Architecture and safety research. Its recommendation
  to reject active-workflow backup mutations is superseded by D-10 through D-13 here.

### Existing Runtime
- `klippy/extras/tool_fallback.py` — Workflow checkpoints, generations, G-Code command
  registration, terminal outcomes, persistence integration, and adapter invocation
  patterns.
- `klippy/extras/tool_fallback_state.py` — Immutable canonical state and atomic
  save-before-publish persistence behavior.
- `klippy/extras/tool_fallback_config.py` — Configured tool defaults and existing
  `notify_gcode` adapter option.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WorkflowCheckpoint` and `_workflow_generation`: provide stable workflow identity,
  stage, tool context, and terminal-state boundaries for notifications and queued work.
- `FallbackState` immutable replacement methods and `StateStore.save()`: provide the
  required candidate, atomic save, then publish pattern for backup-policy changes.
- Configured `notify_gcode`: provides the printer-owned external notification boundary.

### Established Patterns
- Operator commands validate canonical configured tool names, create immutable
  candidates, skip exact no-ops, persist before publishing, and translate failures into
  visible G-Code errors.
- `resolve_backup_graph()` preserves ordered traversal and safely contains graph cycles.
- Workflow checkpoints and route-transition guards protect in-progress physical work.

### Integration Points
- Register `SET_TOOL_BACKUPS`, `RESTORE_TOOL_BACKUPS`, and `RESET_TOOL_BACKUPS` beside
  the existing routing and state commands in `ToolFallback.__init__`.
- Emit notifications at transient-recovery and terminal workflow boundaries in
  `tool_fallback.py`.
- Drain queued backup operations only after a terminal outcome and once route
  transitions are inactive.

</code_context>

<specifics>
## Specific Ideas

- Minimal backup command surface:
  `SET_TOOL_BACKUPS TOOL=T0 BACKUPS=T2,T1`,
  `RESTORE_TOOL_BACKUPS TOOL=T0`, and `RESET_TOOL_BACKUPS`.
- `SET_TOOL_BACKUPS` accepts an empty backup list to clear one tool's policy.
- Notifications remain best-effort observations; downstream delivery is never promised.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-notifications-integration-and-verification*
*Context gathered: 2026-06-11*
