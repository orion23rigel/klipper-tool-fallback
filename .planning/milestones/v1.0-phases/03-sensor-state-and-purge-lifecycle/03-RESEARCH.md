# Phase 3: Sensor State And Purge Lifecycle - Research

**Researched:** 2026-06-08
**Status:** Complete

## Phase Boundary

Phase 3 should add trustworthy per-tool filament authority and purge lifecycle behavior
on top of the verified Phase 2 routing coordinator:

- gracefully resolve configured sensor objects without making sensor availability a
  startup requirement;
- represent missing, disabled, or unreadable sensors as explicitly unknown/unverified;
- reconcile persisted loaded/purged/failed state after a continuous symmetric debounce;
- process explicit runout and insertion hooks without taking ownership of Klipper's
  immediate runout pause;
- provide guarded macro-owned filament-state and manual purge-state commands;
- make `PURGE_TOOL` the only operation that marks a physical tool purged after an
  actual configured purge operation succeeds; and
- conditionally purge every active-print selection of an unpurged physical tool.

Automatic backup traversal, route mutation caused by runout, temperature transfer,
heater shutdown, full fallback execution, external notification adapters, and
real-printer UAT remain outside Phase 3.

## Requirement Interpretation

| Requirement | Phase 3 interpretation |
|-------------|------------------------|
| STATE-03 | Reconcile persisted tool state only after a sensor reading remains continuously stable for `debounce_time`; unknown sensors preserve persisted filament fields but publish unverified authority. |
| SENS-01 | Explicitly configured sensor object names are the source of enabled/availability and raw filament readings. Explicit runout/insert commands provide event hooks; status polling covers startup and enable/disable transitions. |
| SENS-02 | Both loaded and unloaded readings use the same restartable reactor-timer debounce. A reading is committed only if the same available/enabled reading remains current at expiry. |
| SENS-03 | Confirmed unloading always clears `loaded` and `purged`; it marks `failed` only for selected-tool runout during an active print. |
| SENS-04 | Confirmed insertion sets `loaded=true`, `purged=false`, and `failed=false`. |
| PURGE-01 | Public `PURGE_TOOL TOOL=Tn` invokes a distinct configured purge adapter and persists `purged=true` only after successful return. |
| PURGE-02 | No extrusion observation or generic G-code interception changes `purged`. |
| PURGE-03 | Every active-print physical selection runs the purge operation when the selected tool is unpurged, including ordinary routed `Tn` selection and active-route transitions. |
| PURGE-04 | Outside an active print, unpurged selection succeeds and reports status without invoking purge. |
| PURGE-05 | Narrow manual purged/unpurged commands follow the active-tool authorization rules and preserve `loaded=false => purged=false`. |
| ROUTE-05 partial | Fill the existing post-selection transition hook with conditional purge and failure containment. Heating and complete stage execution remain Phase 4 work. |

The Phase 3 context overrides the older design statement that automatic backup
eligibility always requires confirmed loaded state. Sensor-unavailable tools remain
selectable as backups with warnings, but they cannot originate sensor-triggered
fallback events.

## Klipper Filament Sensor Findings

### Standard sensor surface

Klipper's `filament_switch_sensor.SwitchSensor` delegates status and event policy to
`RunoutHelper`. Its public status dictionary contains:

```python
{
    "filament_detected": bool,
    "enabled": bool,
}
```

`SET_FILAMENT_SENSOR SENSOR=<name> ENABLE=0|1` changes `enabled`. The sensor still
updates its internal `filament_present` value while disabled, but suppresses runout and
insert event processing. This makes `get_status(eventtime)` suitable for restoring
authority immediately after re-enable.

The standard helper owns immediate runout pausing when `pause_on_runout: True`. It
schedules runout/insert G-code asynchronously through the reactor. Phase 3 must not
replace or duplicate that immediate pause behavior. The extension's explicit
`TOOL_FALLBACK_RUNOUT TOOL=Tn` and `TOOL_FALLBACK_INSERT TOOL=Tn` commands should only
record the event context and begin/restart the extension's longer symmetric debounce.

### No generic external callback subscription

