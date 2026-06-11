# Phase 5: Runtime Contracts - Research

**Researched:** 2026-06-11
**Status:** Complete
**Scope:** Safety-neutral terminal notifications and atomic runtime backup-policy
management

## Phase Boundary

Phase 5 should add two operational contracts without changing the shipped fallback
safety model:

1. Emit best-effort external observations for final automatic-fallback outcomes.
2. Let operators replace, clear, restore, or reset persisted ordered backup policy.

Notifications must never decide or alter workflow safety. Backup-policy commands must
never select hardware, change mappings, alter the active workflow's frozen graph
decision, or change pause/resume ownership.

The discussion-approved queue contract is authoritative:

> Backup mutations submitted during an active workflow checkpoint or route transition
> are queued, not rejected. They are applied in submission order after a terminal
> workflow outcome or transition exit, once no route transition is active.

This explicitly supersedes the reject-during-workflow advice in
`.planning/research/SUMMARY.md`, `.planning/research/ARCHITECTURE.md`, and
`.planning/research/PITFALLS.md`. Those documents remain useful for persistence,
validation, notification isolation, and injection-safety guidance, but their mutation
rejection recommendation must not be carried into Phase 5 plans.

## Existing Runtime Findings

### Reusable Foundations

| Existing asset | Phase 5 use |
|---|---|
| `WorkflowCheckpoint` and `_workflow_generation` in `tool_fallback.py` | Stable event identity and final workflow context |
| `_block_workflow()` | Existing point where blocked state becomes locally visible |
| `_transition_active` | Exclusion guard and transition-exit queue-drain trigger |
| `resolve_backup_graph()` | Proves ordered runtime backup policy affects future resolution without needing a new resolver |
| `FallbackState._replace_tool()` | Pattern for immutable backup replacement while preserving unrelated fields |
| `StateStore.save()` and `_persist_state()` | Atomic save-before-publish path and exact persisted-state no-op suppression |
| Configured immutable `ToolConfig.backups` | Authoritative restore/reset defaults |
| Configured `notify_gcode` | Printer-owned notification adapter boundary |
| Deterministic reactor, G-Code, heater, and persistence fakes | Adversarial notification, queue, and ordering tests |

### Current Terminal Paths Are Scattered

The implementation does not yet have one terminalization boundary:

- `_complete_transient_runout()` clears the checkpoint before owned resume and recreates
  a blocked checkpoint only if resume fails.
- Normal fallback success persists the mapping, clears the checkpoint, then attempts
  owned resume.
- Guarded-resume success duplicates purge/persist/clear/resume behavior.
- Failures generally pass through `_block_workflow()`, but manual active-route
  transition helpers also use `_block_workflow()`.
- `_transition_active` is cleared in a `finally` block after success or failure.

Plans should introduce narrow terminal helpers rather than adding notification and queue
logic independently at every return site. A blind extension of `_block_workflow()` is
not sufficient because it is also used by manual route transitions, which are not
notification outcomes.

### Important Existing Semantics

- A `heating_timeout` checkpoint is recoverable and is not terminal.
- A `blocked` checkpoint is terminal but intentionally remains visible.
- Successful fallback mapping publication already rebuilds from current canonical state.
- Runtime state remains schema v1; workflow checkpoints and transitions are not durable.
- `StateStore.save()` returns `False` for equal persisted state, while immutable
  candidate helpers conventionally return the same object for an exact no-op.
- Active-route transitions are synchronous, but configured adapters can re-enter G-Code
  while `_transition_active` is true.

## Notification Contract

### Canonical Payload

Every adapter invocation should contain these parameters in this fixed order:

```text
EVENT=<event>
GENERATION=<integer>
LOGICAL_TOOL=<tool-or-n/a>
FAILED_TOOL=<tool-or-n/a>
SELECTED_TOOL=<tool-or-n/a>
REASON_CODE=<stable-code>
```

Use exactly these event names:

- `FALLBACK_SUCCESS`
- `FALLBACK_FAILURE`
- `TRANSIENT_RECOVERY`

Use `n/a` for unavailable canonical fields. Tool names, event names, generation, reason
codes, and the sentinel already fit a bounded token-safe alphabet.

For unexpected failures only, append:

```text
REASON_DETAIL=<sanitized-detail>
```

