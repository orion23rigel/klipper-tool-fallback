# Pitfalls Research: Non-existent Tool Fallback

**Researched:** 2026-06-27
**Scope:** v1.2 — warnings, prevention strategies, and phase placement for risks

## Pitfall 1: State Migration Breaks Existing Installations

**Warning sign:** `load_reconciled()` crashes or produces incorrect state when reading old state files that lack `user_defined_backups` or `user_defined_backup` fields.

**Prevention strategy:** 
- Use `getattr(state, 'user_defined_backups', {})` or `dataclasses.replace()` with defaults
- Add a migration step in `load_reconciled()` that populates missing fields with sensible defaults
- Write a test that loads a v1.1 state file and verifies it reconciles without errors

**Phase to address:** Phase 1 (state schema extension)

## Pitfall 2: G-code Wrapper Breaks Backward Compatibility

**Warning sign:** Users who don't update their macros to call `_TOOL_FALLBACK_TN` instead of raw `Tn` will have undefined tools pass through to Klipper's native behavior (which may error or use the wrong tool).

**Prevention strategy:**
- Provide a migration path: a Klipper macro that wraps `Tn` calls for users who don't want to change their slicer output
- In documentation, clearly distinguish between "opt-in wrapper" and "transparent interception"
- Consider a config option `transparent_undefined_detection = False` (default) that lets advanced users enable monkey-patching

**Phase to address:** Phase 4 (undefined tool detection layer)

## Pitfall 3: User Prompt Deadlock

**Warning sign:** The print is paused waiting for `DEFINE_TOOL_BACKUP` but the user never submits it (e.g., they're away from the printer, or the console is not accessible). The print is stuck indefinitely.

**Prevention strategy:**
- Add a configurable timeout (`undefined_tool_timeout`) that falls back to a default tool (or the first configured backup) if the user doesn't respond
- Log the timeout event via the existing notification system
- Document the timeout behavior clearly

**Phase to address:** Phase 5 (user prompt flow)

## Pitfall 4: User-Defined Backup Conflicts with Configured Backups

**Warning sign:** A user defines `DEFINE_TOOL_BACKUP T5 T3` but T3 is already a configured backup for T5, or T3 is itself undefined. The backup graph resolution produces unexpected results.

**Prevention strategy:**
- Validate that the backup tool exists (is configured) before accepting the definition
- If the backup tool is also undefined, reject with a clear error message
- Document the precedence: user-defined backups override configured backups (or merge with them)

**Phase to address:** Phase 2 (DEFINE_TOOL_BACKUP command)

## Pitfall 5: Fail-Closed Safety Model Violation

**Warning sign:** The user-prompt flow bypasses the existing fail-closed checkpoints. When an undefined tool is detected and the user defines a backup, the backup selection might not go through the full workflow checkpoint validation.

**Prevention strategy:**
- Ensure that user-defined backup application goes through `_select_and_conditionally_purge()` which includes all safety checks
- Do NOT add a separate "fast path" for user-defined backups
- Add a test that verifies fail-closed behavior during user-defined backup application

**Phase to address:** Phase 5 (user prompt flow) — review all code paths

## Pitfall 6: Concurrency Between User Command and Automated Fallback

**Warning sign:** A user defines a backup tool via `DEFINE_TOOL_BACKUP` while an automated fallback (from sensor failure) is in progress. The two operations conflict and produce inconsistent state.

**Prevention strategy:**
- Reuse the existing `_guard_workflow_operation()` mechanism to reject user commands during active transitions
- Queue user-defined backup operations if a transition is active
- Log conflicts clearly

**Phase to address:** Phase 2 (DEFINE_TOOL_BACKUP command)

## Pitfall 7: JSON Schema Version Drift

**Warning sign:** The state file schema changes between releases but the version check doesn't catch it. Old state files are loaded with missing fields, causing subtle bugs.

**Prevention strategy:**
- Include a `schema_version` field in the state file
- On load, compare versions and run migrations if needed
- Increment schema version for each breaking change
- Write tests for each schema version migration

**Phase to address:** Phase 1 (state schema extension)

## Summary Table

| Pitfall | Severity | Prevention | Phase |
|---|---|---|---|
| State migration breaks | High | Defaults + migration step + backward-compat test | 1 |
| G-code wrapper breaks compat | Medium | Macro wrapper + config option | 4 |
| User prompt deadlock | High | Configurable timeout | 5 |
| Backup conflicts | Medium | Validate backup tool exists | 2 |
| Fail-closed violation | High | Use existing safety paths | 5 |
| Concurrency conflicts | Medium | Guard workflow operations | 2 |
| Schema version drift | Medium | schema_version field + migrations | 1 |
