# Phase 3: Sensor State And Purge Lifecycle - Pattern Mapping

**Mapped:** 2026-06-08
**Status:** Complete

## Scope And Architectural Boundary

Phase 3 extends the verified Phase 2 routing coordinator with sensor-derived filament
facts and purge lifecycle behavior. Preserve the existing ownership split:

- `tool_fallback_config.py` normalizes static configuration.
- `tool_fallback_state.py` owns durable, immutable canonical facts.
- `tool_fallback.py` owns Klipper runtime objects, timers, command authorization,
  physical selection, pause ownership, and save-before-publish orchestration.
- focused pytest modules prove pure state/config behavior separately from runtime
  integration and failure containment.

Keep sensor availability, raw readings, debounce candidates, timer handles, outage
acknowledgement, and pause ownership out of schema v1. They are runtime-only facts that
cannot be trusted after restart. Persist only confirmed/operator-owned `loaded`,
`purged`, and `failed` changes through the existing immutable candidate and
save-before-publish pattern.

## Existing Patterns To Preserve

### Immutable candidate, persist, then publish

Closest analogs:

- `FallbackState.with_mapping()` and identity helpers in
  `klippy/extras/tool_fallback_state.py`
- `ToolFallback._persist_state()` and `_apply_mapping_candidate()` in
  `klippy/extras/tool_fallback.py`
- no-op and persistence-failure tests in `tests/test_tool_fallback_state.py` and
  `tests/test_tool_fallback_routing.py`

Concrete guidance:

1. Add pure `FallbackState` helpers that copy only the affected `ToolState`, preserve
   unrelated tools/mappings, canonicalize the result, and return `self` for exact
   no-ops.
2. Enforce `loaded=false => purged=false` in every helper instead of relying only on
   deserialization validation.
3. Runtime commands and sensor confirmations must build a candidate, call
   `_persist_state(candidate)`, and expose success only after persistence returns.
4. Adapter or persistence failure must leave the published state unchanged.

### Runtime ownership publishes only after physical success

Closest analogs:

- `_route_logical()` and `_select_physical()` in `tool_fallback.py`
- physical handler failure and ownership tests in `test_tool_fallback_routing.py`

Concrete guidance:

- Continue invoking saved physical handlers directly with synthetic canonical `Tn`
  commands. Do not redispatch public `Tn` commands.
- Publish `_selected_physical_tool` only after the saved handler returns.
- Publish `_active_logical_tool` only after the complete logical-selection workflow
  succeeds sufficiently to continue printing. Conditional-purge failure must not make
  an ordinary routed selection appear complete.

### Guarded active transitions and pause ownership

Closest analogs:

- `_transition_active_route()` and `_transition_active`
- `_run_pre_selection_transition_stages()` /
  `_run_post_selection_transition_stages()`
- ordered transition, already-paused, reentrancy, rollback, and resume-failure tests in
  `test_tool_fallback_routing.py`

Concrete guidance:

- Active route transitions already own the outer pause/resume sequence. Integrate
  conditional purge into that sequence without issuing a second pause or resume.
- Ordinary routed `Tn` selection currently calls `_select_physical()` directly. Add a
  guarded selection coordinator for an unpurged target during `printing`: pause,
  select, purge, persist purge state, then resume only if the extension initiated the
  pause.
- Preserve user-owned pauses. When print state is already `paused`, selection/purge may
  proceed but must never auto-resume.
- Any purge or purge-state persistence failure must leave the print paused and the tool
  published as unpurged.

### Transactional ready lifecycle

Closest analogs:

- `_handle_ready()`, `_capture_physical_handlers()`, and rollback tests

Concrete guidance:

- Missing or unusable sensors must not join the fail-closed handler-capture transaction
  as startup errors. Resolve them to runtime `unknown` authority and continue ready.
- Establish sensor runtime records and timers only after normalized tools and canonical
  state exist. A sensor resolution failure must not undo successful routing solely
  because sensor functionality is degraded.
- Startup sensor reconciliation is asynchronous: publish initialized routing/state,
  then persist confirmed reconciliation only after a full debounce interval.

## Data Flows

### Sensor observation to durable state

```text
configured sensor name
  -> ready-time lookup_object(name, None)
  -> poll get_status(eventtime)
  -> validate enabled + filament_detected booleans
  -> runtime authority/raw reading
  -> restartable symmetric debounce timer
  -> expiry re-read and stale-candidate check
  -> immutable confirmed filament candidate
  -> StateStore.save(candidate)
  -> publish extension.state
  -> status/reporting
```

