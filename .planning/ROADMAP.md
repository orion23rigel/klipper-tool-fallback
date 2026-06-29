# Roadmap: Klipper Tool Fallback

## Milestones

- [x] **v1.0 MVP** - Phases 1-4 shipped 2026-06-11
- [x] **v1.1 Integration & Operations** - Phases 5-7 shipped 2026-06-12
- [ ] **v1.2 Non-existent Tool Fallback Definition** - Phases 8-12 planned

## Archived Phases

See [v1.0 roadmap](milestones/v1.0-ROADMAP.md) and
[v1.0 phase history](milestones/v1.0-phases/).

---

<details>
<summary>✅ v1.0 MVP (Phases 1-4) - SHIPPED 2026-06-11</summary>

### Phase 1: Configuration Schema

**Goal**: Strict Klipper configuration loaders with immutable normalized tool models and startup-contract validation.
**Depends on**: Nothing
**Requirements**: CONFIG-01, CONFIG-02, CONFIG-03
**Success Criteria** (what must be TRUE):

  1. Extension fails startup with a clear error when the `[tool_fallback]` section is missing or malformed.
  2. Each tool entry is validated for required fields; invalid entries produce actionable error messages.
  3. Normalized tool models are immutable after construction — no mutation after load.

**Plans**: 3/3 plans complete

### Phase 2: State Schema And Persistence

**Goal**: Deterministic state reconciliation with failure-safe atomic JSON persistence.
**Depends on**: Phase 1
**Requirements**: STATE-10, STATE-11, STATE-12, STATE-13, STATE-14
**Success Criteria** (what must be TRUE):

  1. A fresh state file is created on first run with the correct schema version and empty mappings.
  2. Mappings survive a Klipper restart and are loaded deterministically.
  3. Persistence failures leave the previous valid state file intact.
  4. State reconciliation produces a deterministic result given the same inputs.

**Plans**: 3/3 plans complete

### Phase 3: Tool Routing And Fallback

**Goal**: Fail-closed tool selection with recursion-free mapped physical selection and automatic backup fallback.
**Depends on**: Phase 2
**Requirements**: ROUTE-01, ROUTE-02, ROUTE-03, ROUTE-04, ROUTE-05, ROUTE-06, ROUTE-07, ROUTE-08
**Success Criteria** (what must be TRUE):

  1. Selecting a tool produces the correct physical tool selection via the mapped route.
  2. When a primary tool fails, the system falls back to the configured backup tool automatically.
  3. Backup resolution respects the ordered backup list and applies cycle-safe routing.
  4. All fallback transitions are fail-closed — no unsafe tool state is ever exposed.

**Plans**: 3/3 plans complete

### Phase 4: Runtime Safety And Purge

**Goal**: Guarded active-route transitions with pause ownership, purge lifecycle management, and fail-closed runtime checkpoints.
**Depends on**: Phase 3
**Requirements**: SAFETY-01, SAFETY-02, SAFETY-03, SAFETY-04, SAFETY-05, SAFETY-06, SAFETY-07, SAFETY-08, SAFETY-09, SAFETY-10
**Success Criteria** (what must be TRUE):

  1. Active-route transitions are guarded by pause ownership — no concurrent mutations.
  2. Purge operations are owned by the extension and recursion-free.
  3. Sensor-derived filament state is trustworthy and handles outage gracefully.
  4. Runtime checkpoints enforce fail-closed safety on every state transition.

**Plans**: 3/3 plans complete

</details>

---

<details>
<summary>✅ v1.1 Integration & Operations (Phases 5-7) - SHIPPED 2026-06-12</summary>

### Phase 5: Runtime Contracts

