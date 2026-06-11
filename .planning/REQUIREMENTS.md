# v1.0 Requirements

## Foundation And State

- [x] **ROUTE-01:** Require explicit canonical `[tool_fallback Tn]` tool declarations.
- [x] **STATE-01:** Persist state with deterministic atomic JSON writes.
- [x] **STATE-02:** Preserve schema-versioned tool state, mappings, and backup order.
- [x] **STATE-03:** Reconcile startup state with debounced sensor authority.
- [x] **STATE-04:** Expose deterministic read-only state inspection.
- [x] **ADAPT-01:** Keep printer-specific pause, resume, purge, and notification adapters configurable.

## Routing And Manual Transitions

- [x] **ROUTE-02:** Intercept logical `Tn` commands and resolve persisted mappings.
- [x] **ROUTE-03:** Invoke captured physical handlers directly without recursion.
- [x] **ROUTE-04:** Persistently remap, restore, and reset logical mappings.
- [x] **ROUTE-05:** Safely transition active routes through pause, heater transfer, selection, conditional purge, persistence, and ownership-safe resume.

## Sensor And Purge Lifecycle

- [x] **SENS-01:** Treat configured sensors as optional runtime authorities.
- [x] **SENS-02:** Debounce insertion and removal symmetrically.
- [x] **SENS-03:** Persist confirmed unloading and selected-tool runout semantics.
- [x] **SENS-04:** Persist confirmed insertion and clear failed/purged state correctly.
- [x] **PURGE-01:** Invoke a distinct purge adapter and publish purge truth only after success.
- [x] **PURGE-02:** Never infer purge completion from unrelated extrusion.
- [x] **PURGE-03:** Conditionally purge unpurged tools during active-print selection.
- [x] **PURGE-04:** Allow outside-print selection without automatic purge.
- [x] **PURGE-05:** Provide guarded manual purge-state overrides.

## Automatic Fallback

- [x] **FALL-01:** Preserve standard immediate runout pause behavior with explicit ownership.
- [x] **FALL-02:** Begin fallback actions only after confirmed runout debounce.
- [x] **FALL-03:** Resume transient recovery only when the extension owns the pause.
- [x] **FALL-04:** Resolve ordered backup graphs deterministically with loop containment and one rescan.
- [x] **FALL-05:** Select only loaded, non-failed eligible backups.
- [x] **FALL-06:** Execute the complete ordered fallback workflow and publish the new logical route.
- [x] **FALL-07:** Enforce heating deadlines and post-return selection/purge overruns.
- [x] **FALL-08:** Leave every incomplete fallback paused with a visible blocked checkpoint.

## Traceability

| Requirement | Phase | Final Status |
|-------------|-------|--------------|
| ROUTE-01, STATE-01, STATE-02, STATE-04, ADAPT-01 | 01 | Complete |
| ROUTE-02, ROUTE-03, ROUTE-04 | 02 | Complete |
| STATE-03, SENS-01 through SENS-04, PURGE-01 through PURGE-05 | 03 | Complete |
| ROUTE-05, FALL-01 through FALL-08 | 04 | Complete |

## Deferred Beyond v1.0

- Representative live-printer UAT, including the four pending Phase 1 startup/state scenarios.
- External notification invocation and message integration.
- Runtime backup-list mutation commands.
- Printer-specific installation examples and CI automation.
