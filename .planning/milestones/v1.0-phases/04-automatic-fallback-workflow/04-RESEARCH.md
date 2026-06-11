# Phase 4: Automatic Fallback Workflow - Research

**Researched:** 2026-06-08
**Status:** Complete

## Phase Boundary

Phase 4 should turn the verified Phase 3 runout, routing, and purge primitives into one
fail-closed automatic fallback coordinator:

- establish explicit ownership of the standard filament-sensor pause;
- distinguish transient runout from confirmed debounced failure;
- resolve persisted ordered backup graphs recursively and deterministically;
- capture and transfer heater targets without weakening Klipper heater safety;
- preheat before physical selection, then wait, conditionally purge, and persist the
  logical remap;
- enforce stage deadlines where Klipper's execution model permits them;
- intercept normal `RESUME` while fallback is active or blocked; and
- leave every incomplete workflow paused with useful runtime status.

Meaningful external notification adapters, example configuration, and live-printer UAT
remain Phase 5 work. Phase 4 may emit local `respond_info` warnings and errors needed
for safety and diagnosis.

## Requirement Interpretation

| Requirement | Phase 4 interpretation |
|-------------|------------------------|
| FALL-01 | Preserve standard `pause_on_runout: True` behavior. The extension records explicit ownership after the standard sensor pause; it does not replace immediate pause handling. |
| FALL-02 | A runout hook starts a pending debounce workflow, but backup traversal and heater actions begin only after the existing symmetric debounce confirms selected-tool active-print runout. |
| FALL-03 | A continuously confirmed reinsertion before runout confirmation is a transient recovery. Resume only when the explicit hook proves extension ownership; otherwise report recovery and preserve the user pause. |
| FALL-04 | Use deterministic depth-first traversal of persisted ordered backup graphs, with loop detection, failed-intermediary traversal, categorized skips, and one fresh full re-scan before exhaustion. |
| FALL-05 | A candidate is eligible only when current canonical persisted state says `loaded=true` and `failed=false`. Sensor authority may be unknown; warn but trust the durable loaded fact. |
| FALL-06 | Confirmed fallback captures a valid failed-heater target, turns that heater off, resolves a backup, starts backup preheat, selects physically, waits for heat, conditionally purges, persists the logical mapping, and resumes only when owned. |
| FALL-07 | Heating uses a real reactor deadline. Selection and purge adapters are synchronous, so measure and reject overruns after return; arbitrary G-code cannot be safely preempted by this extension. |
| FALL-08 | Any error, timeout, invalid checkpoint, failed persistence, or incomplete stage leaves the print paused and blocks ordinary resume except guarded heating-timeout continuation. |
| ROUTE-05 completion | Active manual remap/restore/reset transitions reuse the same heater-transfer and guarded stage infrastructure, while retaining Phase 2/3 pause ownership, selection, purge, persistence, rollback, and no-resume guarantees. |

The Phase 4 context supersedes two older design details:

- persisted `loaded=true` is sufficient backup eligibility even when current sensor
  authority is unknown; and
- backup preheating starts before physical selection, to keep toolchanger tools on an
  ooze blocker longer.

## Existing Foundation And Required Refactoring

### Reusable behavior

`klippy/extras/tool_fallback.py` already provides:

- transactional capture of physical `Tn` handlers and recursion-free selection;
- `_active_logical_tool`, `_selected_physical_tool`, and `_transition_active`;
- canonical save-before-publish persistence;
- symmetric sensor debounce and confirmed-runout state mutation;
- graceful unknown sensor authority and durable loaded history;
- owned pause behavior for manual active-route transitions;
- conditional purge after selection and before mapping publication; and
- an explicit empty `_run_pre_selection_transition_stages()` Phase 4 hook.

`tool_fallback_state.py` already stores every durable fact needed for graph eligibility
and fallback remapping. Do not add runtime workflow stages, timers, pause ownership, or
heater readings to schema v1. A Klipper restart cannot resume the interrupted print, so
persisting an in-flight fallback checkpoint would create false recovery expectations.

### Refactoring required before orchestration

