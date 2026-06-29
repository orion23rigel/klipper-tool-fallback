---
phase: 09-user-commands
reviewed: 2026-06-29T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - klippy/extras/tool_fallback_state.py
  - klippy/extras/tool_fallback.py
  - tests/test_tool_fallback_state.py
  - tests/test_tool_fallback_extension.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 09: Code Review Report

**Reviewed:** 2026-06-29T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 9 implements three G-code commands (`DEFINE_TOOL_BACKUP`, `UNDEFINE_TOOL_BACKUP`, `SHOW_TOOL_BACKUPS`) plus the `with_user_defined_backup()` state mutation method. The implementation is structurally sound: immutable state objects, atomic file writes, proper validation, and comprehensive test coverage. However, three warnings and two info-level issues were identified, mostly around edge-case handling in the undefined-tool prompt flow and test completeness.

## Structural Findings (fallow)

No structural findings were provided in the prompt. The codebase is consistent across modules — imports, exports, and naming patterns align.

## Warnings

### WR-01: `cmd_DEFINE_TOOL_BACKUP` accepts an unconfigured `LOGICAL` parameter without tool-name validation during undefined-tool prompts

**File:** `klippy/extras/tool_fallback.py:360`
**Issue:** When `is_undefined_prompt` is true, the code reads `logical_tool = gcmd.get("LOGICAL")` without validating that the value is a non-empty string matching `TOOL_NAME_RE`. The `_require_configured_tool` check is skipped, but `state.with_user_defined_backup(logical_tool, backup_tool)` is still called. If `gcmd.get("LOGICAL")` returns `None` (parameter missing), the call proceeds with `logical_tool = None`, which will either fail silently or produce a malformed state entry. The `with_user_defined_backup` method does not validate the `logical` key — it only validates the `backup` value.

**Fix:** Add a validation guard after the `is_undefined_prompt` branch:
```python
if is_undefined_prompt:
    logical_tool = gcmd.get("LOGICAL")
    if logical_tool is None:
        raise gcmd.error("LOGICAL parameter is required")
    if not tool_fallback_config.TOOL_NAME_RE.fullmatch(logical_tool):
        raise gcmd.error("LOGICAL must be a canonical tool name")
else:
    logical_tool = self._require_configured_tool(gcmd, "LOGICAL")
```

### WR-02: `with_user_defined_backup` does not validate the `logical` parameter type

**File:** `klippy/extras/tool_fallback_state.py:313-332`
**Issue:** The method signature is `with_user_defined_backup(self, logical, backup)`. It validates `backup` (checking it's in `self.tools` and not self-referential), but it never validates that `logical` is a string or a valid tool name. If called with `logical=None` (as WR-01 can pass), the method will silently create an entry `None: "T1"` in `user_defined_backups`. Later, `_validate_user_defined_backups()` (line 340-351) also skips type-checking on the logical key — it only checks `backup is not None` and `backup not in configured_names`. This means a `None` key can persist in the state dictionary.

**Fix:** Add validation at the start of `with_user_defined_backup`:
```python
def with_user_defined_backup(self, logical, backup):
    if type(logical) is not str:
        raise StateValidationError(
            "user_defined_backup logical must be a canonical tool name")
    if backup is not None:
        ...
```

### WR-03: `_handle_undefined_tool_timeout` uses `iter()` on dict — iteration order is not guaranteed to be "lowest number"

**File:** `klippy/extras/tool_fallback.py:1152`
**Issue:** The timeout fallback selects `default_tool = next(iter(self.config.tools))`. While Python 3.7+ guarantees insertion-order preservation for dicts, `self.config.tools` is a dict whose insertion order depends on how tools were registered (via `register_tool()` calls). The comment says "first configured tool (lowest number)" per D-17, but there is no guarantee that the first-registered tool is the lowest-numbered one. If tools are registered out of numeric order (e.g., T5 before T0), the fallback will pick T5 instead of T0.

**Fix:** Sort the tools by numeric suffix to guarantee the lowest-numbered tool is selected:
```python
default_tool = min(self.config.tools, key=lambda t: int(t[1:]))
```

## Info

### IF-01: `test_show_tool_backups_with_none_backup` uses a fragile indirect test approach

**File:** `tests/test_tool_fallback_extension.py:408-445`
**Issue:** The test comment explicitly acknowledges that `with_user_defined_backup(T0, None)` removes the entry from the dict, so the test works around this by writing a raw JSON file with `{"T0": null}` in `user_defined_backups` and loading a second extension instance. This is a brittle test that depends on the JSON serialization format. A cleaner approach would be to test the `to_dict()` → `from_dict()` round-trip in `test_tool_fallback_state.py` to verify that `None` values in `user_defined_backups` survive serialization, then test `SHOW_TOOL_BACKUPS` output format with a pre-loaded state.

**Fix:** Add a state-layer test in `test_tool_fallback_state.py`:
```python
def test_user_defined_backup_none_value_round_trips():
    decoded = valid_dict()
    decoded["user_defined_backups"] = {"T0": None}
    state = FallbackState.from_dict(decoded)
    assert state.to_dict()["user_defined_backups"] == {"T0": None}
```
Then simplify the extension test to rely on this invariant.

### IF-02: `test_undefined_tool_prompt_sets_sentinel` only checks sentinel is cleared after timeout, not that it was set during the wait

**File:** `tests/test_tool_fallback_extension.py:589-605`
**Issue:** The test sets a short timeout (0.05s), triggers the undefined tool prompt, then asserts `extension._undefined_tool_pending is None`. This only confirms the sentinel was cleared — it does not verify that the sentinel was actually set to `"T99"` during the prompt's wait loop. The test passes even if the sentinel was never set.

**Fix:** Add an intermediate assertion or monkeypatch the sentinel setter to verify it was assigned:
```python
sentinel_values = []
original_setter = type(extension)._undefined_tool_pending.fset
# ... verify sentinel was set to "T99" during the wait loop
```
Or simply add a separate test that manually sets `_undefined_tool_pending = "T99"` and verifies `cmd_DEFINE_TOOL_BACKUP` clears it.

---

_Reviewed: 2026-06-29T00:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
