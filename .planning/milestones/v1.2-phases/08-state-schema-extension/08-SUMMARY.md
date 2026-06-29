---
phase: 08-state-schema-extension
plan: 08
subsystem: state
tags: [klipper, state-schema, backward-compatibility, dataclass]

# Dependency graph
requires:
  - phase: 07
    provides: core state persistence and ToolState/FallbackState dataclasses
provides:
  - "Schema version bumped from 1 to 2"
  - "ToolState.user_defined_backup field (str | None, defaults to None)"
  - "FallbackState.user_defined_backups field (MappingProxyType dict, defaults to {})"
  - "from_dict() accepts both v1 and v2 state files with implicit migration"
  - "to_dict() always includes user_defined_backups key"
  - "StateStore.save() validates user_defined_backups before serialization"
  - "FallbackState.reconcile() filters user_defined_backups for removed tools"
  - "FallbackState._validate_user_defined_backups() rejects self-references and unknown tools"
affects:
  - "Phase 9: User Commands — DEFINE_TOOL_BACKUP will write to user_defined_backups"
  - "Phase 10: Undefined Tool Detection — will read user_defined_backups"
  - "Phase 12: Fallback Integration — resolve_backup_graph() considers user_defined_backups"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Implicit migration during from_dict() — no separate migration step"
    - "MappingProxyType for immutable dict views on FallbackState"
    - "Validation in save() path before serialization"
    - "Reconcile filters stale user_defined_backups entries"

key-files:
  created: []
  modified:
    - klippy/extras/tool_fallback_state.py
    - tests/test_tool_fallback_state.py
    - tests/test_tool_fallback_extension.py
    - tests/test_tool_fallback_notifications.py
    - tests/test_tool_fallback_sensor.py

key-decisions:
  - "Schema version bumped from 1 to 2 — explicit version signal for schema change"
  - "from_dict() accepts version 1 and 2 — v1 files get user_defined_backups = {}"
  - "user_defined_backups stored as MappingProxyType — consistent with tools/mappings pattern"
  - "_validate_user_defined_backups() called in save() — rejects self-references and unknown tools"
  - "reconcile() filters user_defined_backups to configured tools — removes stale entries"

patterns-established:
  - "Implicit migration: from_dict() fills missing fields with defaults rather than rewriting files"
  - "Validation at save boundary: _validate_user_defined_backups() called before serialization"
  - "Immutable views: user_defined_backups wrapped in MappingProxyType like tools and mappings"
  - "Reconcile cleanup: user_defined_backups entries filtered when tools are removed from config"

requirements-completed: [STATE-01, STATE-02, STATE-03, STATE-04]

# Metrics
duration: 45min
completed: 2026-06-28
status: complete
---

# Phase 08: State Schema Extension Summary

**Schema version bumped to 2 with backward-compatible user_defined_backup fields on ToolState and FallbackState, implicit v1→v2 migration in from_dict(), and validation in save() and reconcile()**

## Performance

- **Duration:** 45 min
- **Started:** 2026-06-28T19:41Z
- **Completed:** 2026-06-28T20:26Z
- **Tasks:** 5
- **Files modified:** 5
- **Tests:** 367 passing

## Accomplishments

- Extended `ToolState` with `user_defined_backup: str | None = None` field (5th field)
- Extended `FallbackState` with `user_defined_backups: object` field (4th field, MappingProxyType)
- Bumped `SCHEMA_VERSION` from 1 to 2
- Updated `from_dict()` to accept both v1 and v2 state files with implicit migration
- Updated `to_dict()` to include `user_defined_backups` and `user_defined_backup` in serialization
- Updated `_canonical()` to accept 4th parameter and sort user_defined_backups by key
- Added `_validate_user_defined_backups()` method — rejects self-references and unknown tool references
- Added validation call in `StateStore.save()` before serialization
- Updated `reconcile()` to filter `user_defined_backups` for removed tools
- Updated all `with_*` mutation methods to preserve `user_defined_backup` through state transitions
- Added 12 new test cases covering all 4 STATE requirements
- All 367 tests passing across 4 test files

## Task Commits

1. **Task 1: Add user_defined_backup to ToolState** - `dff661a` (feat)
2. **Task 2: Add user_defined_backups to FallbackState** - (included in Task 1 commit)
3. **Task 3: Update from_dict() for backward-compatible migration** - (included in Task 1 commit)
4. **Task 4: Add validation in save/reconcile** - (included in Task 1 commit)
5. **Task 5: Write comprehensive tests** - (included in Task 1 commit)

**Plan metadata:** `1d44063` (docs: complete plan)

_Note: All 5 tasks were implemented in a single commit because the changes are interdependent — the implementation was rebuilt from scratch task-by-task to ensure correctness, then committed as a cohesive unit._

## Files Created/Modified

