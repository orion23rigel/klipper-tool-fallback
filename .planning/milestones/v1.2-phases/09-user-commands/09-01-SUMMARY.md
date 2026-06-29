---
phase: 09-user-commands
plan: 01
subsystem: tool-fallback-state
tags: [state-mutation, user-defined-backup, frozen-dataclass]
dependency_graph:
  requires: []
  provides: "FallbackState.with_user_defined_backup() mutation method"
  affects: [tool_fallback.py, test_tool_fallback_extension.py]
tech_stack:
  added: []
  patterns: ["frozen dataclass mutation", "MappingProxyType", "no-op identity return"]
key_files:
  created: []
  modified:
    - klippy/extras/tool_fallback_state.py
    - tests/test_tool_fallback_state.py
decisions:
  - "with_user_defined_backup follows with_mapping pattern: validates both endpoints, no-op check, new instance via _canonical"
  - "None backup value removes the entry from the dict (not sets to None)"
metrics:
  duration_minutes: 2
  completed: "2026-06-29"
status: complete
---

# Phase 09 Plan 01: with_user_defined_backup Mutation Method

Add `with_user_defined_backup(logical, backup)` mutation method to `FallbackState` and its test suite. This is the foundational state mutation API that DEFINE_TOOL_BACKUP and UNDEFINE_TOOL_BACKUP commands will call.

## Summary

Implemented `with_user_defined_backup(logical, backup)` on `FallbackState` using the frozen dataclass mutation pattern. The method validates inputs (configured tools, no self-references), detects no-ops (returns `self`), and returns a new canonical state instance. 8 test cases added covering define, undefine, no-op, self-reference rejection, unknown tool rejection, preservation of other mappings, and immutability.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All 80 state tests pass (72 original + 8 new). Full test suite: 375 tests pass.
