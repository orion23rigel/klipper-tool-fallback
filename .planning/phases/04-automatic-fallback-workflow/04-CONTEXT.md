# Phase 4: Automatic Fallback Workflow - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the complete confirmed-runout fallback workflow: explicit pause ownership,
transient recovery, recursive ordered backup resolution, temperature capture and
transfer, failed-heater shutdown, stage timeouts, physical selection, conditional purge,
persistent remapping, guarded resume, and recoverable paused failures.

Meaningful external notification adapters and live-printer integration verification
remain in Phase 5.

</domain>

<decisions>
## Implementation Decisions

### Backup Resolution Policy
- **D-01:** Resolve backup graphs depth-first in configured priority order. Fully traverse each candidate's ordered backup chain before moving to the next sibling.
- **D-02:** Failed tools are never selectable, but their backup chains remain traversable. A failed intermediary may still lead to an eligible tool.
- **D-03:** Prevent recursion with deterministic loop detection and report loops/skipped tools without aborting traversal of other reachable branches.
- **D-04:** Eligibility requires persisted `loaded=true` and `failed=false`. Current sensor authority may be unknown; removing or disabling a sensor preserves the last confirmed or explicit persisted loaded fact.
- **D-05:** A sensor-unavailable candidate with persisted `loaded=true` remains automatically eligible but must emit a warning that loaded state is not live-verified.
- **D-06:** A sensor-unavailable candidate with persisted `loaded=false` remains ineligible until an operator or load-filament macro explicitly sets it loaded.
- **D-07:** Before declaring backups exhausted, re-scan the complete reachable graph once so a tool that became eligible during the workflow can be selected.
- **D-08:** If the re-scan still finds no eligible candidate, leave the print paused and report attempted, skipped, failed, unloaded, and looped tools.

### Temperature And Heater Behavior
- **D-09:** At confirmed runout, capture the failed physical tool heater's requested target temperature.
- **D-10:** If the failed tool target is zero, missing, or unavailable, warn/notify the operator, stop fallback, and remain paused. Never guess a printing or purge target.
- **D-11:** After capturing a valid target, turn off the failed tool heater immediately.
- **D-12:** Once an eligible backup is chosen, set its heater target and begin preheating before physical selection. This keeps toolchanger tools on the ooze blocker longer.
- **D-13:** Do not override or weaken Klipper's heater safety behavior.

### Timeout And Failure Recovery
- **D-14:** A physical selection error or selection timeout stops fallback immediately and leaves the print paused. Never try another backup because physical machine state may be unsafe or unknown; toolchanger-specific recovery is out of scope.
- **D-15:** Heating waits under Klipper's normal safety behavior. A configurable heating timeout warns and leaves the print paused; never try another backup automatically.
- **D-16:** Preserve a recoverable workflow checkpoint after heating timeout. On normal `RESUME`, recheck the current backup heater and continue from the next stage only if the required target has been reached. Otherwise reject resume, warn, and remain paused.
- **D-17:** A purge failure or purge timeout stops fallback and leaves the print paused. Do not retry automatically or try another backup.
- **D-18:** Selection, purge, persistence, rollback, or other non-heating failures reject normal `RESUME` until explicitly corrected; automatic fallback must not be bypassed.
- **D-19:** Every incomplete fallback workflow remains paused and exposes a recoverable status/checkpoint where safe.

### Pause Ownership And Transient Recovery
- **D-20:** Use an explicit runout-hook pause ownership contract, such as `TOOL_FALLBACK_RUNOUT TOOL=Tn PAUSE_OWNED=1`, rather than inferring ownership from print-state timing.
- **D-21:** Auto-resume after transient runout or completed fallback only when explicit pause ownership proves the extension owns the pause.
- **D-22:** If a runout signal clears before debounce confirms failure, and pause ownership is explicit, automatically resume only after confirmed reinsertion.
- **D-23:** User-owned pauses never auto-resume. Transient recovery may update/report state while preserving the pause.
- **D-24:** While fallback is active or blocked at a non-heating failure, user `RESUME` is rejected and the print remains paused.
- **D-25:** Guarded normal `RESUME` is the recovery entry point for heating timeout only; it must validate readiness before continuing.

