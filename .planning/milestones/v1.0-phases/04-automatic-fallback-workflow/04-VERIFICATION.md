---
phase: "04"
slug: automatic-fallback-workflow
verified: 2026-06-11
status: passed
requirements_verified:
  - ROUTE-05
  - FALL-01
  - FALL-02
  - FALL-03
  - FALL-04
  - FALL-05
  - FALL-06
  - FALL-07
  - FALL-08
gaps: []
human_verification:
  - Representative live-printer heater, runout, purge, and resume behavior
---

# Phase 04: Automatic Fallback Workflow Verification

## Result

**Status:** PASSED

Phase 04 completes the automatic fallback loop and the active-route transition
requirement. A post-completion integration audit found and closed four fail-closed
control-flow gaps plus missing logical-route publication. The corrected implementation
stops on every blocked stage, enforces purge post-return overruns, preserves visible
resume-failure checkpoints, and persists the selected backup as the active logical
route.

## Requirement Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FALL-01 | SATISFIED | Standard runout pause behavior remains authoritative; ownership is explicit through `PAUSE_OWNED`. |
| FALL-02 | SATISFIED | Heater and backup actions begin only after confirmed debounce and failed-state persistence. |
| FALL-03 | SATISFIED | Transient recovery resumes only explicitly owned pauses. |
| FALL-04 | SATISFIED | Ordered DFS traversal contains loops and performs exactly one fresh exhaustion rescan. |
| FALL-05 | SATISFIED | Automatic candidates require durable loaded and non-failed state; unknown authority warns without guessing. |
| FALL-06 | SATISFIED | Confirmed fallback orders shutdown, resolution, preheat, selection, heating, purge, mapping persistence, and owned resume. |
| FALL-07 | SATISFIED | Heating uses a reactor deadline; selection and purge reject synchronous post-return overruns. |
| FALL-08 | SATISFIED | Blocked stages terminate execution and retain visible paused checkpoints; only heating timeout has guarded continuation. |
| ROUTE-05 | SATISFIED | Active manual route transitions reuse fail-closed heater, selection, purge, persistence, and ownership-safe resume stages. |

## Integration Audit Closure

| Finding | Resolution |
|---------|------------|
| Blocked heater stages could continue | All automatic and manual stage callers now treat `stage=blocked` as terminal; regressions prove no selection, purge, persistence, or resume follows. |
| Resume failure lost checkpoint | Completion retains the saved checkpoint and recreates a visible blocked checkpoint on resume failure. |
| Purge timeout was unused | Purge adapters now reject post-return elapsed-time overruns before purge-state publication. |
| Documentation could not produce owned fallback | README and design use a distinct purge adapter and explicit `PAUSE_OWNED=1` sensor hook. |
| Successful fallback did not publish new route | Normal and guarded-resume completion persist the selected backup for the active logical tool. |

## Automated Verification

| Command | Result |
|---------|--------|
| `python3 -m py_compile klippy/extras/tool_fallback.py klippy/extras/tool_fallback_config.py klippy/extras/tool_fallback_state.py` | PASS |
| `pytest -q tests/test_tool_fallback_fallback.py` | PASS: 47 tests |
| `pytest -q tests/test_tool_fallback_purge.py tests/test_tool_fallback_routing.py` | PASS: 73 tests |
| `pytest -q` | PASS: 260 tests |
| `git diff --check` | PASS |

## Deferred Items

- Representative hardware verification remains deferred to Phase 5 by user direction.
- External notifications and runtime backup-list mutation commands remain beyond v1.0.
- Existing environment-level `pytest-asyncio` deprecation warnings remain.

## Residual Risk

Deterministic fakes verify ordering, persistence, ownership, deadlines, and
failure-containment behavior. They cannot prove printer-specific macro semantics,
physical toolchanger behavior, heater dynamics, or real sensor polarity. Those risks
remain explicitly deferred to supervised hardware UAT.