The current confirmed sensor-debounce callback directly persists a failed-runout
candidate and stops. It needs a narrow callback into a fallback coordinator after that
save succeeds. The sensor layer should remain responsible for deciding whether removal
was continuously confirmed; the workflow layer should own everything after confirmation.

The current active-route transition is synchronous and uses local `owns_pause`. Phase 4
needs shared stage helpers for temperature capture/shutdown, preheat, selection, heating
readiness, purge, persistence, and resume. Do not force ordinary slicer `Tn` selection
through fallback temperature transfer; ROUTE-05 applies to active mapping changes, not
normal mapped selection.

`_transition_active` is currently cleared in `finally`, including failed transitions.
Fallback needs a separate checkpoint/guard that remains visible after a recoverable
heating timeout or terminal blocked failure. Keep the existing flag for synchronous
route-transition exclusion, and add explicit fallback status rather than overloading it.

## Explicit Runout Pause Ownership

### Hook contract

Extend the public hook to require or accept a strict ownership parameter:

```text
TOOL_FALLBACK_RUNOUT TOOL=T0 PAUSE_OWNED=1
```

Klipper's standard `filament_switch_sensor` implementation calls
`pause_resume.send_pause_command()`, waits `pause_delay`, then executes a script whose
prefix is `PAUSE` before configured `runout_gcode`. Therefore a correctly configured
hook runs after the standard pause command in the same runout script.

Treat `PAUSE_OWNED=1` as an explicit integration assertion, but validate it against
runtime facts before accepting ownership:

- the tool is the selected physical tool;
- the job was active for this runout context; and
- the print is paused when the hook executes.

If any validation fails, record the runout event without ownership and never
auto-resume. Do not infer ownership merely because `print_stats` says `paused`.

### Pending debounce workflow

The existing `SensorRuntime.pending_runout_context` is not enough for transient
recovery because it is replaced when the observed target changes back to loaded.
Introduce a separate pending runout record or fallback checkpoint that survives the
unloaded-to-loaded debounce reversal:

```text
kind: pending_runout
tool: T0
logical_tool: T0 or None
pause_owned: bool
started_at: monotonic time
```

Only one fallback-affecting workflow may exist at a time. A second runout event while a
checkpoint is active should be reported and ignored or rejected without replacing the
first checkpoint.

### Transient recovery

When continuously loaded state is confirmed before continuously unloaded state was
confirmed:

1. clear the pending runout checkpoint;
2. preserve/commit the normal confirmed insertion state transition;
3. report transient recovery locally; and
4. invoke the configured resume adapter only if `pause_owned=true`.

If resume fails, keep a blocked checkpoint/status and remain paused. User-owned pauses
must only receive the recovery report.

## Backup Graph Resolution

Implement graph resolution as a pure deterministic helper over one immutable
`FallbackState` snapshot. Keep physical selection and state mutation outside the
resolver so graph behavior is cheaply unit tested.

### Depth-first ordered algorithm

For each direct backup in the failed tool's persisted order:

1. Detect a path-local loop before descending. Record the loop and continue with other
   reachable branches.
2. Inspect the candidate against the current snapshot.
3. If `loaded=true` and `failed=false`, return it immediately.
4. If ineligible, record the reason, but recursively traverse its own backup chain.
   This allows failed or unloaded intermediaries to lead to an eligible descendant.
5. Avoid duplicate evaluation within one scan while preserving deterministic reports.

Use path-local ancestry for loop reporting and a scan-local evaluated set for duplicate
work. Never reject a configured graph merely because it contains a cycle; startup
currently permits cross-tool cycles and runtime traversal must contain them safely.

### Fresh re-scan before exhaustion

If the first complete scan finds no eligible candidate, take a new canonical state
snapshot and run the complete traversal once more. This is not an automatic retry after
selection/heating/purge failure; it only gives tools that became loaded or non-failed
during graph search one final eligibility opportunity.

The exhausted report should categorize, at minimum:

- evaluated/attempted tools;
- unloaded tools;
- failed tools;
- loop edges or paths; and
- unknown-sensor eligible tools that would require a warning if selected.

