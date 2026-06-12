# Phase 6: Examples And Live Integration - Research

**Researched:** 2026-06-12
**Status:** Complete
**Scope:** One representative Trident integration bundle and bounded supervised live
evidence for `EXAMPLE-01` and `UAT-01`

## Phase Boundary

Phase 6 should deliver and validate one internally consistent integration for the
representative Voron Trident at revision
`e7790d022346a62662acfe0b3098ad39eb9eaddc`. It should not attempt to create a generic
toolchanger abstraction or claim compatibility beyond that tested printer.

The representative topology is:

- active tools `T0` and `T1` only; configured-but-disabled `T2` through `T6` remain out
  of scope;
- reciprocal ordered fallback policy: `T0 -> T1` and `T1 -> T0`;
- MadMax toolchanger paths, per-tool probes, two-stepper liftbar, independent CAN
  toolboards, independent `extruder` / `extruder1` heaters, and `T0_sensor` /
  `T1_sensor`;
- printer-owned `BUCKET_PURGE`, `BUCKET_PARK`, `SILICONE_PARK`, `PAUSE`, `RESUME`, and
  Moonraker Discord notification behavior.

Live work is supervised controlled simulation of failure inputs. It must not physically
remove filament, detach tools, inject MCU/heater/sensor faults, provoke collisions, or
credit the four excluded Phase 1 UAT scenarios.

## Explicit Exclusion

The evidence matrix and all planning artifacts must explicitly name and not execute or
credit:

1. Valid Configuration Startup
2. Persisted State Survives Restart
3. Invalid State Blocks Startup Clearly
4. Read-Only Status Inspection

Startup/restart or state display may be incidental setup or evidence capture, but cannot
be represented as completion of these scenarios.

## Representative Printer Findings

### Baseline Is Present And Revision-Bound

The clone at `/tmp/Laurion3D_Trident-phase6` is available and its `HEAD` is exactly
`e7790d022346a62662acfe0b3098ad39eb9eaddc`. Relevant structure:

| Representative file | Relevant contract |
|---|---|
| `printer.cfg` | Includes `macros.cfg`, `brush_bucket.cfg`, and `klipper-toolchanger/includes.cfg` |
| `klipper-toolchanger/includes.cfg` | Enables `tool_0.cfg` and `tool_1.cfg`; comments out `tool_2.cfg` through `tool_6.cfg` |
| `klipper-toolchanger/toolchanger.cfg` | MadMax paths, safe Y, liftbar stow Z, change hooks, and crash handler |
| `klipper-toolchanger/liftbar.cfg` | Real dual-stepper liftbar motion and homing |
| `klipper-toolchanger/tool_0.cfg` | `T0`, `extruder`, `tool_probe T0`, `T0_sensor`, and private CAN identity |
| `klipper-toolchanger/tool_1.cfg` | `T1`, `extruder1`, `tool_probe T1`, `T1_sensor`, and private CAN identity |
| `macros.cfg` | Printer `PAUSE`/`RESUME`, legacy fallback macros, liftbar/tool-change behavior, and Discord calls |
| `brush_bucket.cfg` | `BUCKET_PURGE`, `BUCKET_PARK`, `SILICONE_PARK`, and `_TOOL_PURGE` |
| `moonraker.conf` | Printer-owned Discord notifier definitions containing live private URLs |

The example should copy only the assumptions needed to integrate the extension. It
should not copy the complete printer repository or reproduce hardware pin assignments,
dock coordinates, CAN identities, notifier URLs, or unrelated printer macros.

### Existing Ownership Conflicts Must Be Removed

The representative printer already has a separate fallback implementation:

- `[gcode_macro REMAP_TOOL]`;
- `[gcode_macro BACKUP_SPOOL]`;
- `[gcode_macro _TOOL_RUNOUT]`;
- `T0` / `T1` macro variables and branches for the legacy remap mechanism; and
- both sensor sections call `_TOOL_RUNOUT`.

The extension also registers `REMAP_TOOL` and owns logical routing and fallback. Leaving
both implementations enabled risks duplicate command registration and two independent
owners of runout, routing, pause/resume, and physical selection.

The bundle must therefore show the complete migration:

1. remove or rename the legacy `REMAP_TOOL`, `BACKUP_SPOOL`, and `_TOOL_RUNOUT` macros;
2. simplify the physical `T0` / `T1` handlers so they remain direct MadMax
   `SELECT_TOOL T=0/1` handlers for the extension to capture at `klippy:ready`;
3. replace each active sensor hook with exactly one extension hook;
4. leave disabled `T2` through `T6` untouched and out of the extension sections; and
5. provide exact rollback instructions restoring the prior macros and hooks.

