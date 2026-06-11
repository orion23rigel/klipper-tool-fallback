---
phase: 02
slug: command-routing-and-manual-remapping
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-07
---

# Phase 02 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none |
| **Quick run command** | `pytest -q tests/test_tool_fallback_routing.py tests/test_tool_fallback_state.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | < 10 seconds |

## Sampling Rate

- **After every task commit:** Run the task-specific pytest command from the plan.
- **After every plan wave:** Run `pytest -q`.
- **Before phase verification:** Run `python3 -m py_compile klippy/extras/tool_fallback*.py && pytest -q`.
- **Max feedback latency:** 10 seconds.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ROUTE-02, ROUTE-03 | T-02-01 | Handler capture fails closed and restores originals | integration | `pytest -q tests/test_tool_fallback_routing.py -k "capture or missing_handler or rollback"` | No - Wave 0 | Pending |
| 02-01-02 | 01 | 1 | ROUTE-02, ROUTE-03 | T-02-02 | Logical routing invokes saved physical handler without recursion | integration | `pytest -q tests/test_tool_fallback_routing.py -k "logical or physical_handler or ownership"` | No - Wave 0 | Pending |
| 02-02-01 | 02 | 2 | ROUTE-04 | T-02-03 | Mapping mutations remain canonical and immutable | unit | `pytest -q tests/test_tool_fallback_state.py -k mapping` | Yes | Pending |
| 02-02-02 | 02 | 2 | ROUTE-03, ROUTE-04 | T-02-04 | Commands validate names, publish only persisted state, and reject changed active routes during active jobs until Plan 02-03 | integration | `pytest -q tests/test_tool_fallback_routing.py -k "remap or restore or reset or bypass or active_route_rejected"` | No - Wave 0 | Pending |
| 02-03-01 | 03 | 3 | ROUTE-05 (partial: transition ownership/routing safety) | T-02-05 | Active transitions preserve pause ownership and reject reentrancy | integration | `pytest -q tests/test_tool_fallback_routing.py -k "active or pause or transition"` | No - Wave 0 | Pending |
| 02-03-02 | 03 | 3 | ROUTE-05 (partial: transition ownership/routing safety) | T-02-06 | Failures leave the print paused and preserve published mapping state | integration | `pytest -q tests/test_tool_fallback_routing.py -k "failure or rollback or resume"` | No - Wave 0 | Pending |

## Wave 0 Requirements

- [ ] `tests/test_tool_fallback_routing.py` - routing, bypass, manual command, and transition test module.
- [ ] `tests/conftest.py` - synthetic G-code commands, physical-handler spies, print state, script recording, and failure injection.
- [ ] Existing pytest infrastructure covers framework setup.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Representative printer macros receive the expected synthetic physical `Tn` command identity | ROUTE-03 | Requires a real Klipper installation and printer-specific macros | Deferred until the software is more feature complete and installed for Phase 5 integration verification. |
| Active-print remap safely pauses, physically selects, and resumes on representative hardware | ROUTE-05 | Requires a live printer and safe operator supervision | Deferred until the software is more feature complete and installed for Phase 5 integration verification. |

## Validation Sign-Off

- [x] All tasks have automated verification or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing test references.
- [x] No watch-mode flags.
- [x] Feedback latency < 10 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-07
