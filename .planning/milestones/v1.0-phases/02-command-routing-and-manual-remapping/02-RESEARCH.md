# Phase 2: Command Routing And Manual Remapping - Research

**Researched:** 2026-06-07
**Status:** Complete

## Phase Boundary

Phase 2 should establish the routing and transition-control layer that later sensor,
purge, and automatic-fallback phases can reuse:

- transactionally capture and replace every configured logical `Tn` command;
- preserve original physical handlers and invoke them without routing recursion;
- resolve intercepted logical commands through persisted mappings;
- expose physical bypass, remap, restore, and reset commands;
- track transient active logical and selected physical ownership;
- own pause/select/persist/resume sequencing for active-print mapping changes.

Do not add sensor lookup or debounce, purge-state mutations or purge execution, backup
graph mutation/traversal, heater transfer, automatic fallback, timeouts, or external
notifications in this phase.

## Requirements And Observable Outcomes

| Requirement | Phase 2 outcome |
|-------------|-----------------|
| ROUTE-02 | Each configured logical `Tn` is replaced at ready time and resolves its current persisted mapping before physical selection. |
| ROUTE-03 | Saved original handlers are the only physical-selection implementation; routed and bypass selections never redispatch a public `Tn` command. |
| ROUTE-04 | `REMAP_TOOL`, `RESTORE_TOOL`, and `RESET_TOOL_MAPPINGS` validate configured canonical names, create immutable state replacements, persist atomically, and publish only successful mutations. |
| ROUTE-05 | Mapping changes affecting the active logical tool during an active print use one transition coordinator with explicit pause ownership, warning, physical selection, persistence, failure containment, and ownership-safe resume. |

The phase should also expose active logical and selected physical values in status so
later phases and operators can distinguish routing intent from the hardware most recently
selected through this extension.

## Klipper Command Handler Capture

### Verified registration contract

Klipper's `GCodeDispatch.register_command(cmd, None)` removes a ready-state command and
returns its previous handler. Re-registering the command with a new handler replaces the
public route while the returned callable remains directly invokable. This is the same
capture pattern used by upstream `safe_z_home`, `homing_override`, and
`gcode_macro.rename_existing`.

Configured `Tn` names are traditional G-code commands. Klipper therefore stores their
handlers without the extended-command parameter wrapper used for commands such as
`REMAP_TOOL`. Capture and replacement must occur at `klippy:ready`, after configured
macros and other command providers have registered their handlers.

### Transactional capture recommendation

Handler interception changes process-global command dispatch and must fail closed:

1. Finalize configuration and load/reconcile the candidate state.
2. For each configured tool in canonical order, call
   `gcode.register_command(tool, None)` and retain the returned handler.
3. If any handler is missing, restore every handler removed so far and raise an
   actionable configuration error naming the missing tool.
4. After all handlers exist, register one logical routing wrapper per configured tool.
5. If replacement registration or subsequent ready-time persistence fails, restore all
   originals before propagating the startup error.
6. Publish `state`, `_state_store`, and captured handlers only after the complete ready
   transaction succeeds.

Keep capture and restoration in narrow helpers so rollback behavior is directly testable.
Do not silently accept a missing handler: every configured physical tool is a possible
mapping target.

### Synthetic physical commands

Directly invoking a saved handler prevents recursion, but the handler should receive a
`gcmd` representing the physical command being selected. If logical `T0` maps to physical
`T2`, passing the original `T0` command object would expose the wrong command line to the
saved `T2` macro. Passing the public `SELECT_PHYSICAL_TOOL` command object would also leak
its `TOOL` parameter into the physical macro.

Use `gcode.create_gcode_command()` when available to create a physical `Tn` command object,
then call the captured handler directly. Preserve the intercepted logical command's raw
parameters only if compatibility requires parameters on traditional `Tn` commands;
physical bypass should create a clean parameterless physical command. Extend `FakeGCode`
with the same creation behavior so tests can assert the physical handler observes the
mapped physical command name.

## Routing And Ownership Model

### Recommended transient fields

Keep these out of persisted schema v1:

- `_physical_handlers`: immutable/canonical mapping from configured `Tn` to captured
  original callable;
- `_active_logical_tool`: last logical `Tn` successfully selected through an intercepted
  logical route;
- `_selected_physical_tool`: last physical `Tn` successfully selected through an
  intercepted route or internal active transition;
