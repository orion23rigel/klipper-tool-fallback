---
wave: 1
depends_on: []
files_modified:
  - klippy/extras/tool_fallback_state.py
  - tests/test_tool_fallback_state.py
autonomous: true
requirements: STATE-01, STATE-02, STATE-03, STATE-04
---

# Phase 08: State Schema Extension — Plan

## Objective

Extend the persistent state schema with backward-compatible user-defined backup fields so the extension can store and restore mappings without breaking existing state files.

## must_haves

### truths
- [STATE-01] ToolState has an optional user_defined_backup field defaulting to None
- [STATE-02] FallbackState has an optional user_defined_backups dict field defaulting to {}
- [STATE-03] load_reconciled handles state files lacking user_defined_backups (backward compatible)
- [STATE-04] save() persists user_defined_backups to the JSON state file
- Schema version bumped from 1 to 2
- from_dict() accepts both version 1 and version 2 state files
- Existing v1 state files load without error and remain on disk unchanged
- user_defined_backups values are validated against TOOL_NAME_RE or None
- Self-references in user_defined_backups are rejected
- to_dict() always includes user_defined_backups key (even when empty)

### prohibitions
- No user commands are added (reserved for Phase 9)
- No undefined tool detection logic is added (reserved for Phase 10)
- No routing changes are made (reserved for Phase 12)
- No existing behavior for version 1 state files is changed beyond adding the default field

## Tasks

### Task 1: Add user_defined_backup to ToolState

<read_first>
- klippy/extras/tool_fallback_state.py (current ToolState definition)
- tests/test_tool_fallback_state.py (existing test patterns)
</read_first>

<action>
Add `user_defined_backup: str | None = None` as the 5th field to the `ToolState` frozen dataclass in `klippy/extras/tool_fallback_state.py`. This field defaults to `None` and is optional (has a default value). Update all places that construct `ToolState` instances to include `user_defined_backup=None` as the 5th positional argument or keyword argument. The field must appear after `backups` in the dataclass definition.
</action>

<acceptance_criteria>
- Source: `klippy/extras/tool_fallback_state.py` contains `user_defined_backup: str | None = None` in the `ToolState` dataclass definition, after the `backups` field
- Source: All `ToolState(` constructor calls in `tool_fallback_state.py` include `user_defined_backup=None` (either positional 5th arg or keyword arg)
- Test: `pytest tests/test_tool_fallback_state.py -x` passes with no errors
- Source: `ToolState` dataclass has exactly 5 fields: `loaded`, `purged`, `failed`, `backups`, `user_defined_backup`
</acceptance_criteria>

### Task 2: Add user_defined_backups to FallbackState

<read_first>
- klippy/extras/tool_fallback_state.py (current FallbackState definition, from_dict, to_dict, _canonical)
- klippy/extras/tool_fallback_config.py (ToolConfig — for reference)
</read_first>

<action>
Add `user_defined_backups: object` (MappingProxyType-wrapped dict) as a 4th field to the `FallbackState` frozen dataclass in `klippy/extras/tool_fallback_state.py`. The field type annotation should be `object` (consistent with `tools` and `mappings` which also use `object` for MappingProxyType). Default value: an empty MappingProxyType. Update `_canonical()` to accept a 4th parameter `user_defined_backups` and pass it to the FallbackState constructor. Update `from_config()` to pass `MappingProxyType({})` as the 4th argument. Update `to_dict()` to include `"user_defined_backups": dict(self.user_defined_backups)` in the serialized output.
</action>

<acceptance_criteria>
- Source: `klippy/extras/tool_fallback_state.py` FallbackState dataclass has 4 fields: `version`, `tools`, `mappings`, `user_defined_backups`
- Source: `FallbackState._canonical()` accepts 4 parameters and passes all 4 to `cls()` constructor
- Source: `FallbackState.from_config()` passes `MappingProxyType({})` as the 4th argument to `_canonical()`
- Source: `FallbackState.to_dict()` includes `"user_defined_backups": dict(self.user_defined_backups)` in the returned dict
- Source: `FallbackState.__init__` signature has 4 parameters matching the 4 fields
</acceptance_criteria>

### Task 3: Update from_dict() for backward-compatible migration

<read_first>
- klippy/extras/tool_fallback_state.py (current from_dict implementation with _require_fields)
</read_first>

<action>
Modify `FallbackState.from_dict()` to accept version 1 and version 2 state files:
1. Change the version check from `version != SCHEMA_VERSION` to `version not in (1, 2)` — this allows both v1 and v2 files
2. In the data validation section, change `_require_fields(data, {"version", "tools", "mappings"}, "state")` to `_require_fields(data, {"version", "tools", "mappings", "user_defined_backups"}, "state")` — but wrap this in a try/except that catches StateValidationError with "unknown user_defined_backups" or "missing user_defined_backups" and falls back to v1 behavior
3. For v1 files (version == 1) or files missing user_defined_backups: set `raw_user_defined_backups = {}`
4. For v2 files (version == 2) with user_defined_backups present: validate it as a dict, check each value is either None or matches TOOL_NAME_RE, reject self-references
5. Pass `MappingProxyType(ordered_user_defined_backups)` as the 4th argument to `_canonical()`
</action>

