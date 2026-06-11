# Phase 3: Sensor State And Purge Lifecycle - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-06-07
**Phase:** 03-sensor-state-and-purge-lifecycle
**Areas discussed:** Startup sensor reconciliation, Runout and failed-state semantics, Purge command authority, Automatic purge during selection

---

## Startup Sensor Reconciliation

The initial fail-startup option was rejected. Missing or disabled sensors degrade the
tool to unknown/unverified sensor authority without preventing startup or ordinary use.

The selected physical tool pauses once when its sensor first becomes unavailable during
a print. Resuming acknowledges the outage, and later use continues without repeated
pauses. Sensor-unavailable tools cannot originate fallback events but remain allowed and
automatically selectable as backup tools with warnings.

## Runout And Failed-State Semantics

The user selected immediate standard-sensor pause followed by symmetric debounce.
Confirmed active-print runout marks the selected physical tool failed; ordinary
unloading does not. User-owned pauses are never auto-resumed or used to launch fallback,
but confirmed runout still records failed state.

## Purge Command Authority

The user selected purge with warning when sensor state is unknown. Purged state changes
only after successful dedicated purge execution.

For sensor-unavailable tools, load/unload macros use one explicit
`SET_TOOL_FILAMENT_STATE TOOL=Tn LOADED=0|1` command. Inactive tools may be changed while
printing; the selected physical tool may be changed explicitly only while paused.
Manual purge-state commands follow the same restriction.

## Automatic Purge During Selection

The user selected automatic purge for every active-print selection of an unpurged
physical tool, including ordinary logical `Tn` commands. Unknown sensor state warns but
does not block automatic purge. Purge failure leaves the print paused and the tool
unpurged. Outside an active print, selection succeeds without automatic purge and reports
unpurged status.

## the agent's Discretion

- Exact warning and status wording.
- Internal unknown-sensor and outage-acknowledgement representation.
- Exact explicit purged/unpurged command names.
- Klipper callback and timer integration details.

## Deferred Ideas

- Automatic backup resolution and fallback execution remain in Phase 4.
- External notifications and real-printer verification remain in Phase 5.