### Sensor Hook Adaptation

The current Trident sensors use `pause_on_runout: False`. The extension documentation
describes `TOOL_FALLBACK_RUNOUT TOOL=Tn PAUSE_OWNED=1` for a hook whose standard sensor
pause owns the pause. The representative bundle must make one internally consistent
choice.

Recommended representative choice:

```ini
[filament_switch_sensor T0_sensor]
pause_on_runout: True
runout_gcode:
  TOOL_FALLBACK_RUNOUT TOOL=T0 PAUSE_OWNED=1
insert_gcode:
  TOOL_FALLBACK_INSERT TOOL=T0
```

Repeat for `T1`. This removes the old macro as fallback owner and makes pause ownership
explicit. The adaptation guide must tell operators to verify their own pause behavior
and not blindly copy `PAUSE_OWNED=1`.

### Adapter Shapes

The extension configuration should bind directly to the representative ownership
boundaries:

```ini
[tool_fallback]
state_path: ~/printer_data/config/tool_fallback_state.json
pause_gcode: PAUSE
resume_gcode: RESUME
purge_gcode: _TOOL_FALLBACK_TRIDENT_PURGE
notify_gcode: _TOOL_FALLBACK_TRIDENT_NOTIFY

[tool_fallback T0]
filament_sensor: filament_switch_sensor T0_sensor
heater: extruder
backups: T1

[tool_fallback T1]
filament_sensor: filament_switch_sensor T1_sensor
heater: extruder1
backups: T0
```

`_TOOL_FALLBACK_TRIDENT_PURGE TOOL=Tn` should validate that `Tn` is the selected
physical tool, then delegate to the printer-owned bucket purge flow. It must remain
distinct from public `PURGE_TOOL` and must not implement routing or persistence.

`_TOOL_FALLBACK_TRIDENT_NOTIFY` should accept only the extension's fixed canonical
fields and call the printer-owned Moonraker `notify` remote method with notifier name
`discord`. The notifier URL remains in private Moonraker configuration and must never
appear in this repository.

The Trident `RESUME` macro performs bucket parking, cleaning, silicone parking, and
position restoration. The runbook must treat those as real motion and inspect their
preconditions before every owned or guarded resume.

## Recommended Example Package

Create one dedicated surface, rather than scattering fragments through the root README:

```text
examples/
  trident/
    README.md
    tool_fallback.cfg
    tool_fallback_macros.cfg
    sensor_hooks.cfg
    LIVE-UAT.md
    evidence/
      README.md
      phase6-live-log.md
tests/
  test_examples.py
README.md
```

`examples/trident/README.md` should contain:

- exact representative revision and bounded-compatibility statement;
- topology and ownership table;
- copied/adapted assumptions versus values every operator must verify;
- installation and complete legacy-owner removal;
- rollback;
- adapter and sensor-hook explanations;
- staged commissioning order;
- live-UAT prerequisites and stop conditions;
- Trident-specific hazards; and
- links to `LIVE-UAT.md` and evidence.

Keep machine-specific facts such as `extruder` / `extruder1`, active tool names, MadMax,
liftbar, bucket, silicone park, and notifier name because they define this example.
Replace or omit serial numbers, CAN UUIDs, webhook URLs, tokens, API keys, exact private
delivery details, and unrelated hardware configuration.

## Safe Controlled Simulation Architecture

### General Rules

Every live row should have a preflight, one bounded action, immediate observations, and
explicit cleanup. Required global stop conditions:

- unexpected X/Y/Z or liftbar motion;
- unexpected tool attachment/detachment state;
- heater target or temperature outside the stated row;
- purge or extrusion outside the cleared bucket;
- missing pause at a fail-closed checkpoint;
- unexpected automatic resume;
- duplicate or malformed notification; or
- state/mapping/backup change outside the row.

Use a harmless virtual-SD UAT sentinel print that reaches a deliberate paused state with
no model extrusion. This gives `print_stats` an active paused context without consuming
filament or requiring a real print. Its pause macro still moves to the Trident's
silicone/bucket area, so commissioning and clearance checks remain mandatory.

Before every mutating scenario capture:

- extension and representative-config revisions;
- Klipper, Moonraker, and toolchanger revisions;
- active `T0`/`T1` topology and selected tool;
- sensor state, heater targets, mappings, backup policy, purge flags, workflow, and
  backup queue;
- clear bed/docks/bucket, attached tool, liftbar state, homing, and operator presence.

After each scenario restore reciprocal backups, identity mappings, normal heater targets,
normal sensor enablement, and no active workflow/queue. Do not rely on restart as cleanup.

