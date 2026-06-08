# Phase 4: Automatic Fallback Workflow - Pattern Mapping

**Mapped:** 2026-06-08
**Status:** Complete

## Scope And Architectural Boundary

Phase 4 composes the verified routing, sensor, purge, and persistence primitives into a
runtime-only fallback coordinator. Preserve the existing ownership split:

- `tool_fallback_config.py` normalizes static heater and timeout configuration.
- `tool_fallback_state.py` remains the immutable durable authority for tools, mappings,
  backup order, loaded state, purge state, and failed state.
- `tool_fallback.py` owns runtime checkpoints, pause ownership, heater objects, reactor
  timers, physical selection, purge execution, persistence ordering, and guarded resume.
- `tests/conftest.py` supplies deterministic Klipper adapters and time control.
- focused pytest modules prove pure graph resolution separately from workflow ordering
  and failure containment.

Do not persist an in-flight fallback checkpoint. A Klipper restart cannot safely resume
an interrupted print or infer the machine's physical tool state. Runtime checkpoint
status may expose only JSON-safe values, never timer handles, heater objects, saved
handlers, callables, or exceptions.

## Existing Patterns To Preserve

### Immutable candidates, save before publish

Closest analogs:

- `FallbackState.with_failed_runout()`, `with_mapping()`, and tool replacement helpers
  in `klippy/extras/tool_fallback_state.py`
- `ToolFallback._persist_state()` and `_merge_mapping_candidate()` in
  `klippy/extras/tool_fallback.py`
- persistence failure tests in `test_tool_fallback_state.py`,
  `test_tool_fallback_routing.py`, and `test_tool_fallback_purge.py`

Concrete guidance:

- Resolve backup eligibility from one immutable `FallbackState` snapshot.
- Keep graph traversal pure. It must not select tools, alter heaters, persist state, or
  mutate the extension.
- Persist the confirmed failed-runout candidate before beginning fallback actions.
- Persist the new logical mapping only after selection, heating, and conditional purge
  succeed.
- Rebuild the final mapping candidate from current canonical state so a successful purge
  persistence is not overwritten by an older snapshot.

### Publish runtime ownership only after physical success

Closest analogs:

- `_select_physical()` invokes a captured handler and publishes
  `_selected_physical_tool` only after return.
- `_transition_active_route()` contains failures and preserves pause state.
- conditional purge publishes `_active_logical_tool` only after its workflow completes.

Concrete guidance:

- Continue invoking captured physical handlers directly with synthetic canonical `Tn`
  commands. Never redispatch public logical `Tn` handlers.
- A physical selection exception or post-return timeout ends fallback immediately.
- Never automatically select a second backup after a physical selection attempt. The
  machine may have a partially docked or obstructing tool.
- Automatic fallback must not physically roll back to the failed original tool after
  selection, purge, or mapping persistence failure. The original tool is unloaded and
  selecting it may be unsafe.

### Explicit pause ownership

Closest analogs:

- `_transition_active_route()` local `owns_pause`
- `_select_and_conditionally_purge()` pause/resume ordering
- sensor outage acknowledgement in `_handle_selected_sensor_outage()`

Concrete guidance:

- Extend `TOOL_FALLBACK_RUNOUT` with strict `PAUSE_OWNED=0|1` parsing.
- Accept ownership only when the hook tool is selected, the runout context was active,
  and print state is paused at hook time.
- Keep pending runout ownership outside `SensorRuntime.pending_runout_context`, because
  that flag is cleared/replaced when the reading reverses during debounce.
- User-owned pauses may receive state updates and reports but never automatic resume.
- Only an explicitly owned transient recovery or completed fallback may resume.

### Reactor generation/deadline checks

Closest analogs:

- `SensorRuntime.debounce_generation`, `debounce_deadline`, and
  `_sensor_debounce_handler()`
- deterministic `FakeReactor` stable ordering and explicit advancement

Concrete guidance:

- Use reactor timers for asynchronous heating checks and deadlines.
- Validate checkpoint identity/generation and expected stage in every timer callback so
  stale callbacks cannot continue a replacement or blocked workflow.
- Clear or reschedule timers explicitly when stages change.
- Do not use sleeps or `set_temperature(..., wait=True)`; both prevent recoverable
  checkpoint behavior.

## Required Data Flows

### Explicit runout ownership and transient recovery

