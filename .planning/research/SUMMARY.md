# v1.1 Research Summary: Integration & Operations

**Synthesized:** 2026-06-11  
**Sources:** `PROJECT.md`, `STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, and
`PITFALLS.md`

## Executive Summary

v1.1 should operationalize the shipped v1.0 fallback system without redesigning its
core routing, sensor, purge, heater, persistence, or automatic-fallback behavior. The
recommended milestone delivers five bounded capabilities:

1. Best-effort external notifications for meaningful fallback outcomes.
2. Atomic runtime replacement and restoration of ordered backup lists.
3. Printer-specific integration examples and a supervised live-printer UAT runbook.
4. Representative live-printer evidence for the v1.1 integration scenarios.
5. Clean-checkout CI and exact-commit release verification.

The existing architecture already provides the required foundations: a configurable
`notify_gcode` adapter, immutable schema-v1 state, atomic save-before-publish
persistence, ordered graph resolution, visible workflow checkpoints, and deterministic
pytest fakes. v1.1 should preserve the stdlib-only runtime and add no new service,
network client, package framework, durable schema, or hardware simulation framework.

The most important planning decision is notification failure policy. `ARCHITECTURE.md`
contains a conflicting proposal that notification failure should block otherwise
successful recovery. The stronger cross-source recommendation from `STACK.md`,
`FEATURES.md`, and `PITFALLS.md` is safer and should govern requirements:

> Notifications observe outcomes; they do not determine safety outcomes.

A notification adapter failure must be locally visible, but must never change canonical
state, mappings, hardware actions, workflow stage, pause ownership, or the extension's
existing resume decision.

## Explicit Scope Exclusion

The following four Phase 1 UAT scenarios are **not v1.1 requirements** and must not be
included in v1.1 UAT, release acceptance, milestone completion claims, blockers, or
evidence attribution:

1. Valid Configuration Startup
2. Persisted State Survives Restart
3. Invalid State Blocks Startup Clearly
4. Read-Only Status Inspection

They remain separately deferred by user instruction. Automated regression coverage and
incidental startup, restart, or status observations may continue, but they do not
complete or absorb these four scenarios.

## Key Findings

### Preserve The Existing Stack

- Keep production code Python-stdlib-only in `klippy/extras/`.
- Continue using Klipper lifecycle objects, reactor timers, G-Code registration, and
  `gcode.run_script_from_command()` for printer-owned adapters.
- Continue using immutable `FallbackState` candidates and `StateStore.save()` for all
  durable changes.
- Keep schema version 1; ordered `backups` are already durable canonical state.
- Keep pytest and the existing deterministic fakes as the automated verification stack.
- Use Markdown/config examples, GitHub Actions, semantic version tags, and GitHub
  Releases for operational delivery.
- Do not publish a wheel; the deliverable remains Klipper extension modules plus
  examples and documentation.

### Notifications Are An Adapter Boundary

- Invoke the existing configured `notify_gcode`; do not add direct Moonraker, HTTP,
  webhook, Discord, Telegram, MQTT, or credential handling to Python.
- Emit only externally meaningful terminal outcomes:
  `FALLBACK_SUCCESS`, `FALLBACK_FAILURE`, and `TRANSIENT_RECOVERY`.
- Build event data centrally from immutable workflow context and deduplicate by workflow
  generation plus event identity.
- Use a fixed, bounded, injection-safe parameter contract. Free-form exception text must
  be sanitized, bounded, or omitted from the external transport.
- Catch adapter failures once, report them locally, and preserve the already-decided
  workflow outcome.
- Adapter success means only that the configured macro returned successfully; it does
  not prove downstream message delivery.

### Backup Mutation Fits Schema V1

- Add one pure immutable state primitive equivalent to
  `FallbackState.with_backups(tool, ordered_backups)`.
- Validate the complete replacement before persistence: configured canonical tools only,
  no self-reference, no duplicates, exact order preserved, and cycles still allowed
  because the existing resolver safely contains them.
- Follow immutable candidate -> atomic save -> publish. Persistence failure must leave
  the prior published state unchanged; exact no-ops must not rewrite the file.
- Reject mutation while any workflow checkpoint or active route transition exists.
- Allow mutation during an otherwise active or paused print when no extension workflow
  is active, because it changes future policy only.
- Mutation must not select hardware, change mappings, or alter pause ownership.

Recommended minimal command surface:

```text
SET_TOOL_BACKUPS TOOL=T0 BACKUPS=T2,T1
RESTORE_TOOL_BACKUPS TOOL=T0
RESET_TOOL_BACKUPS
```

`SET_TOOL_BACKUPS` replaces one complete ordered list and accepts an empty list.
`RESTORE_TOOL_BACKUPS` restores one tool's configured startup list.
`RESET_TOOL_BACKUPS` restores all configured startup lists in one persisted transaction.
Incremental add/remove/move convenience commands should remain out of initial v1.1 scope.

### Live Evidence Must Remain Bounded

- Examples are executable operational interfaces and require automated drift checks plus
  explicit printer-specific assumptions.
- Live UAT must be supervised, staged, reversible, and run only after automated contracts
  and adapter examples are stable.
- Record the exact printer topology, configuration revision, Klipper/Moonraker revisions,
  extension commit/tag, procedure, expected result, observed result, and evidence.
- Separate automated, simulated, configuration-load, and live-hardware claims.
- One representative printer does not establish universal compatibility.

### CI And Release Verification Encode Settled Contracts

- CI should run from a clean checkout on pushes and pull requests.
- Run stdlib compile/import checks, the complete pytest suite with zero-tests protection,
  example-contract tests, and `git diff --check`.
- Use an explicit representative Python matrix; the research recommends 3.9, 3.11, and
  3.13 initially.
- Keep hosted CI hardware-free and network-independent.
- Release only from a clean, verified semantic-version tag whose commit matches the
  examples, documentation, artifacts, and current live-UAT evidence.

## Recommended v1.1 Scope

### In Scope

- Stable notification event contract and injection-safe adapter invocation.
- Exactly-once outcome notification behavior for successful fallback, fallback failure,
  transient recovery, heating timeout/guarded continuation outcomes, and resume failures
  where applicable.
- Notification failure isolation and local diagnostics.
- Atomic backup-list replace, per-tool restore, and all-tool reset commands.
- Validation, workflow conflict guards, durability, visibility, no-op behavior, and
  resolver-priority proof for runtime backup mutation.
- Complete printer-specific installation/integration example for the representative UAT
  printer, plus clearly marked adaptation guidance.
- Supervised live UAT for routing, active remap, sensor integration, purge lifecycle,
  automatic fallback success, contained failure, transient recovery, guarded resume,
  notifications, and runtime backup mutation.
- CI, local/release verification commands, release checklist, and exact-commit evidence
  audit.

### Out Of Scope

- The four explicitly excluded Phase 1 UAT scenarios.
- Direct notifier clients, credentials, retries, queues, delivery databases, or persisted
  notification state.
- Notification delivery as a prerequisite for fallback completion or resume.
- A schema migration or separate backup graph store.
- Live mutation of configured tool identities, heaters, sensors, or physical handlers.
- Incremental backup-list editing commands in the initial command contract.
- Universal printer/toolchanger compatibility claims.
- Destructive or unsupervised hardware fault injection.
- New packaging/test frameworks or automatic release publication without live evidence.

## Recommended Architecture And Build Order

### Phase 5A: Runtime Contracts And Automated Proof

1. Add the pure immutable backup replacement primitive and state-level tests.
2. Add `SET_TOOL_BACKUPS`, `RESTORE_TOOL_BACKUPS`, and `RESET_TOOL_BACKUPS` through the
   existing persistence and workflow-guard paths.
3. Define one centralized notification event/formatting boundary with fixed event names,
   bounded safe transport, re-entry protection, and generation/event deduplication.
4. Integrate notifications at final outcome boundaries without changing existing safety,
   checkpoint, persistence, or resume decisions.
5. Add adversarial tests for special characters, recursion/re-entry, adapter exceptions,
   stale callbacks, duplicate callbacks, persistence failures, workflow conflicts, and
   changed graph priority.

**Gate:** Runtime behavior is deterministic; notification failures cannot alter safety
outcomes; backup mutation validates and saves before publication.

### Phase 5B: Examples And Supervised Integration UAT

1. Build examples from the stabilized command and adapter contracts.
2. Document installation, rollback, physical `Tn` ownership, sensor hooks,
   `PAUSE_OWNED`, purge, notification, guarded resume, backup mutation, preflight, and
   stop/recovery procedures.
3. Add lightweight automated checks that examples use current command/option names and
   distinct non-recursive adapters.
4. Execute the staged representative live-printer matrix and record exact evidence.

**Gate:** Examples are loadable and bounded to stated hardware assumptions; every live
claim has recorded observations; incomplete workflows remain paused according to the
existing safety model.

### Phase 5C: CI And Release Verification

1. Add one local verification entry point for compile/import checks, full pytest,
   example checks, zero-tests protection, and whitespace checks.
2. Make pull-request/push CI invoke the same verification contract.
3. Add tag/release verification for exact commit, artifact contents, documentation,
   examples, changelog/version, migration/rollback notes, and live-UAT evidence.
4. Audit release claims against the tested commit and explicitly state that the four
   Phase 1 UAT scenarios were excluded.

**Gate:** The exact release candidate commit has green clean-checkout verification,
matching artifacts/docs/examples, and current representative live-printer evidence.

## Principal Risks And Mitigations

| Risk | Required mitigation |
|---|---|
| Notification adapter changes workflow behavior | Best-effort isolation; catch once; preserve original state, checkpoint, ownership, and resume decision |
| G-Code injection or parser breakage from messages | Fixed event vocabulary; bounded reversible encoding or sanitized fields; special-character and real-parser tests |
| Duplicate or stale notification events | Deduplicate by workflow generation and event identity; test retries, stale timers, and guarded resume |
| Notification recursion/re-entry | Distinct private adapter, first-token validation, delivery guard, and re-entry tests |
| Backup mutation publishes before persistence | Pure immutable candidate, complete validation, one atomic save, publish only after success |
| Backup graph changes during active work | Reject mutation for every checkpoint and active transition |
| Runtime/config default semantics become ambiguous | Persisted runtime policy remains authoritative; configured lists are used only for new tools and explicit restore/reset |
| Examples encode unsafe universal behavior | Mark substitutions and assumptions, use non-recursive adapters, stage commissioning, validate against the UAT printer |
| Simulated tests are presented as hardware proof | Maintain an evidence matrix and label each claim by proof type |
| Release evidence does not match the tag | Verify exact clean commit; rerun affected UAT after behavior/example changes; audit release contents and claims |

## Requirement Recommendations

The v1.1 requirements should be written as observable contracts:

1. **NOTIFY-01:** Emit at most one stable external event per workflow generation and
   terminal outcome for fallback success, fallback failure, and transient recovery.
2. **NOTIFY-02:** Notification adapter absence, failure, delay, recursion, or re-entry
   cannot change canonical state, mappings, hardware actions, workflow outcome, pause
   ownership, or resume policy; failure remains locally visible.
3. **NOTIFY-03:** External event parameters use a fixed injection-safe bounded transport
   and include useful canonical context without promising downstream delivery.
4. **BACKUP-01:** Replace one tool's complete ordered backup list atomically, including
   clearing it, while preserving all unrelated state.
5. **BACKUP-02:** Restore one tool or all tools to configured backup defaults through the
   same atomic persistence path.
6. **BACKUP-03:** Reject malformed, unknown, duplicate, and self-referential lists;
   preserve order; retain current loop-safe cycle policy.
7. **BACKUP-04:** Reject mutation during any workflow checkpoint or active transition;
   successful changes affect only future resolution and are immediately visible.
8. **BACKUP-05:** Persistence failure leaves published state unchanged; exact no-ops do
   not write.
9. **EXAMPLE-01:** Ship an internally consistent representative integration example with
   installation, rollback, adapters, hooks, ownership assumptions, commissioning, and
   printer-specific hazards.
10. **UAT-01:** Record supervised representative live-printer evidence for the bounded
    v1.1 routing, sensor, heater, purge, fallback, guarded-resume, notification, and
    backup-mutation matrix.
11. **CI-01:** Clean-checkout CI runs syntax/import checks, the complete deterministic
    pytest suite with zero-tests protection, example checks, and `git diff --check`.
12. **RELEASE-01:** Release verification binds green CI, artifact contents, docs/examples,
    and current live-UAT evidence to the exact clean semantic-version tag.
13. **SCOPE-01:** Release and milestone evidence explicitly names the four excluded
    Phase 1 UAT scenarios and makes no claim that v1.1 completes them.

## Completion Recommendation

Declare v1.1 complete only when operational notifications are useful but safety-neutral,
operators can durably manage ordered fallback policy without restart, representative
printer integration is documented and evidenced, and CI/release verification proves the
exact deliverable. Keep all claims bounded to the tested configuration and preserve the
four Phase 1 UAT scenarios as separately deferred work.