<acceptance_criteria>
- Source: `klippy/extras/tool_fallback_state.py` version check uses `version not in (1, 2)` instead of `version != SCHEMA_VERSION`
- Source: `from_dict()` handles state JSON missing `user_defined_backups` key by defaulting to `{}`
- Source: `from_dict()` validates `user_defined_backups` values when present — each value is None or matches TOOL_NAME_RE
- Source: `from_dict()` rejects self-references in user_defined_backups (logical tool mapping to itself)
- Test: A state JSON with only `{"version": 1, "tools": {...}, "mappings": {...}}` loads without error
- Test: A state JSON with `{"version": 2, "tools": {...}, "mappings": {...}, "user_defined_backups": {"T0": "T1"}}` loads correctly
- Test: A state JSON with self-reference `{"T0": "T0"}` in user_defined_backups raises StateValidationError
</acceptance_criteria>

### Task 4: Add user_defined_backups validation in save/reconcile

<read_first>
- klippy/extras/tool_fallback_state.py (current save, reconcile methods)
- klippy/extras/tool_fallback_config.py (TOOL_NAME_RE reference)
</read_first>

<action>
Add validation for user_defined_backups in the StateStore.save() path:
1. In `StateStore.save()`, before calling `state.to_dict()`, validate that all values in `state.user_defined_backups` are either None or valid tool names (matching TOOL_NAME_RE)
2. Add a method `FallbackState._validate_user_defined_backups()` that checks: each value is None or str matching TOOL_NAME_RE; no self-references (logical tool == backup tool); no references to tools not in `self.tools`
3. Call this validation in `save()` before serialization — raise StateValidationError if invalid
4. Also validate in `reconcile()` — when tools change, filter out user_defined_backups entries that reference tools no longer configured
</action>

<acceptance_criteria>
- Source: `klippy/extras/tool_fallback_state.py` has a `_validate_user_defined_backups` method on FallbackState
- Source: `StateStore.save()` calls validation on user_defined_backups before serialization
- Source: `FallbackState.reconcile()` filters user_defined_backups to only include tools still in configured_tools
- Test: Saving state with invalid user_defined_backups (self-reference) raises StateValidationError
- Test: Reconciling state removes user_defined_backups entries for tools that were removed from config
</acceptance_criteria>

### Task 5: Write comprehensive tests

<read_first>
- tests/test_tool_fallback_state.py (existing test patterns, 555 lines)
- klippy/extras/tool_fallback_state.py (final implementation after Tasks 1-4)
</read_first>

<action>
Add test cases to `tests/test_tool_fallback_state.py` following the existing test patterns:
1. Test `ToolState` with `user_defined_backup=None` (default) and `user_defined_backup="T1"` (set)
2. Test `FallbackState.from_config()` includes empty `user_defined_backups` (MappingProxyType of {})
3. Test `FallbackState.from_dict()` with v1 state (no user_defined_backups field) — loads successfully, defaults to {}
4. Test `FallbackState.from_dict()` with v2 state (user_defined_backups present) — loads correctly
5. Test `FallbackState.to_dict()` includes user_defined_backups key even when empty
6. Test `StateStore.save()` and round-trip with user_defined_backups data
7. Test validation: self-reference in user_defined_backups raises StateValidationError
8. Test validation: invalid tool name in user_defined_backups raises StateValidationError
9. Test `reconcile()` filters out user_defined_backups for removed tools
10. Test `_canonical()` sorts user_defined_backups by key
</action>

<acceptance_criteria>
- Test: `pytest tests/test_tool_fallback_state.py -x` passes with all new and existing tests
- Source: New tests cover all 4 STATE requirements (STATE-01 through STATE-04)
- Source: Each new test follows the existing test naming convention (`def test_...`)
- Test: No existing tests are broken by the changes
</acceptance_criteria>

## Artifacts this phase produces

- `klippy/extras/tool_fallback_state.py`: Modified — adds `user_defined_backup` field to `ToolState`, adds `user_defined_backups` field to `FallbackState`, updates `from_dict()`, `to_dict()`, `_canonical()`, `from_config()`, `reconcile()`, adds `_validate_user_defined_backups()`, updates `StateStore.save()` validation
- `tests/test_tool_fallback_state.py`: Modified — adds test cases for all new fields and validation
- `SCHEMA_VERSION`: Changed from 1 to 2