```text
standard sensor pauses print
  -> TOOL_FALLBACK_RUNOUT TOOL=Tn PAUSE_OWNED=1
  -> validate selected tool + active context + currently paused
  -> create pending-runout checkpoint
  -> existing symmetric unloaded debounce
     -> confirmed loaded first: persist insertion/reconciliation
        -> clear checkpoint
        -> resume only if explicitly owned
     -> confirmed unloaded first: persist failed-runout state
        -> advance checkpoint into automatic fallback
```

A second fallback-affecting event must not replace an active checkpoint. Reject or
report the conflict while preserving the original workflow.

### Pure backup graph resolution

```text
failed physical tool + immutable state snapshot
  -> depth-first traversal in persisted backup order
  -> path-local ancestry detects loops
  -> scan-local evaluated set prevents duplicate work
  -> loaded=true and failed=false returns eligible candidate
  -> failed/unloaded intermediary remains traversable
  -> exhausted first scan
  -> take one fresh canonical snapshot and scan once more
  -> return candidate or categorized exhaustion report
```

Sensor authority does not change eligibility. Persisted `loaded=true` is sufficient;
selection of an unknown-authority candidate emits the existing warning.

### Complete automatic fallback

```text
confirmed failed runout already persisted
  -> identify active logical route for failed selected physical tool
  -> capture finite failed-heater target > 0
  -> turn off failed heater
  -> resolve candidate, with one re-scan only on exhaustion
  -> set backup target without waiting
  -> invoke physical selection once
  -> asynchronously wait for heater readiness/deadline
  -> conditionally purge through existing internal purge authority
  -> merge and persist logical remap from current canonical state
  -> clear checkpoint
  -> resume only if explicitly owned
```

Every incomplete branch leaves a visible checkpoint and the print paused. Missing
logical ownership, invalid target, heater errors, exhaustion, selection failure,
heating timeout, purge failure, persistence failure, or resume failure must never
silently clear the workflow.

### Guarded heating-timeout resume

```text
public RESUME
  -> no checkpoint: delegate to original RESUME behavior
  -> active/incomplete non-heating checkpoint: reject and remain paused
  -> heating-timeout checkpoint:
       re-read selected backup heater
       still busy/not ready: reject and remain paused
       ready: advance to purge/persist/owned completion
```

Normal `RESUME` is not a general fallback cancellation mechanism. Only the
`heating_timeout` checkpoint may use it as continuation.

## Likely Files And Concrete Patterns

### `klippy/extras/tool_fallback.py`

**Role:** Runtime fallback coordinator and all Klipper integration.

**Likely changes:**

- Add a private runtime checkpoint dataclass with fields such as source, stage,
  generation, logical tool, failed/current physical tool, requested backup, explicit
  pause ownership, transferred target, stage deadline, graph report, and failure reason.
- Add a pure resolver helper/dataclass near the runtime records, or a small private
  module if isolation materially improves testing.
- Resolve configured heater objects at ready time and retain them runtime-only.
- Extend runout hooks to establish explicit pause ownership and preserve pending
  transient context across reading reversal.
- Start fallback only after existing debounce persists confirmed failed state.
- Add heater target capture/shutdown, preheat, asynchronous readiness polling, and
  timeout checkpoint behavior.
- Guard public `RESUME` while a fallback checkpoint is active.
- Refactor active route transitions to reuse temperature/select/heat/purge/persist
  stages where applicable, completing ROUTE-05.
- Extend `get_status()` with a deterministic JSON-safe workflow snapshot.

**Closest analogs:**

- `SensorRuntime` for a bounded runtime-only record
- `_sensor_debounce_handler()` for generation/deadline timer validation
- `_capture_physical_handlers()` for transactional command-handler capture
- `_transition_active_route()` for pause ownership and stage ordering
- `_run_pre_selection_transition_stages()` as the explicit temperature-transfer hook
- `_run_post_selection_transition_stages()` and `_purge_physical_tool()` for purge
  authority
- `_merge_mapping_candidate()` and `_persist_state()` for current-state persistence

**Pattern guidance:**

- Keep `_transition_active` for synchronous active-route exclusion, and add a separate
  workflow checkpoint that survives recoverable or blocked failures.
- Do not route ordinary slicer `Tn` commands through temperature transfer. ROUTE-05
  applies to active mapping transitions; automatic fallback has its own coordinator.
- Resolve a configured heater through the `heaters` object at ready. A configured
  missing heater is a startup configuration error because fallback cannot safely run.
- Read target with `heater.get_temp(eventtime)` or the narrow adapter chosen for the
  installed Klipper API. Reject missing, non-finite, or non-positive targets.