Unknown sensor authority does not alter eligibility. A tool with persisted
`loaded=true` remains eligible and selection emits the existing unknown-authority
warning. A tool with persisted `loaded=false` remains ineligible until a sensor or
explicit load macro durably changes that fact.

## Heater Integration

### Klipper heater APIs

Klipper's `heaters` object exposes:

```python
heater = printer.lookup_object("heaters").lookup_heater(name)
temperature, target = heater.get_temp(eventtime)
status = heater.get_status(eventtime)  # temperature, target, power
printer.lookup_object("heaters").set_temperature(heater, target, wait=False)
heater.check_busy(eventtime)
```

Relevant upstream behavior:

- `set_temperature(..., wait=False)` registers a toolhead lookahead barrier, sets the
  target, and returns without bypassing heater verification.
- `heater.set_temp(0.0)` or `set_temperature(heater, 0.0)` turns a heater off.
- `check_busy(eventtime)` uses the configured control algorithm's readiness criteria.
- `set_temperature(..., wait=True)` blocks in a loop and has no project-specific
  timeout, so it is unsuitable for the recoverable Phase 4 checkpoint design.

Resolve each configured heater at ready time through `heaters.lookup_heater()`.
Unlike optional sensors, a configured but nonexistent heater prevents safe fallback and
should fail initialization with a clear tool/heater configuration error. Keep heater
objects runtime-only.

Sources:

- `https://github.com/Klipper3d/klipper/blob/master/klippy/extras/heaters.py`
- `https://github.com/Klipper3d/klipper/blob/master/klippy/extras/filament_switch_sensor.py`
- `https://github.com/Klipper3d/klipper/blob/master/klippy/extras/pause_resume.py`

### Target capture and shutdown

At confirmed runout:

1. read the failed tool's configured heater target at the current reactor time;
2. reject missing, non-finite, unavailable, or `<= 0` targets with a warning and a
   blocked paused checkpoint;
3. store the exact valid target in the runtime checkpoint; and
4. immediately set the failed heater target to zero.

Do not use measured temperature, the backup heater's existing target, or a guessed
default. If failed-heater shutdown itself errors, stop before selecting a backup.

### Preheat, selection, and wait

After resolving one eligible backup:

1. set the backup heater to the transferred target with `wait=False`;
2. record the heat deadline;
3. invoke the saved physical selection handler;
4. after selection succeeds, poll `heater.check_busy(eventtime)` from a reactor timer;
5. continue to purge only when the heater is no longer busy; and
6. on deadline expiry, keep the checkpoint at `heating_timeout`, warn, and remain
   paused.

Starting preheat before selection is intentional. A selection error stops immediately
and must not select another tool. The plan should decide whether to turn off the backup
heater after selection failure; fail-closed behavior favors turning it off when that
can be done without obscuring the original error, while never attempting another
physical change.

## Workflow Checkpoint And Stage Machine

Use one runtime-only dataclass or similarly explicit record, for example:

```text
kind/source                 automatic_fallback or active_route_transition
stage                       debouncing, resolving, preheating, selecting,
                            heating, heating_timeout, purging, persisting,
                            blocked, complete
logical_tool
failed/current physical
requested/backup physical
pause_owned
target_temperature
started_at / stage_deadline
attempted/skipped/loop report
failure_reason
```

Expose a JSON-safe checkpoint snapshot through `get_status()`. Timer handles, heater
objects, exceptions, and callables must not appear in status.

Recommended automatic fallback order:

1. hook establishes pending runout and ownership;
2. sensor debounce confirms runout and persists failed/unloaded/unpurged state;
3. capture valid target and turn off failed heater;
4. resolve backup graph, then re-scan once if exhausted;
5. begin backup preheat;
6. select backup physically;
7. wait for heater readiness;
8. conditionally purge through the existing purge authority;
9. merge and persist the active logical route mapping;
10. clear checkpoint and resume only if owned.