Recommended `REASON_DETAIL` policy:

- convert to one ASCII line;
- replace every run outside `[A-Za-z0-9._:/+-]` with `_`;
- strip leading/trailing replacement characters;
- fall back to `n/a` if empty;
- limit to 160 characters after sanitization.

This remains human-readable while preventing whitespace, newline, quote, comment, and
second-command injection. Keep rich exception text in local `respond_info`; external
detail is intentionally lossy. Do not place raw exception text, JSON, quoted strings,
or arbitrary user text in the adapter command.

Recommended invocation shape:

```text
<notify_gcode> EVENT=FALLBACK_FAILURE GENERATION=7 LOGICAL_TOOL=T0 \
FAILED_TOOL=T0 SELECTED_TOOL=T1 REASON_CODE=PURGE_FAILED
```

The configured adapter prefix is trusted printer configuration, but dynamic parameters
must be generated centrally. Adapter success means only that
`run_script_from_command()` returned; it does not promise downstream delivery.

### Stable Reason-Code Vocabulary

Pass reason codes explicitly at failure call sites. Do not derive them by parsing the
human-readable `failure_reason`.

Recommended initial vocabulary:

| Code | Meaning |
|---|---|
| `NONE` | Successful fallback or transient recovery |
| `GRAPH_EXHAUSTED` | No eligible backup after the required rescan |
| `ACTIVE_ROUTE_UNKNOWN` | Failed physical tool has no known active logical route |
| `PAUSE_FAILED` | Required pre-fallback pause failed |
| `SOURCE_HEATER_MISSING` | Source heater was unavailable |
| `SOURCE_HEATER_READ_FAILED` | Source target read failed |
| `SOURCE_TARGET_INVALID` | Captured source target was invalid |
| `SOURCE_SHUTDOWN_FAILED` | Failed heater could not be shut down |
| `DESTINATION_HEATER_MISSING` | Backup heater was unavailable |
| `PREHEAT_FAILED` | Backup preheat command failed |
| `SELECTION_FAILED` | Physical backup selection failed |
| `SELECTION_TIMEOUT` | Physical selection returned after its deadline |
| `HEATER_READINESS_FAILED` | Readiness check failed |
| `PURGE_FAILED` | Required backup purge failed |
| `MAPPING_PERSIST_FAILED` | Final fallback mapping could not be persisted |
| `RESUME_FAILED` | Automatic resume failed after transient or fallback recovery |
| `UNEXPECTED_FAILURE` | Unclassified internal failure with sanitized detail |

`HEATING_TIMEOUT` should not be emitted because a heating timeout is a recoverable
checkpoint, not a final outcome. If guarded continuation later fails, emit the specific
terminal failure code.

Add `failure_code` to runtime checkpoint context or pass a separate immutable event
record into terminalization. Do not persist it in schema v1.

### Timing And Final Outcome Rules

Notification timing must describe the final outcome, including resume:

| Path | Required timing |
|---|---|
| Transient clears, no owned resume | Emit `TRANSIENT_RECOVERY` after confirmed loaded state and checkpoint completion |
| Transient clears, owned resume succeeds | Emit `TRANSIENT_RECOVERY` after resume succeeds |
| Transient clears, owned resume fails | Establish blocked checkpoint, emit `FALLBACK_FAILURE` / `RESUME_FAILED` |
| Normal fallback succeeds without owned resume | Emit `FALLBACK_SUCCESS` after final mapping persistence |
| Normal fallback succeeds with owned resume | Emit `FALLBACK_SUCCESS` after resume succeeds |
| Normal or guarded fallback resume fails | Establish blocked checkpoint, emit `FALLBACK_FAILURE` / `RESUME_FAILED` |
| Any other terminal failure | Establish blocked checkpoint first, then immediately emit `FALLBACK_FAILURE` |
| Heating timeout | Emit nothing until guarded continuation reaches success or blocked failure |

This ordering is necessary for D-08: a physically completed recovery with a failed
automatic resume is externally a failure, not a success.

Build the event from captured immutable terminal context before queue draining. Queue
application may change future backup policy and must not change the event describing the
completed generation.

### Deduplication And Re-entry

Maintain a runtime-only set of attempted event identities:

```text
(generation, event_name)
```

