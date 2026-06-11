# Phase 4: Automatic Fallback Workflow - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 04-automatic-fallback-workflow
**Areas discussed:** Backup resolution policy, Temperature and heater behavior, Timeout and retry behavior, Pause ownership and transient recovery

---

## Backup Resolution Policy

The user selected depth-first ordered traversal and chose to traverse through failed
intermediaries without selecting them. Sensor-unavailable tools use persisted loaded
state for eligibility: persisted loaded tools remain eligible with warnings, while
persisted unloaded tools require an explicit load state change.

Before declaring exhaustion, the workflow must re-scan the reachable graph once. If no
tool is eligible after re-scan, it remains paused and reports attempted/skipped tools.

## Temperature And Heater Behavior

Fallback captures the failed tool's requested target at confirmed runout. Missing or
zero target stops fallback with a warning. A valid target is captured before immediately
turning off the failed heater.

The chosen backup begins preheating before physical selection so toolchanger hardware
remains on the ooze blocker longer.

## Timeout And Retry Behavior

Physical selection error/timeout stops immediately; no alternate tool is attempted
because machine state may be unsafe. Heating timeout warns and leaves a recoverable
paused checkpoint. Normal `RESUME` continues only after validating that target
temperature was reached.

Purge failure/timeout stops paused and requires explicit operator correction. No
automatic purge retry or alternate backup selection occurs.

## Pause Ownership And Transient Recovery

Pause ownership is explicit in the runout hook contract, not inferred from timing.
Transient reinsertion and completed fallback auto-resume only when ownership is proven.
User-owned pauses never auto-resume.

While fallback is active or blocked on a non-heating failure, normal `RESUME` is
rejected. Guarded normal `RESUME` is allowed only for heating-timeout continuation after
readiness validation.

## the agent's Discretion

- Workflow checkpoint/status representation.
- Heater adapter details that preserve Klipper safety.
- Warning/error wording and attempted-tool report format.
- Graph traversal, timer, and guarded-resume implementation details.

## Deferred Ideas

- External notifications, example configuration, and live-printer verification remain in Phase 5.