- `_transition_active`: reentrancy guard for manual transition workflows.

On startup, active logical and selected physical ownership are unknown (`None`). Persisted
mappings describe routing policy, not proof of currently selected hardware.

### Logical route behavior

An intercepted logical command should:

1. reject use before ready state or during another transition;
2. read the mapped physical tool from the current canonical state;
3. invoke the captured physical handler directly with a physical command object;
4. update active logical and selected physical ownership only after the handler returns
   successfully.

Do not persist on ordinary logical selection because the mapping did not change. If the
physical handler raises, ownership remains unchanged.

### Physical bypass behavior

`SELECT_PHYSICAL_TOOL TOOL=Tn` is a low-level maintenance surface:

- validate `TOOL` as a configured canonical name;
- reject direct user invocation while a print is active;
- outside active prints, directly invoke the captured physical handler;
- do not change or clear active logical ownership;
- do not change persisted mappings.

Internal transition code should call a private physical-selection helper rather than
calling the public command or redispatching `SELECT_PHYSICAL_TOOL`. The private call path
is the authorization mechanism for physical selection during active prints. It should
update selected physical ownership only after successful selection.

## Immutable Persistent Mapping Mutations

Add pure methods to `FallbackState`, returning canonical replacement objects:

```python
state.with_mapping(logical, physical)
state.with_identity_mapping(logical)
state.with_identity_mappings()
```

These methods should require names already present in the canonical state, preserve all
tool records and backup order, and reuse `_canonical()`. Returning `self` for a no-op is
useful but not required because `StateStore.save()` already suppresses equal writes.

At the Klipper adapter boundary, use one mutation helper that:

1. builds the candidate immutable state;
2. saves it atomically;
3. publishes `self.state = candidate` only after save succeeds.

Translate validation and filesystem failures to `gcmd.error(...)`. A failed save must
leave the prior in-memory state published. This preserves the Phase 1 rule that status
never advertises state that was not successfully persisted.

### Command semantics

- `REMAP_TOOL LOGICAL=T0 PHYSICAL=T2`: set one route.
- `RESTORE_TOOL TOOL=T0`: restore one identity route.
- `RESET_TOOL_MAPPINGS`: restore every route to identity.

All names must be exact configured canonical names. No command in this phase changes
loaded, purged, failed, or backup state.

Outside an active transition, no-op mutations should avoid physical selection and writes.
During an active print, changing an inactive logical route remains a persistence-only
operation. Reset changes inactive routes together, but its active route is not considered
complete until the active physical transition succeeds.

## Print-State Detection And Transition Ownership

### Active-print detection

Use the optional Klipper `print_stats` object and its public `get_status(eventtime)`
result. Treat both `"printing"` and `"paused"` as an active print:

```python
print_stats = printer.lookup_object("print_stats", None)
state = print_stats.get_status(reactor.monotonic())["state"]
active = state in ("printing", "paused")
```

Treat missing `print_stats` or any other state (`standby`, `complete`, `error`,
`cancelled`) as not active. Looking only for `"printing"` is unsafe because a transition
itself changes print state to `"paused"` and user-issued physical bypass must remain
rejected while that print is paused.

### Pause ownership

The coordinator must distinguish:

- an actively printing job that this transition pauses and may resume;
- an already paused active job that it must leave paused;
- a non-print operation that needs no pause or resume.

Before changing active physical hardware, report a warning naming logical, current
physical, and requested physical tools. If the job is printing, invoke configured
`pause_gcode` synchronously through `gcode.run_script_from_command()` and mark the
transition as owning the pause only after that call succeeds. If the job is already
paused, proceed without claiming ownership. Resume through configured `resume_gcode`
only after every required Phase 2 transition step succeeds and only when the coordinator
owns the pause.

Any selection, persistence, or resume failure must surface a command error and leave the
printer paused. Clear the reentrancy guard in `finally`, but never convert a failure into
success.

### Active remap sequence

Recommended sequence for a changed active route:

1. Set the transition reentrancy guard.
2. Determine current selected physical tool from transient ownership; reject a transition
   if active logical ownership exists but selected physical ownership is unknown.
3. Pause if currently printing; preserve an existing pause otherwise.
4. Emit the planned-transition warning.
5. Select the requested physical tool through the private captured-handler path.
6. Persist and publish the candidate mapping state.
7. Update selected physical ownership.
8. Resume only if this transition owns the pause.

