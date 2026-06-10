# Phase 2: Command Routing And Manual Remapping - Pattern Map

**Mapped:** 2026-06-07
**Status:** Complete

## Implementation Shape

Keep Phase 2 concentrated in the existing Klipper adapter and immutable state
model. The adapter owns command registration, handler capture, transient routing
ownership, print-state inspection, transition sequencing, and command-error
translation. The state model owns pure mapping replacements. The test harness
models only the Klipper surfaces needed to prove those behaviors.

```text
public logical Tn / manual command
  -> ToolFallback adapter validates and decides direct mutation vs transition
  -> saved original physical Tn handler performs selection without redispatch
  -> StateStore atomically persists candidate mapping when policy changes
  -> ToolFallback publishes candidate and transient ownership only after success
```

Persisted mappings remain policy. `_active_logical_tool` and
`_selected_physical_tool` remain transient evidence of selections successfully
performed through this extension.

## File Pattern Map

### `klippy/extras/tool_fallback.py`

**Role**

- Klipper-facing lifecycle and command adapter.
- Transactionally captures configured physical handlers at ready time.
- Routes logical selections and exposes manual remap, restore, reset, and
  physical-bypass commands.
- Coordinates active-print transitions and translates internal failures into
  configuration or command errors.

**Closest existing analogs**

- `_handle_ready()` already follows a candidate-first, publish-last startup
  transaction: finalize configuration, load/reconcile, save, then assign
  `_state_store` and `state`.
- `_raise_state_error()` is the local pattern for categorized boundary error
  translation.
- `cmd_SHOW_TOOL_FALLBACK_STATE()` and its constructor registration establish the
  `cmd_COMMAND_NAME` naming and `gcmd` adapter style.
- `get_status()` builds a detached snapshot rather than exposing mutable runtime
  objects.

**Data flow**

```text
klippy:ready
  -> finalize_configuration()
  -> StateStore.load_reconciled() + save()
  -> capture every configured public Tn handler
  -> install logical wrappers
  -> publish store, state, and captured handlers together

logical Tn wrapper
  -> read current state.mappings[logical]
  -> create synthetic physical Tn gcmd
  -> invoke saved original handler directly
  -> publish active logical and selected physical only after success

manual mapping command
  -> validate canonical configured names
  -> build immutable candidate state
  -> direct save/publish when inactive or outside a print
  -> guarded transition when the active logical route changes in an active print
```

**Concrete code patterns**

- Initialize runtime-only fields to unpublished defaults in `__init__`:
  `_physical_handlers = None`, `_active_logical_tool = None`,
  `_selected_physical_tool = None`, and `_transition_active = False`.
- Register extended manual commands in `__init__`, beside
  `SHOW_TOOL_FALLBACK_STATE`, with short `desc` values. Do not register logical
  `Tn` wrappers until ready time because their original handlers must already
  exist.
- Preserve the ready-time publish-last invariant. Build local `store`, `state`,
  and `physical_handlers`; if any later ready step fails, restore all public
  handlers already changed before raising. Assign runtime fields only after the
  complete transaction succeeds.
- Iterate `normalized.tools` directly. It is already a canonical,
  numerically-sorted `MappingProxyType`, so no second ordering rule is needed.
- Keep capture/installation/restoration in narrow private helpers. A practical
  split is `_capture_physical_handlers(tools)`, `_install_logical_handlers(...)`,
  and `_restore_physical_handlers(...)`; each should make rollback behavior
  independently testable.
- Bind logical names when creating wrappers. Use a helper/factory or a default
  argument so every wrapper does not close over the final loop value.
- Never route by running a public `Tn` command string. `_select_physical(...)`
  should obtain the saved callable, create a clean physical command with
  `gcode.create_gcode_command(tool, tool, {})`, invoke the callable directly,
  and update `_selected_physical_tool` only after it returns.
- Keep logical ownership update separate from physical selection:
  `_route_logical(logical, gcmd)` resolves the mapping, calls the private physical
  helper, then assigns `_active_logical_tool = logical` only after success.
