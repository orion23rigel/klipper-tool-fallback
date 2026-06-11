# Requirements: Klipper Tool Fallback v1.1

**Defined:** 2026-06-11  
**Core Value:** Automatic fallback remains safe and operationally trustworthy.

## v1.1 Requirements

### Notifications

- [ ] **NOTIFY-01:** Operators receive at most one stable external event per workflow generation and terminal outcome for fallback success, fallback failure, and transient recovery.
- [ ] **NOTIFY-02:** Notification adapter absence, failure, delay, recursion, or re-entry cannot change canonical state, mappings, hardware actions, workflow outcome, pause ownership, or resume policy; failures remain locally visible.
- [ ] **NOTIFY-03:** External event parameters use a fixed, bounded, injection-safe transport with useful canonical context without promising downstream delivery.

### Runtime Backup Policy

- [ ] **BACKUP-01:** Operators can atomically replace or clear one tool's complete ordered backup list while preserving unrelated state.
- [ ] **BACKUP-02:** Operators can restore one tool or all tools to configured backup defaults through the same atomic persistence path.
- [ ] **BACKUP-03:** Runtime backup mutations reject malformed, unknown, duplicate, and self-referential entries, preserve order, and retain the current loop-safe cycle policy.
- [ ] **BACKUP-04:** Backup mutation is rejected during any workflow checkpoint or active transition; successful changes affect only future resolution and are immediately visible.
- [ ] **BACKUP-05:** Backup persistence failure leaves published state unchanged and exact no-ops do not write.

### Integration Evidence

- [ ] **EXAMPLE-01:** Operators have an internally consistent representative integration example covering installation, rollback, adapters, hooks, ownership assumptions, commissioning, and printer-specific hazards.
- [ ] **UAT-01:** Maintainers record supervised representative live-printer evidence for v1.1 routing, sensor, heater, purge, fallback, guarded-resume, notification, and backup-mutation scenarios.

### Delivery

- [ ] **CI-01:** Clean-checkout CI runs syntax/import checks, the complete deterministic pytest suite with zero-tests protection, example-contract checks, and `git diff --check`.
- [ ] **RELEASE-01:** Release verification binds green CI, artifact contents, documentation/examples, and current live-UAT evidence to the exact clean semantic-version tag.
- [ ] **SCOPE-01:** Release and milestone evidence explicitly names the four excluded Phase 1 UAT scenarios and makes no claim that v1.1 completes them.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Four Phase 1 UAT scenarios | Separately deferred by explicit user instruction |
| Direct HTTP/Moonraker/notifier clients | Printer-owned notification adapter remains the boundary |
| Notification retries, queues, or persisted delivery state | Notifications are best-effort and safety-neutral |
| Incremental add/remove/move backup commands | Complete-list replace and restore/reset provide the initial atomic contract |
| Tool/heater/sensor identity mutation | Runtime backup policy only |
| Universal printer compatibility claims | Evidence remains bounded to representative tested hardware |
| Unsupervised destructive hardware fault injection | Unsafe and unnecessary for milestone acceptance |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| NOTIFY-01 through NOTIFY-03 | TBD | Pending |
| BACKUP-01 through BACKUP-05 | TBD | Pending |
| EXAMPLE-01, UAT-01 | TBD | Pending |
| CI-01, RELEASE-01, SCOPE-01 | TBD | Pending |

**Coverage:**
- v1.1 requirements: 13 total
- Mapped to phases: 0
- Unmapped: 13

---
*Requirements defined: 2026-06-11*
*Last updated: 2026-06-11 after v1.1 research*
