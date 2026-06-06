---
phase: 01-extension-foundation-and-persistence
plan: 01-01
subsystem: configuration
tags: [klipper, pytest, configuration, validation]

requires: []
provides:
  - Klipper global and prefixed configuration loaders
  - Immutable normalized global and per-tool configuration models
  - Strict lightweight Klipper adapter test fakes
affects: [01-02-state-persistence, 01-03-lifecycle-status, phase-2-routing]

tech-stack:
  added: [pytest]
  patterns: [thin Klipper adapter, immutable normalized configuration, ready-time finalization]

key-files:
  created:
    - klippy/extras/tool_fallback.py
    - klippy/extras/tool_fallback_config.py
    - tests/conftest.py
    - tests/test_tool_fallback_config.py
    - pytest.ini
  modified: []

key-decisions:
  - "Cross-tool validation runs during explicit ready-time finalization after all prefixed sections load."
  - "Canonical tool identities reject leading zeros and all non-uppercase Tn forms."
  - "The default purge adapter is PURGE_TOOL, while all adapter names remain configurable."

patterns-established:
  - "Klipper-facing loaders delegate parsing and validation to pure configuration helpers."
  - "Configuration fakes track every consumed option and fail unexpected object access."

requirements-completed: [ROUTE-01, ADAPT-01]

duration: 7 min
completed: 2026-06-06
---

# Phase 1 Plan 01: Configuration And Test Foundation Summary

**Strict Klipper configuration loaders with immutable normalized tool models and 31 startup-contract tests**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-06T11:15:00Z
- **Completed:** 2026-06-06T11:22:01Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added strict printer, reactor, G-code, command, and config fakes for isolated adapter tests.
- Implemented global and `[tool_fallback Tn]` parsing with normalized paths, positive timing validation, and ready-time cross-tool finalization.
- Added 31 tests covering valid defaults, explicit adapters, canonical identities, immutable results, preserved backup order, and all planned startup failures.

## Task Commits

Each task was committed atomically:

1. **Task 1: Establish the pytest harness and Klipper adapter fakes** - `1423c74` (test)
2. **Task 2: Implement normalized global and per-tool configuration** - `8fed378` (feat)
3. **Task 3: Prove configuration contracts and failure behavior** - `9171cbe` (test)

## Files Created/Modified

- `pytest.ini` - Focused pytest discovery and repository import path.
- `tests/conftest.py` - Strict lightweight Klipper adapter fakes and fixtures.
- `klippy/extras/tool_fallback.py` - Global and prefixed Klipper configuration loaders.
- `klippy/extras/tool_fallback_config.py` - Immutable normalized models and validation.
- `tests/test_tool_fallback_config.py` - Configuration success and startup-failure contracts.

## Decisions Made

- Cross-tool backup validation is deferred to ready-time finalization because Klipper may load prefixed sections in any order.
- Tool identities must be canonical uppercase `T` plus a non-negative integer without leading zeros.
- Existing `Tn` handlers remain untouched in Phase 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added the repository root to pytest's import path**
- **Found during:** Task 3 (Prove configuration contracts and failure behavior)
- **Issue:** The local pytest environment did not place the repository root on `sys.path`, preventing collection of the extension package.
- **Fix:** Added `pythonpath = .` to `pytest.ini`.
- **Files modified:** `pytest.ini`
- **Verification:** `pytest -q tests/test_tool_fallback_config.py` passes all 31 tests.
- **Committed in:** `9171cbe`

---

**Total deviations:** 1 auto-fixed (1 blocking issue). **Impact:** Required for deterministic test collection; no product scope change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `01-02-PLAN.md` to build versioned state and atomic persistence on the normalized configuration contracts.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback.py klippy/extras/tool_fallback_config.py` - PASS
- `pytest -q tests/test_tool_fallback_config.py` - PASS, 31 tests
- `pytest -q` - PASS, 31 tests
- `git diff --check` - PASS

## Self-Check: PASSED

All key files exist, all three task commits are present, and every plan-level verification passes.

---
*Phase: 01-extension-foundation-and-persistence*
*Completed: 2026-06-06*