- Validate manual command tool names at the adapter boundary against
  `self.config.tools`, not merely the `Tn` regex. Return errors through
  `raise gcmd.error(...)` with the offending logical or physical route named.
- Centralize save-before-publish behavior in one helper:

  ```python
  def _persist_state(self, candidate):
      self._state_store.save(candidate)
      self.state = candidate
  ```

  Wrap `OSError` at the calling command boundary. Do not assign `self.state`
  before `save()` succeeds.
- Suppress transition work for no-op candidates. `StateStore.save()` suppresses
  equal writes, but the adapter must also avoid unnecessary pause and physical
  selection.
- Use `printer.lookup_object("print_stats", None)` and
  `printer.get_reactor().monotonic()` for print-state inspection. Treat both
  `"printing"` and `"paused"` as active; missing `print_stats` is inactive.
- Authorize active-print physical selection by private call path. The public
  `SELECT_PHYSICAL_TOOL` command rejects active prints, while the transition
  coordinator calls `_select_physical(...)` directly.
- Keep one active-route transition coordinator for remap, restore, and reset.
  It should:
  1. reject reentrancy;
  2. record whether the print was `"printing"` or already `"paused"`;
  3. pause only a printing job and claim pause ownership only after the pause
     script succeeds;
  4. report the planned logical/current/requested physical transition;
  5. select the requested physical tool;
  6. persist and publish the complete candidate;
  7. resume only if this transition owns the pause;
  8. clear the guard in `finally`.
- Invoke configured pause/resume adapters synchronously through
  `gcode.run_script_from_command()`. A transition failure after pausing must not
  resume.
- If selection succeeds but persistence fails, preserve the old published state,
  attempt a direct best-effort selection of the prior physical tool, and report
  both persistence and rollback failures when applicable.
- Extend `get_status()` with detached transient values such as
  `active_logical_tool`, `selected_physical_tool`, and `transition_active`.
  Preserve the existing pre-ready result unless downstream behavior explicitly
  needs unknown transient fields before initialization.
- Do not add heating, purge, sensor, backup traversal, or notification behavior.
  The transition coordinator is the extension point those later phases will
  enrich.

### `klippy/extras/tool_fallback_state.py`

**Role**

- Canonical immutable persisted-state model.
- Pure mapping mutation surface for Phase 2 commands.
- Existing atomic persistence implementation remains unchanged.

**Closest existing analogs**

- `FallbackState.reconcile()` creates fresh dictionaries and returns
  `_canonical(...)` rather than mutating mappings.
- `from_config()` and `_canonical()` establish identity mapping creation,
  deterministic numeric ordering, and `MappingProxyType` publication.
- `StateStore.save()` already suppresses equal writes and publishes its internal
  persisted-state marker only after `_atomic_write()` succeeds.

**Data flow**

```text
current FallbackState
  -> pure with_mapping / identity helper
  -> copied mappings with unchanged tool records
  -> _canonical(tools, mappings)
  -> candidate returned to adapter
```

**Concrete code patterns**

- Add instance methods near `reconcile()`:
  `with_mapping(logical, physical)`, `with_identity_mapping(logical)`, and
  `with_identity_mappings()`.
- Validate membership in `self.tools` for both logical and physical names. Raise
  `StateValidationError` with route-specific context; the Klipper adapter will
  translate it to `gcmd.error(...)`.
- Copy with `dict(self.mappings)`, update only the requested entries, and return
  `self._canonical(self.tools, mappings)`. Passing the existing immutable tool
  mapping is consistent because `_canonical()` copies/sorts it.
- Returning `self` for exact no-ops is appropriate and makes identity explicit,
  though equal replacement objects are already write-suppressed by
  `StateStore.save()`.
- Do not add transient active/selected fields to schema v1 or alter `to_dict()`.
- Do not change `StateStore` atomic-write behavior for Phase 2. Adapter-level
  save-before-publish and transition rollback are separate responsibilities.