Mark the identity before invoking the adapter. An adapter failure still consumes the
single best-effort attempt; there are no retries. Stale callbacks and repeated terminal
helpers then become local no-ops for external delivery.

Use a `_notification_in_progress` guard around adapter invocation. During that guard:

- recursive notification attempts are suppressed and reported locally;
- extension-owned public commands that could mutate state, mappings, hardware,
  workflow, pause ownership, or resume policy must reject re-entry;
- notification exceptions and elapsed delays are caught and reported locally;
- the already-decided terminal outcome, checkpoint, canonical state, and resume result
  remain unchanged.

Backup commands invoked by the notification adapter should be rejected as notification
re-entry, not queued. Queueing them would allow notification behavior to mutate future
canonical policy, conflicting with NOTIFY-02.

Do not add a notification timeout that implies cancellation. Like existing synchronous
G-Code adapters, arbitrary macro execution cannot safely be preempted. A delayed adapter
may delay the caller, but after it returns it must not alter the final outcome.

## Backup Mutation Contract

### Pure Immutable State Operations

Add `FallbackState.with_backups(tool, ordered_backups)` with these semantics:

- require a known canonical source tool;
- require every backup to be a known canonical tool;
- reject self-reference and duplicates;
- preserve requested tuple order exactly;
- preserve every loaded/purged/failed field, every unrelated tool, and every mapping;
- allow cross-tool cycles because the existing resolver contains them safely;
- return `self` for an exact no-op.

For reset-all, either add a pure all-backups replacement helper or derive a candidate by
repeated immutable `with_backups()` calls and persist only the final candidate once.
Never persist intermediate reset state.

### Command Parsing And Operations

Register beside the existing routing commands:

```text
SET_TOOL_BACKUPS TOOL=T0 BACKUPS=T2,T1
RESTORE_TOOL_BACKUPS TOOL=T0
RESET_TOOL_BACKUPS
```

`SET_TOOL_BACKUPS TOOL=T0 BACKUPS=` clears the list. Parse and validate the complete
request before immediate application or enqueue:

- trim the complete `BACKUPS` value;
- empty complete value means `()`;
- otherwise split on commas and reject empty interior/trailing entries;
- require exact configured canonical names;
- reject duplicate and self entries;
- preserve order.

Early validation ensures malformed commands are rejected rather than becoming delayed
queue failures. Queue application still builds its candidate from the latest canonical
state, so multiple queued commands for the same tool remain distinct ordered operations.

Restore semantics use immutable configured defaults:

- `RESTORE_TOOL_BACKUPS TOOL=T0` restores only `config.tools["T0"].backups`;
- `RESET_TOOL_BACKUPS` restores every configured tool's defaults in one transaction.

Configured defaults do not otherwise override persisted runtime policy.

### Immediate Application

When no workflow checkpoint, route transition, notification delivery, or older queued
operation is active:

1. Build the immutable candidate from current canonical state.
2. If it is an exact no-op, report `no write` and the unchanged canonical ordered list.
3. Otherwise call the existing `_persist_state(candidate)` once.
4. Publish only after save succeeds.
5. Report the affected tool and complete canonical persisted ordered list.

Backup mutation never calls physical handlers, pause/resume, purge, heater, mapping, or
graph-resolution workflow code.

### Queue Lifecycle

Recommended queue representation is a runtime-only FIFO of frozen records:

```text
sequence, operation, tool, backups
```

Do not store a `gcmd` object. The submitting command receives its immediate queue receipt
through `gcmd.respond_info`; later drain results use global `gcode.respond_info`.

Queue when either condition is true:

- `_workflow_checkpoint is not None`, including `debouncing`, `heating_timeout`, and
  terminal `blocked`;
- `_transition_active is True`.

The immediate receipt should report queue position, normalized operation, target/tool
where applicable, and active stage (`checkpoint.stage` or `route_transition`).

The active workflow must continue using the graph decision and physical candidate it
already resolved. Queued policy changes are future-resolution policy only.

### Drain Triggers And Safety

Drain only while `_transition_active` is false and notification delivery is not active:

- after transient recovery reaches final success or final resume failure;
- after normal fallback reaches final success or blocked failure;
- after guarded continuation reaches final success or blocked failure;
- after `_block_workflow()` establishes a terminal automatic-fallback block;
- after a synchronous route transition exits its `finally` block, whether it succeeded
  or failed.