Unknown authority preserves durable filament facts as historical/operator-owned state,
but status must explicitly show that those facts are unverified. Unknown tools cannot
originate sensor-triggered fallback events, but they remain selectable and may be used
as fallback targets with warnings.

### Explicit macro state command

```text
SET_TOOL_FILAMENT_STATE TOOL=Tn LOADED=0|1
  -> strict configured-tool and strict 0|1 validation
  -> authorize against selected physical tool + print state
  -> warn if live sensor authority may later supersede override
  -> immutable loaded/unloaded candidate
  -> persist then publish
```

Inactive physical tools may be changed during printing. The selected physical tool may
be changed outside a print or while paused, but not while actively printing. This path
never triggers fallback or resume.

### Purge command and selection purge

```text
public PURGE_TOOL TOOL=Tn or conditional selection
  -> validate/authorize tool and known-loaded vs unknown authority
  -> warn for unknown authority
  -> invoke distinct configured purge adapter with TOOL=Tn
  -> immutable mark-purged candidate
  -> persist then publish
```

Only this dedicated successful operation marks a tool purged. Manual extrusion and
unrelated scripts remain outside the state machine.

## Likely Files And Concrete Patterns

### `klippy/extras/tool_fallback_config.py`

**Role:** Static normalization and fail-fast validation for options whose invalidity is
knowable at configuration time.

**Likely changes:**

- Change `ToolConfig.filament_sensor` to permit `None`.
- Parse omitted `filament_sensor` as `None`; keep a provided empty string invalid so an
  accidental blank is not silently treated as deliberate omission.
- Change the default configured purge adapter from public `PURGE_TOOL` to a distinct
  private adapter such as `_TOOL_FALLBACK_PURGE`.
- Reject configured purge adapter values whose normalized command name is
  `PURGE_TOOL`.

**Closest analogs:**

- `_nonempty()` for required nonempty options
- `_positive_finite_float()` for centralized validation
- `finalize_config()` for cross-tool checks

**Pattern guidance:**

- Add a small optional-nonempty parser rather than weakening `_nonempty()` globally.
- Validate the adapter command token, not an arbitrary substring. At minimum trim and
  compare the first command token case-insensitively so `PURGE_TOOL TOOL=T0` cannot
  evade the recursion guard.
- Preserve frozen dataclasses and immutable normalized tool mappings.

### `klippy/extras/tool_fallback_state.py`

**Role:** Durable filament/purge transition authority and invariant enforcement.

**Likely changes:**

- Add a private per-tool replacement helper to avoid duplicating canonical copy logic.
- Add explicit candidates equivalent to:
  - confirmed/explicit loaded: `loaded=true`, `purged=false`, `failed=false`;
  - ordinary/explicit unloaded: `loaded=false`, `purged=false`, preserve `failed`;
  - confirmed active runout: `loaded=false`, `purged=false`, `failed=true`;
  - mark purged: require loaded and set `purged=true`;
  - mark unpurged: set `purged=false`.

**Closest analogs:**

- `with_mapping()` validation, exact no-op return, and canonical rebuild
- strict `purged while unloaded` validation in `from_dict()`

**Pattern guidance:**

- Validate the physical tool exists before replacement.
- Preserve `backups`, mappings, and unrelated tool objects.
- Return `self` when the resulting `ToolState` is equal to the current one.
- Do not add runtime sensor-authority fields or bump schema version.

### `klippy/extras/tool_fallback.py`

**Role:** Runtime sensor authority, timers, commands, pause ownership, physical
selection, warnings, purge adapter execution, and persistence orchestration.

**Likely changes:**

- Register public commands:
  - `TOOL_FALLBACK_RUNOUT`
  - `TOOL_FALLBACK_INSERT`
  - `SET_TOOL_FILAMENT_STATE`
  - `PURGE_TOOL`
  - `MARK_TOOL_PURGED`
  - `MARK_TOOL_UNPURGED`
- Add one private transient sensor record per configured physical tool. A small private
  class/dataclass is preferable to parallel dictionaries.
- Resolve sensor objects at ready without failing startup; register one poll timer and
  one restartable debounce timer per tool, or an equivalent bounded design.
- Extend `get_status()` with deterministic JSON-safe per-tool sensor authority,
  enabled/detected values, and outage acknowledgement.
- Add one command-authorization helper shared by explicit filament and manual purge
  state commands.
- Add one internal purge operation shared by public purge and automatic selection.
- Refactor selection coordination so ordinary active-print selection and active route
  transition both apply conditional purge exactly once while preserving pause
  ownership.

