# Phase 3: Sensor State And Purge Lifecycle - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement per-tool sensor authority, symmetric debounce, startup reconciliation,
loaded/purged/failed state transitions, explicit macro-owned filament-state updates,
dedicated purge-state commands, and conditional purge integration for physical tool
selection.

Automatic backup graph traversal and complete fallback execution remain in Phase 4.
Notifications and real-printer integration verification remain in Phase 5.

</domain>

<decisions>
## Implementation Decisions

### Sensor Availability And Graceful Degradation
- **D-01:** A missing, disabled, or unavailable filament sensor must not fail Klipper startup. The affected tool enters an explicit unknown/unverified sensor state.
- **D-02:** A sensor-unavailable tool cannot originate a sensor-triggered automatic fallback event because the extension cannot confirm runout.
- **D-03:** A sensor-unavailable tool remains usable for ordinary selection and remains eligible for automatic fallback selection. Assigning or automatically selecting it as a backup is allowed but must emit a warning that loaded state is unverified.
- **D-04:** If the currently selected physical tool's sensor first becomes unavailable during a print, warn and pause once. Resuming acknowledges the unavailable condition; future use must continue without repeatedly pausing for the same acknowledged condition.
- **D-05:** On resume, recheck sensor availability and restore sensor-dependent behavior if authority has returned.
- **D-06:** Do not add extension-specific sensor polarity handling. Incorrect normally-open/normally-closed behavior belongs in the underlying Klipper sensor configuration.

### Debounce, Runout, And Failed State
- **D-07:** Enabled sensor readings are authoritative only after one continuous symmetric debounce interval for both insertion and removal.
- **D-08:** Standard filament-sensor behavior owns the immediate runout pause. The extension waits for debounce before deciding whether runout is confirmed.
- **D-09:** Confirmed unloading always sets `loaded=false` and `purged=false`.
- **D-10:** Set `failed=true` only for confirmed runout of the selected physical tool during an active print. Ordinary unloading, maintenance swaps, explicit macro state changes, and sensor unavailability do not mark failed.
- **D-11:** Confirmed insertion sets `loaded=true`, sets `purged=false`, and clears `failed`.
- **D-12:** If a transient runout clears before confirmation, auto-resume only when the extension owns the pause.
- **D-13:** If the print was already user-paused, confirmed reinsertion updates state and reports recovery but never auto-resumes.
- **D-14:** If unloading remains confirmed while a print is already user-paused, mark the selected tool failed but do not start fallback. Preserve user pause ownership.

### Explicit Filament And Purge State Commands
- **D-15:** Provide one macro integration command: `SET_TOOL_FILAMENT_STATE TOOL=Tn LOADED=0|1`.
- **D-16:** `LOADED=0` sets `loaded=false` and `purged=false` without marking failed. `LOADED=1` sets `loaded=true`, sets `purged=false`, and clears `failed`.
- **D-17:** During printing, explicit filament-state changes are allowed for inactive physical tools. The selected physical tool may be changed explicitly only while paused.
- **D-18:** Explicit filament-state changes never directly trigger fallback or auto-resume.
- **D-19:** Manual purged/unpurged state commands use the same active-tool restriction: inactive tools may change anytime; the selected physical tool may change only while paused.
- **D-20:** `PURGE_TOOL TOOL=Tn` is allowed when sensor state is unknown, with a warning. Mark purged only after the configured purge operation succeeds.
- **D-21:** Manual extrusion never changes purged state.

### Conditional Purge During Selection
- **D-22:** Every active-print physical selection of an unpurged tool, including ordinary slicer `Tn` commands, manual route transitions, and later fallback transitions, must automatically run the configured purge operation before the print continues.
- **D-23:** Automatic purge proceeds with a warning when the selected tool's sensor state is unknown.
- **D-24:** Automatic purge failure leaves the print paused, reports the failure, and leaves the tool unpurged. It must never continue printing or mark purge success.
- **D-25:** Outside an active print, selecting an unpurged tool succeeds without automatic purge and reports that the tool remains unpurged.

### the agent's Discretion
- Exact warning and status wording, provided it clearly identifies the tool, unknown sensor authority, and resulting automation limits.
- Internal representation of sensor availability/unknown state and one-time unavailable-sensor pause acknowledgement.
- Exact names for explicit purged/unpurged commands.
- How sensor callbacks and timers integrate with Klipper internals while preserving the locked behavior above.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product And Scope
- `.planning/PROJECT.md` - Core value, sensor authority constraint, and project-level state decisions. Phase 3 decisions above override the earlier confirmed-loaded-only fallback eligibility assumption for sensor-unavailable tools.
- `.planning/ROADMAP.md` - Phase boundary, requirement allocation, and Phase 3 contribution to ROUTE-05.
- `.planning/REQUIREMENTS.md` - STATE-03, SENS-01 through SENS-04, PURGE-01 through PURGE-05, and ROUTE-05 acceptance requirements.
- `.planning/STATE.md` - Verified foundation and routing decisions carried forward from Phases 1 and 2.

### Behavioral Design
- `.planning/DESIGN.md` - Existing sensor, state transition, purge, and active-selection behavior. The graceful-degradation and unknown-sensor decisions above refine its confirmed-loaded eligibility rule.

### Routing Integration Contract
- `.planning/phases/02-command-routing-and-manual-remapping/02-VERIFICATION.md` - Verified routing-transition coordinator, pause ownership, physical-selection hooks, and explicit ROUTE-05 boundary.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `klippy/extras/tool_fallback.py`: Owns ready lifecycle, active-print detection, pause ownership, physical selection, state persistence, and Phase 3 conditional-purge integration hooks.
- `klippy/extras/tool_fallback_state.py`: Owns immutable `ToolState` fields and canonical save-before-publish state replacement patterns.
- `klippy/extras/tool_fallback_config.py`: Already loads per-tool `filament_sensor`, global `debounce_time`, configured purge adapter, and purge timeout.
- `tests/conftest.py`: Provides fake reactor, print state, G-code command execution, script sequencing, and failure injection.

### Established Patterns
- Runtime state changes build immutable candidates, persist atomically, then publish.
- Active transitions preserve pause ownership and leave failures paused.
- Physical selection uses private saved handlers and exposes before/after Phase 3 integration hooks.
- Tool identities are strict canonical uppercase `Tn` names.

### Integration Points
- Extend ready-time initialization to resolve configured sensor objects without failing startup when unavailable.
- Add sensor callbacks/timers and explicit unknown/unverified availability to runtime/status state.
- Extend immutable state helpers for loaded, purged, and failed transitions.
- Implement purge behavior through the existing active-selection integration hooks.
- Extend routing fakes and add focused sensor/purge lifecycle tests.

</code_context>

<specifics>
## Specific Ideas

- Users should recover from a broken sensor through normal Klipper sensor disable/enable behavior, not a second polarity or sensor-control system in this extension.
- Load/unload macros should call `SET_TOOL_FILAMENT_STATE TOOL=Tn LOADED=0|1` when sensor authority is unavailable.
- Acknowledging a selected-tool sensor outage by resuming should prevent repeated pauses while preserving visible warnings and unverified status.

</specifics>

<deferred>
## Deferred Ideas

- Recursive backup resolution and automatic fallback execution remain in Phase 4.
- External notifications and live-printer verification remain in Phase 5.

</deferred>

---

*Phase: 03-sensor-state-and-purge-lifecycle*
*Context gathered: 2026-06-07*