### `tests/conftest.py`

**Role**

- Minimal Klipper contract fake shared by adapter tests.
- Phase 2 needs observable synthetic commands, command invocation, script calls,
  print state, and injectable failures.

**Closest existing analogs**

- `FakeGCode.register_command()` already implements the crucial Klipper
  unregister-and-return-previous-handler contract.
- `FakePrinter.lookup_object(name, default)` already models optional objects.
- `FakeGCmd.error()` and `FakeConfig.error()` preserve the real boundary pattern
  of returning exception objects that callers raise.
- Existing fakes keep public recording fields (`commands`, `responses`, `events`)
  simple and directly assertable.

**Concrete code patterns**

- Extend `FakeGCmd` with command identity fields while preserving existing
  `FakeGCmd(params=...)` callers. A compatible shape records command name,
  command line, raw parameters, parsed parameters, and responses.
- Add `FakeGCode.create_gcode_command(command, commandline, params)` returning a
  `FakeGCmd` with those exact observable values.
- Add a small invocation helper that resolves `commands[name]` and calls it with
  a supplied or constructed `FakeGCmd`; keep direct access to `commands` for
  existing tests.
- Add `run_script_from_command(script)` with a `script_calls` list and targeted
  failure injection. Tests need to distinguish pause and resume failures and
  assert call order.
- Add response recording suitable for transition warnings. Prefer the same
  `respond_info` surface unless implementation deliberately uses another
  Klipper response API.
- Add `FakePrintStats` with a mutable `state` and
  `get_status(eventtime) -> {"state": state}`. Register it through
  `printer.add_object("print_stats", fake)`.
- Keep physical handler spies in the routing test module unless they become
  broadly reused fixtures. They should record received synthetic command
  identity and optionally raise `CommandError`.

### `tests/test_tool_fallback_state.py`

**Role**

- Unit proof that mapping mutations are pure, canonical, complete, and
  compatible with atomic persistence.

**Closest existing analogs**

- `valid_dict()` supplies a non-identity mapping and varied tool order.
- Reconcile tests assert fresh canonical results while preserving unrelated
  state.
- Save tests already prove equal-write suppression and failure preservation.

**Concrete code patterns**

- Add focused tests beside reconcile coverage for:
  changed mapping, one identity restore, all identity reset, no-op behavior,
  unknown logical tool, and unknown physical tool.
- Assert the original state remains unchanged, unrelated mappings and every
  `ToolState` remain unchanged, and result key order remains `T0`, `T1`, `T2`.
- Use existing `valid_dict()` and `configured()` helpers rather than introducing
  a second state-building convention.
- Leave command-boundary save/publish failure tests to the routing adapter test;
  retain `StateStore` filesystem mechanics in this module.

### `tests/test_tool_fallback_routing.py` (new)

**Role**

- Dedicated integration-style adapter tests for ROUTE-02 through ROUTE-05.
- Keeps Phase 2 workflow and failure-order assertions out of Phase 1 lifecycle
  tests.

**Closest existing analogs**

- Reuse `load_extension()` and `tool_options()` semantics from
  `test_tool_fallback_extension.py`; move them to shared fixtures only if both
  modules genuinely need imports without duplication.
- Follow existing tests' arrange, invoke, assert spacing and direct inspection
  of extension/fake fields.
- Use `track_replacements()`-style monkeypatching for narrow failure injection,
  but assert workflow call order through one explicit event list.

**Concrete code patterns**

- Build configured physical handlers before sending `klippy:ready`; the ready
  event must capture and replace them exactly as production does.
- Use handler spies that append events like
  `("select", "T2", received_command_name)` and can fail on demand.
- Assert capture rollback for both a missing first handler and a missing later
  handler. After failure, all originally registered public handlers must be
  restored and extension runtime state must remain unpublished.
- Prove routing with a persisted non-identity mapping: public `T0` invokes the
  saved original `T2` callable, which receives a synthetic `T2` command object.
  Assert the public routed `T2` wrapper was not recursively invoked.