**Closest analogs:**

- `_require_configured_tool()` for strict canonical configured-tool validation
- `_get_print_state()` and `_print_is_active()` for authorization
- `_persist_state()` for save-before-publish
- `_transition_active_route()` for guard, pause ownership, ordering, and failure
  containment
- `_run_post_selection_transition_stages()` as the explicit Phase 3 route-transition
  integration point

**Pattern guidance:**

- Use `printer.get_reactor()` timers and generation/token checks; do not monkeypatch
  Klipper sensor internals.
- Poll configured sensor `get_status(eventtime)` and accept authority only when
  `enabled` and `filament_detected` are actual booleans.
- On a changed available reading, set a debounce target and deadline. Equal repeated
  polls must not extend the deadline. At expiry, re-read and commit only if authority
  and target still match.
- On unknown authority, cancel pending confirmation, preserve durable state, warn, and
  prevent sensor-triggered fallback origin.
- Pause once when the selected physical tool first loses authority during `printing`.
  Set acknowledgement only after pause succeeds. Do not repeatedly pause an
  acknowledged outage. Clear acknowledgement when restored authority completes valid
  debounce.
- Standard Klipper sensor behavior owns immediate runout pause. Do not auto-resume a
  transient in Phase 3 because ownership is ambiguous.
- Confirmed selected-tool removal during `printing` or an already user-paused active
  job marks failed but does not traverse backups in Phase 3.
- Build purge adapter script with an explicit `TOOL=Tn` argument. Adapter/persistence
  failure leaves published state unpurged.
- Do not claim or implement `purge_timeout`; synchronous script execution has no
  established Phase 3 timeout protocol.

### `tests/conftest.py`

**Role:** Deterministic Klipper adapter simulation.

**Likely changes:**

- Extend `FakeReactor` with `NEVER`, timer registration, timer rescheduling, and
  deterministic time advancement that invokes due callbacks in order.
- Add `FakeFilamentSensor` with mutable `enabled`/`filament_detected`, status call
  recording, malformed status, and injected status failure.
- Add strict `FakeGCmd.get_int()` support or an equivalent production-compatible path
  for `LOADED=0|1`.
- Preserve ordered `script_events` and targeted failure injection for purge adapter
  calls with parameters.

**Closest analogs:**

- mutable `FakePrintStats`
- `FakeGCode.script_events` / `inject_script_failure()`
- synthetic physical G-code command support

**Pattern guidance:**

- Time advancement should be explicit in tests; do not use wall-clock sleeps.
- Support stale timer callbacks and same-deadline ordering so debounce correctness is
  provable.
- Keep fake behavior narrow and observable rather than reproducing all of Klipper.

### `tests/test_tool_fallback_state.py`

**Role:** Pure transition and invariant proof.

**Likely changes:**

- Test every filament/purge helper's exact field changes, unrelated-state preservation,
  immutability, canonical ordering, and no-op identity.
- Test known-unloaded mark-purged rejection and invariant preservation.

**Closest analogs:**

- mapping mutation no-op, immutability, and unrelated-state tests
- strict parsing rejection tests

### `tests/test_tool_fallback_config.py`

**Role:** Configuration migration and recursion guard proof.

**Likely changes:**

- Prove omitted sensors normalize to `None` and provided empty sensors remain invalid.
- Update default purge adapter expectation.
- Reject `PURGE_TOOL` adapter variants that would recurse.
- Preserve required `heater` and all existing timing validation.

**Closest analogs:**

- global default/explicit option tests
- missing/empty required tool option tests

### `tests/test_tool_fallback_sensor.py` (new)

**Role:** Focused sensor authority, debounce, reconciliation, event, outage, and
explicit-command integration.

**Concrete test groups:**

- Startup succeeds for missing config, missing object, disabled sensor, malformed
  status, and status exceptions; all expose unknown authority.
- Startup reading changes durable state only after one full stable debounce.
- Insert and remove share symmetric continuous debounce; oscillation invalidates stale
  candidates; equal polling does not postpone expiry.
- Confirmed insertion/unloading/runout apply exact state semantics.
- Unknown sensors cannot originate fallback, selection, mapping mutation, or resume.
- Selected-tool authority outage pauses once; inactive outage does not pause;
  acknowledgement clears after valid restoration.
- Explicit macro command authorization and semantics, including no fallback/resume.

**Closest analogs:**

- ready lifecycle tests in `test_tool_fallback_extension.py`
- print-state and failure-injection patterns in `test_tool_fallback_routing.py`

