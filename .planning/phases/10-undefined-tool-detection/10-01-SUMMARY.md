---
phase: 10-undefined-tool-detection
plan: 01
subsystem: api
tags: [klipper, gcode, tool-routing, undefined-tool, workflow-checkpoint]

# Dependency graph
requires:
  - phase: 09-user-commands
    provides: "Tool fallback extension infrastructure, gcode command registration patterns, FakeGCmd/FakePrinter test harness"
  - phase: 08-state-schema-extension
    provides: "FallbackState schema, StateStore persistence, WorkflowCheckpoint dataclass"
provides:
  - "_TOOL_FALLBACK_TN wrapper G-code command for tool selection"
  - "Undefined-tool detection via WorkflowCheckpoint(source='undefined_tool')"
  - "T parameter validation with TOOL_NAME_RE regex"
  - "7 new tests for _TOOL_FALLBACK_TN command"
affects:
  - 11-prompt-flow
  - 12-fallback-integration

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wrapper command pattern: internal command with underscore prefix intercepts and routes"
    - "Checkpoint-based signaling: source + stage + generation for cross-phase communication"
    - "Guard-then-parse-then-validate-then-act command structure"

key-files:
  created:
    - tests/test_tool_fallback_extension.py (7 new tests)
  modified:
    - klippy/extras/tool_fallback.py (_TOOL_FALLBACK_TN command + registration)

key-decisions:
  - "Used gcmd.get('T', None) instead of gcmd.get('T') to allow None default for missing parameter detection"
  - "Logging via self.gcode.respond_info() rather than gcmd.respond_info() for info messages"
  - "Undefined-tool checkpoint uses pause_owned=False — Phase 11 handles pausing"

patterns-established:
  - "Wrapper command: guard → parse → validate → route/trigger"
  - "Checkpoint signaling: WorkflowCheckpoint with source='undefined_tool' for Phase 11 consumption"
  - "Info messages use self.gcode.respond_info() (goes to gcode.responses), not gcmd.respond_info()"

requirements-completed: [DETECT-01, DETECT-02, DETECT-03, DETECT-04]

# Metrics
duration: 10min
completed: 2026-06-29
status: complete
---

# Phase 10 Plan 01: Summary

**_TOOL_FALLBACK_TN wrapper G-code command with T parameter validation, configured-tool routing delegation, and undefined-tool detection via WorkflowCheckpoint**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-29T04:08:00Z
- **Completed:** 2026-06-29T04:10:26Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments
- Implemented `_TOOL_FALLBACK_TN` wrapper command in `ToolFallback` class with full validation and routing logic
- Registered command in `__init__` with info message "Tool fallback routing initialized"
- Implemented T parameter parsing, format validation via `TOOL_NAME_RE`, and configured/unconfigured tool branching
- Configured tools delegate to `_route_logical`; unconfigured tools create `WorkflowCheckpoint(source="undefined_tool", stage="tool_not_configured")`
- Added 7 comprehensive tests covering registration, missing T, invalid format, configured delegation, undefined trigger, no-pause guarantee, and not-initialized guard
- All 397 tests pass (390 existing + 7 new)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement _TOOL_FALLBACK_TN command** - `da133a6` (feat)
2. **Task 2: Add 7 tests for _TOOL_FALLBACK_TN** - `6d94046` (test)

**Plan metadata:** `e2f42b0` (docs: create phase 10 plan)

## Files Created/Modified
- `klippy/extras/tool_fallback.py` — Added `cmd_TOOL_FALLBACK_TN` method (40 lines) and command registration in `__init__`
- `tests/test_tool_fallback_extension.py` — Added 7 test functions for `_TOOL_FALLBACK_TN` command (87 lines)

## Decisions Made
- Used `gcmd.get("T", None)` with explicit `None` default to properly detect missing T parameter (plan specified `gcmd.get("T")` but Klipper's FakeGCmd raises on missing params without a default)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed T parameter parsing to use explicit None default**
- **Found during:** Task 2 (test execution)
- **Issue:** Plan specified `gcmd.get("T")` which in FakeGCmd raises `CommandError("Parameter 'T' must be specified")` rather than returning `None` when T is absent. The test expected the custom error message "_TOOL_FALLBACK_TN requires a T parameter" but got the generic Klipper parameter error.
- **Fix:** Changed to `gcmd.get("T", None)` with explicit `None` default so missing T returns `None` and the custom error message is raised.
- **Files modified:** klippy/extras/tool_fallback.py
- **Verification:** test_tool_fallback_tn_missing_t_parameter passes
- **Committed in:** `6d94046` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed test assertion to check printer.gcode.responses**
- **Found during:** Task 2 (test execution)
- **Issue:** Tests checked `gcmd.responses` but implementation uses `self.gcode.respond_info()` which appends to `printer.gcode.responses`, not the FakeGCmd object.
- **Fix:** Changed test assertions to check `printer.gcode.responses` for info messages.
- **Files modified:** tests/test_tool_fallback_extension.py
- **Verification:** All 7 new tests pass
- **Committed in:** `6d94046` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep.

## Issues Encountered
- None — deviations were minor implementation details caught during testing.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 10 (undefined-tool detection) is complete
- Phase 11 (prompt flow) can now consume `WorkflowCheckpoint(source="undefined_tool")` and implement the user interaction flow
- The checkpoint infrastructure is in place with `source="undefined_tool"`, `stage="tool_not_configured"`, and `logical_tool` populated

---
*Phase: 10-undefined-tool-detection*
*Completed: 2026-06-29*
