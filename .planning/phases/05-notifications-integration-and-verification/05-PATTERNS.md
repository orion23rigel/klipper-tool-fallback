# Phase 5: Runtime Contracts - Pattern Mapping

**Mapped:** 2026-06-11
**Scope:** Safety-neutral terminal notifications and atomic runtime backup-policy
management

## File Map

| Likely file | Closest existing analog | Reuse |
|---|---|---|
| `klippy/extras/tool_fallback_state.py` | `with_mapping()`, `with_identity_mappings()`, `_replace_tool()` | Pure immutable candidates, exact no-op identity, canonical validation |
| `klippy/extras/tool_fallback.py` | mapping commands, `_persist_state()`, `_transition_active_route()`, automatic fallback terminal paths | Command registration/parsing, save-before-publish, FIFO drain triggers, final-outcome notification timing |
| `klippy/extras/tool_fallback_config.py` | `_purge_adapter()` and `parse_global_config()` | Optional first-token recursion validation for `notify_gcode`; otherwise no change |
| `tests/conftest.py` | `FakeGCode.run_script_from_command()`, script failure/duration injection, global responses | Minimal adapter callback/re-entry support and ordered observation |
| `tests/test_tool_fallback_state.py` | mapping mutation and filament/purge candidate tests | Backup candidate semantics, validation, immutability, no-op behavior |
| `tests/test_tool_fallback_backups.py` (recommended new) | `tests/test_tool_fallback_routing.py` | Runtime backup commands, immediate persistence, queue lifecycle, transition re-entry |
| `tests/test_tool_fallback_fallback.py` | complete fallback, transient recovery, heating timeout, guarded resume, resume failure tests | Notification timing/reason codes and terminal queue drains |
| `tests/test_tool_fallback_notifications.py` (optional new) | `tests/test_tool_fallback_fallback.py` plus `tests/test_tool_fallback_routing.py` re-entry tests | Pure payload/sanitization and adversarial adapter-isolation cases |
| `tests/test_tool_fallback_config.py` | purge-adapter recursion validation tests | Only needed if notification-adapter recursion is rejected at configuration time |

## `klippy/extras/tool_fallback_state.py`

### Closest Analogs

- `FallbackState.with_mapping(logical, physical)` validates both endpoints, returns
  `self` for an exact no-op, copies one collection, and returns `_canonical(...)`.
- `FallbackState.with_identity_mappings()` builds the complete replacement in memory and
  returns one candidate, matching reset-all atomicity.
- `_replace_tool(physical, replacement)` preserves all unrelated tools and mappings,
  validates the replacement invariant, and returns `self` when unchanged.
- `from_dict()` already defines backup invariants: canonical known names, no self
  reference, no duplicates, ordered tuples.

### Patterns And Signatures To Reuse

Add a pure operation shaped like:

```python
def with_backups(self, physical, backups):
    current = self._require_tool(physical)
    # validate the complete ordered tuple before replacement
    return self._replace_tool(
        physical,
        ToolState(current.loaded, current.purged, current.failed, backups),
    )
```

- Normalize to a tuple before comparison/replacement.
- Validate every backup against `self.tools`; use `StateValidationError`, consistent
  with `with_mapping()` and `_require_tool()`.
- Preserve order exactly. Do not sort backup tuples in `_canonical()`.
- Preserve `loaded`, `purged`, and `failed` exactly.
- Permit cross-tool cycles; `resolve_backup_graph()` already contains path-local loops.
- For reset-all, either add one pure all-backups replacement helper or repeatedly call
  `with_backups()` against an in-memory candidate. Persist only the final candidate.
- Keep schema version 1. Backups are already durable schema data.

### Pitfalls

- Do not reuse `parse_tool_config()` behavior for runtime values: it silently drops empty
  comma entries, while runtime commands must reject interior/trailing empty entries.
- Do not publish or persist inside state methods.
- Do not reject graph cycles.
- Do not rebuild tools from configured defaults except for explicit restore/reset.

## `klippy/extras/tool_fallback.py`

### Initialization And Runtime Records

Closest analogs are the frozen `WorkflowCheckpoint`/`GraphResolution` records and the
runtime-only guards initialized in `ToolFallback.__init__`.

