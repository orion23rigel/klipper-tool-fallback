# Feature Research: v1.1 Integration & Operations

## Scope

v1.1 should operationalize the shipped v1.0 behavior without redesigning routing,
sensor, purge, active-transition, or automatic-fallback semantics. The milestone adds:

- external success, failure, and transient-recovery notifications;
- atomic runtime mutation of persisted ordered backup lists;
- printer-specific installation and integration examples;
- representative supervised live-printer UAT; and
- CI and release verification.

The extension already has the required foundations: configurable `notify_gcode`,
immutable canonical state, atomic persistence, ordered backup traversal, visible workflow
checkpoints, and deterministic fakes covering the complete fallback workflow.

## Explicit Exclusion

The following four Phase 1 UAT scenarios are **not v1.1 requirements** and must not be
included in v1.1 UAT, release acceptance, or milestone completion claims:

1. Valid Configuration Startup
2. Persisted State Survives Restart
3. Invalid State Blocks Startup Clearly
4. Read-Only Status Inspection

They remain separately deferred by user instruction. Existing automated regression
coverage may continue to run, but it does not make these scenarios part of v1.1 UAT.

## Feature Classification

| Class | Feature | Expected behavior and testable contract |
|---|---|---|
| Table stakes | External outcome notifications | Invoke the configured adapter for automatic-fallback success, terminal or recoverable failure, and confirmed transient recovery. Each event is emitted at most once per workflow generation and contains stable machine-readable event identity plus useful operator context. |
| Table stakes | Notification failure isolation | Notification is an operational side effect, not a safety checkpoint. Adapter absence or failure produces a local warning but never changes mappings, tool state, workflow stage, pause ownership, or resume policy. |
| Table stakes | Runtime backup-list replacement | A public command atomically replaces one physical tool's complete ordered backup list, including replacing it with an empty list. The list is validated using the same canonical-name, configured-tool, duplicate, and self-reference rules as persisted/configured state. |
| Table stakes | Runtime backup-list reset | A public command restores one tool's backup list to its configured default. This gives operators a deterministic escape from accumulated runtime policy changes. |
| Table stakes | Mutation durability and visibility | Successful mutation persists before publication, survives extension restart, immediately appears in status, and controls the next fallback graph resolution. Persistence failure leaves the prior published list unchanged. |
| Table stakes | Workflow conflict guard | Backup-list mutation is rejected while any fallback/transition workflow checkpoint is active. It may be allowed during an otherwise active print because it changes future policy and does not select hardware. |
| Table stakes | Installable printer examples | Provide complete examples showing file installation, `[tool_fallback]`, every managed `[tool_fallback Tn]`, sensor hooks, physical `Tn` macros, pause/resume integration, purge adapter, notification adapter, and state-file location. |
| Table stakes | Representative live-printer UAT | A supervised runbook proves command identity/routing, sensor hooks, heater target transfer, purge execution, successful fallback, contained failures, and guarded resume on real Klipper hardware. Evidence identifies printer/config revision and observed result. |
| Table stakes | CI verification | Every push and pull request runs syntax checks, the complete pytest suite, and a whitespace/diff check in a clean environment. A no-tests-collected result must fail. |
| Table stakes | Release verification | A tagged release is created only from a clean verified commit, has a documented version/changelog, packages the three extension modules plus required examples/docs, and passes a clean-install smoke check. |
| Differentiator | Truthful, context-rich notifications | Success names logical route, failed physical tool, selected backup, and attempted graph; failure names stage and reason; transient recovery names source and whether fallback-owned resume succeeded or was unnecessary. |
| Differentiator | Notification deduplication across guarded recovery | A heating timeout may notify failure/recovery-needed once; later guarded completion may notify success once. Repeated `RESUME` attempts or stale callbacks do not duplicate either event. |
| Differentiator | Ordered policy editing without restart | Operators can change fallback priority during normal operation and verify it immediately through status without editing JSON or restarting Klipper. |
| Differentiator | Configuration reset without overwriting runtime policy at startup | Runtime backup policy remains operator-owned persisted state; configured defaults are used only for new tools and explicit reset, preserving v1.0 reconciliation semantics. |
| Differentiator | Hardware evidence matrix | UAT records which claims are software-tested, live-printer-verified, printer-specific, or still unverified, preventing broad compatibility claims from one setup. |