- Assert physical-handler failure leaves active logical and selected physical
  ownership unchanged.
- Cover `SELECT_PHYSICAL_TOOL` outside a print, during `"printing"`, and during
  `"paused"`; successful bypass must not change active logical ownership or
  mappings.
- Cover remap, restore, and reset success, unknown tools, no-ops, restart
  persistence, and injected save failure. On save failure, assert the old
  `extension.state` remains published.
- For active transition tests, seed ownership by invoking a logical route rather
  than assigning private fields unless the test specifically targets an
  impossible/unknown ownership condition.
- Assert ordered events for the successful printing path:
  pause script, warning, physical selection, save/publication observation,
  resume script.
- Assert an already-paused print transitions without pause or resume, while an
  inactive logical remap during a print only persists.
- Inject failure at every stage and assert later stages do not run. Selection,
  persistence, rollback, and resume failures must leave the print unresumed and
  the transition guard cleared.
- For active reset, assert inactive identity changes are published only with the
  complete candidate after the active physical transition succeeds.

### `tests/test_tool_fallback_extension.py`

**Role**

- Phase 1 lifecycle regression coverage.

**Closest existing analogs and guidance**

- Preserve its ready-time, state-error, and deterministic-status tests.
- Update setup to register original `Tn` handlers before ready once capture
  becomes mandatory; otherwise existing lifecycle tests will fail for the right
  new startup rule but stop testing their original purpose.
- Extend the status expectation only for the new transient status fields.
- Do not move Phase 2 workflow cases into this file.

## Cross-Cutting Patterns

### Error Boundaries

- Startup capture/configuration failures: raise `self._config_error(...)` and
  leave ready-time runtime fields unpublished.
- User command validation or workflow failures: `raise gcmd.error(...)`.
- Pure state model validation: raise `StateValidationError`.
- Preserve the original exception context in messages, but name the logical
  route, current physical tool, and requested physical tool for transition
  failures.

### Transaction Boundaries

- **Ready transaction:** original handlers remain recoverable until state,
  capture, replacement, and publication all succeed.
- **Mapping transaction:** candidate state is saved before `self.state` changes.
- **Active-route transition:** hardware selection and filesystem persistence
  cannot be atomic; contain failure with best-effort physical rollback, old
  published state, and no resume.

### Naming And Style

- Follow existing ASCII-only source, percent-format error strings, four-space
  indentation, and `cmd_UPPERCASE_COMMAND` handlers.
- Use canonical uppercase `Tn` values throughout. Configuration ordering already
  uses numeric tool order.
- Prefer narrow private helpers over a new module or framework. Phase 2 behavior
  is coupled to the existing `ToolFallback` adapter and does not yet justify a
  separate routing class.

## Plan-Aligned Change Groups

| Group | Primary files | Pattern objective |
|-------|---------------|-------------------|
| Handler capture and logical routing | `tool_fallback.py`, `conftest.py`, new routing tests, extension regression tests | Transactional ready interception, synthetic physical commands, publish ownership after success |
| Immutable mapping commands | `tool_fallback_state.py`, state tests, `tool_fallback.py`, routing tests | Pure candidates, save before publish, validated bypass/remap/restore/reset |
| Active-print transition ownership | `tool_fallback.py`, `conftest.py`, routing tests | One guarded coordinator, pause ownership, ordered failure containment and rollback |

## Avoided Patterns

- Do not redispatch mapped `Tn` commands through public G-code parsing.
- Do not use the public physical-bypass command as the internal authorization
  path.
- Do not persist active logical or selected physical ownership.
- Do not mutate `FallbackState.mappings` or tool records in place.
- Do not publish candidate state before atomic persistence succeeds.
- Do not resume an already-paused print or any failed transition.
- Do not broaden Phase 2 into purge, heating, sensor, fallback-graph, timeout, or
  notification implementation.

---

*Phase: 02-command-routing-and-manual-remapping*
*Pattern mapping based on repository state and Phase 2 context/research*