### Scenario Mechanisms

| Area | Safe mechanism | What it proves | Important boundary |
|---|---|---|---|
| Routing | From a staged safe state, select logical `T0`, then use extension remap/restore commands with both docks clear | Logical handler capture, physical selection, mapping publication, restore, and MadMax/liftbar integration | Real tool motion occurs; run only after ordinary toolchange commissioning |
| Sensor | Verify adapted `T0_sensor` / `T1_sensor` hooks and use explicit extension runout/insert commands as simulated inputs | One extension owner receives canonical tool identity and records sensor/workflow behavior | Do not physically remove filament; do not claim electrical sensor-fault coverage |
| Heater | Use a low, operator-approved non-extruding source target and observe source shutdown plus destination target transfer | Independent heater ownership and transfer ordering | Never disable Klipper heater safety or inject faults |
| Purge | Run `PURGE_TOOL` only with selected loaded tool, cleared bucket, safe temperature, and supervised normal purge path | Adapter reaches the Trident-owned bucket flow and durable purge state follows success | This is controlled normal hardware operation, not a destructive failure simulation |
| Fallback | Mark backup loaded, establish reciprocal policy, optionally pre-mark backup purged, then issue `TOOL_FALLBACK_RUNOUT TOOL=T0 PAUSE_OWNED=1` from the staged paused sentinel print | Simulated runout drives heater transfer, one physical selection, mapping, owned resume, and final notification | The current runtime treats this explicit owned command as authoritative even if the live sensor still reads loaded; label it only as simulated command input |
| Guarded resume | Temporarily use a documented short `heating_timeout`, select a target requiring safe warm-up, simulate owned runout, observe `heating_timeout`, then invoke `RESUME` only after readiness | Ordinary resume is guarded; later continuation completes only when ready | Configuration restart may be setup but is not evidence for any excluded Phase 1 scenario |
| Notification | Use the real printer-owned adapter and capture sanitized Klipper/Moonraker receipt plus terminal event fields | Fixed payload and one attempt at the representative adapter boundary | Do not promise Discord delivery; redact notifier destination and private IDs |
| Backup mutation | Exercise immediate set/restore, then submit a mutation while the guarded-resume checkpoint is active and observe queue/drain after terminalization | Immediate atomic policy, queue position, future-only behavior, FIFO drain, and final policy | Restore reciprocal defaults during cleanup; do not claim restart persistence UAT |

The authoritative explicit-runout path is especially useful for Phase 6 because it avoids
physical runout and destructive fault injection. It also means the runbook must protect
the command: it should be visibly labeled simulation-only, issued only after all
preconditions are recorded, and never presented as proof that a physical sensor changed.

### Staging Order

Plan the live execution in increasing-risk order:

1. offline example-contract and redaction checks;
2. visual/preflight inspection and normal MadMax `T0`/`T1` toolchanges;
3. notification adapter receipt with no fallback;
4. immediate backup mutation and cleanup;
5. sensor-hook command simulation outside automatic fallback;
6. controlled heater transfer and purge adapter checks;
7. paused sentinel-print fallback with backup already marked purged;
8. guarded-resume checkpoint plus queued backup mutation; and
9. final cleanup/audit.

Do not combine the first real fallback, first purge, first notification, first liftbar
movement, and first guarded resume into one row.

## Evidence Architecture

Commit a Markdown matrix whose claims remain understandable without external media.
Recommended columns:

| Field | Purpose |
|---|---|
| ID / requirement | Stable reference such as `UAT-ROUTE-01`; maps to `EXAMPLE-01` or `UAT-01` |
| Evidence class | `automated-contract`, `simulated-input/live-output`, or `normal-live-operation` |
| Claim | One bounded claim, not a broad compatibility statement |
| Topology / revisions | Trident topology plus exact extension, Trident, Klipper, Moonraker, and toolchanger revisions |
| Preconditions | Selected tool, print state, sensors, targets, mappings, backup policy, purge flags, clearances |
| Procedure | Exact bounded commands/actions |
| Expected | Observable result and stop conditions |
| Observed | What actually occurred |
| Result | `PASS`, `FAIL`, `BLOCKED`, or `NOT RUN` |
| Evidence | Concise committed log excerpt IDs and optional supplementary media link |
| Cleanup | Restoration performed and verified |

Use `examples/trident/evidence/phase6-live-log.md` for concise curated excerpts. Each
excerpt should include timestamp, row ID, command/event order, and enough surrounding
context to audit the claim. Replace secrets and machine identifiers with stable labels
such as `<TRIDENT_MAIN_MCU>`, `<T0_CAN_UUID>`, and `<DISCORD_DESTINATION>`, and include a
redaction legend.