Standard filament sensor objects expose `get_status()` but no stable public API for
another extension to subscribe to all raw state and enabled changes. Reaching into
`runout_helper`, wrapping `note_filament_present`, or replacing built-in command
handlers would couple this extension to private implementation details and compete with
Klipper's own runout logic.

Use two complementary inputs instead:

1. Explicit configured `runout_gcode` / `insert_gcode` hooks start debounce promptly.
2. A lightweight reactor timer polls each resolved sensor's status to support startup
   reconciliation, detect disabled/re-enabled sensors, detect a hook configuration
   mistake, and validate the reading when debounce expires.

The poll interval should be bounded and independent of `debounce_time`; a value such as
`min(0.25, debounce_time / 2)` gives adequate enable/disable responsiveness without a
busy loop. Keep it an internal constant unless real integration evidence shows a user
configuration need.

### Sensor resolution and graceful degradation

At ready time, resolve each configured `filament_sensor` through
`printer.lookup_object(name, None)`. Treat all of the following as unknown/unverified
without aborting ready:

- no sensor name configured for the tool;
- configured object not found;
- object lacks a callable `get_status`;
- `get_status()` raises or returns missing/non-boolean `enabled` or
  `filament_detected`; or
- sensor reports `enabled=false`.

The current config parser requires a nonempty `filament_sensor`, which conflicts with
the locked graceful-degradation decision. Phase 3 planning must make this option
optional and normalize absence to `None` (or another explicit internal sentinel).

Do not infer electrical failure or wrong polarity. A valid enabled sensor reporting
open/unloaded is an authoritative unloaded reading. Users correct polarity in Klipper
configuration or deliberately disable the sensor to enter unknown/unverified mode.

## Recommended Runtime Model

### Keep persisted schema focused on durable filament facts

Do not add sensor availability, debounce candidates, timer handles, pause
acknowledgements, or pause ownership to schema v1. They are runtime facts that are
invalid after restart.

Add immutable `FallbackState` / `ToolState` candidate helpers for:

- confirmed loaded transition: loaded, unpurged, non-failed;
- confirmed ordinary unload: unloaded, unpurged, preserve failed;
- confirmed active-print runout: unloaded, unpurged, failed;
- explicit macro loaded/unloaded transitions;
- mark purged and mark unpurged.

Each helper should return the same state object for exact no-ops and enforce the
existing invariant that an unloaded tool cannot be purged. Continue the established
save-before-publish pattern for every durable change.

### Per-tool transient sensor record

Maintain one private runtime record per configured physical tool with fields equivalent
to:

```text
sensor_object             resolved object or None
authority                 "available" or "unknown"
raw_loaded                bool or None
debounce_target           bool or None
debounce_generation       monotonically increasing token
debounce_timer            reactor timer handle
outage_acknowledged       bool
pending_runout_context    whether removal began as selected-tool active-print runout
```

Expose JSON-safe status fields per tool, preferably separately from canonical persisted
state:

```json
{
  "sensor_authority": "available",
  "sensor_enabled": true,
  "sensor_detected": true,
  "sensor_outage_acknowledged": false
}
```

Do not present the last persisted `loaded` value as currently verified when authority is
unknown. It may remain in canonical state as historical/operator-owned information, but
status must clearly distinguish it from live sensor authority.

## Symmetric Debounce Strategy

Use one restartable reactor timer per tool. Klipper reactor timers are registered once
and rescheduled with `update_timer(timer, deadline)`; callbacks return
`reactor.NEVER` when idle.

On any observed available sensor reading:

1. If it differs from the current debounce target, replace the target, increment its
   generation/token, and schedule expiry at `eventtime + debounce_time`.
2. If it matches the target, do not extend the deadline. This preserves the requirement
   for one continuous interval rather than repeated polling indefinitely postponing it.
3. At expiry, read sensor status again. Commit only if authority is still available and
   the current reading still matches the target/token.
4. If authority disappeared or the reading changed, cancel or restart without committing
   the stale candidate.

Use the same mechanism for ready-time reconciliation and runtime transitions. Startup
should publish the already reconciled persisted state and routing promptly, then allow
sensor timers to persist any confirmed reconciliation changes after ready. Sensor
absence must not roll back the transactional Phase 2 handler installation.