A blocked checkpoint may remain visible while its queued backup operations drain.
Treating every checkpoint as a drain prohibition would violate D-11.

Drain after the terminal notification attempt so notification re-entry cannot join or
alter the terminal batch. Queue failures must not replace, raise over, or otherwise
change the original workflow/transition outcome.

Process each record against the latest state produced by the preceding record:

1. Build candidate.
2. Report and remove exact no-op without writing.
3. Persist and publish changed candidate, then report and remove it.
4. On first failure, report the failed record and all remaining unapplied records, stop,
   and leave the failed record plus remaining records in FIFO order.
5. Report final applied/no-op/failed/remaining totals.

Retaining the failed suffix avoids silently discarding accepted commands. A later safe
drain trigger may retry from the failed head; a newly submitted safe command must join
behind an existing queue rather than bypass it. Expose queue depth and last drain
failure in runtime status so retained work is not hidden.

The queue should remain runtime-only and be lost on Klipper restart/shutdown. Persisting
it would introduce replay and schema-migration hazards outside Phase 5. Register a
shutdown/disconnect diagnostic if the available lifecycle permits it, and document that
pending queue entries must be resubmitted after restart.

## Persistence And No-op Behavior

- Keep schema version 1. Ordered backups already exist in durable state.
- Reuse `_persist_state()`; do not create a backup-specific store.
- Candidate construction and full validation happen before one save.
- Save failure leaves `self.state` unchanged.
- Exact no-ops do not call `StateStore.save()`.
- Reset-all performs one final save or no save.
- Queue processing publishes each successful distinct operation separately, because
  D-12 requires every queued command to remain a distinct operation.
- A later same-tool queued command must observe the prior successful queued result.
- A queued exact no-op is still reported as a processed distinct operation.

## Likely Files And Changes

| File | Likely work |
|---|---|
| `klippy/extras/tool_fallback_state.py` | Add pure ordered-backup replacement helper(s) |
| `klippy/extras/tool_fallback.py` | Register commands; parse/apply/queue/drain operations; central terminal helpers; notification formatting, guard, dedup, and invocation; status diagnostics |
| `klippy/extras/tool_fallback_config.py` | Validate `notify_gcode` first-token ownership only if the chosen runtime design adds a meaningful direct-recursion rule; no new timeout is recommended |
| `tests/test_tool_fallback_state.py` | Backup candidate validation, immutability, order, cycles, unrelated-state preservation, and no-op tests |
| `tests/test_tool_fallback_routing.py` or new `tests/test_tool_fallback_backups.py` | Commands, persistence, queue lifecycle, transition re-entry, and future-resolution tests |
| `tests/test_tool_fallback_fallback.py` | Terminal timing, guarded resume, reason codes, dedup, queue drain, and resume-failure outcome tests |
| `tests/conftest.py` | Only the minimum fake support needed to invoke/re-enter notification adapters and observe ordered diagnostics |

A small pure notification helper module is optional. It is justified only if it keeps
payload sanitization and event construction independently testable without duplicating
workflow policy outside `ToolFallback`.

## Test Recommendations

### Notification Tests

- Fixed field order and `n/a` sentinel for unavailable values.
- Sanitization and bounding of spaces, quotes, backslashes, Unicode, newline, `#`,
  semicolon, command-looking text, and very long unexpected exceptions.
- Exactly one event for normal fallback success.
- No event at recoverable heating timeout; one final event after guarded success/failure.
- Resume failure produces only `FALLBACK_FAILURE REASON_CODE=RESUME_FAILED`.
- Transient recovery emits only after confirmed recovery and owned resume success.
- Every blocked automatic-fallback path emits one specific failure code.
- Adapter absence/failure/delay leaves state, mapping, selected tool, checkpoint,
  workflow outcome, ownership, and resume result unchanged.
- Recursive notification and adapter-triggered extension command re-entry cannot mutate
  extension-owned state or hardware actions.
- Duplicate terminal calls and stale generation callbacks do not emit again.
- Manual route-transition failures do not emit fallback outcome events.

### Backup-State And Immediate-Command Tests