## Recommended Testable Contracts

### 1. External Notifications

Recommended event identities:

| Event | Emit point | Required context |
|---|---|---|
| `FALLBACK_SUCCESS` | After selection, readiness, conditional purge, and mapping persistence complete; after owned resume succeeds, or immediately when no resume is owned | workflow generation, logical tool, failed physical tool, selected backup, attempted tools |
| `FALLBACK_FAILURE` | When a workflow enters `blocked` or `heating_timeout`; also when post-recovery resume fails | generation, logical tool when known, failed/source tool, requested backup when known, stage, attempted tools when available, failure reason, pause ownership |
| `TRANSIENT_RECOVERY` | After debounce confirms filament returned before runout confirmation | generation, physical tool, logical tool when known, pause ownership, resume outcome |

Notification implementation contracts:

- Use `notify_gcode` as the printer-owned adapter boundary; do not hard-code Moonraker,
  Discord, webhook, or service credentials in Python.
- Define a stable adapter parameter schema and safely encode free-form values such as
  failure reasons. Tests must include whitespace, quotes, and adapter exceptions.
- Emit only externally meaningful outcomes. Do not notify for ignored runout, stale
  callbacks, ordinary selection, manual remap, or every internal stage transition.
- Deduplicate by workflow generation plus event identity. A guarded retry must not replay
  the original failure event, and stale generations must emit nothing.
- Preserve local `respond_info` and status visibility even when notification succeeds.
- Catch adapter failures, report them locally, and continue the already-decided safety
  behavior. A notifier outage must never prevent or cause resume.

Automated acceptance:

- Success, each representative failure stage, heating timeout, guarded completion,
  transient owned recovery, and transient user-owned recovery assert exact event count,
  ordering, and parameters.
- Injected notification failures prove unchanged canonical state, checkpoint, scripts,
  and pause/resume behavior.
- Repeated/stale callbacks and repeated guarded resume attempts prove no duplicates.

### 2. Runtime Backup-List Mutation

Recommended public commands:

```text
SET_TOOL_BACKUPS TOOL=T0 BACKUPS=T1,T3,T2
SET_TOOL_BACKUPS TOOL=T0 BACKUPS=
RESET_TOOL_BACKUPS TOOL=T0
```

`SET_TOOL_BACKUPS` should replace the entire ordered list rather than expose incremental
append/remove/move operations. Whole-list replacement is deterministic, easy to audit,
and naturally atomic. `RESET_TOOL_BACKUPS` restores the normalized configuration list.

Mutation contracts:

- Require initialized routing/state and a configured canonical `TOOL`.
- Preserve the supplied order exactly.
- Reject malformed, unknown, duplicate, and self references before persistence.
- Allow graph cycles, matching current configuration/state rules; the existing resolver
  already terminates safely using visited/attempted sets.
- Block mutation while `_workflow_checkpoint` is non-null so a running resolution cannot
  observe policy changing underneath it.
- Allow mutation during printing or paused state when no workflow is active; it changes
  future policy only and must not select hardware, change mappings, or alter ownership.
- Build an immutable candidate, validate the complete state, atomically persist it, then
  publish it. A no-op does not rewrite the file.
- On persistence error, return a command error and retain the old published state/list.
- Status and `SHOW_TOOL_FALLBACK_STATE` expose the new list immediately after success.
- The next graph resolution uses the new list; an already-active workflow never does.
- Restart preserves successful mutations. Explicit reset restores configured order and is
  itself durable.

Automated acceptance:

- Unit-test state candidate creation and validation.
- Command-test replace, reorder, clear, reset, no-op, malformed input, duplicate, self,
  unknown tool, uninitialized state, active workflow, active print, persistence failure,
  restart durability, and changed resolver choice.

### 3. Printer-Specific Installation And Integration Examples

At least one complete, internally consistent reference configuration should target the
representative UAT printer. A second example should demonstrate adaptation boundaries
rather than claim universal compatibility.

Each example must include:

- installation path or symlink/update procedure for all three Python modules;
- Klipper restart and rollback procedure;
- global and per-tool sections with real heater and sensor object names;
- original physical `Tn` macros that exist before ready-time interception;
- `filament_switch_sensor` `runout_gcode` and `insert_gcode` hooks, including correct
  `PAUSE_OWNED` use;