### Transition semantics

- Confirmed insertion: persist `loaded=true`, `purged=false`, `failed=false`.
- Confirmed ordinary unloading: persist `loaded=false`, `purged=false`, preserve
  `failed`.
- Confirmed selected-tool unloading during `printing`: persist
  `loaded=false`, `purged=false`, `failed=true`; do not traverse backups in Phase 3.
- Confirmed selected-tool unloading while already `paused`: persist failed state and
  report it, but do not start fallback or resume.
- Transient unload that returns to continuously loaded before removal confirmation:
  update/report recovery. Resume only if a future fallback coordinator can prove it owns
  the pause; Phase 3 must not guess ownership from print state alone.

The final point exposes a boundary issue: Phase 2 pause ownership is currently local to
`_transition_active_route()`, and the standard sensor performs the immediate pause.
Phase 3 can record whether the print was already paused when the runout hook arrived,
but it cannot reliably prove ownership of a standard sensor pause without an explicit
contract. Plan Phase 3 to preserve user pauses and leave automatic transient resume
disabled unless an unambiguous ownership token is introduced. Full FALL-01 through
FALL-03 behavior belongs to Phase 4.

## Sensor Availability And One-Time Pause

Poll status to detect transitions into and out of unknown authority:

- Any tool becoming unknown: cancel pending debounce, clear raw verification status,
  preserve canonical durable state, and warn.
- Inactive selected status or inactive physical tool: do not pause.
- Currently selected physical tool becoming unknown while `printing`: invoke configured
  pause once, warn, and set `outage_acknowledged=true` only after pause succeeds.
- Selected tool becoming unknown while already paused: warn but do not claim pause
  ownership or invoke pause again.
- Subsequent selection/use of the same unknown tool: warn as appropriate, but do not
  repeatedly pause for the acknowledged outage.
- Authority restored: clear outage acknowledgement, begin debounce from the current
  reading, and restore sensor-dependent behavior only after confirmation.

The instruction "on resume, recheck sensor availability" can be satisfied by continuous
polling; no interception of the public `RESUME` command is required. The next poll sees
the new print state and latest sensor status. If a stronger immediate resume hook is
needed later, add it through an explicit adapter rather than capturing arbitrary user
macros.

Unknown tools cannot originate sensor-triggered fallback events. They remain selectable,
including by future automatic fallback, with a warning that filament state is
unverified.

## Explicit Macro-Owned Filament State

Register:

```text
SET_TOOL_FILAMENT_STATE TOOL=Tn LOADED=0|1
```

Use strict canonical tool validation and strict integer/boolean parsing. Authorization:

- inactive physical tools may be changed at any time;
- the selected physical tool may be changed outside a print or while `paused`;
- reject selected-tool changes while `printing`;
- explicit changes never directly trigger fallback or resume.

Semantics:

- `LOADED=0`: unloaded, unpurged, preserve failed;
- `LOADED=1`: loaded, unpurged, clear failed.

This command is an intentional operator/macro override and may be used while sensor
authority is unknown. If the enabled sensor is authoritative, warn that its next
confirmed reading may supersede the explicit state. Do not silently disable the sensor
or alter its polarity.

## Purge Command Architecture

### Resolve the current recursion hazard before implementation

The current normalized config defaults `purge_gcode` to `PURGE_TOOL`, while Phase 3 must
register public `PURGE_TOOL` as the lifecycle command. Calling the configured adapter
from that command would recursively invoke itself.

Recommended correction:

- public command: `PURGE_TOOL TOOL=Tn`;
- configured operator adapter: a distinct macro such as `_TOOL_FALLBACK_PURGE`;
- change the default `purge_gcode` accordingly; and
- reject an adapter value equal to `PURGE_TOOL` after command-name normalization.

This is a Phase 3 configuration-contract migration, not automatic fallback work. Update
configuration tests and documentation in the same plan. An alternative capture-and-wrap
scheme is unnecessarily fragile because it depends on registration order and makes the
public command's ownership ambiguous.

### Dedicated purge operation

Implement one internal method used by public purge and automatic selection:

```text
_purge_physical_tool(tool, warning_sink/context)
```

Behavior:

1. Require initialized routing/state and a loaded tool unless sensor authority is
   unknown. Known-unloaded purge must be rejected because it would otherwise violate the
   persisted invariant.
2. If authority is unknown, warn and proceed under explicit operator policy.
3. Invoke the configured purge adapter with an explicit `TOOL=Tn` parameter using
   `run_script_from_command`.
4. Only after successful return, build, persist, and publish a `purged=true` candidate.
5. On adapter or persistence failure, leave the tool unpurged and surface the failure.

Klipper's synchronous script call provides success/failure completion but not a native
wall-clock timeout around arbitrary G-code execution. `purge_timeout` enforcement is a
Phase 4 stage-execution concern unless the project introduces a dedicated asynchronous
completion protocol. Do not falsely claim timeout enforcement in Phase 3.

### Manual purge-state commands

Use narrow commands such as:

```text
MARK_TOOL_PURGED TOOL=Tn
MARK_TOOL_UNPURGED TOOL=Tn
```

Apply the same active-tool authorization as `SET_TOOL_FILAMENT_STATE`: inactive tools
anytime; selected physical tool only outside a print or while paused. `MARK_TOOL_PURGED`
must reject a known-unloaded tool. For an unknown-authority tool, allow with a warning,
consistent with the operator override decision. Both commands use save-before-publish
and exact no-op suppression.

Manual extrusion remains entirely outside the state machine.

## Conditional Purge Selection Integration

Phase 2 currently has two selection paths:

- ordinary logical routing calls `_select_physical()` directly; and
- active route transitions call `_select_physical()` followed by
  `_run_post_selection_transition_stages()`.

Implement the purge policy once so every active-print physical selection receives it.
The least error-prone shape is to make `_select_physical()` responsible for:

1. direct saved physical handler invocation;
2. publish selected physical ownership only after successful selection;
3. inspect print state after selection;
4. outside an active print, report unpurged status and return;
5. during `printing` or `paused`, purge when unpurged; and
6. surface purge failure without changing purged state.

However, ordinary slicer `Tn` selection occurs while `printing` and does not currently
pause before `_select_physical()`. To satisfy "purge before the print continues" and
"purge failure leaves the print paused," conditional purge needs an owned-pause wrapper
for ordinary routed selections:

- if print state is `printing` and selected target is unpurged, pause before physical
  selection/purge and resume only after success;
- if already paused, never auto-resume;
- if purge fails, leave paused and unpurged;
- if the target is already purged, preserve the existing direct fast path.

Active route transitions already pause and own resume around selection. Their conditional
purge stage must reuse that existing ownership rather than issuing a second pause or
resume. This likely favors a selection context argument or a separate internal
`_select_and_conditionally_purge(..., owns_pause/already_guarded)` coordinator over
placing all behavior directly in `_select_physical()`.

Do not purge outside active prints. Do warn when selecting an unpurged tool and when an
unknown-authority tool is selected or purged.

### Failure containment

- Physical selection failure: do not purge, do not publish selected ownership, and
  preserve existing mapping/state.
- Purge adapter failure: leave tool unpurged, surface error, and leave active print
  paused.
- Purge-state persistence failure after physical purge: leave published state unpurged,
  surface error, and leave active print paused. The physical purge occurred, but durable
  truth was not recorded, so retrying is safer than falsely publishing success.
- Active route transition purge failure: prevent mapping persistence and resume. Phase
  2's current coordinator already persists mapping after the post-selection hook, which
  is the correct order.
- Ordinary routed selection purge failure: active logical ownership should not publish
  as successfully selected for continued printing. Selected physical ownership may
  truthfully reflect the hardware selection, but status must make the incomplete
  transition visible.

## Likely Code Changes