Physical selection and filesystem persistence cannot be one atomic operation. If saving
fails after selection, make a best-effort direct selection of the previous physical tool,
keep the old state published, report whether rollback also failed, and leave the print
paused. Tests must lock down this recovery policy.

For `RESET_TOOL_MAPPINGS`, construct one all-identity candidate. If the active logical
route needs a physical transition, run the sequence once and publish the complete
candidate only after selection succeeds. This ensures inactive routes are not reported
as reset while the active reset transition is still incomplete.

## Scope Conflict: Meaning Of "Complete Safe Transition"

`DESIGN.md` describes manual active remapping as the full pause, temperature-transfer,
selection, conditional-purge, and resume workflow. However:

- purge lifecycle and purge-state authority are allocated to Phase 3;
- temperature transfer, timeout enforcement, and general fallback-stage execution are
  allocated to Phase 4;
- Phase 2 explicitly excludes purge lifecycle and later fallback behavior.

The Phase 2 plan should therefore implement the complete **routing transition ownership
workflow available in this phase**: pause ownership, warning, recursion-free selection,
atomic mapping persistence, failure containment, and ownership-safe resume. It should
provide one coordinator/helper that Phases 3 and 4 extend with heating and purge stages.
It must not pretend to perform conditional purge or temperature transfer before those
authoritative capabilities exist.

Verification should record partial ROUTE-05 coverage for transition ownership and routing
safety, while leaving ROUTE-05 incomplete until the richer temperature/purge stages are
integrated and verified under their assigned later phases. If project governance
interprets ROUTE-05 as requiring those later stages now, the roadmap must be changed
before planning; implementing them in Phase 2 would violate the current phase boundary.

## Recommended Project Structure

Keep the change concentrated:

```text
klippy/extras/tool_fallback.py
  command registration, ready-time capture transaction, routing handlers,
  print-state adapter, transition coordinator, status fields

klippy/extras/tool_fallback_state.py
  pure immutable mapping mutation methods

tests/conftest.py
  synthetic G-code creation/invocation, fake print_stats, script calls/failures

tests/test_tool_fallback_state.py
  pure mapping mutation and persistence invariants

tests/test_tool_fallback_routing.py
  handler capture, routing, bypass, manual commands, active transitions
```

A dedicated routing test module will keep Phase 2 workflow coverage readable instead of
overloading the existing Phase 1 lifecycle adapter tests.

## Likely Implementation Plan

### Plan 02-01: Handler Capture And Logical Routing

- Extend fakes for command creation and handler observation.
- Add transactional ready-time capture/replacement with rollback.
- Implement recursion-free logical routing and transient ownership/status.
- Cover missing handlers, partial capture rollback, mapped command identity, handler
  failure, and restart initialization.

### Plan 02-02: Immutable Mapping Commands

- Add pure `FallbackState` mapping replacement methods.
- Register and implement remap, restore, reset, and physical bypass commands.
- Persist before publishing and translate command-time failures.
- Cover configured-name validation, no-op behavior, atomic-save failure, bypass
  restrictions, and restart persistence.

### Plan 02-03: Active-Print Transition Ownership

- Add optional `print_stats` detection and pause/resume adapter invocation.
- Implement guarded active remap/restore/reset coordinator.
- Add warnings, pause ownership, failure containment, and best-effort rollback.
- Cover printing, already-paused, inactive logical, transition reentrancy, selection
  failure, persistence failure, rollback failure, and resume failure.

## Risks And Mitigations

| Risk | Mitigation |
|------|------------|
| Partial ready-time capture leaves commands missing or replaced after startup failure. | Make capture/replacement transactional and restore originals on every failure path. |
| Routed handler receives a logical or bypass `gcmd` and behaves differently. | Create a synthetic physical command object before direct invocation. |
| Public `Tn` redispatch causes recursion. | Only invoke saved original callables; never run a mapped `Tn` as a G-code script. |
| Direct bypass changes logical ownership or is used during a paused print. | Keep bypass private internally, preserve active logical ownership, and treat printing plus paused as active. |
| Persisted and in-memory mappings diverge after write failure. | Save candidate first and publish only after success. |
| Physical selection succeeds but persistence fails. | Best-effort select the previous physical tool, preserve old mapping, report rollback outcome, and leave paused. |
| Transition resumes a user-owned pause. | Track pause ownership per transition and resume only when owned. |
| Nested command invocation starts another transition. | Guard the coordinator and reject reentrant mapping transitions. |
| Phase 2 accidentally implements purge/heating semantics without authoritative state. | Keep explicit extension points and defer those stages to Phases 3 and 4. |
| Real printer macros depend on unusual `Tn` parameters or command identity. | Test synthetic command identity and document parameter-forwarding policy; validate representative macros in Phase 5. |