- Register `SET_TOOL_BACKUPS`, `RESTORE_TOOL_BACKUPS`, and `RESET_TOOL_BACKUPS` beside
  `REMAP_TOOL`, `RESTORE_TOOL`, and `RESET_TOOL_MAPPINGS`.
- Use a frozen normalized queue record, for example
  `sequence, operation, tool, backups`; never retain a `gcmd`.
- Initialize FIFO queue, monotonic sequence, last-drain failure, attempted notification
  identities, and `_notification_in_progress` in `__init__`.
- Extend `get_status()` with JSON-safe queue depth/failure diagnostics. Follow
  `_workflow_status_snapshot()` and avoid exposing record objects.

### Backup Command Parsing And Application

Closest command analogs:

- `_require_configured_tool(gcmd, parameter)` for exact canonical configured names.
- `cmd_REMAP_TOOL()`, `cmd_RESTORE_TOOL()`, and `cmd_RESET_TOOL_MAPPINGS()` for command
  shape and configured initialization checks.
- `_apply_mapping_candidate()` and `_persist_state()` for save-before-publish and
  command-visible persistence failures.
- `_merge_mapping_candidate()` for applying a requested policy to the latest canonical
  state rather than a stale snapshot.

Recommended data flow:

```text
gcmd -> parse and fully validate normalized operation
     -> notification re-entry check
     -> queue when checkpoint/transition/older queue is active
     -> otherwise build candidate from current self.state
     -> exact no-op report, no save
     -> _persist_state(candidate)
     -> success report with complete ordered policy
```

- Parse `BACKUPS` as one complete value: strip, allow exactly empty to mean `()`, split
  non-empty input on commas, strip entries, and reject any empty entry.
- Restore from immutable `self.config.tools[tool].backups`.
- Reset every tool from `self.config.tools` in one candidate and one save.
- Use `gcmd.respond_info` for immediate receipt/result; use global
  `self.gcode.respond_info` for later drain results.
- Queue when `_workflow_checkpoint is not None` or `_transition_active` is true. A
  retained failed suffix means new commands must also queue behind it.
- Backup operations must not call selection, mapping, purge, heater, pause/resume, or
  resolver workflow code.

### Queue Drain

The closest ordering analog is `_transition_active_route()`:

```python
self._transition_active = True
try:
    ...
finally:
    self._transition_active = False
```

Add the drain after the guard is cleared, not inside the active transition. The
re-entrant transition test demonstrates that configured scripts can invoke commands
while the guard is true.

- Drain after automatic terminal notification attempts and after route-transition
  `finally` clears `_transition_active`.
- A `blocked` checkpoint is terminal and may remain visible while draining.
- Do not drain at `debouncing`, `confirmed_runout`, `heating`, or `heating_timeout`.
- Apply each FIFO record against the latest `self.state`; do not coalesce same-tool
  operations.
- Count exact no-ops as processed operations without calling `StateStore.save()`.
- Stop on first application failure, retain the failed record and suffix in order, and
  report failed plus remaining operations. Never raise a drain failure over the
  workflow/transition outcome.
- Drain after notification, so adapter re-entry cannot join or alter that terminal
  batch.

### Notification Construction And Invocation

Closest adapter analog:

```python
adapter = "%s TOOL=%s" % (
    self.config.global_config.purge_gcode, physical_tool)
self.gcode.run_script_from_command(adapter)
```

Use the same configured adapter boundary, but do not reuse purge timeout semantics:
notification is best effort and cannot be safely cancelled.

- Build all dynamic parameters centrally in fixed order:
  `EVENT`, `GENERATION`, `LOGICAL_TOOL`, `FAILED_TOOL`, `SELECTED_TOOL`,
  `REASON_CODE`, then optional `REASON_DETAIL`.
- Use `n/a` for missing canonical values.
- Pass stable reason codes explicitly at failure sites or carry them in runtime
  checkpoint context. Do not parse `failure_reason`.
- Sanitize unexpected detail to one ASCII safe-token line and bound it after
  sanitization.
