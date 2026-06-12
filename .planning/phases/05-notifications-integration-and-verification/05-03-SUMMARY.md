---
phase: 05-notifications-integration-and-verification
plan: 05-03
subsystem: runtime-notifications
tags: [klipper, notifications, fallback, safety, pytest]

requires:
  - phase: 05-01
    provides: Atomic immediate backup policy operations
  - phase: 05-02
    provides: Ordered queued backup operations and terminal drain hook
provides:
  - Bounded fixed-field safety-neutral terminal notification transport
  - Generation-level immutable final-event latch and notification re-entry guard
  - Final notification timing before queued backup-policy drain
affects: [06-examples-and-live-integration, notification-adapters, automatic-fallback]

tech-stack:
  added: []
  patterns: [final-event latch before adapter invocation, notification-before-drain terminalization]

key-files:
  created:
    - tests/test_tool_fallback_notifications.py
  modified:
    - klippy/extras/tool_fallback.py
    - tests/conftest.py
    - tests/test_tool_fallback_fallback.py

key-decisions:
  - "The first complete immutable TerminalEvent for a workflow generation is latched before adapter invocation; all later events for that generation are suppressed."
  - "Only UNEXPECTED_FAILURE transports bounded sanitized REASON_DETAIL; stable known reason codes keep detailed diagnostics local."
  - "Automatic terminal outcomes notify after final state is established and before queued backup policy drains; manual route failures never emit fallback events."

patterns-established:
  - "Terminal observation: establish outcome, latch immutable event, invoke best-effort adapter, then drain future policy."
  - "Notification isolation: reject extension command re-entry and contain adapter recursion, delay, and exceptions locally."

requirements-completed: [NOTIFY-01, NOTIFY-02, NOTIFY-03, BACKUP-01, BACKUP-02, BACKUP-03, BACKUP-04, BACKUP-05]

duration: 35 min
completed: 2026-06-12
---

# Phase 05 Plan 03: Safety-Neutral Terminal Notifications And Contract Verification Summary

**Fixed bounded terminal events with generation-level deduplication, adapter isolation, and notification-before-queue-drain ordering**

## Performance

- **Duration:** 35 min
- **Started:** 2026-06-12T15:20:00-04:00
- **Completed:** 2026-06-12T15:55:00-04:00
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added stable fallback success, fallback failure, and transient-recovery observations
  with fixed canonical fields, `n/a` sentinels, stable reason codes, and bounded safe
  unexpected-failure detail.
- Added immutable per-generation final-event latching plus recursion, exception, delay,
  and extension-command re-entry isolation.
- Routed automatic fallback terminal outcomes through notification-before-drain ordering
  while preserving recoverable heating timeout and all existing safety behavior.
- Closed deterministic Phase 5 coverage with a full suite of 312 passing tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build bounded notification transport and adversarial isolation** - `d0c9692` (feat)
2. **Task 2: Refactor terminal outcomes and verify notification-before-drain ordering** - `be8cbec` (feat)
3. **Task 3: Close Phase 5 automated contract coverage** - `d66058b` (test)

## Files Created/Modified

- `klippy/extras/tool_fallback.py` - Terminal event model, bounded transport, finalizers,
  event latch, adapter guard, and terminal integration.
- `tests/conftest.py` - Deterministic synchronous notification adapter callback support.
- `tests/test_tool_fallback_notifications.py` - Payload, latch, re-entry, failure,
  ordering, manual-silence, and runtime-only coverage.
- `tests/test_tool_fallback_fallback.py` - Final outcome timing and reason-code
  integration assertions.

## Decisions Made

- Kept notification delivery synchronous and best-effort; delay is observable but does
  not introduce cancellation, retry, queue, or delivery guarantees.
- Kept the finalized-event latch runtime-only so persisted schema remains version 1.
- Used explicit reason codes at known terminal paths and sanitized detail only for
  unexpected failures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Resumed Wave 3 locally after executor usage-limit failure**
- **Found during:** Wave 3 dispatch
- **Issue:** The delegated executor stopped before making any edits because its usage
  allowance was exhausted.
- **Fix:** Verified the safe-resume gate, then executed all plan tasks sequentially on
  the main worktree.
- **Files modified:** All Plan 05-03 files.
- **Verification:** No partial Wave 3 commit or summary existed before local execution;
  all planned verification commands pass.
- **Committed in:** `d0c9692`, `be8cbec`, `d66058b`

**2. [Rule 2 - Missing Critical] Prevented known reason codes from carrying detail**
- **Found during:** Task 3 contract audit
- **Issue:** The generic script builder could transport detail supplied with a known
  reason code, contrary to the fixed safe contract.
- **Fix:** Restricted external `REASON_DETAIL` to `UNEXPECTED_FAILURE`.
- **Files modified:** `klippy/extras/tool_fallback.py`,
  `tests/test_tool_fallback_notifications.py`
- **Verification:** Focused notification/backup suite and full suite pass.
- **Committed in:** `d66058b`

---

**Total deviations:** 2 auto-fixed (1 blocking execution recovery, 1 missing critical contract guard)
**Impact on plan:** Both fixes were required to complete the approved plan safely; no scope was added.

## Issues Encountered

- Existing third-party `pytest_asyncio` deprecation warnings remain under Python 3.14;
  they do not affect Phase 5 behavior.

## Verification

- `python3 -m py_compile klippy/extras/tool_fallback*.py` - PASS
- `pytest -q tests/test_tool_fallback_notifications.py tests/test_tool_fallback_backups.py` - PASS, 37 tests
- Focused terminal notification/queue suite - PASS, 39 tests
- `pytest -q` - PASS, 312 tests
- `git diff --check` - PASS
- Persisted schema audit - PASS; queue, notification, latch, and delivery state remain runtime-only.

## User Setup Required

None - notification adapter configuration and representative integration examples remain
part of Phase 6.

## Next Phase Readiness

- Phase 5 runtime contracts are complete and ready for independent phase verification.
- Phase 6 can build representative notification adapter examples and live-printer
  evidence against the stable event and backup-policy command contracts.

## Self-Check: PASSED

All three task commits exist, all plan verification commands pass, the full deterministic
suite reports 312 passing tests, and no Phase 6 live-printer or example work was added.

---
*Phase: 05-notifications-integration-and-verification*
*Completed: 2026-06-12*
