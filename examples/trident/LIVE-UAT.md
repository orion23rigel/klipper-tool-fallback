# Trident Representative Live-UAT Runbook

> **Scope:** This runbook is bounded to the representative Trident revision
> `e7790d022346a62662acfe0b3098ad39eb9eaddc` with active tools `T0` and `T1`.
> It is **not** a universal compatibility claim.

## Global Rules

- **Supervised only.** An operator must be present and watching for the entire run.
- **Simulation-only failure inputs.** Filament-runout and fault scenarios use
  explicit extension commands (e.g. `TOOL_FALLBACK_RUNOUT TOOL=T0`), not physical
  sensor triggers. **This does not prove a physical sensor transition.**
- **Increasing risk.** Rows are ordered from offline checks to live hardware motion.
  Do not combine the first real fallback, first purge, first notification, first
  liftbar movement, and first guarded resume into one row.
- **Stop, do not improvise.** On any unexpected X/Y/Z motion, liftbar motion,
  tool attachment/detachment state change, heater target outside the stated row,
  purge or extrusion outside the cleared bucket, missing pause at a fail-closed
  checkpoint, unexpected automatic resume, duplicate or malformed notification,
  or state/mapping/backup change outside the row — **stop immediately**.
- **Cleanup after every row.** Restore identity mappings, reciprocal backups,
  normal heater targets, normal sensor enablement, and no active workflow/queue.
  **Do not rely on restart as cleanup.**
- **Record before mutating.** Before every mutating row, record: extension and
  representative-config revisions, Klipper/Moonraker/toolchanger revisions,
  active T0/T1 topology and selected tool, sensor state, heater targets,
  mappings, backup policy, purge flags, workflow state, backup queue, physical
  clearances (bed, docks, bucket, liftbar), homing status, attached tool, and
  operator presence.

## Revision Capture

| Field | Value |
|---|---|
| Trident revision | `e7790d022346a62662acfe0b3098ad39eb9eaddc` |
| Extension revision | `d27b367` |
| Klipper revision | _(record before run on live printer)_ |
| Moonraker revision | _(record before run on live printer)_ |
| Toolchanger revision | _(record before run on live printer)_ |
| Active topology | T0/T1 only (T2–T6 disabled) |
| Run header prepared | 2026-06-26 |

---

## Staged Matrix

| ID / Requirement | Evidence Class | Claim | Topology / Revisions | Preconditions | Procedure | Expected | Observed | Result | Evidence | Cleanup |
|---|---|---|---|---|---|---|---|---|---|---|
| UAT-OFFLINE-01 / EXAMPLE-01 | automated-contract | Offline example-contract and redaction checks pass | As captured above | Printer powered, Klipper running, bundle installed | Run `pytest -q tests/test_examples.py`; inspect output for all-pass | All contract tests pass with zero failures | | NOT RUN | | Not applicable (offline) |
| UAT-PREFLIGHT-01 / EXAMPLE-01 | normal-live-operation | Physical preflight and normal T0/T1 toolchanges succeed | As captured above | Bed clear, docks clear, liftbar homed, operator present | Issue `T0`, verify MadMax completes selection; issue `T1`, verify selection; run `SHOW_TOOL_FALLBACK_STATE` | Each tool selects without error; state reflects selected tool | | NOT RUN | | Return to T0 or T1; verify state canonical |
| UAT-NOTIFY-01 / UAT-01 | normal-live-operation | Notification adapter receipt without fallback | As captured above | Selected tool, Klipper running | Trigger a benign event that produces a notification (e.g. manual status query) | Klipper log shows adapter macro invocation; Moonraker `notify` remote method called with notifier name `discord`; no extension mutation commands invoked | | NOT RUN | | Verify no residual state change |
| UAT-BACKUP-MUTATE-01 / UAT-01 | normal-live-operation | Immediate backup mutation and cleanup | As captured above | Selected tool, reciprocal backups in place | Use extension backup mutation command to change a backup policy; verify mutation recorded in state file | Mutation recorded; affects future resolution only; no active workflow or current routing affected | | NOT RUN | | Restore reciprocal backups; verify state canonical |
| UAT-SENSOR-SIM-01 / UAT-01 | simulated-input/live-output | Sensor-hook command simulation (safe simulated input) | As captured above | Selected tool, printer in known state | Issue `TOOL_FALLBACK_RUNOUT TOOL=T0 PAUSE_OWNED=1` as explicit command (not physical sensor trigger) | Extension receives command, enters fallback, resolves correct backup tool, adapter macros invoked in correct order | | NOT RUN | | Restore mappings, backups, sensor state; verify no residual workflow |
| UAT-HEATER-PURGE-01 / UAT-01 | normal-live-operation | Controlled heater transfer and purge adapter checks | As captured above | Simulated fallback complete, selected tool, bucket clear, safe temperature | Verify purge adapter validates selected tool; verify purge delegates to BUCKET_PURGE without invoking PURGE_TOOL; verify no persistence mutation during purge | Purge to correct location; no wrong heater transfer; no persistence change | | NOT RUN | | Restore heater targets; verify state canonical |
| UAT-FALLBACK-01 / UAT-01 | simulated-input/live-output | Paused sentinel-print simulated fallback with backup already purged | As captured above | Sentinel print paused (no model extrusion), backup purged, clearances verified | Issue `TOOL_FALLBACK_RUNOUT TOOL=T0 PAUSE_OWNED=1` from paused sentinel; observe heater transfer, one physical selection, mapping, owned resume, final notification | Fallback completes; purge adapter invoked; notification emitted; state reflects outcome | | NOT RUN | | Restore mappings, backups, sensor state; verify no queued operations |
| UAT-GUARDED-RESUME-01 / UAT-01 | simulated-input/live-output | Guarded resume plus queued backup mutation | As captured above | Short `heating_timeout` set, sentinel paused, fallback simulated | Simulate owned runout, observe `heating_timeout` checkpoint, invoke `RESUME` only after readiness; submit queued backup mutation during active checkpoint | Resume guarded by heating timeout; queued mutation received and drained after terminalization | | NOT RUN | | Restore reciprocal defaults; verify queue empty; heating_timeout restored |
| UAT-AUDIT-01 / EXAMPLE-01, UAT-01 | normal-live-operation | Final cleanup and claim audit | As captured above | All rows executed or skipped with documented reason | Restore identity mappings, reciprocal backups, normal sensor enablement; verify no residual mutation or queue; verify adapter macros in consistent state | All state canonical; no residual mutation or queue; adapters consistent | | NOT RUN | | Document any residual state for follow-up |

## Explicitly Excluded Phase 1 Scenarios

The following four Phase 1 UAT scenarios are **EXCLUDED — NOT EXECUTED / NOT CREDITED**:

1. **Valid Configuration Startup**
2. **Persisted State Survives Restart**
3. **Invalid State Blocks Startup Clearly**
4. **Read-Only Status Inspection**

Incidental startup, restart, or state display used during setup or observation must not
be represented as completion of these scenarios. Configuration restart is not evidence
for any excluded scenario.

---

*These results are bounded to the listed representative Trident topology and revisions.*
*They are not a universal compatibility claim.*
