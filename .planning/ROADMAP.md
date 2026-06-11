# Roadmap: Klipper Tool Fallback

## Milestones

- [x] **v1.0 MVP** - Phases 1-4 shipped 2026-06-11
- [ ] **v1.1 Integration & Operations** - Phases 5-7 planned

## Archived Phases

See [v1.0 roadmap](milestones/v1.0-ROADMAP.md) and
[v1.0 phase history](milestones/v1.0-phases/).

## v1.1 Integration & Operations

**Milestone Goal:** Make the shipped fallback runtime operationally manageable,
integrated on a representative printer, and verifiable as an exact release.

**Scope Boundary:** The four separately deferred Phase 1 UAT scenarios are not v1.1
requirements, work items, acceptance gates, or completion claims:

1. Valid Configuration Startup
2. Persisted State Survives Restart
3. Invalid State Blocks Startup Clearly
4. Read-Only Status Inspection

### Phase 5: Runtime Contracts

**Goal:** Add safety-neutral external outcome notifications and atomic runtime backup policy management without changing the shipped fallback safety model.
**Depends on:** Phase 4
**Requirements:** NOTIFY-01, NOTIFY-02, NOTIFY-03, BACKUP-01, BACKUP-02, BACKUP-03, BACKUP-04, BACKUP-05
**Success Criteria** (what must be TRUE):

  1. Operators receive at most one stable external event per workflow generation and terminal fallback success, fallback failure, or transient-recovery outcome, using fixed bounded injection-safe parameters with useful canonical context.
  2. Missing, failing, delayed, recursive, or re-entering notification adapters leave canonical state, mappings, hardware actions, workflow outcome, pause ownership, and resume policy unchanged while failures remain locally visible.
  3. Operators can atomically replace or clear one tool's ordered backup list, with successful changes immediately visible and affecting only future resolution while unrelated state remains unchanged.
  4. Operators can atomically restore one tool or all tools to configured backup defaults through the same persistence path.
  5. Invalid backup mutations are rejected; mutations submitted during active workflows or transitions are queued and processed in submission order after any terminal outcome, stopping at the first application failure; exact no-ops do not write, persistence failures do not publish, and accepted lists preserve order and the existing loop-safe cycle policy.

**Plans:** 0/3 plans executed

### Phase 6: Examples And Live Integration

**Goal:** Provide a representative printer integration contract and record supervised live evidence for the bounded v1.1 operational scenarios.
**Depends on:** Phase 5
**Requirements:** EXAMPLE-01, UAT-01
**Success Criteria** (what must be TRUE):

  1. Operators have one internally consistent representative integration example covering installation, rollback, adapters, hooks, ownership assumptions, commissioning, and printer-specific hazards.
  2. Maintainers can execute a supervised, staged, and reversible representative-printer procedure covering v1.1 routing, sensor, heater, purge, fallback, guarded-resume, notification, and backup-mutation scenarios.
  3. Each live claim records the tested topology, relevant revisions, procedure, expected result, observed result, and evidence, and remains bounded to the representative tested hardware.
  4. The v1.1 live-evidence matrix neither executes nor credits the four excluded Phase 1 UAT scenarios toward milestone completion.

**Plans:** TBD

### Phase 7: CI And Release Verification

**Goal:** Prove the exact v1.1 release candidate through clean-checkout automation and evidence-bound release verification.
**Depends on:** Phase 6
**Requirements:** CI-01, RELEASE-01, SCOPE-01
**Success Criteria** (what must be TRUE):

  1. Clean-checkout CI runs syntax/import checks, the complete deterministic pytest suite with zero-tests protection, example-contract checks, and `git diff --check`.
  2. Release verification accepts only a clean semantic-version tag whose exact commit has green CI and matching artifact contents, documentation, examples, and current representative live-UAT evidence.
  3. Release and milestone evidence explicitly names the four excluded Phase 1 UAT scenarios and makes no claim that v1.1 completes them.
  4. Maintainers can distinguish automated, example-contract, and representative live-hardware evidence when auditing the release candidate.

**Plans:** TBD

## Progress

**Execution Order:** Phase 5 -> Phase 6 -> Phase 7

| Phase | Requirements | Plans Complete | Status | Completed |
|-------|--------------|----------------|--------|-----------|
| 5. Runtime Contracts | 8 | 0/3 | Planned    |  |
| 6. Examples And Live Integration | 2 | 0/TBD | Not started | - |
| 7. CI And Release Verification | 3 | 0/TBD | Not started | - |

## Requirement Coverage

| Phase | Requirements |
|-------|--------------|
| Phase 5 | NOTIFY-01, NOTIFY-02, NOTIFY-03, BACKUP-01, BACKUP-02, BACKUP-03, BACKUP-04, BACKUP-05 |
| Phase 6 | EXAMPLE-01, UAT-01 |
| Phase 7 | CI-01, RELEASE-01, SCOPE-01 |

**Coverage:** 13/13 v1.1 requirements mapped exactly once; 0 unmapped.
