---
phase: 01-extension-foundation-and-persistence
reviewed: 2026-06-06T11:41:27Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - klippy/extras/tool_fallback.py
  - klippy/extras/tool_fallback_config.py
  - klippy/extras/tool_fallback_state.py
  - tests/conftest.py
  - tests/test_tool_fallback_config.py
  - tests/test_tool_fallback_state.py
  - tests/test_tool_fallback_extension.py
  - pytest.ini
  - README.md
findings:
  critical: 2
  warning: 2
  info: 0
  total: 4
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-06-06T11:41:27Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 01 establishes the intended configuration, lifecycle, status, and atomic-write
structure, and its 65 tests pass. However, two validation gaps allow values that violate
the safety contracts later phases will trust: impossible persisted purge state and
non-finite timeout values. The persistence parser also accepts ambiguous duplicate JSON
keys, and the test harness globally converts a zero-test run into success.

## Critical Issues

### CR-01: Persisted state accepts an unloaded tool marked as purged

**File:** `klippy/extras/tool_fallback_state.py:66-71`
**Issue:** `FallbackState.from_dict()` validates the three flags independently but does
not validate their relationship. It accepts and republishes
`{"loaded": false, "purged": true}`, even though the design states that confirmed
unloading clears both loaded and purged state. Later selection and fallback workflows
will trust `purged` when deciding whether purge is required, so accepting this impossible
state undermines the safety invariant that purge status applies only to the current
filament load. This also contradicts the Phase 01 research requirement that invalid
invariants block startup.
**Fix:** Validate cross-field tool-state invariants before constructing `ToolState`.
At minimum, reject `purged` when `loaded` is false. Add a strict-parsing regression test
for the rejected combination and document any other permitted `loaded`/`failed`
combinations explicitly.

### CR-02: Positive timing validation accepts NaN and Infinity

**File:** `klippy/extras/tool_fallback_config.py:57-69`
**Issue:** Passing `above=0.0` rejects zero and negative finite numbers, but IEEE `NaN`
compares false to the range check and positive infinity passes it. As a result,
`debounce_time: nan` and all timeout options set to `nan` or `inf` are accepted. A NaN
debounce or timeout can prevent a later deadline comparison from ever completing, while
infinity explicitly disables a safety timeout. Non-finite values also produce
non-standard `NaN`/`Infinity` values in the status JSON.
**Fix:** Parse each timing value through a helper that calls `config.getfloat`, then
rejects values for which `math.isfinite(value)` is false. Add parameterized tests for
`nan`, `inf`, and `-inf` across debounce and timeout options.

## Warnings

### WR-01: Duplicate JSON object keys are silently accepted

**File:** `klippy/extras/tool_fallback_state.py:141-142`
**Issue:** `json.load()` silently keeps the final value when a persisted JSON object
contains duplicate keys. Duplicate tool records, mappings, or fields therefore bypass
the strict-schema policy and can silently discard operator state instead of blocking
startup as malformed or ambiguous state. The later exact-field and reference checks
cannot detect keys that the decoder already discarded.
**Fix:** Decode with an `object_pairs_hook` that raises `StateValidationError` when a key
appears more than once. Add tests for duplicate top-level fields, tool names, tool
fields, and mapping keys.

### WR-02: The test harness reports success when no tests are collected

**File:** `tests/conftest.py:4-6`
**Issue:** The session-finish hook globally rewrites pytest's
`NO_TESTS_COLLECTED` failure into success. A broken discovery configuration, accidental
test deletion, or incorrectly scoped CI command can therefore pass without executing
any verification. This directly weakens the phase's automated quality gate.
**Fix:** Remove the hook. If a specific bootstrap or collection-only workflow genuinely
needs zero tests to succeed, handle that explicitly in that workflow instead of changing
the result of every pytest invocation.

## Verification

- `pytest -q`: passed, 65 tests
- `python3 -m py_compile klippy/extras/tool_fallback.py klippy/extras/tool_fallback_config.py klippy/extras/tool_fallback_state.py`: passed
- `git diff --check`: passed
- Reproduced acceptance of `loaded=false, purged=true`
- Reproduced acceptance of `debounce_time: nan` and `debounce_time: inf`

---

_Reviewed: 2026-06-06T11:41:27Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