### `tests/test_tool_fallback_purge.py` (new)

**Role:** Purge command authority, manual purge-state authorization, and failure
containment.

**Concrete test groups:**

- Public `PURGE_TOOL` calls the distinct adapter exactly once with `TOOL=Tn`.
- Known-unloaded purge rejects; unknown-authority purge warns and proceeds.
- Adapter and persistence failure leave published state unpurged.
- Manual purged/unpurged commands enforce inactive/selected/printing/paused policy and
  exact no-op suppression.
- Outside-print selection reports unpurged and does not purge.
- Active ordinary selection pauses/selects/purges/persists/resumes in order only when
  extension-owned.
- Already-paused selection never resumes.
- Purge failure leaves paused and prevents successful logical ownership publication.

**Closest analogs:**

- ordered transition event helpers and persistence failure injection in
  `test_tool_fallback_routing.py`

### `tests/test_tool_fallback_routing.py`

**Role:** Phase 2 regression proof and conditional-purge integration at routing
boundaries.

**Likely changes:**

- Update helper defaults/configuration for optional sensors and distinct purge adapter.
- Extend active-transition ordering expectations to include exactly one conditional
  purge before mapping persistence/resume.
- Prove already-purged paths preserve the existing fast path.
- Prove active-route purge failure prevents mapping persistence and resume while
  retaining existing rollback/reentrancy guarantees.

### `tests/test_tool_fallback_extension.py`

**Role:** Ready/status integration and deterministic status surface.

**Likely changes:**

- Update default purge adapter expectation.
- Assert runtime sensor status is deterministic and read-only.
- Prove degraded sensor startup does not undo handler interception or initialized state.

### `README.md`

**Role:** User-facing configuration and macro integration contract.

**Likely changes:**

- Document `filament_sensor` as optional with degraded unknown authority semantics.
- Document required sensor `runout_gcode` / `insert_gcode` hooks when a sensor is used.
- Change the `purge_gcode` default to the distinct private adapter and explain why it
  must not be `PURGE_TOOL`.
- Document `SET_TOOL_FILAMENT_STATE`, public purge, and manual purge-state commands.

This file is currently dirty from unrelated/user work. Any implementation plan that
edits it must preserve those existing changes.

## Critical Hazard: `PURGE_TOOL` Adapter Recursion

The current configuration defaults `purge_gcode` to `PURGE_TOOL`, while Phase 3 must
register public `PURGE_TOOL TOOL=Tn` as the lifecycle command. If the public command
invokes the configured adapter unchanged, it invokes itself recursively.

Required pattern:

```text
public lifecycle command: PURGE_TOOL TOOL=Tn
configured adapter:       _TOOL_FALLBACK_PURGE TOOL=Tn
```

Planning and implementation must:

1. change the configured adapter default to a distinct command;
2. reject adapter configuration that resolves to public `PURGE_TOOL`;
3. invoke only the distinct adapter from the public/internal purge operation;
4. test registration, default migration, explicit recursion rejection, and exactly-once
   adapter invocation.

Do not solve this by capturing/wrapping an existing `PURGE_TOOL` handler. That would
reintroduce registration-order ambiguity and the same recursion class Phase 2 avoided
for physical `Tn` routing.

## Recommended Implementation Order

1. **Durable state, config migration, and fake runtime foundation**
   - immutable filament/purge candidates;
   - optional sensor config;
   - distinct purge adapter and recursion guard;
   - fake reactor/sensor support.
2. **Sensor runtime and explicit filament authority**
   - graceful resolution, polling, debounce, startup reconciliation;
   - runout/insert hooks, outage acknowledgement, explicit macro command.
3. **Purge lifecycle and selection integration**
   - public/manual purge commands;
   - internal purge operation;
   - ordinary and active-route conditional purge with pause ownership.

The sequence is intentionally serial: sensor/purge commands depend on durable state
helpers and deterministic fakes, while conditional selection purge depends on the
internal purge authority contract.

## Verification Focus

- Run focused state/config tests after pure changes.
- Run `tests/test_tool_fallback_sensor.py` after every sensor-runtime task.
- Run `tests/test_tool_fallback_purge.py` plus routing regressions after every purge or
  selection-coordinator task.
- Run the full suite after each plan wave.
- Before phase verification run:

```text
python3 -m py_compile klippy/extras/tool_fallback*.py
pytest -q
git diff --check
```

Real-printer sensor hooks, enable/disable behavior, pause/resume macros, and purge
adapter execution remain intentionally deferred to Phase 5.