- distinct purge implementation macro, never recursive public `PURGE_TOOL`;
- printer's actual `PAUSE`/`RESUME` assumptions and guarded-resume behavior;
- `_TOOL_FALLBACK_NOTIFY` adapter example using printer-owned notification integration;
- safe commissioning sequence before enabling runout-triggered fallback;
- operational commands for inspection, remap, purge state, and backup-list mutation;
- known printer-specific assumptions and unsupported variants.

Documentation acceptance:

- Every referenced command/config option exists and every example parses under a
  representative Klipper config validation or equivalent smoke harness.
- Example names and adapter calls agree with the live UAT configuration.
- No example asks an operator to edit the persisted JSON directly.

### 4. Representative Live-Printer UAT

Run on a named, supervised printer with a reversible test configuration, safe
temperatures/material, and an operator able to stop motion/heating. Capture Klipper and
Moonraker logs, relevant status snapshots, notification evidence, and pass/fail notes.

Required v1.1 live scenarios:

| Scenario | Observable acceptance |
|---|---|
| Logical and physical routing | Logical `Tn` invokes the mapped physical handler; direct physical selection bypasses mapping; macro command identity is compatible with the printer. |
| Active remap | During a controlled active job, remap pauses safely, transfers heat/selects/purges as required, persists route, and resumes only when owned. |
| Sensor integration | Real runout/insert hooks and sensor disable/re-enable behavior update authority/state without false fallback. |
| Purge lifecycle | Real purge adapter executes once when required, marks purged only after success, and leaves unpurged on injected/observed failure. |
| Successful automatic fallback | Confirmed runout shuts down source heat, selects the expected ordered eligible backup, reaches readiness, purges if needed, persists mapping, sends one success notification, and resumes only when owned. |
| Contained fallback failure | A safely induced no-backup, selection, heating, purge, or persistence-class failure leaves the printer paused, exposes a useful checkpoint/reason, and sends one failure notification. Do not induce destructive hardware faults. |
| Transient runout recovery | Filament returns before confirmation; no tool failure/mapping change occurs, one transient notification is sent, and only an extension-owned pause resumes. |
| Guarded resume | A controlled heating-timeout checkpoint blocks normal resume; after readiness is restored, guarded resume completes remaining work once and emits the correct final notification. |
| Runtime backup mutation | Reorder backup policy without restart, verify status, then trigger a controlled resolution proving the new first eligible candidate is chosen; reset restores configured order. |

Evidence must state that results apply to the tested printer configuration. Passing this
matrix does not claim compatibility with all toolchangers, sensors, macros, or heaters.

### 5. CI And Release Verification

CI table stakes:

- Trigger on pull requests and pushes to the maintained branch.
- Use a supported Python matrix representative of Klipper's Python 3 runtime.
- Run `python3 -m py_compile klippy/extras/tool_fallback*.py`.
- Run `pytest -q` and explicitly fail if zero tests are collected.
- Run `git diff --check`.
- Keep tests deterministic and independent of network, Moonraker, or live hardware.
- Publish concise failure logs; optional coverage may inform quality but should not become
  a release gate until a justified threshold exists.

Release table stakes:

- CI is green on the exact release commit and the working tree is clean.
- Release notes enumerate operator-visible behavior, commands, configuration changes,
  compatibility assumptions, known limitations, and migration/rollback instructions.
- Tag/version format remains consistent with `v1.0.0`.
- A clean-install smoke test verifies the release artifact contains/imports all extension
  modules and that examples reference valid commands/options.
- Live-printer UAT evidence is linked or recorded before release approval.
- Release verification explicitly notes that the four excluded Phase 1 UAT scenarios
  were not part of v1.1 acceptance.

## Anti-Features