| File | Likely role |
|------|-------------|
| `klippy/extras/tool_fallback_config.py` | Make `filament_sensor` optional; separate configured purge adapter from public `PURGE_TOOL`; validate recursion hazard. |
| `klippy/extras/tool_fallback_state.py` | Add immutable loaded/unloaded/failed/purged candidate helpers with no-op suppression and invariants. |
| `klippy/extras/tool_fallback.py` | Resolve/poll sensors, manage debounce timers and unknown authority, register explicit state/purge commands, coordinate pause ownership, and integrate conditional purge into all selection paths. |
| `tests/conftest.py` | Add timer scheduling/advancement, fake filament sensor status/failures, strict integer G-code parsing, and purge script event/failure support. |
| `tests/test_tool_fallback_state.py` | Cover pure sensor and purge transitions and invariants. |
| `tests/test_tool_fallback_config.py` | Cover optional sensors and distinct purge adapter validation. |
| `tests/test_tool_fallback_sensor.py` | Focused sensor resolution, authority, debounce, startup reconciliation, runout semantics, and macro override tests. |
| `tests/test_tool_fallback_purge.py` | Focused command authorization, purge success/failure, and active-selection integration tests. |
| `tests/test_tool_fallback_routing.py` | Regression coverage for Phase 2 transition ordering and conditional-purge hook integration. |

## Recommended Plan Breakdown

### Plan 03-01: Durable State And Sensor Runtime Foundation

- Add immutable filament/purge state candidates.
- Make sensor configuration optional and expose explicit runtime authority status.
- Extend the fake reactor and fake sensor test infrastructure.
- Resolve sensor objects gracefully at ready and establish polling/timer lifecycle.

### Plan 03-02: Symmetric Debounce And Explicit Filament Authority

- Implement continuous symmetric debounce and startup reconciliation.
- Register explicit runout/insert hooks and `SET_TOOL_FILAMENT_STATE`.
- Implement unknown-sensor transitions, one-time selected-tool pause, acknowledgement,
  restoration, and failed-state semantics.
- Prove that Phase 3 does not traverse backups or mutate mappings on runout.

### Plan 03-03: Purge Lifecycle And Selection Integration

- Resolve the `PURGE_TOOL` / configured-adapter naming conflict.
- Implement public purge and manual purged/unpurged commands.
- Integrate conditional purge with ordinary logical selection and Phase 2 active route
  transitions using explicit pause ownership.
- Verify all purge/selection/persistence failures remain paused and unpurged.

These plans are sequential because later behavior depends on state helpers, reactor
fakes, and sensor authority contracts established earlier.

## Validation Architecture

### Test layers

| Layer | Scope | Command |
|-------|-------|---------|
| Syntax | All extension modules | `python3 -m py_compile klippy/extras/tool_fallback*.py` |
| Pure state/config | Immutable transitions, optional sensor config, adapter validation | `pytest -q tests/test_tool_fallback_state.py tests/test_tool_fallback_config.py` |
| Sensor lifecycle | Resolution, availability, timers, debounce, reconciliation, failed state, explicit command | `pytest -q tests/test_tool_fallback_sensor.py` |
| Purge lifecycle | Purge commands, authorization, adapter failure, persistence failure | `pytest -q tests/test_tool_fallback_purge.py` |
| Routing integration | Ordinary selection and active-transition conditional purge ordering/failure containment | `pytest -q tests/test_tool_fallback_routing.py` |
| Phase regression | Entire project | `pytest -q` |

### Required automated evidence

#### Sensor authority and startup

- Missing sensor config, missing object, disabled object, malformed status, and status
  exception all reach ready successfully with unknown authority.
- Unknown tools preserve persisted filament facts but expose them as unverified.
- Enabled sensor startup readings commit only after a full continuous debounce.
- Loaded startup reconciliation preserves purged only when persisted loaded was already
  true; newly confirmed load is unpurged and clears failed.
- Unloaded startup reconciliation clears loaded and purged.
- Sensor re-enable begins fresh debounce and restores authority only after confirmation.

#### Debounce and event semantics

- Insertion and removal use the same interval.
- Oscillation restarts debounce; stale timer callbacks cannot commit.
- Repeated equal polling does not postpone a valid deadline.
- Removal always clears loaded and purged.
- Only selected-tool confirmed runout during active print marks failed.
- Already user-paused confirmed runout marks failed without fallback or resume.
- Confirmed insertion clears failed and marks unpurged.
- Unknown sensor cannot originate fallback behavior.
- No sensor path traverses backups or changes mappings in Phase 3.