- Mark `(generation, event_name)` attempted before invoking the adapter.
- Set `_notification_in_progress` around `run_script_from_command()`, catch all adapter
  exceptions locally, and report them without changing terminal state.
- Reject extension-owned mutating public commands during notification re-entry.
  Backup commands must reject here, not queue.

### Terminal Workflow Refactor

The current terminal paths are the required analogs, but should be funneled through
narrow finalization helpers rather than independently decorated:

- `_complete_transient_runout()` currently clears the checkpoint, optionally resumes,
  and recreates `blocked` on resume failure.
- `_on_confirmed_runout()` currently persists mapping, clears the checkpoint, then
  optionally resumes.
- `_handle_guarded_resume()` duplicates purge, persist, clear, and resume behavior.
- `_block_workflow()` establishes a visible terminal checkpoint, but is also used by
  manual route transitions.

Required reuse and ordering:

```text
decide final outcome, including owned RESUME result
-> establish final checkpoint state (clear success or visible blocked failure)
-> capture immutable event context
-> attempt one notification
-> drain queued backup operations when safe
```

- `heating_timeout` remains recoverable: no notification and no drain.
- Resume failure after transient or fallback recovery becomes only
  `FALLBACK_FAILURE / RESUME_FAILED`.
- Emit blocked automatic-fallback failures immediately after the blocked checkpoint is
  visible.
- Gate automatic outcome notification by `checkpoint.source == "automatic_fallback"`;
  manual route-transition failures must not emit fallback events.
- Preserve generation/stage checks in `_checkpoint_matches()` and
  `_advance_workflow_checkpoint()` to contain stale callbacks.

### Pitfalls

- A blind notification/drain call in `_block_workflow()` will incorrectly treat manual
  transition failures as automatic fallback outcomes.
- Clearing the checkpoint before capturing terminal context loses logical/failed/selected
  tool data.
- Emitting success before `RESUME` violates the final-outcome contract.
- Treating every non-`None` checkpoint as a drain prohibition prevents drain after a
  terminal block.
- Letting notification exceptions or queue persistence failures propagate can change an
  already-decided physical safety outcome.

## `klippy/extras/tool_fallback_config.py`

### Closest Analog

`_purge_adapter()` validates the configured prefix by inspecting only the first token:

```python
if adapter.split(None, 1)[0].upper() == "PURGE_TOOL":
    ...
```

### Recommended Use

- `notify_gcode` is already parsed as a required non-empty configured adapter and is
  available through `GlobalConfig`; no new option is needed.
- Modify this file only if implementation chooses a meaningful direct-recursion
  prohibition for notification adapter ownership. If so, mirror `_purge_adapter()` with
  first-token, case-insensitive validation and focused config tests.
- Runtime `_notification_in_progress` remains mandatory even with config validation,
  because an otherwise valid macro can indirectly re-enter extension commands.

### Pitfalls

- Do not add a notification timeout config; synchronous macro execution cannot be
  cancelled safely.
- Do not over-validate the trusted configured macro prefix or attempt to parse arbitrary
  macro bodies.

## `tests/conftest.py`

### Closest Analogs

- `FakeGCode.run_script_from_command()` records exact scripts, injects failures, advances
  deterministic time, and updates PAUSE/RESUME print state.
- `FakeGCode.invoke_command()` and the routing test's local wrapper demonstrate
  synchronous command re-entry.
- `FakeGCode.responses` captures global delayed diagnostics; `FakeGCmd.responses`
  captures immediate command receipts.

### Minimal Likely Extension

Prefer a small generic script callback/hook facility rather than notification-specific
logic. It should run synchronously from `run_script_from_command()` and allow tests to:

- observe the exact notification payload;
- invoke an extension command during notification delivery;
- trigger recursive notification behavior;
- preserve existing script failure and duration behavior.

Keep ordered observation deterministic. Existing tests often locally wrap
`run_script_from_command()`; use that approach if only a few tests need callbacks and no
shared fake change is necessary.

### Pitfalls

- Do not make the fake infer or parse notification semantics.
- Preserve recording-before-failure behavior used by existing adapter tests.
- Keep global responses distinct from submitting `FakeGCmd.responses` so queue receipt
  and later drain diagnostics can be asserted separately.

