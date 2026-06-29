# Requirements: Klipper Tool Fallback — v1.2

**Defined:** 2026-06-27
**Core Value:** Automatic fallback remains safe and operationally trustworthy.

## v1.2 Requirements

### State Schema

- [x] **STATE-01**: The `ToolState` dataclass includes an optional `user_defined_backup` field that defaults to `None`
- [x] **STATE-02**: The `ToolFallbackState` dataclass includes an optional `user_defined_backups` dict field that defaults to `{}`
- [x] **STATE-03**: `StateStore.load_reconciled()` handles state files that lack `user_defined_backups` (backward-compatible migration)
- [x] **STATE-04**: `StateStore.save()` persists `user_defined_backups` to the JSON state file

### User Commands

- [x] **CMD-01**: User can define a backup tool mapping via `DEFINE_TOOL_BACKUP <logical_tool> <backup_tool>`
- [x] **CMD-02**: `DEFINE_TOOL_BACKUP` validates that the backup tool is configured (exists in `self.config.tools`)
- [x] **CMD-03**: `DEFINE_TOOL_BACKUP` rejects the command during an active workflow transition
- [x] **CMD-04**: `DEFINE_TOOL_BACKUP` persists the mapping immediately via `StateStore.save()`
- [x] **CMD-05**: User can remove a user-defined backup mapping via `UNDEFINE_TOOL_BACKUP <logical_tool>`
- [x] **CMD-06**: `UNDEFINE_TOOL_BACKUP` validates the mapping exists before removing
- [x] **CMD-07**: User can list all user-defined backup mappings via `SHOW_TOOL_BACKUPS`
- [x] **CMD-08**: `SHOW_TOOL_BACKUPS` displays both configured and user-defined backup mappings

### Undefined Tool Detection

- [x] **DETECT-01**: A wrapper G-code command `_TOOL_FALLBACK_TN` parses the tool number from G-code parameters
- [x] **DETECT-02**: `_TOOL_FALLBACK_TN` checks if the tool is configured in `self.config.tools`
- [x] **DETECT-03**: If the tool is configured, `_TOOL_FALLBACK_TN` delegates to existing routing (`_route_logical`)
- [x] **DETECT-04**: If the tool is NOT configured, `_TOOL_FALLBACK_TN` triggers the undefined-tool flow

### User Prompt Flow

- [x] **PROMPT-01**: When an undefined tool is detected, the print is paused using the existing `pause_gcode` mechanism
- [x] **PROMPT-02**: A console message prompts the user: "Tool Tn not defined. Define a backup tool: `DEFINE_TOOL_BACKUP Tn Tm`"
- [x] **PROMPT-03**: The system waits for the user to submit `DEFINE_TOOL_BACKUP`
- [x] **PROMPT-04**: If the user defines a backup, the mapping is applied and the print resumes via the existing `resume_gcode` mechanism
- [x] **PROMPT-05**: If the user does not respond within a configurable timeout (`undefined_tool_timeout`), the system falls back to a default tool (or the first configured backup) and resumes
- [x] **PROMPT-06**: The timeout event is logged via the existing notification system

### Fallback Application

- [x] **FALLBACK-01**: `resolve_backup_graph()` considers user-defined backups alongside configured backups
- [x] **FALLBACK-02**: User-defined backups are applied through the existing `_select_and_conditionally_purge()` path (no separate fast path)
- [x] **FALLBACK-03**: User-defined backup application respects all fail-closed safety checkpoints
- [x] **FALLBACK-04**: User-defined backup mappings are included in `state.mappings` after reconciliation

### Observability

- [x] **OBSERVE-01**: `SHOW_TOOL_FALLBACK_STATE` includes user-defined backup mappings in its output
- [x] **OBSERVE-02**: Undefined tool detection events are logged to Klipper's log system

## Out of Scope

| Feature | Reason |
|---|---|
| Transparent G-code interception (monkey-patching) | Higher risk, version-dependent; wrapper command is safer for v1.2 |
| Web UI for backup definition | Console commands suffice; frontend adds scope creep |
| Automatic tool discovery/probing | Requires hardware integration; out of scope for software-only extension |
| Multi-user backup profiles | Klipper is single-user; profiles add unnecessary complexity |
| Network-based prompts | Local Klipper console is the interaction surface |

## Traceability

| Requirement | Phase | Status |
|---|---|---|
| STATE-01 | Phase 8 | Complete |
| STATE-02 | Phase 8 | Complete |
| STATE-03 | Phase 8 | Complete |
| STATE-04 | Phase 8 | Complete |
| CMD-01 | Phase 9 | Complete |
| CMD-02 | Phase 9 | Complete |
| CMD-03 | Phase 9 | Complete |
| CMD-04 | Phase 9 | Complete |
| CMD-05 | Phase 9 | Complete |
| CMD-06 | Phase 9 | Complete |
| CMD-07 | Phase 9 | Complete |
| CMD-08 | Phase 9 | Complete |
| DETECT-01 | Phase 10 | Complete |
| DETECT-02 | Phase 10 | Complete |
| DETECT-03 | Phase 10 | Complete |
| DETECT-04 | Phase 10 | Complete |
| PROMPT-01 | Phase 11 | Complete |
| PROMPT-02 | Phase 11 | Complete |
| PROMPT-03 | Phase 11 | Complete |
| PROMPT-04 | Phase 11 | Complete |
| PROMPT-05 | Phase 11 | Complete |
| PROMPT-06 | Phase 11 | Complete |
| FALLBACK-01 | Phase 12 | Complete |
| FALLBACK-02 | Phase 12 | Complete |
| FALLBACK-03 | Phase 12 | Complete |
| FALLBACK-04 | Phase 12 | Complete |
| OBSERVE-01 | Phase 12 | Complete |
| OBSERVE-02 | Phase 12 | Complete |

**Coverage:**

- v1.2 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0 ✓
- **Complete: 28/28**

---
*Requirements defined: 2026-06-27*
*Last updated: 2026-06-29 after v1.2 milestone completion*