Never commit complete `klippy.log`, `moonraker.log`, printer configuration, state file,
or command history without review. The representative clone contains live Discord
webhook URLs, a Telegram bot token, an Obico token, CAN UUIDs, and serial identifiers.
Contract tests should reject common secret forms, but human review remains required.

The matrix must include a prominent scope statement:

> These results are bounded to the listed representative Trident topology and revisions.
> They are not a universal compatibility claim.

It must also include the four excluded Phase 1 UAT scenarios with status `EXCLUDED -
NOT EXECUTED / NOT CREDITED`.

## Example Contract Testing

Phase 7 will place example-contract checks in clean-checkout CI, but Phase 6 should
create the checks with the example so the bundle cannot drift before then.

Add `tests/test_examples.py` with deterministic repository-level checks:

- required example files and README links exist;
- the example declares only `T0` and `T1`;
- reciprocal defaults are exactly `T0 -> T1` and `T1 -> T0`;
- heaters are `extruder` and `extruder1`;
- sensor hooks name canonical tools and invoke one extension owner;
- `purge_gcode` and `notify_gcode` point to distinct private adapters;
- legacy `REMAP_TOOL`, `BACKUP_SPOOL`, and `_TOOL_RUNOUT` definitions are absent from
  the shipped bundle;
- adapter macros do not invoke extension public commands recursively;
- installation, rollback, ownership, commissioning, hazards, adaptation, and evidence
  sections exist;
- the evidence matrix has the required fields, bounded-claim statement, and all four
  exclusions;
- no obvious Discord webhook, token, API key, CAN UUID, serial-by-id, or private URL
  pattern appears under `examples/trident`.

Use structured or narrowly scoped parsing for the small `.cfg` contract rather than one
large snapshot. These tests can prove internal consistency and redaction properties;
they cannot prove that Jinja macros load in arbitrary Klipper versions or that hardware
motion is safe.

## Likely Files And Tasks

### Plan 06-01: Representative Bundle And Adaptation Guide

Likely files:

- `examples/trident/README.md`
- `examples/trident/tool_fallback.cfg`
- `examples/trident/tool_fallback_macros.cfg`
- `examples/trident/sensor_hooks.cfg`
- `README.md`

Tasks:

1. Build the complete redacted T0/T1 configuration and printer-owned adapters.
2. Document legacy ownership removal, installation, rollback, commissioning, hazards,
   and operator-verified values.
3. Link the bundle from the root README without implying universal compatibility.

### Plan 06-02: Contract Checks And Live-UAT Runbook

Likely files:

- `tests/test_examples.py`
- `examples/trident/LIVE-UAT.md`
- `examples/trident/evidence/README.md`
- `examples/trident/evidence/phase6-live-log.md`

Tasks:

1. Add deterministic example structure, consistency, recursion, exclusion, and redaction
   checks.
2. Write the staged reversible procedure, stop conditions, cleanup, evidence matrix, and
   redaction legend.
3. Seed every live row as `NOT RUN`; do not manufacture observations.

### Plan 06-03: Supervised Representative Execution And Evidence Finalization

Likely files:

- `examples/trident/LIVE-UAT.md`
- `examples/trident/evidence/phase6-live-log.md`
- possibly a phase verification artifact under `.planning/phases/06-examples-and-live-integration/`

Tasks:

1. Bind the run to exact current revisions and complete preflight.
2. Execute rows in staged order with operator supervision and immediate cleanup.
3. Record observed results and curated redacted excerpts, leaving blocked/unrun rows
   explicit.
4. Audit that no secret, universal claim, destructive scenario, or excluded Phase 1
   claim entered committed evidence.

Plan 06-03 has a genuine human/hardware gate. Planning should not mark `UAT-01`
complete merely because the runbook and empty matrix exist.

## Risks And Planning Constraints

### Hardware Safety

- MadMax docking and liftbar motion are real; wrong dock/liftbar state can collide.
- `PAUSE` and `RESUME` invoke bucket/silicone motion and position restoration.
- The bucket occupies the rear-left area; the representative config warns that the
  left-rear `130x35mm` bed area is unusable.
- `BUCKET_PURGE` can extrude a large configured amount and heat to its minimum purge
  temperature.
- Toolchanger crash detection behavior changes depending on print state.
- The UAT must stop rather than improvise after unexpected motion or attachment state.

### Evidence And Secret Safety

- The representative clone contains active private credentials and identifiers.
- Log excerpts may expose paths, URLs, MCU IDs, notifier destinations, or unrelated
  operator data.