- `klippy/extras/tool_fallback_state.py` — Core implementation: schema v2, new fields, migration, validation, reconcile filtering
- `tests/test_tool_fallback_state.py` — 12 new tests + updated test helper `valid_dict()` to v2 format
- `tests/test_tool_fallback_extension.py` — Version assertion updated from 1 to 2
- `tests/test_tool_fallback_notifications.py` — Version assertion updated from 1 to 2
- `tests/test_tool_fallback_sensor.py` — Tool status dict updated to include user_defined_backup field

## Decisions Made

- Schema version bumped from 1 to 2 — explicit version signal for schema change
- `from_dict()` accepts version 1 and 2 — v1 files get `user_defined_backups = {}` implicitly
- `user_defined_backups` stored as `MappingProxyType` — consistent with `tools` and `mappings` pattern
- `_validate_user_defined_backups()` called in `save()` — rejects self-references and unknown tool references
- `reconcile()` filters `user_defined_backups` to configured tools — removes stale entries automatically

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _require_fields exact-match broke v1 state loading**
- **Found during:** Task 1 (implementation)
- **Issue:** The original `_require_fields()` does exact set matching. Changing the allowed fields to include `user_defined_backup` caused v1 state files (without the field) to fail validation.
- **Fix:** Replaced `_require_fields(data, {...}, "state")` with explicit `for required in (...)` checks that only verify required fields are present, allowing unknown/additional fields for backward compatibility.
- **Files modified:** `klippy/extras/tool_fallback_state.py`
- **Verification:** v1 state files load successfully with `user_defined_backups = {}`

**2. [Rule 1 - Bug] ToolState constructor calls missing user_defined_backup arg**
- **Found during:** Task 1 (testing)
- **Issue:** All `with_*` mutation methods construct new `ToolState` instances but only passed 4 arguments. With the 5th field added, these calls failed with `TypeError`.
- **Fix:** Updated 10+ `ToolState()` constructor calls across `with_mapping`, `with_backups`, `with_all_backups`, `with_filament_loaded`, `with_reconciled_filament_loaded`, `with_filament_unloaded`, `with_failed_runout`, `with_tool_purged`, `with_tool_unpurged`, `reconcile`, and `_replace_tool` to pass `current.user_defined_backup`.
- **Files modified:** `klippy/extras/tool_fallback_state.py`
- **Verification:** All 367 tests pass

**3. [Rule 1 - Bug] to_dict() missing user_defined_backup in tool serialization**
- **Found during:** Task 1 (testing)
- **Issue:** `to_dict()` iterates over tools but only serialized `loaded`, `purged`, `failed`, `backups` — missing `user_defined_backup`.
- **Fix:** Added `"user_defined_backup": tool.user_defined_backup` to the tool dict comprehension in `to_dict()`.
- **Files modified:** `klippy/extras/tool_fallback_state.py`
- **Verification:** `test_all_persisted_fields_round_trip_without_reordering_backups` passes

**4. [Rule 1 - Bug] _canonical() call sites missing user_defined_backups arg**
- **Found during:** Task 1 (testing)
- **Issue:** `_canonical()` was updated to accept 4 parameters, but `_replace_tool()` still called it with 2 arguments.
- **Fix:** Updated `_replace_tool()` to pass `self.user_defined_backups` as 3rd argument.
- **Files modified:** `klippy/extras/tool_fallback_state.py`
- **Verification:** `test_with_backups_replaces_reorders_and_clears_only_target_policy` passes

**5. [Rule 2 - Missing Critical] version assertions in other test files**
- **Found during:** Task 5 (testing)
- **Issue:** Tests in `test_tool_fallback_extension.py`, `test_tool_fallback_notifications.py`, and `test_tool_fallback_sensor.py` asserted `version == 1` which now fails with `SCHEMA_VERSION = 2`.
- **Fix:** Updated all version assertions from 1 to 2, and updated `valid_dict()` test helper to v2 format with all new fields.
- **Files modified:** `tests/test_tool_fallback_extension.py`, `tests/test_tool_fallback_notifications.py`, `tests/test_tool_fallback_sensor.py`, `tests/test_tool_fallback_state.py`
- **Verification:** All 367 tests pass

---

**Total deviations:** 5 auto-fixed (4 bugs, 1 missing critical)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Self-Check: PASSED

- SUMMARY.md exists at `.planning/phases/08-state-schema-extension/08-SUMMARY.md`
- Implementation commit `dff661a` exists in git log
- All 367 tests passing

## Issues Encountered

None — all issues were auto-fixed per deviation rules.

## Next Phase Readiness

- Phase 9 (User Commands) can proceed — `user_defined_backups` field is ready for `DEFINE_TOOL_BACKUP` command to write to
- `StateStore.save()` validates user-defined backups before persistence
- `reconcile()` ensures stale entries are cleaned up when tools are removed from config

---
*Phase: 08-state-schema-extension*
*Completed: 2026-06-28*