## Validation Architecture

### Test layers

| Layer | Scope | Command |
|-------|-------|---------|
| Syntax | All extension modules | `python3 -m py_compile klippy/extras/tool_fallback*.py` |
| State unit | Immutable mapping mutations and save/publish invariants | `pytest -q tests/test_tool_fallback_state.py` |
| Routing adapter | Capture, routing, bypass, manual commands, transitions | `pytest -q tests/test_tool_fallback_routing.py` |
| Regression | Existing configuration, persistence, and lifecycle behavior | `pytest -q tests/test_tool_fallback_config.py tests/test_tool_fallback_extension.py` |
| Phase | Complete repository suite | `pytest -q` |

### Required fake capabilities

- `FakeGCode.create_gcode_command()` with observable command name, command line, raw
  parameters, and parsed parameters;
- script-call recording and injectable failures for configured pause/resume adapters;
- command invocation helper that uses registered handlers;
- `FakePrintStats.get_status()` with controllable printing, paused, and inactive states;
- physical handler spies that record command identity and can raise command errors;
- state-store save failure injection;
- response/warning recording.

### Requirement coverage matrix

| Requirement | Automated evidence |
|-------------|--------------------|
| ROUTE-02 | Persisted non-identity mapping routes logical `T0` to saved physical `T2`; mapping survives restart; ordinary selection does not write state. |
| ROUTE-03 | Captured physical handler receives a physical `T2` command object; no public `T2` redispatch occurs; missing handler blocks startup and restores prior handlers. |
| ROUTE-04 | Remap/restore/reset produce canonical immutable states, persist once, validate names, suppress no-ops, and leave old published state on save failure. |
| ROUTE-05 | Active route changes pause/warn/select/persist/resume in order, preserve user-owned pauses, leave paused on every failure, and reset active plus inactive routes as one successful state publication. |

### Critical failure-path tests

- missing first and later physical handler during ready-time capture;
- replacement registration failure and persistence failure after capture;
- physical handler failure leaves ownership unchanged;
- direct bypass rejected in both printing and paused states;
- inactive-route remap during a print does not pause or select;
- active no-op remap does not transition;
- pause adapter failure prevents selection and persistence;
- selection failure prevents persistence and resume;
- persistence failure after selection attempts physical rollback and leaves paused;
- rollback failure reports both failures and leaves paused;
- resume failure reports failure and leaves transition ownership/status coherent;
- reset publishes no identity changes until the active physical transition succeeds.

### Nyquist rules

- Every plan task includes a narrow runnable test command.
- Every state mutation is tested for success, no-op, and persistence failure.
- Every workflow stage is tested with its next stage asserted not to run after failure.
- Tests assert call order for pause, warning, physical selection, save, and resume.
- Final phase verification runs syntax compilation, the complete pytest suite, and
  `git diff --check`.
- Real-printer UAT remains deferred until the user installs a more feature-complete
  version; automated fakes are the Phase 2 acceptance evidence.

## Sources

- `.planning/phases/02-command-routing-and-manual-remapping/02-CONTEXT.md`
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/DESIGN.md`,
  `.planning/STATE.md`, and `.planning/PROJECT.md`
- `.planning/phases/01-extension-foundation-and-persistence/01-RESEARCH.md`
- `.planning/phases/01-extension-foundation-and-persistence/01-VERIFICATION.md`
- `klippy/extras/tool_fallback.py`, `tool_fallback_state.py`, and
  `tool_fallback_config.py`
- `tests/conftest.py`, `test_tool_fallback_extension.py`, and
  `test_tool_fallback_state.py`
- Upstream Klipper `klippy/gcode.py`: command registration/unregistration, synthetic
  command creation, direct command execution, and traditional-command behavior
- Upstream Klipper `klippy/extras/gcode_macro.py`: captured-handler and macro parameter
  behavior
- Upstream Klipper `klippy/extras/print_stats.py`: public print-state values
- Upstream Klipper `klippy/extras/pause_resume.py`: pause state and synchronous
  pause/resume command behavior