- Redaction tests catch common patterns only; require a final manual secret review of
  `git diff`.
- Do not paste private source configuration into the example or evidence.

### Contract Accuracy

- A command-simulated runout proves the extension's explicit input path and live output,
  not a physical sensor transition.
- A returned notification adapter call proves an attempt at the Moonraker boundary, not
  downstream Discord delivery.
- A short-timeout guarded-resume scenario proves behavior under that recorded temporary
  configuration only.
- Example-contract tests prove repository consistency, not universal loadability or
  hardware compatibility.

## Validation Architecture

### Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest plus supervised representative-printer runbook |
| Quick automated command | `pytest -q tests/test_examples.py` |
| Focused regression command | `pytest -q tests/test_examples.py tests/test_tool_fallback_config.py tests/test_tool_fallback_notifications.py` |
| Full automated command | `python3 -m py_compile klippy/extras/tool_fallback*.py && pytest -q && git diff --check` |
| Manual artifact | `examples/trident/LIVE-UAT.md` and curated evidence log |

### Per-Task Verification Map

| Planned task | Requirement | Verification |
|---|---|---|
| Complete T0/T1 bundle | EXAMPLE-01 | Example contract tests assert topology, reciprocal backups, adapters, hooks, and no legacy owner |
| Adaptation/rollback/hazards guide | EXAMPLE-01 | Contract tests assert required sections; manual review checks Trident accuracy |
| Redaction controls | EXAMPLE-01, UAT-01 | Secret-pattern tests plus mandatory human `git diff` review |
| Runbook and evidence schema | UAT-01 | Contract tests assert matrix fields, bounded claim, evidence classes, and four exclusions |
| Routing/sensor/heater/purge rows | UAT-01 | Supervised live execution with preflight, expected/observed result, excerpt, and cleanup |
| Fallback/guarded-resume/notification/backup rows | UAT-01 | Supervised simulated-input/live-output execution and terminal-state audit |
| Final evidence audit | EXAMPLE-01, UAT-01 | Full pytest, syntax check, diff check, secret review, and manual claim-to-evidence review |

### Manual-Only Verifications

| Behavior | Why manual |
|---|---|
| MadMax/liftbar tool selection and restore | Requires representative physical topology and collision supervision |
| Real heater target transfer | Requires live independent heaters while preserving Klipper safety |
| Bucket/silicone purge and resume motion | Requires clearances, loaded filament, and direct observation |
| Complete simulated-runout fallback | Requires live printer state, toolchanger motion, heaters, and pause ownership |
| Guarded resume with queued mutation | Requires a live recoverable checkpoint and operator-timed continuation |
| Moonraker notifier receipt | Requires the representative printer-owned adapter and private notifier configuration |

### Validation Rules

- No live row passes without observed result, concise committed evidence, and cleanup.
- `NOT RUN`, `BLOCKED`, and `FAIL` remain honest outcomes and cannot be converted to
  automated-contract evidence.
- External media is supplementary only.
- No evidence row may credit the four excluded Phase 1 scenarios.
- Final verification must distinguish automated contract checks, simulated-input live
  behavior, and normal live hardware operation.

## Planning Recommendations

1. Split implementation, contract/runbook creation, and live execution into separate
   plans; the final plan must retain a real supervised hardware gate.
2. Treat removal of the Trident's legacy fallback macros as a first-class ownership
   migration with exact rollback, not an incidental edit.
3. Use the runtime's explicit owned runout command as the bounded simulated-runout input,
   while clearly stating that it does not prove a physical sensor transition.
4. Stage purge, motion, notification, fallback, guarded resume, and queued mutation so
   the first exercise of each is independently observable and reversible.
5. Add example-contract and secret-pattern tests in Phase 6 so Phase 7 can adopt settled
   checks rather than inventing them.
6. Commit only curated redacted excerpts and a complete matrix; never commit raw printer
   configs/logs or claim universal compatibility.
7. Preserve the explicit exclusion of all four Phase 1 UAT scenarios in the guide,
   runbook, matrix, and final verification.

## RESEARCH COMPLETE

Phase 6 can be planned well as three bounded plans: create the complete redacted T0/T1
Trident bundle and ownership migration, create deterministic example contracts plus a
staged evidence runbook, then execute the supervised representative-printer rows and
commit only auditable redacted evidence. The highest-risk planning issues are legacy
fallback ownership conflicts, real MadMax/liftbar/bucket motion hidden behind adapters,
credential leakage from the representative clone, and overstating what simulated
runout, notifier receipt, or one representative printer proves.