**Goal**: Add safety-neutral external outcome notifications and atomic runtime backup policy management.
**Depends on**: Phase 4
**Requirements**: NOTIFY-01, NOTIFY-02, NOTIFY-03, BACKUP-01, BACKUP-02, BACKUP-03, BACKUP-04, BACKUP-05
**Success Criteria** (what must be TRUE):

  1. Operators receive at most one stable external event per workflow generation and terminal fallback outcome.
  2. Failing notification adapters leave canonical state, mappings, and hardware actions unchanged.
  3. Operators can atomically replace or clear one tool's ordered backup list.
  4. Operators can restore configured backup defaults through the same persistence path.
  5. Invalid backup mutations are rejected; mutations during active workflows are queued.

**Plans**: 3/3 plans complete

### Phase 6: Examples And Live Integration

**Goal**: Provide representative printer integration guidance and record supervised live evidence.
**Depends on**: Phase 5
**Requirements**: EXAMPLE-01, UAT-01
**Success Criteria** (what must be TRUE):

  1. Operators have one internally consistent representative integration example covering installation, rollback, adapters, hooks, and commissioning.
  2. Maintainers can execute a supervised, staged, and reversible representative-printer procedure.
  3. Each live claim records topology, revisions, procedure, expected result, observed result, and evidence.
  4. The live-evidence matrix excludes the four Phase 1 UAT scenarios from v1.1 completion claims.

**Plans**: TBD

### Phase 7: CI And Release Verification

**Goal**: Prove the exact v1.1 release candidate through clean-checkout automation.
**Depends on**: Phase 6
**Requirements**: CI-01, RELEASE-01, SCOPE-01
**Success Criteria** (what must be TRUE):

  1. Clean-checkout CI runs syntax/import checks, the complete pytest suite, example-contract checks, and `git diff --check`.
  2. Release verification accepts only a clean semantic-version tag with green CI and matching artifacts.
  3. Release evidence explicitly names the four excluded Phase 1 UAT scenarios.
  4. Maintainers can distinguish automated, example-contract, and live-hardware evidence.

**Plans**: TBD

</details>

---

## v1.2 Non-existent Tool Fallback Definition

**Milestone Goal:** Gracefully handle G-code calling a tool that doesn't exist on the printer by prompting the user to define a backup tool.

**Scope Boundary:** Only handles undefined tool references via wrapper command, user prompt flow, and persistence. No transparent interception (monkey-patching), web UI, hardware discovery, or multi-user profiles.

### Phase 8: State Schema Extension

**Goal**: Extend the persistent state schema with backward-compatible user-defined backup fields so the extension can store and restore mappings without breaking existing state files.
**Depends on**: Phase 7
**Requirements**: STATE-01, STATE-02, STATE-03, STATE-04
**Success Criteria** (what must be TRUE):

  1. The `ToolState` dataclass includes an optional `user_defined_backup` field defaulting to `None`.
  2. The `ToolFallbackState` dataclass includes an optional `user_defined_backups` dict defaulting to `{}`.
  3. Existing state files that lack `user_defined_backups` load successfully with the field initialized to `{}`.
   4. New or updated state files persist `user_defined_backups` to disk on every save.

**Plans**: 1/1 plans complete

### Phase 9: User Commands

**Goal**: Provide operators with commands to define, remove, and list backup-tool mappings at runtime.
**Depends on**: Phase 8
**Requirements**: CMD-01, CMD-02, CMD-03, CMD-04, CMD-05, CMD-06, CMD-07, CMD-08
**Success Criteria** (what must be TRUE):

  1. Operators can define a backup mapping via `DEFINE_TOOL_BACKUP <logical> <backup>` and the mapping persists immediately.
  2. `DEFINE_TOOL_BACKUP` rejects the command when the backup tool is not configured on the printer.
  3. `DEFINE_TOOL_BACKUP` rejects the command during an active workflow transition.
  4. Operators can remove a mapping via `UNDEFINE_TOOL_BACKUP <logical>` and the removal persists.
  5. `UNDEFINE_TOOL_BACKUP` rejects the command when the mapping does not exist.
  6. Operators can list all user-defined and configured backup mappings via `SHOW_TOOL_BACKUPS`.

**Plans**: TBD
**UI hint**: yes