Mapping persistence must remain after successful selection, heating, and purge. This
preserves canonical route truth if an earlier stage fails. If mapping persistence fails
after fallback hardware changes, do not attempt automatic physical rollback: the failed
original tool is unloaded and mechanically selecting it could be unsafe. Remain paused,
retain the checkpoint, and report the mismatch.

If no active logical route can be associated with the selected failed physical tool,
stop after confirmed failure and remain paused. Guessing which logical mapping to
rewrite would corrupt routing truth.

## Timeouts And Synchronous Adapter Limits

### Heating timeout

Heating is naturally asynchronous and can enforce `heating_timeout` with a reactor
deadline. Poll at a bounded interval, use `heater.check_busy()`, and never interfere
with Klipper shutdown or verify-heater behavior.

### Selection and purge timeouts

The current physical handlers and purge adapter execute synchronously in the G-code
thread. There is no safe supported mechanism for this extension to interrupt arbitrary
G-code midway through mechanical selection or purge. A reactor timer cannot preempt a
blocked synchronous callback.

The practical Phase 4 contract is:

- record monotonic start/deadline;
- invoke the adapter exactly once;
- on exception, fail immediately;
- after successful return, reject an elapsed-time overrun and remain paused; and
- never try another backup after a selection or purge error/overrun.

This enforces stage deadlines at the workflow boundary without pretending to make
arbitrary macros cancellable. Real cooperative cancellation would require a future
adapter protocol and is outside v1 scope. Tests must explicitly verify both raised
errors and post-return overruns.

## Guarded `RESUME` Interception

Phase 4 must prevent user `RESUME` from bypassing incomplete fallback work. At ready
time, transactionally capture the existing public `RESUME` handler and install a
wrapper, using the same rollback discipline as `Tn` capture. Preserve the original
handler for authorized pass-through.

Wrapper policy:

- no active checkpoint: call the original `RESUME` handler unchanged;
- active/in-progress fallback: reject and remain paused;
- blocked non-heating failure: reject and remain paused;
- `heating_timeout`: re-read the selected backup heater;
- still busy/cold: reject, warn, and remain paused;
- ready: continue the checkpoint from conditional purge, mapping persistence, and
  owned resume completion.

Do not invoke the public wrapped `RESUME` recursively from automatic completion.
Automatic completion may use the configured `resume_gcode` adapter as today, but the
plan must prevent that adapter from resolving back into the guard in a way that treats
the extension's own completion as user bypass. A private captured resume handler is
the cleanest path when `resume_gcode` is exactly `RESUME`; custom multi-command resume
adapters need a documented non-recursive internal invocation rule.

Preserve user parameters such as `VELOCITY` by passing the original `gcmd` to the saved
handler on ordinary authorized resume. Heating-timeout continuation should complete
fallback first, then use the saved original handler or configured adapter exactly once.

Capture failure or later ready-time failure must restore the original `RESUME` handler,
just as physical handler capture currently restores `Tn` handlers.

## Completing Manual Active-Route Transitions

ROUTE-05 should reuse the heater adapter and stage helpers without conflating manual
remap with automatic fallback:

- capture the current physical tool's valid target;
- turn off its heater;
- preheat the requested physical tool before selection;
- select, wait, conditionally purge, persist requested mapping, and resume only when
  the transition owns the pause;
- reject missing/zero targets and all incomplete stages while paused.

Manual transition persistence failure may retain the existing rollback behavior only
when rollback is demonstrably safe. Automatic fallback must never select the failed
unloaded tool as rollback. Keep those policies explicit in separate coordinator entry
points.

The current active-route transition is synchronous. Heating makes it asynchronous, so
the command should establish a checkpoint and return while the reactor advances the
workflow. During that checkpoint, reject logical selections, mapping commands, physical
bypass, and conflicting state changes that could invalidate the transition.

## Failure Containment And Invariants

Phase 4 plans and tests should preserve these invariants:

- Never begin fallback before confirmed debounced runout.
- Never claim pause ownership from print state timing alone.
- Never auto-resume a user-owned pause.
- Never select a candidate unless the latest scan snapshot says loaded and non-failed.
- Never let a loop abort traversal of unrelated reachable branches.
- Never guess or substitute a missing/zero failed-tool target.
- Never weaken or replace Klipper heater safety.
- Never automatically select another tool after physical selection begins and fails.
- Never mark purge success before the configured purge adapter and persistence succeed.
- Never publish a fallback route mapping before selection, heat, and purge succeed.
- Never clear a blocked checkpoint merely because a user issued `RESUME`.
- Never leave an incomplete workflow printing.

## Recommended Plan Breakdown

### Plan 04-01: Runout Ownership, Graph Resolution, And Runtime Foundation

- Add explicit `PAUSE_OWNED` hook parsing and validated ownership.
- Separate pending runout/transient context from sensor debounce internals.
- Add pure depth-first graph resolver with loop detection, categorized reports, and
  one fresh re-scan.
- Add runtime checkpoint/status model and conflict guards.
- Extend deterministic fakes for heater objects and elapsed-time adapter behavior.

### Plan 04-02: Heater Transfer And Guarded Stage Execution

- Resolve configured heaters at ready time.
- Implement target capture, failed-heater shutdown, backup preheat, selection boundary
  timeout measurement, reactor-driven heating wait/timeout, and purge boundary timeout.
- Add guarded transactional `RESUME` capture and heating-timeout continuation.
- Complete manual active-route temperature/stage integration for ROUTE-05.

### Plan 04-03: Complete Automatic Fallback And Failure Containment

- Connect confirmed runout to full fallback orchestration.
- Persist logical remap only after selection/heating/purge success.
- Implement owned success resume, transient recovery, exhausted graph behavior, and
  terminal blocked status.
- Add comprehensive success, timeout, retry/resume, persistence, and conflict tests.
- Verify no Phase 5 external notifications or real-printer UAT are introduced.

## Likely Files

| File | Expected Phase 4 role |
|------|-----------------------|
| `klippy/extras/tool_fallback.py` | Runtime checkpoint, ownership, graph orchestration, heater adapters, timers, resume guard, and active-route integration. |
| `klippy/extras/tool_fallback_state.py` | Prefer no schema change; optionally add a narrowly scoped immutable helper for merging fallback mapping with latest canonical state. |
| `klippy/extras/tool_fallback_config.py` | Existing timeout/heater fields are sufficient unless planning identifies a bounded polling interval option; avoid unnecessary new config. |
| `tests/conftest.py` | Fake heaters/heater manager, resume-handler capture support, deterministic stage elapsed time, and richer event ordering. |
| `tests/test_tool_fallback_fallback.py` | New focused graph, ownership, transient, heater, timeout, resume, and complete workflow coverage. |
| `tests/test_tool_fallback_routing.py` | ROUTE-05 completion and regression coverage for manual active-route behavior. |
| `tests/test_tool_fallback_sensor.py` | Confirmed-runout handoff and transient-recovery integration coverage. |
| `tests/test_tool_fallback_purge.py` | Purge timeout/failure integration regressions. |

## Validation Architecture

### Test layers

1. **Pure resolver tests**
   - depth-first priority ordering;
   - failed/unloaded intermediary traversal;
   - loops, duplicate reachability, and deterministic reports;
   - unknown-authority loaded eligibility;
   - fresh second scan observing a newly eligible tool;
   - exhausted graph reporting.

2. **Checkpoint and ownership tests**
   - strict `PAUSE_OWNED` parsing and validation;
   - no fallback before debounce confirmation;
   - owned and user-owned transient recovery;
   - second runout/conflicting command rejection;
   - JSON-safe status for every stage and blocked reason.

3. **Heater and timeout tests**
   - ready-time heater resolution and missing-heater failure;
   - valid target capture and immediate failed-heater shutdown;
   - zero/missing/non-finite target rejection;
   - backup preheat before physical selection;
   - heater busy polling, readiness continuation, and timeout checkpoint;
   - guarded normal `RESUME` while cold and after ready;
   - selection/purge exceptions and post-return overruns;
   - no second candidate after selection starts.