- Turn off the failed heater before graph resolution or backup selection. Do not weaken
  verify-heater behavior or catch/suppress Klipper shutdown errors as success.
- Start backup heating with `set_temperature(..., wait=False)` before physical
  selection, then use `heater.check_busy(eventtime)` from a reactor timer.
- On selection failure, stop immediately. Turning off the newly preheated backup is
  reasonable if it can be done without hiding the original selection error, but never
  attempt another physical selection.
- On automatic-fallback persistence failure after physical changes, remain paused and
  report canonical/physical mismatch. Do not use the manual transition's physical
  rollback behavior.

### Resume-wrapper recursion constraint

Guarding normal `RESUME` introduces a command-interception hazard analogous to, but
stricter than, `Tn` interception:

- Capture the original public `RESUME` handler transactionally before installing a
  wrapper, and restore it if later ready initialization fails.
- When no checkpoint blocks resume, the wrapper must delegate directly to the saved
  original handler with an appropriate synthetic/preserved G-code command.
- Extension-owned resume must not call public wrapped `RESUME` recursively.
- If `resume_gcode` is configurable and may itself invoke `RESUME`, use a tightly scoped
  internal-resume permit that lets the wrapper delegate once to the saved handler.
- Clear any permit in `finally`; never leave a global bypass enabled after adapter
  failure.
- Reject reentrant or user-issued resume while fallback stages are active. A generic
  boolean that allows every nested resume is too broad.

Tests must prove ordinary resume delegation, owned resume, custom adapter-to-`RESUME`
delegation, recursion absence, guard rejection, and restoration after ready failure.

### Synchronous selection and purge timeout constraint

Captured physical handlers and `run_script_from_command()` purge adapters execute
synchronously in the G-code thread. A reactor timer cannot safely interrupt arbitrary
mechanical G-code midway.

Concrete guidance:

- Record monotonic start/deadline before invoking selection or purge exactly once.
- Fail immediately on adapter exception.
- After successful return, compare monotonic elapsed time to the configured timeout and
  fail closed on overrun.
- Never claim that the extension cancels a running selection or purge macro.
- Never retry or select another backup after exception or overrun.
- Preserve the blocked checkpoint and remain paused.

Heating is different: it is asynchronous and supports a real enforceable reactor
deadline.

### Heater safety constraint

- Treat Klipper's heater objects and verification as authoritative.
- Never manually bypass heater checks, synthesize a guessed target, or continue on an
  invalid/zero failed-tool target.
- Never replace a Klipper heater error with workflow success.
- Heating timeout is a workflow warning/checkpoint, not a heater-safety shutdown.
- On guarded `RESUME`, re-read readiness; do not trust a stale timer observation.

### `klippy/extras/tool_fallback_state.py`

**Role:** Existing durable graph and mapping authority.

**Likely changes:** None required for the in-flight workflow. A small pure graph-result
type belongs outside persisted schema.

**Closest analogs:**

- `ToolState.backups` persisted tuple order
- `with_failed_runout()` for confirmed failure
- `with_mapping()` for final logical remap

**Pattern guidance:**

- Do not add checkpoint, target temperature, pause ownership, timer, stage, or heater
  fields to schema v1.
- Resolver reads `state.tools[tool].backups`, `loaded`, and `failed` only.
- Preserve state immutability and exact mapping no-op behavior.

### `klippy/extras/tool_fallback_config.py`

**Role:** Existing normalized heater names and positive finite stage timeouts.

**Likely changes:** Usually none. Existing `ToolConfig.heater` and global
`selection_timeout`, `heating_timeout`, and `purge_timeout` already provide the Phase 4
contract.

**Closest analogs:**

- `_positive_finite_float()` for strict timing validation
- `_purge_adapter()` for recursion prevention at configuration time

**Pattern guidance:**

- Do not add a guessed fallback temperature.
- If resume interception requires validating an adapter command token, follow the
  token-based recursion guard style used by `_purge_adapter()`.

### `tests/conftest.py`

**Role:** Deterministic heaters, elapsed-time adapters, handler capture, and workflow
event ordering.

**Likely changes:**

- Add `FakeHeater` with mutable measured/target values, `get_temp()`,
  `get_status()`, `check_busy()`, injected errors, and call recording.
- Add `FakeHeaters` manager with `lookup_heater()` and `set_temperature(..., wait=False)`.
- Let fake scripts and physical handlers advance reactor monotonic time to prove
  post-return selection/purge overruns.