### Phase 10: Undefined Tool Detection

**Goal**: Detect when G-code references a tool number not configured on the printer and trigger the undefined-tool flow.
**Depends on**: Phase 9
**Requirements**: DETECT-01, DETECT-02, DETECT-03, DETECT-04
**Success Criteria** (what must be TRUE):

  1. The wrapper command `_TOOL_FALLBACK_TN` correctly parses the tool number from G-code parameters.
  2. When the referenced tool is configured, routing delegates to the existing `_route_logical` path.
  3. When the referenced tool is NOT configured, the system triggers the undefined-tool flow.
  4. Detection events are logged to Klipper's log system.

**Plans**: TBD
**UI hint**: yes

### Phase 11: User Prompt Flow

**Goal**: Pause the print, prompt the user to define a backup tool, and resume once the user responds or a configurable timeout expires.
**Depends on**: Phase 10
**Requirements**: PROMPT-01, PROMPT-02, PROMPT-03, PROMPT-04, PROMPT-05, PROMPT-06
**Success Criteria** (what must be TRUE):

  1. An undefined tool detected during print pauses the job via the existing `pause_gcode` mechanism.
  2. The Klipper console displays a prompt instructing the user to run `DEFINE_TOOL_BACKUP Tn Tm`.
  3. The system waits for the user to submit `DEFINE_TOOL_BACKUP` and applies the mapping when received.
  4. After a backup is defined, the print resumes via the existing `resume_gcode` mechanism.
  5. If the user does not respond within the configurable timeout, the system falls back to a default tool and resumes.
  6. Timeout events are logged via the existing notification system.

**Plans**: TBD

### Phase 12: Fallback Integration And Observability

**Goal**: Merge user-defined backups into the routing resolution pipeline and expose runtime state for operator visibility.
**Depends on**: Phase 11
**Requirements**: FALLBACK-01, FALLBACK-02, FALLBACK-03, FALLBACK-04, OBSERVE-01, OBSERVE-02
**Success Criteria** (what must be TRUE):

  1. `resolve_backup_graph()` considers user-defined backups alongside configured backups when resolving routes.
  2. User-defined backups are applied through the existing `_select_and_conditionally_purge()` path — no separate fast path.
  3. All fail-closed safety checkpoints are respected when applying user-defined backups.
  4. `SHOW_TOOL_FALLBACK_STATE` includes user-defined backup mappings in its output.
  5. Undefined tool detection events are visible in Klipper's log system.

**Plans**: TBD

## Progress

**Execution Order:** Phase 8 → Phase 9 → Phase 10 → Phase 11 → Phase 12

| Phase | Requirements | Plans Complete | Status | Completed |
|-------|--------------|----------------|--------|-----------|
| 8. State Schema Extension | 4 | 1/1 | Complete    | 2026-06-29 |
| 9. User Commands | 8 | 0/TBD | Not started | - |
| 10. Undefined Tool Detection | 4 | 0/TBD | Not started | - |
| 11. User Prompt Flow | 6 | 0/TBD | Not started | - |
| 12. Fallback Integration And Observability | 6 | 0/TBD | Not started | - |

## Requirement Coverage

| Phase | Requirements |
|-------|--------------|
| Phase 8 | STATE-01, STATE-02, STATE-03, STATE-04 |
| Phase 9 | CMD-01, CMD-02, CMD-03, CMD-04, CMD-05, CMD-06, CMD-07, CMD-08 |
| Phase 10 | DETECT-01, DETECT-02, DETECT-03, DETECT-04 |
| Phase 11 | PROMPT-01, PROMPT-02, PROMPT-03, PROMPT-04, PROMPT-05, PROMPT-06 |
| Phase 12 | FALLBACK-01, FALLBACK-02, FALLBACK-03, FALLBACK-04, OBSERVE-01, OBSERVE-02 |

**Coverage:** 28/28 v1.2 requirements mapped exactly once; 0 unmapped.
