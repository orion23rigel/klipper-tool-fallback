---
status: testing
phase: 09-user-commands
source: 09-01-SUMMARY.md, 09-02-SUMMARY.md, 09-03-SUMMARY.md, 09-user-commands-SUMMARY.md
started: 2026-06-29T00:00:00Z
updated: 2026-06-29T00:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: with_user_defined_backup creates new mapping
expected: |
  Calling FallbackState.with_user_defined_backup(logical_tool, backup_tool) returns a new FallbackState instance with the mapping added. The original instance is unchanged (immutable). The new instance's user_defined_backups shows the mapping.
result: pending

## Tests

### 1. with_user_defined_backup creates new mapping
expected: Calling FallbackState.with_user_defined_backup(logical_tool, backup_tool) returns a new FallbackState instance with the mapping added. The original instance is unchanged (immutable). The new instance's user_defined_backups shows the mapping.
result: pending

### 2. with_user_defined_backup rejects unknown tools
expected: Passing an unknown tool name (not in configured tools) raises an error or returns an error state.
result: pending

### 3. with_user_defined_backup rejects self-reference
expected: Mapping a tool to itself (e.g., T0 -> T0) is rejected with an appropriate error.
result: pending

### 4. with_user_defined_backup no-op returns same instance
expected: Defining a mapping that already exists returns the same instance (identity), not a new one.
result: pending

### 5. with_user_defined_backup None removes entry
expected: Passing None as the backup value removes the entry from user_defined_backups (not sets it to None).
result: pending

### 6. with_user_defined_backup preserves other mappings
expected: Adding a new mapping does not affect existing backup mappings (core or other user-defined).
result: pending

### 7. DEFINE_TOOL_BACKUP command is registered
expected: The DEFINE_TOOL_BACKUP G-code command is recognized by Klipper's command handler. Sending it with LOGICAL and BACKUP parameters triggers the handler.
result: pending

### 8. DEFINE_TOOL_BACKUP defines a mapping
expected: Sending `DEFINE_TOOL_BACKUP LOGICAL=T0 BACKUP=T1` when both are configured tools creates the mapping and persists state. The command responds confirming the definition.
result: pending

### 9. DEFINE_TOOL_BACKUP rejects unknown tools
expected: Sending `DEFINE_TOOL_BACKUP LOGICAL=UNKNOWN BACKUP=T1` or with an unknown BACKUP tool reports an error about the tool not being configured.
result: pending

### 10. DEFINE_TOOL_BACKUP no-op reports unchanged
expected: Defining an already-existing mapping reports "unchanged: no write" and does not persist to disk.
result: pending

### 11. DEFINE_TOOL_BACKUP blocked during workflow transition
expected: Sending DEFINE_TOOL_BACKUP while a workflow transition is in progress is rejected (workflow guard).
result: pending

### 12. DEFINE_TOOL_BACKUP blocked during notification
expected: Sending DEFINE_TOOL_BACKUP while notifications are in progress is rejected (notification guard).
result: pending

### 13. UNDEFINE_TOOL_BACKUP command is registered
expected: The UNDEFINE_TOOL_BACKUP G-code command is recognized by Klipper's command handler. Sending it with a TOOL parameter triggers the handler.
result: pending

### 14. UNDEFINE_TOOL_BACKUP removes a mapping
expected: Sending `UNDEFINE_TOOL_BACKUP TOOL=T0` when T0 has a user-defined backup removes the mapping and persists state. The command responds confirming the removal.
result: pending

### 15. UNDEFINE_TOOL_BACKUP rejects missing mapping
expected: Sending `UNDEFINE_TOOL_BACKUP TOOL=T99` when T99 has no user-defined backup reports an error.
result: pending

### 16. UNDEFINE_TOOL_BACKUP blocked during workflow transition
expected: Sending UNDEFINE_TOOL_BACKUP while a workflow transition is in progress is rejected (workflow guard).
result: pending

### 17. UNDEFINE_TOOL_BACKUP blocked during notification
expected: Sending UNDEFINE_TOOL_BACKUP while notifications are in progress is rejected (notification guard).
result: pending

### 18. SHOW_TOOL_BACKUPS command is registered
expected: The SHOW_TOOL_BACKUPS G-code command is recognized by Klipper's command handler.
result: pending

### 19. SHOW_TOOL_BACKUPS shows empty state
expected: With no user-defined mappings, `SHOW_TOOL_BACKUPS` outputs "(empty)".
result: pending

### 20. SHOW_TOOL_BACKUPS shows single mapping
expected: With one user-defined mapping, `SHOW_TOOL_BACKUPS` shows it in human-readable format.
result: pending

### 21. SHOW_TOOL_BACKUPS shows multiple mappings sorted
expected: With multiple user-defined mappings, `SHOW_TOOL_BACKUPS` lists them sorted by tool name.
result: pending

### 22. SHOW_TOOL_BACKUPS shows None as (none)
expected: Mappings with None backup value display as "(none)" in the output.
result: pending

### 23. Full workflow: define, show, undefine, show
expected: A complete lifecycle works end-to-end: define a mapping, verify it appears in SHOW_TOOL_BACKUPS, undefine it, verify it disappears from SHOW_TOOL_BACKUPS. State persists across operations.
result: pending

## Summary

total: 23
passed: 0
issues: 0
pending: 23
skipped: 0
blocked: 0

## Gaps

[none yet]