- Replace, reorder, and clear one list while preserving all unrelated state.
- Restore one and reset all from configured defaults.
- Reject unknown source/backup, lowercase/malformed names, empty interior entries,
  duplicates, and self-reference.
- Allow and safely resolve cross-tool cycles.
- Exact no-op reports unchanged policy and never saves.
- Persistence failure leaves published state unchanged.
- Commands work while printing or paused when no workflow/transition is active.
- Runtime order changes only future resolver priority and performs no physical action.

### Queue Tests

- Commands at every nonterminal workflow stage queue and do not change active resolution.
- Commands at `heating_timeout` queue and drain only after guarded terminal outcome.
- Commands submitted while a terminal blocked checkpoint exists queue and then drain
  safely despite the retained checkpoint.
- Adapter re-entry during `_transition_active` queues with correct position/stage.
- Transition exit drains on success and failure without masking the transition result.
- Same-tool operations apply distinctly in submission order.
- Queued restore/reset use configured defaults and current canonical state at application.
- Queued no-op does not write but counts as processed.
- First persistence failure stops the drain, preserves the failed suffix, reports every
  remaining unapplied command, and reports totals.
- A later trigger retries from the failed head; new work cannot bypass retained work.
- Restart does not replay runtime-only queued commands.

### Verification Baseline

The existing deterministic suite is green before Phase 5 work:

```text
260 passed
```

The suite currently emits third-party `pytest_asyncio` deprecation warnings under Python
3.14; they are unrelated to Phase 5 runtime behavior.

## Validation Architecture

- Use the existing pytest infrastructure and deterministic Klipper fakes; no new test
  framework or live hardware is required for Phase 5.
- Run focused state/backup tests after backup-policy tasks and focused fallback tests
  after notification or queue-lifecycle tasks.
- Run the complete `pytest -q` suite after every plan wave and before phase verification.
- All Phase 5 behavior is automatable. No manual-only acceptance checks are required.
- Preserve a maximum feedback latency of roughly 30 seconds by using focused test-file
  commands for task-level sampling.

## Principal Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Notification emitted before the real final outcome | Finalize resume result first; treat resume failure as `FALLBACK_FAILURE` |
| Notification adapter changes extension behavior through re-entry | Runtime delivery guard plus public-command re-entry rejection |
| Dynamic detail injects or breaks G-Code | Fixed tokens and bounded single-line safe-alphabet sanitization |
| Duplicate/stale terminal callbacks emit multiple events | Mark `(generation, event)` before adapter invocation |
| Generic `_block_workflow()` notifies manual transitions | Gate notification terminalization to automatic-fallback outcomes |
| Queue drains while graph/transition is still active | Drain only after terminalization and when `_transition_active` is false |
| Retained blocked checkpoint prevents required queue drain | Treat blocked as terminal and allow drain while it remains visible |
| Queue failure masks original workflow result | Catch/report queue failures locally after terminal notification; never raise into terminal path |
| Accepted queued commands disappear silently | Retain failed suffix, expose status, report shutdown loss policy |
| Same-tool queued commands collapse into one mutation | Store and apply every normalized operation as a distinct FIFO record |
| Reset-all partially persists | Build complete candidate and save once |
| Runtime mutation creates restart-invalid state | Reuse strict canonical validation and existing schema-v1 invariants |

## Concrete Planning Recommendations

1. Implement and test pure immutable backup replacement first.
2. Add one normalized backup-operation record and one apply function shared by immediate
   and queued commands.
3. Add command parsing, immediate/no-op feedback, FIFO queue receipts, retained-suffix
   failure behavior, and status diagnostics.
4. Refactor transient, normal fallback, guarded resume, and blocked paths through explicit
   terminal helpers before integrating notifications or queue drains.
5. Add centralized event construction, stable reason codes, sanitization, runtime dedup,
   and notification re-entry isolation.
6. Integrate final notification timing, then drain queued operations after the event
   attempt and after route-transition exit.
7. Add adversarial tests for resume failure, heating timeout, blocked retained
   checkpoints, adapter re-entry, same-tool FIFO operations, and queue persistence
   failure.
8. Run the full deterministic suite and `git diff --check`; Phase 6 examples and live
   integration should consume the stabilized contracts rather than define them.

## RESEARCH COMPLETE

File written:

- `.planning/phases/05-notifications-integration-and-verification/05-RESEARCH.md`
