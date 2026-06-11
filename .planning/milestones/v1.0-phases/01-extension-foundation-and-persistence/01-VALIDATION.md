---
phase: 1
slug: extension-foundation-and-persistence
created: 2026-06-06
status: draft
---

# Phase 1 Validation Strategy

## Objective

Verify that Phase 1 produces a trustworthy, independently testable configuration and
persistence foundation before routing and workflow behavior depends on it.

## Test Layers

| Layer | Scope | Command |
|-------|-------|---------|
| Syntax | All extension modules | `python3 -m py_compile klippy/extras/tool_fallback*.py` |
| Unit | State schema, reconciliation, atomic store | `pytest -q tests/test_tool_fallback_state.py` |
| Adapter | Config parsing and Klipper-facing status behavior | `pytest -q tests/test_tool_fallback_config.py tests/test_tool_fallback_extension.py` |
| Phase | Entire Phase 1 behavior | `pytest -q` |

## Requirement Coverage

| Requirement | Evidence |
|-------------|----------|
| ROUTE-01 | Global/prefixed config tests prove explicit managed tool configuration |
| STATE-01 | Atomic write success and injected failure-path tests |
| STATE-02 | Round-trip and reconciliation tests preserve canonical fields |
| STATE-04 | `get_status()` and `SHOW_TOOL_FALLBACK_STATE` integration tests |
| ADAPT-01 | Configurable adapter values parse without toolchanger dependencies |

## Nyquist Rules

- Every implementation task includes a directly runnable automated verification.
- State mutation and persistence failure paths receive unit tests in the same task.
- No task may rely only on manual inspection.
- The final plan runs the full suite and syntax compilation.
- Later-phase interfaces are validated as data/API contracts without implementing their
  behavior early.

## Manual Checks

None required for Phase 1. A representative real Klipper configuration is deferred to
Phase 5 after routing and sensor integration exist.