- Preserve original/public resume handler behavior so wrapper delegation and recursion
  can be observed.
- Add workflow event recording across heater target changes, selection, purge,
  persistence, and resume.

**Closest analogs:**

- `FakeReactor.advance()` for deterministic asynchronous deadlines
- `FakeGCode.script_events` and `inject_script_failure()`
- `FakeFilamentSensor` mutable status/error injection
- physical-handler spies in `test_tool_fallback_routing.py`

**Pattern guidance:**

- Keep heater readiness explicit and deterministic; never use wall-clock sleeps.
- Model only the Klipper heater methods production code calls.
- Distinguish heater workflow timeout from injected heater safety/error behavior.

### `tests/test_tool_fallback_fallback.py` (new)

**Role:** Focused Phase 4 resolver, ownership, checkpoint, timeout, and complete workflow
proof.

**Required coverage:**

- Explicit ownership validation and user-pause preservation.
- Transient runout resumes only after confirmed reinsertion and only when owned.
- DFS priority, failed/unloaded intermediary traversal, path-local loops, duplicate
  suppression, unknown-authority eligibility, one fresh re-scan, and categorized
  exhaustion.
- JSON-safe runtime checkpoint and conflicting workflow rejection.
- Invalid/zero target rejection and failed-heater shutdown ordering.
- Backup preheat before selection, then asynchronous wait before purge.
- Real heating deadline and guarded `RESUME` continuation/rejection.
- Selection/purge exceptions and post-return overruns without cancellation claims.
- Full success ordering through mapping persistence and owned resume.
- No automatic physical rollback and no second candidate after physical-stage failure.
- Persistence/resume failure leaves paused checkpoint/status.
- Resume-wrapper recursion and saved-handler delegation.

### `tests/test_tool_fallback_routing.py`

**Role:** ROUTE-05 completion and routing regression proof.

**Likely changes:**

- Update active route ordering expectations to include temperature capture, failed/current
  heater shutdown, requested-tool preheat, selection, heating readiness, purge,
  persistence, and owned resume.
- Prove already-paused active transitions never resume.
- Prove manual active-transition rollback behavior remains intentionally distinct from
  automatic fallback no-rollback behavior.
- Preserve ordinary logical selection, inactive remap, handler capture, and recursion
  regression coverage.

### `tests/test_tool_fallback_sensor.py` and `tests/test_tool_fallback_purge.py`

**Role:** Regression coverage for the Phase 3 primitives that Phase 4 composes.

**Likely changes:**

- Update runout hook tests for strict `PAUSE_OWNED` semantics and checkpoint creation.
- Preserve debounce proof that fallback cannot begin before confirmed runout.
- Preserve purge authority, recursion prevention, save-before-publish, and conditional
  purge behavior.

## No-Rollback Boundary

Manual active-route transitions currently attempt physical rollback when mapping
persistence fails. Automatic fallback must not reuse that behavior:

- the original failed tool is confirmed unloaded and marked failed;
- physical state after a fallback selection may be uncertain;
- another automatic toolchange could cause damage;
- route truth may remain stale if persistence fails, but that mismatch is safer than an
  automatic mechanical rollback.

Use source-aware stage execution or separate completion policies so shared helpers do
not accidentally apply manual rollback to automatic fallback. Tests should assert zero
additional physical handler calls after any automatic fallback selection, purge, or
persistence failure.

## Recommended Implementation Order

1. Add Wave 0 fakes and `test_tool_fallback_fallback.py`.
2. Add explicit pending-runout ownership, pure DFS resolver, and JSON-safe checkpoint.
3. Add ready-time heater resolution, target transfer, preheat, asynchronous wait, and
   guarded resume interception.
4. Compose the complete automatic fallback workflow with purge and final mapping
   persistence.
5. Refactor active manual transitions onto shared safe stages while preserving their
   distinct rollback policy.
6. Run focused Phase 4 tests, routing/sensor/purge regressions, compilation, full suite,
   and `git diff --check`.

## Scope Guards

- Do not add meaningful external notification adapters or example configuration; those
  remain Phase 5.
- Do not claim synchronous G-code cancellation.
- Do not persist runtime checkpoints.
- Do not infer pause ownership from timing alone.
- Do not guess heater targets or weaken Klipper heater safety.
- Do not automatically select another tool or roll back after a physical fallback
  attempt.
- Keep real-printer UAT deferred to Phase 5 per user direction.

---
*Phase: 04-automatic-fallback-workflow*
*Mapped: 2026-06-08*