## Test File Patterns

### `tests/test_tool_fallback_state.py`

Closest tests:

- `test_with_mapping_returns_canonical_immutable_candidate`
- `test_with_identity_mapping_preserves_unrelated_state`
- `test_mapping_mutation_no_ops_return_existing_state`
- `test_filament_and_purge_candidates_have_exact_field_semantics`
- parametrized unknown-endpoint and strict parsing tests

Add focused tests for replace/reorder/clear, unknown source/backup, duplicate,
self-reference, cycle allowance, preservation of unrelated fields/mappings, immutable
canonical output, and exact no-op identity. Use `valid_dict()` because it already
contains meaningful loaded/purged/failed/mapping state and ordered backups.

### `tests/test_tool_fallback_backups.py` (Recommended New)

Use `tests/test_tool_fallback_routing.py` as the primary structural analog:

- copy its `load_extension()` style and real `StateStore` path;
- use `FakeGCmd` to assert command-local responses;
- monkeypatch `extension._state_store.save` to count writes or inject failures;
- use physical handler spies and `script_events` to prove policy mutation performs no
  hardware action;
- use `record_transition_scripts()`/re-entrant transition style to enqueue during
  `_transition_active`;
- assert disk state with a fresh `StateStore(str(path)).load()`.

Keep backup command/queue tests out of routing unless the new file would contain only a
few cases. Queue semantics are large enough to justify the new file.

Critical cases: immediate set/clear/restore/reset, exact no-op feedback, atomic reset,
printing/paused availability, future-resolution-only behavior, every active workflow
stage queues, blocked-stage drain, same-tool FIFO, queued no-op, first-save-failure
suffix retention/retry, transition success/failure drains, and new work not bypassing
retained work.

### `tests/test_tool_fallback_fallback.py`

Closest helpers/tests:

- `load_extension()`, `begin_runout()`, and `_load_fallback_config()` create complete
  deterministic workflows.
- owned/user-owned transient recovery tests establish resume ownership behavior.
- complete fallback success ordering establishes pause/select/purge/persist/resume flow.
- heating-timeout and guarded-resume tests establish recoverable versus terminal timing.
- `test_fallback_resume_failure_preserves_visible_blocked_checkpoint` is the direct
  analog for `RESUME_FAILED`.
- checkpoint generation/stage tests cover stale callback containment.

Extend these paths to assert exact one-event timing and queue drain ordering. Assert
notification script strings via `printer.gcode.script_events`, and clear unrelated
setup scripts before checking exact payload/order where needed.

Critical cases: no event at heating timeout, final event after guarded outcome,
transient event only after owned resume succeeds, fallback success only after resume,
resume failure emits only failure, specific blocked-path reason codes, no manual
transition event, dedup for repeated/stale terminal calls, and notification-before-drain.

### `tests/test_tool_fallback_notifications.py` (Optional New)

Create this only if payload formatting/sanitization and adapter isolation produce a
substantial focused matrix. Use pure helper tests for fixed field order, `n/a`, safe
alphabet, Unicode/newline/quote/comment/semicolon replacement, and 160-character bound.
Use initialized extension tests for adapter absence/failure/delay, recursive delivery,
and command re-entry rejection.

### `tests/test_tool_fallback_config.py`

Only add tests if `tool_fallback_config.py` changes. Mirror
`test_recursive_public_purge_adapter_variants_block_startup` with case, whitespace, and
arguments variants for the exact notification-owned command(s) being prohibited. Keep
the existing `notify_gcode` default/explicit/empty tests unchanged.

## Verification Pattern

Use focused files while implementing:

```text
pytest -q tests/test_tool_fallback_state.py
pytest -q tests/test_tool_fallback_backups.py
pytest -q tests/test_tool_fallback_fallback.py tests/test_tool_fallback_notifications.py
pytest -q tests/test_tool_fallback_config.py
```

Then run `pytest -q` and `git diff --check`. The pre-Phase-5 baseline documented by
research is 260 passing tests.

## PATTERN MAPPING COMPLETE

File written:

- `.planning/phases/05-notifications-integration-and-verification/05-PATTERNS.md`
