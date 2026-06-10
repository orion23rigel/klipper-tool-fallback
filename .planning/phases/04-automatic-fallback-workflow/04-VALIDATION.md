---
phase: 04
slug: automatic-fallback-workflow
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-08
---

# Phase 04 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none |
| **Quick run command** | `pytest -q tests/test_tool_fallback_fallback.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | < 15 seconds |

## Sampling Rate

- **After every task commit:** Run the task-specific pytest command from the plan.
- **After every plan wave:** Run `pytest -q`.
- **Before phase verification:** Run `python3 -m py_compile klippy/extras/tool_fallback*.py && pytest -q`.
- **Max feedback latency:** 15 seconds.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | FALL-01, FALL-02, FALL-03 | T-04-01 | Explicit pause ownership prevents user-pause auto-resume and fallback-before-confirmation | integration | `pytest -q tests/test_tool_fallback_fallback.py -k "ownership or transient or debounce"` | No - Wave 0 | Pending |
| 04-01-02 | 01 | 1 | FALL-04, FALL-05 | T-04-02 | DFS traversal contains loops, trusts persisted loaded state, and re-scans once before exhaustion | unit | `pytest -q tests/test_tool_fallback_fallback.py -k "resolver or graph or loop or rescan"` | No - Wave 0 | Pending |
| 04-01-03 | 01 | 1 | FALL-08 | T-04-03 | Runtime checkpoint is JSON-safe and conflicting workflows are rejected | integration | `pytest -q tests/test_tool_fallback_fallback.py -k "checkpoint or conflict or status"` | No - Wave 0 | Pending |
| 04-02-01 | 02 | 2 | FALL-06, FALL-07 | T-04-04 | Failed target capture/shutdown and backup preheat preserve heater safety and stage ordering | integration | `pytest -q tests/test_tool_fallback_fallback.py -k "heater or target or preheat"` | No - Wave 0 | Pending |
| 04-02-02 | 02 | 2 | FALL-07, FALL-08 | T-04-05 | Heating deadline and guarded RESUME cannot bypass incomplete fallback | integration | `pytest -q tests/test_tool_fallback_fallback.py -k "timeout or RESUME or heating"` | No - Wave 0 | Pending |
| 04-02-03 | 02 | 2 | ROUTE-05 | T-04-06 | Manual active-route transitions complete temperature/select/purge/persist/resume stages | integration | `pytest -q tests/test_tool_fallback_routing.py -k "temperature or heater or active_transition"` | Yes | Pending |
| 04-03-01 | 03 | 3 | FALL-01 through FALL-08 | T-04-07 | Confirmed runout executes one complete fail-closed fallback workflow | workflow | `pytest -q tests/test_tool_fallback_fallback.py -k "success or workflow or exhausted"` | No - Wave 0 | Pending |
| 04-03-02 | 03 | 3 | FALL-07, FALL-08 | T-04-08 | Selection/purge errors and post-return overruns stop without selecting another backup | workflow | `pytest -q tests/test_tool_fallback_fallback.py -k "selection or purge or overrun or failure"` | No - Wave 0 | Pending |

## Wave 0 Requirements

- [ ] `tests/test_tool_fallback_fallback.py` - graph resolution, ownership, heaters, stage timeouts, guarded resume, full fallback workflow.
- [ ] `tests/conftest.py` - fake heaters/heater manager, elapsed-time adapters, captured resume handler, workflow event ordering.
- [ ] Existing pytest infrastructure covers framework setup.

## Timeout Contract

- Heating is asynchronous and must enforce a real reactor deadline.
- Physical selection and purge G-code are synchronous and cannot be safely preempted.
- Selection/purge timeouts therefore enforce exceptions and post-return elapsed-time overruns, then fail closed.
- Tests must not claim arbitrary G-code cancellation.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real heater target transfer, ooze-blocker preheat ordering, and toolchanger safety | FALL-06, FALL-07 | Requires a live printer and representative toolchanger | Deferred until Phase 5 integration verification. |
| Complete automatic fallback and guarded resume on representative hardware | FALL-01 through FALL-08, ROUTE-05 | Requires supervised live runout and failure testing | Deferred until Phase 5 integration verification. |

## Validation Sign-Off

- [x] All tasks have automated verification or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing test references.
- [x] No watch-mode flags.
- [x] Feedback latency < 15 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-08