### Complete Safe Transition
- **D-26:** Fallback order is: confirm runout and ownership, capture valid failed-tool target, turn off failed heater, resolve/re-scan backup graph, preheat chosen backup, select physically, wait for target, conditionally purge, persist logical remap/workflow state, and resume only when owned.
- **D-27:** Manual active-route transitions use the same temperature-transfer/stage-execution infrastructure where applicable, completing ROUTE-05 without weakening Phase 2/3 pause, purge, persistence, and failure-containment guarantees.

### the agent's Discretion
- Exact workflow checkpoint representation and status field names.
- Exact heater adapter/API integration, provided it uses configured heater ownership and preserves Klipper safety behavior.
- Exact warning/error wording and attempted-tool report format.
- Internal implementation of deterministic graph traversal, stage timers, and guarded `RESUME` interception.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product And Scope
- `.planning/PROJECT.md` - Core value, safety constraints, compatibility constraints, and fallback goals.
- `.planning/ROADMAP.md` - Phase boundary and Phase 4 ownership of complete ROUTE-05 integration.
- `.planning/REQUIREMENTS.md` - FALL-01 through FALL-08 and ROUTE-05 acceptance requirements.
- `.planning/STATE.md` - Verified decisions and implementation foundation from earlier phases.

### Behavioral Design
- `.planning/DESIGN.md` - Existing fallback sequence, backup graph, heater, purge, resume, and safety contract. Decisions above refine backup eligibility and preheat ordering.

### Sensor And Purge Integration Contract
- `.planning/phases/03-sensor-state-and-purge-lifecycle/03-CONTEXT.md` - Locked unknown-sensor, failed-state, purge, and pause behavior.
- `.planning/phases/03-sensor-state-and-purge-lifecycle/03-VERIFICATION.md` - Verified sensor authority, conditional purge, transition ordering, and explicit Phase 4 boundary.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `klippy/extras/tool_fallback.py`: Owns sensor-confirmed runout context, pause/resume adapters, active transition coordination, private physical selection, conditional purge, persistence, and empty Phase 4 pre-selection hook.
- `klippy/extras/tool_fallback_state.py`: Owns persisted mappings, ordered backup graphs, loaded/purged/failed facts, and immutable state candidates.
- `klippy/extras/tool_fallback_config.py`: Already loads per-tool heaters and selection/heating/purge timeouts.
- `tests/conftest.py`: Provides deterministic reactor timers, fake print state, script ordering, sensors, and failure injection.

### Established Patterns
- Durable state changes use immutable candidates and save-before-publish.
- Any incomplete active transition remains paused.
- Physical selection is recursion-free and selection errors preserve machine safety.
- Conditional purge executes before route persistence and owned resume.
- Sensor authority is runtime-only; persisted loaded state remains durable eligibility evidence.

### Integration Points
- Extend confirmed-runout handling into an explicit fallback workflow checkpoint/state machine.
- Implement recursive graph resolution over persisted ordered backups.
- Fill the Phase 4 pre-selection temperature-transfer hook and reuse post-selection purge integration.
- Add heater status/target adapters and deterministic stage timeout handling.
- Guard/intercept normal resume while a fallback checkpoint is active.
- Extend fake heater/tool-selection support and add focused fallback workflow tests.

</code_context>

<specifics>
## Specific Ideas

- Preheat the backup before physical selection so a toolchanger tool stays on its ooze blocker longer.
- Physical selection failures must never cause another automatic tool selection because a tool may be hanging in an unsafe position.
- Normal `RESUME` should recover a heating timeout only after validating that the selected backup reached the required target.

</specifics>

<deferred>
## Deferred Ideas

- Meaningful external notifications, example configuration, and live-printer integration verification remain in Phase 5.

</deferred>

---

*Phase: 04-automatic-fallback-workflow*
*Context gathered: 2026-06-08*