4. **End-to-end workflow tests**
   - exact successful fallback order:
     confirmed runout -> failed state persist -> target capture -> failed heater off ->
     resolve -> preheat -> select -> heat ready -> purge if needed -> mapping persist ->
     owned resume;
   - already-purged backup fast path;
   - unknown-sensor loaded backup warning and use;
   - exhausted backups and one re-scan;
   - persistence failure after hardware transition;
   - user-owned pause never resumes;
   - every incomplete path remains paused.

5. **ROUTE-05 regression tests**
   - active remap/restore/reset use target transfer and preheat-before-selection;
   - purge remains before mapping persistence;
   - failures preserve prior mapping truth;
   - ordinary logical selection does not perform temperature transfer;
   - existing Phase 2/3 routing, sensor, and purge suites remain green.

### Deterministic fake requirements

Add a `FakeHeater` with mutable `temperature`, `target`, `busy`, status/error injection,
and ordered events. Add a `FakeHeaters` manager exposing `lookup_heater()` and
`set_temperature()`. Use the existing `FakeReactor` to advance heating deadlines and
resume continuation deterministically.

Extend fake script/physical handlers so a test can advance reactor monotonic time before
return, proving selection and purge post-return timeout behavior. Preserve exact event
ordering across heater targets, physical selection, purge, persistence, and resume.

### Suggested verification commands

```bash
python3 -m py_compile klippy/extras/tool_fallback*.py
pytest -q tests/test_tool_fallback_fallback.py
pytest -q tests/test_tool_fallback_sensor.py tests/test_tool_fallback_routing.py tests/test_tool_fallback_purge.py
pytest -q
git diff --check
```

### Requirement matrix

| Requirement | Primary automated evidence |
|-------------|----------------------------|
| FALL-01 | Explicit standard-sensor pause ownership hook tests; no duplicate immediate pause. |
| FALL-02 | Debounce handoff tests proving no heater/traversal action before confirmation. |
| FALL-03 | Owned versus user-owned transient recovery and resume tests. |
| FALL-04 | Pure DFS, loop, duplicate, failed-intermediary, and re-scan tests. |
| FALL-05 | Loaded/failed eligibility matrix including unknown sensor authority. |
| FALL-06 | Full ordered workflow and persistence tests. |
| FALL-07 | Heating deadline plus selection/purge exception and overrun tests. |
| FALL-08 | Failure matrix asserting paused state, blocked checkpoint, and guarded resume. |
| ROUTE-05 | Active remap/restore/reset complete temperature, selection, purge, persistence, and resume ordering tests. |

## Planning Risks

1. **Synchronous timeout semantics:** selection and purge cannot be safely preempted.
   Plans must document post-return overrun enforcement and avoid claiming cancellable
   arbitrary G-code.
2. **Resume recursion and macro ownership:** wrapping public `RESUME` while supporting a
   configurable resume adapter requires an explicit private pass-through design.
3. **Asynchronous active-route transitions:** introducing heater waiting changes command
   completion timing and requires durable runtime conflict guards.
4. **Mapping persistence after hardware change:** automatic fallback cannot safely roll
   back to a failed unloaded tool; state mismatch must remain visible and paused.
5. **Transient context loss:** reusing only `pending_runout_context` would lose ownership
   when the debounce target reverses. Keep workflow context separate.
6. **Heater readiness definition:** use Klipper's `check_busy()` rather than inventing a
   temperature tolerance that may conflict with heater control configuration.
7. **Scope creep:** external notify adapter invocation, example config, and real-printer
   behavior verification remain Phase 5 even though local warnings are required now.

## Research Conclusion

Phase 4 can be planned cleanly around a runtime-only checkpoint state machine that
extends, rather than replaces, the verified Phase 3 sensor, routing, purge, and
persistence behavior. The safest architecture uses explicit pause ownership, a pure
snapshot-based DFS resolver, ready-time heater resolution, nonblocking heater targets,
reactor-driven heating waits, and a captured `RESUME` guard. Selection and purge
timeouts must be represented honestly as fail-closed boundary overruns because Klipper
does not provide safe preemption of arbitrary synchronous G-code adapters.