| Anti-feature | Why exclude it from v1.1 |
|---|---|
| Hard-coded notifier providers, credentials, URLs, or network clients | Violates the existing printer-adapter boundary and creates security/reliability scope unrelated to fallback safety. |
| Treating notification delivery as a fallback success prerequisite | An external service outage must not leave hardware in a less safe state or change resume behavior. |
| Notification retries with background queues or persistent delivery state | Adds duplicate, restart, and ordering complexity disproportionate to v1.1; printer-owned adapters may handle delivery policy. |
| Editing backup lists by modifying JSON | Bypasses validation, atomic command semantics, status feedback, and operator safety. |
| Incremental append/remove/move command family | Creates more race and partial-update surface than atomic whole-list replacement. |
| Changing backup policy during an active workflow | Makes attempted/visited graph evidence and deterministic resolution unreliable. |
| Silently overwriting runtime backup lists from config at restart | Breaks established operator-owned persistence semantics. |
| Changing mappings or selecting hardware as a side effect of backup mutation | Backup lists are future fallback policy, not active routing commands. |
| Universal printer compatibility claims | One representative UAT setup cannot validate every toolchanger macro, sensor polarity, heater, or pause implementation. |
| Destructive live fault injection | Hardware UAT should induce safe, reversible failure classes rather than damage-risking mechanical/electrical faults. |
| Folding the four Phase 1 UAT scenarios into v1.1 acceptance | Directly conflicts with the user's explicit milestone boundary. |
| Automatic publishing from any green branch build | Releases require human approval, live-printer evidence, and verification of the exact tagged commit. |

## Complexity And Risk

| Area | Complexity | Main risks | Mitigation / proof |
|---|---|---|---|
| Notification adapter invocation | Medium | Unsafe parameter encoding, duplicate events, adapter exception changing workflow | Central event helper; generation/event dedupe; injected failures and special-character tests |
| Notification timing | High | Reporting success before persistence/resume; missing failure at a caller boundary | Emit at terminal outcome boundaries; adversarial tests for every block/timeout/resume path |
| Backup-list state mutation | Medium | Partial publication, invalid references, changed graph during workflow | Immutable full-state candidate; existing state validator; persist-before-publish; workflow guard |
| Config-default reset semantics | Low-Medium | Confusing configured defaults with persisted operator policy | Explicit reset only; tests for restart/reconciliation and reset |
| Printer examples | Medium | Examples drift from commands or encode unsafe printer assumptions | Use live UAT config as reference; smoke-check examples; document assumptions |
| Live-printer UAT | High | Safety, irreproducible evidence, printer-specific behavior | Supervised reversible runbook, preconditions, logs/status evidence, bounded claims |
| CI | Low-Medium | False-green runs, environment drift, warning noise | Clean runner, full-suite command, zero-test guard, pinned/declared tooling where needed |
| Release verification | Medium | Tagging wrong commit, incomplete artifact, undocumented migration | Exact-commit gates, clean-install smoke test, checklist and release notes |

## Dependencies And Ordering

| Dependency | Needed by | Notes |
|---|---|---|
| Existing `notify_gcode` normalized global option | Notifications and printer examples | Already present but not invoked. |
| Existing `WorkflowCheckpoint`, generation, graph report, and failure reason | Truthful notification context and deduplication | Notification design should consume these rather than create parallel workflow state. |
| Existing fail-closed caller boundaries | Failure notifications | Audit all paths entering `blocked` or `heating_timeout`; a central transition hook reduces omissions. |
| Existing immutable `FallbackState` and atomic `StateStore.save` | Runtime backup mutation | Add a narrow `with_tool_backups`-style candidate operation; do not mutate mappings or other tool flags. |
| Existing normalized configured backup lists | Reset command | `self.config.tools[tool].backups` is the reset source. |
| Existing `_guard_workflow_operation` | Runtime mutation conflict safety | Reuse the established user-facing guard behavior. |
| Deterministic fake G-code adapter and injected script failures | Notification and mutation tests | Extend fakes to capture notification adapter calls and failures. |
| Representative printer and operator access | Live UAT and example validation | Hardware UAT cannot be replaced by fake-based CI. |
| Stable examples/runbook | Release verification | Release smoke tests should validate the same artifacts operators receive. |

Recommended implementation order:

1. Add atomic state-level backup replacement and command contracts with automated tests.
2. Add centralized best-effort notification emission and adversarial outcome tests.
3. Create printer-specific examples and a supervised UAT runbook from the actual target.
4. Execute and record representative live-printer UAT.
5. Add CI gates and release verification using the stabilized commands, examples, and UAT
   evidence.

## Milestone Acceptance Summary

v1.1 is complete when external outcomes are useful without affecting safety, operators
can atomically manage ordered backup policy at runtime, a real printer has passed the
bounded integration matrix, examples accurately reproduce that integration, and CI plus
release checks verify the exact deliverable. Completion must explicitly retain the four
Phase 1 UAT scenarios as excluded, separately deferred work.