#### Availability and explicit commands

- First selected-tool outage while printing pauses and warns once.
- Pause failure does not falsely acknowledge the outage.
- Repeated polls/selections during an acknowledged outage do not pause again.
- Inactive tool outage never pauses.
- Authority restoration clears acknowledgement after confirmation.
- `SET_TOOL_FILAMENT_STATE` enforces active/inactive/paused authorization and exact
  transition semantics.
- Explicit changes never trigger fallback or resume.

#### Purge lifecycle

- Public `PURGE_TOOL` calls a distinct adapter and marks purged only after adapter and
  persistence success.
- Known-unloaded purge is rejected; unknown-authority purge proceeds with warning.
- Adapter and persistence failures leave published state unpurged.
- Manual mark commands enforce loaded/unknown and active-tool authorization.
- No-op marks perform no write.
- Manual extrusion and unrelated scripts cannot alter purge state.

#### Selection integration and ROUTE-05 contribution

- Outside-print unpurged selection reports but does not purge.
- Active-print ordinary `Tn` selection of an unpurged tool pauses, selects, purges,
  persists, and resumes only when extension-owned.
- Active transition reuses existing pause ownership and purges exactly once before
  mapping persistence/resume.
- Already purged selection does not invoke purge or add unnecessary pause.
- Unknown-authority selection/purge proceeds with warning.
- Purge failure and purge-state persistence failure leave print paused and mapping
  unpublished.
- Existing user pause is never resumed.
- Phase 2 routing, rollback, and reentrancy tests remain green.

### Manual verification

Real-printer UAT remains explicitly deferred. Phase 5 should verify actual
`filament_switch_sensor` macro hooks, `SET_FILAMENT_SENSOR` disable/re-enable behavior,
printer-specific pause/resume macros, and purge adapter execution.

## Planning Risks And Required Decisions

1. **Purge command recursion is a blocker.** Planning must explicitly rename/separate the
   configured purge adapter before implementing public `PURGE_TOOL`.
2. **Sensor config is currently mandatory.** Planning must change parser and tests to
   honor graceful degradation.
3. **Klipper sensors lack a stable callback subscription.** Use explicit hooks plus
   status polling; do not monkeypatch `RunoutHelper`.
4. **Immediate runout pause ownership is ambiguous.** Phase 3 must never auto-resume
   based only on observing `paused`; complete transient recovery ownership in Phase 4.
5. **Ordinary logical selection lacks transition ownership.** Conditional purge requires
   a guarded pause/resume coordinator for unpurged active-print selections.
6. **Persistence can fail after physical purge.** Published state must remain unpurged
   and printing must remain paused, even though repeating purge may waste material.
7. **Ready-time debounce is asynchronous.** Status must distinguish initialized routing
   from sensor authority still awaiting confirmation.
8. **Unknown does not mean unloaded.** Do not clear durable state merely because a
   sensor is absent or disabled, and do not let unknown tools originate runout events.

## Sources

- Phase 3 decisions: `.planning/phases/03-sensor-state-and-purge-lifecycle/03-CONTEXT.md`
- Requirements and phase allocation: `.planning/REQUIREMENTS.md`,
  `.planning/ROADMAP.md`
- Existing behavioral contract: `.planning/DESIGN.md`
- Verified routing integration and hooks:
  `.planning/phases/02-command-routing-and-manual-remapping/02-VERIFICATION.md`
- Existing implementation: `klippy/extras/tool_fallback.py`,
  `klippy/extras/tool_fallback_state.py`, `klippy/extras/tool_fallback_config.py`
- Klipper standard filament sensor implementation:
  https://github.com/Klipper3d/klipper/blob/master/klippy/extras/filament_switch_sensor.py
- Klipper motion sensor reuse of `RunoutHelper` and reactor timers:
  https://github.com/Klipper3d/klipper/blob/master/klippy/extras/filament_motion_sensor.py
- Klipper reactor timer/callback contract:
  https://github.com/Klipper3d/klipper/blob/master/klippy/reactor.py
- Klipper configuration reference:
  https://www.klipper3d.org/Config_Reference.html#filament_switch_sensor

