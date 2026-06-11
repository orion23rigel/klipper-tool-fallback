# Architecture Research: v1.1 Integration & Operations

## Scope

v1.1 should integrate the operational work deferred from v1.0 without changing the
core routing, sensor, purge, heater, or fallback model:

- invoke the configured notification adapter for automatic fallback success, terminal
  failure, and transient recovery;
- make notification delivery part of fail-closed workflow completion;
- provide atomic runtime commands for ordered backup-list mutation;
- add printer-specific examples and operator documentation;
- add repeatable CI and release verification; and
- produce supervised live-printer UAT procedures and result artifacts.

The four pending Phase 1 UAT scenarios are explicitly excluded from v1.1:

1. Valid Configuration Startup
2. Persisted State Survives Restart
3. Invalid State Blocks Startup Clearly
4. Read-Only Status Inspection

They remain separate deferred work. v1.1 live-printer UAT must not silently absorb,
rename, or claim completion of those scenarios.

## Existing Architecture To Preserve

The extension is deliberately compact:

| Component | Current responsibility | v1.1 implication |
|-----------|------------------------|------------------|
| `klippy/extras/tool_fallback.py` | Klipper lifecycle, G-Code commands, logical/physical routing, sensor runtime, purge, workflow checkpoints, heater stages, fallback orchestration | Remains the coordinator and the only component allowed to decide whether a workflow may resume or must block. |
| `klippy/extras/tool_fallback_config.py` | Strict normalization of global adapters, timeouts, and per-tool configuration | Retains the existing `notify_gcode` contract and should validate any new notification-specific option only if one proves necessary. |
| `klippy/extras/tool_fallback_state.py` | Immutable schema-v1 durable state and atomic save-before-publish persistence | Owns ordered-backup candidate construction and validation. No schema version change is required because `backups` already persist in schema v1. |
| `tests/conftest.py` | Deterministic Klipper fakes and elapsed-time/script failure injection | Extends script observation so notification invocation and failure ordering are deterministic. |
| `tests/test_tool_fallback_*.py` | Unit, integration, and workflow safety proof | Adds focused notification, backup mutation, example, and release-contract coverage. |

The following established invariants are architectural constraints, not optional
implementation details:

- Durable changes use immutable candidate -> atomic save -> publish.
- Failed persistence never changes published state.
- Every incomplete automatic fallback remains paused with a visible runtime checkpoint.
- A user-owned pause is never resumed by the extension.
- No second backup is selected after physical selection begins.
- Runtime workflow/checkpoint data remains outside persisted schema v1.
- Printer-specific behavior enters through configured G-Code adapters, not direct
  Moonraker or toolchanger dependencies.

## Proposed Component Changes

### Runtime Extension

Modify `klippy/extras/tool_fallback.py` to:

- register backup mutation commands;
- call a single internal notification boundary;
- retain enough completion context until success notification finishes;
- route every terminal automatic fallback failure through one failure-blocking helper;
- block backup mutation while an automatic workflow checkpoint or active route
  transition exists; and
- expose notification failure in the existing workflow checkpoint rather than creating
  a second runtime state machine.

The coordinator must remain authoritative. Notification helpers may format and invoke
an adapter, but they must not clear checkpoints, resume prints, mutate durable state, or
select hardware.

### Notification Formatting

Add `klippy/extras/tool_fallback_notify.py` as a small pure helper module. Keeping
formatting and G-Code argument escaping outside the already large coordinator makes the
message contract independently testable and prevents ad hoc string construction at
multiple failure sites.

Recommended public helper responsibilities:

- define stable event names:
  `fallback_succeeded`, `fallback_failed`, and `transient_recovered`;
- construct a deterministic schema-versioned payload;
- normalize optional fields to explicit `null`/empty values;
- convert `GraphResolution` data to ordinary JSON-compatible values;
- collapse exception text to one bounded single line; and
- quote/escape the payload for one G-Code adapter invocation, rejecting CR/LF and other
  command-injection boundaries.

Recommended adapter invocation:

```text
_TOOL_FALLBACK_NOTIFY EVENT=fallback_failed MESSAGE="<compact JSON payload>"
```

The payload should be compact deterministic JSON with this logical shape:

```json
{
  "version": 1,
  "event": "fallback_failed",
  "generation": 7,
  "logical_tool": "T0",
  "failed_physical_tool": "T0",
  "selected_backup": "T1",
  "stage": "blocked",
  "pause_owned": true,
  "attempted_tools": ["T1", "T2"],
  "unloaded_tools": ["T2"],
  "failed_tools": [],
  "looped_paths": [],
  "reason": "Purge of backup tool T1 failed: ..."
}
```

`EVENT` gives simple macros a stable branch key. `MESSAGE` gives Moonraker notifiers and
logs a complete structured record. The example adapter should forward `params.MESSAGE`
to Moonraker's existing `notify` remote method. The implementation and fake parser tests
must prove that quotes, backslashes, spaces, and exception text cannot inject a second
G-Code command. Do not interpolate unescaped exception text directly into a script.

No new direct Moonraker API client is recommended. It would add network lifecycle,
credentials, retry, and dependency concerns that are already delegated to the configured
printer macro.

### Durable Backup Mutation

Modify `klippy/extras/tool_fallback_state.py` with one immutable primitive:

```text
FallbackState.with_backups(tool, ordered_backups)
```

It should validate the complete replacement list before constructing a candidate:

- source and every backup are configured canonical tools;
- source does not reference itself;
- duplicate references are rejected;
- input order is preserved;
- unrelated tool state and every mapping are preserved; and
- exact no-ops return the existing state object.

Modify `klippy/extras/tool_fallback.py` to expose narrow commands built on that primitive:

```text
SET_TOOL_BACKUPS TOOL=T0 BACKUPS=T1,T3,T2
ADD_TOOL_BACKUP TOOL=T0 BACKUP=T2
REMOVE_TOOL_BACKUP TOOL=T0 BACKUP=T1
CLEAR_TOOL_BACKUPS TOOL=T0
```

`SET_TOOL_BACKUPS` is the authoritative complete-list operation. The convenience
commands must read the latest canonical state, derive one complete ordered replacement,
then call the same persistence path. `ADD_TOOL_BACKUP` appends only; operators use
`SET_TOOL_BACKUPS` to reorder. Removing an absent entry and clearing an already empty
list are exact no-ops.

Every mutation command follows:

```text
parse all parameters
  -> reject if routing is uninitialized
  -> reject if workflow checkpoint or active transition exists
  -> build and fully validate immutable candidate
  -> atomically persist candidate
  -> publish candidate
  -> report final ordered list
```

Backup mutations may be allowed while a print is otherwise active because they do not
move hardware or change the current route. They must be rejected while a fallback
checkpoint or active route transition exists, because changing the graph during
resolution, heating, guarded resume, or transition recovery makes diagnostic and retry
context ambiguous.

Configuration continues to initialize backups only for newly discovered tools.
Persisted operator-managed backup order remains authoritative at restart. Schema v1 and
startup reconciliation behavior remain unchanged.

## Notification Data Flow And Ordering

### Central Failure Boundary

The current `_block_workflow(checkpoint, reason)` is the natural single terminal-failure
boundary. Extend it so all automatic fallback failures:

1. publish `stage=blocked` and the original local failure reason;
2. invoke exactly one `fallback_failed` notification using the blocked checkpoint;
3. if notification succeeds, retain the original blocked checkpoint;
4. if notification fails, retain the blocked checkpoint and append a bounded
   `notification_error` detail to the visible failure reason; and
5. never retry notification automatically, never recurse through `_block_workflow()`,
   and never resume.

The local blocked state must be published before adapter invocation. If the adapter
raises or overruns, the printer is already visibly contained. A notification failure
must not obscure the original hardware/workflow failure.

Notification timeout semantics should match existing synchronous adapter semantics:
adapter exceptions fail immediately; a configured deadline can reject a post-return
elapsed-time overrun but cannot safely cancel arbitrary G-Code mid-execution. Prefer a
new positive finite `notify_timeout` option only if plans require bounded adapters;
otherwise explicitly document that notification completion is synchronous and operator
macros must return promptly.

### Transient Recovery

Current ordering clears the checkpoint before attempting owned resume. v1.1 should use:

```text
stable loaded debounce
  -> build transient_recovered payload from pending checkpoint
  -> invoke notification adapter
  -> on notification failure: convert pending checkpoint to blocked; do not resume
  -> on notification success: clear checkpoint
  -> resume only if pause_owned
  -> on resume failure: recreate visible blocked checkpoint
```

For an unowned pause, successful notification clears the transient checkpoint but never
resumes. Fail-closed notification semantics still preserve a blocked checkpoint on
adapter failure so the operational event is not silently lost.

### Successful Automatic Fallback

Success notification belongs after all hardware and durable state work succeeds but
before checkpoint clearing and owned resume:

```text
confirmed failed state persisted
  -> source heater shutdown
  -> graph resolution and candidate freeze
  -> destination preheat/select/readiness
  -> conditional purge and purge-state persistence
  -> logical mapping persistence from latest canonical state
  -> invoke fallback_succeeded notification
  -> on notification failure: block using saved completion checkpoint; do not resume
  -> on notification success: clear checkpoint
  -> resume only if pause_owned
```

At notification failure the physical selection and persisted route may already point to
the backup. Automatic rollback remains prohibited. The visible blocked checkpoint must
therefore report selected backup and persisted logical route so the operator can
understand that machine transition succeeded but operational notification did not.

The guarded heating-timeout resume continuation must use the same success finalizer.
Do not duplicate notification/clear/resume logic between normal completion and guarded
resume.

## Safety Boundaries

### Adapter Boundary

- The configured `notify_gcode` is an external synchronous adapter and may fail.
- Adapter success means the configured macro returned successfully; it does not prove
  downstream delivery by Discord, email, or another service.
- Adapter failure is workflow failure for success and transient events: keep paused,
  retain a blocked checkpoint, and do not resume.
- Failure-event adapter failure cannot trigger another failure notification. Record it
  locally once and stop.
- Notification invocation never mutates durable schema-v1 state or hardware.
- Dynamic message data is escaped centrally and cannot inject G-Code.

### Mutation Boundary

- No in-place edits of `ToolState.backups`.
- No mutation is published before `StateStore.save()` succeeds.
- No partial add/remove/reorder sequence is persisted; each command writes one complete
  candidate.
- Reject mutation during any workflow checkpoint or active route transition.
- Mutations affect future graph resolution only; an already frozen selected candidate is
  never changed.
- Existing configuration validation and startup reconciliation remain authoritative for
  configured tool membership.

### UAT Boundary

- Live-printer procedures require explicit operator supervision, safe temperatures,
  loaded test filament, and an immediate abort path.
- UAT records observed command/status evidence and operator result; it does not replace
  deterministic automated failure-injection tests.
- Printer-specific macro behavior, sensor polarity, physical toolchanger mechanics,
  heater dynamics, and notifier delivery are live-UAT concerns.
- The four Phase 1 startup/state UAT scenarios listed in Scope remain excluded.

## Examples And Documentation Architecture

Add an `examples/` directory with small composable files rather than one assumed-universal
printer configuration:

| New file | Purpose |
|----------|---------|
| `examples/tool_fallback.cfg` | Complete generic extension/tool/sensor wiring with explicit physical `Tn`, pause ownership, purge adapter, and backup commands. |
| `examples/moonraker_notify.cfg` | `_TOOL_FALLBACK_NOTIFY` adapter forwarding `EVENT` and structured `MESSAGE` to Moonraker notifier integration. |
| `examples/toolchanger_integration.cfg` | Representative captured physical-tool macros and safe purge/selection adapter integration points. |

Add operator-facing documentation:

| New/modified file | Purpose |
|-------------------|---------|
| `README.md` | Installation overview, command inventory, links to detailed examples/UAT, and explicit adapter failure semantics. |
| `docs/operations.md` | Backup mutation commands, status interpretation, blocked notification recovery, and no-rollback behavior. |
| `docs/integration.md` | Printer-specific pause/resume/purge/notify/toolchanger contracts and message schema. |
| `docs/live-printer-uat.md` | Safety prerequisites and reusable live test procedure. |

Examples should be treated as tested interfaces. Add lightweight tests that load or
inspect example sections and assert command names, non-recursive adapters, explicit
`PAUSE_OWNED=1`, and current configuration option names. Documentation must not claim
delivery guarantees beyond successful adapter return.

## Live-Printer UAT Artifacts

Use two layers:

1. `docs/live-printer-uat.md` is the stable reusable operator procedure.
2. `.planning/phases/05-notifications-integration-and-verification/05-UAT.md` records
   the actual representative printer, firmware/config revision, date, preconditions,
   observed evidence, result, and issues for this milestone.

Recommended v1.1 live scenarios:

- intercepted logical `Tn` invokes the expected printer-specific physical tool macro;
- active-print remap performs pause, source shutdown, destination preheat, physical
  selection, conditional purge, persistence, and ownership-safe resume;
- real runout/insert hooks and sensor disable/re-enable produce expected authority and
  debounce behavior;
- printer-specific purge adapter executes once and only publishes purged state after
  completion;
- transient runout emits the structured notification and resumes only when owned;
- successful automatic fallback emits notification after route persistence and before
  owned resume;
- exhausted/failed fallback emits a failure notification and remains paused;
- heating timeout remains paused and guarded `RESUME` completes only after readiness;
- notifier adapter failure leaves a visible blocked checkpoint and prevents resume;
- runtime backup mutation changes the next fallback priority without changing the
  current physical route.

Do not include startup, restart persistence, corrupt-state startup, or read-only status
inspection as v1.1 UAT scenarios; those are the explicitly excluded Phase 1 items.

## CI And Release Verification

Add one local verification entry point and make automation call it:

| New file | Responsibility |
|----------|----------------|
| `scripts/verify-release.sh` | Run Python compilation, the complete pytest suite, example-contract tests, and repository whitespace checks with fail-fast exit status. |
| `.github/workflows/ci.yml` | Run verification on pushes and pull requests using supported Python versions. |
| `.github/workflows/release.yml` | On `v*` tags, rerun the same verification and build an installable source artifact containing extension modules, README/docs, and examples. |

The release workflow must depend on the same script used locally so release checks do
not drift from pull-request checks. It should fail before artifact publication on any
test, compile, example-contract, or packaging error. The artifact should include all
four extension modules once the notification helper is added.

Recommended automated coverage additions:

- `tests/test_tool_fallback_notify.py`: deterministic payload schema, escaping,
  adapter success/failure/overrun behavior, and no recursive failure notification;
- `tests/test_tool_fallback_backups.py`: immutable replacement/add/remove/clear,
  validation, no-op behavior, save-before-publish failure containment, ordering, and
  workflow conflict guards;
- `tests/test_tool_fallback_fallback.py`: notification placement in transient, success,
  every terminal failure class, and guarded resume;
- `tests/test_examples.py`: example option/command drift and required adapter wiring;
- `tests/conftest.py`: exact script event capture for structured adapter calls.

Release verification remains automated software verification. Supervised UAT evidence is
a separate release gate recorded in the Phase 5 UAT artifact, because hosted CI cannot
prove printer hardware behavior.

## Modified And New Components Summary

### Modify

- `klippy/extras/tool_fallback.py`
- `klippy/extras/tool_fallback_state.py`
- `tests/conftest.py`
- `tests/test_tool_fallback_fallback.py`
- `tests/test_tool_fallback_state.py`
- `README.md`

### Add

- `klippy/extras/tool_fallback_notify.py`
- `tests/test_tool_fallback_notify.py`
- `tests/test_tool_fallback_backups.py`
- `tests/test_examples.py`
- `examples/tool_fallback.cfg`
- `examples/moonraker_notify.cfg`
- `examples/toolchanger_integration.cfg`
- `docs/operations.md`
- `docs/integration.md`
- `docs/live-printer-uat.md`
- `scripts/verify-release.sh`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `.planning/phases/05-notifications-integration-and-verification/05-UAT.md`

`klippy/extras/tool_fallback_config.py` needs modification only if v1.1 adopts a
`notify_timeout` option or adds normalized notification adapter recursion restrictions.
No durable schema migration is recommended.

## Suggested Build Order

1. **Pure notification contract and adapter safety**
   - Add payload formatting/escaping helper and focused tests.
   - Establish exact event schema before integrating workflow calls or writing examples.

2. **Central fail-closed notification integration**
   - Refactor one failure-blocking boundary and one shared success finalizer.
   - Integrate transient recovery, normal fallback success, all terminal failures, and
     guarded resume.
   - Prove notification failures never clear checkpoints or resume.

3. **Atomic backup-list state primitive and commands**
   - Add `with_backups()` and state tests first.
   - Add complete-list and convenience commands using one persistence path.
   - Prove conflict guards and graph priority changes without modifying active hardware.

4. **Examples and operator documentation**
   - Write examples against the now-stable adapter payload and command contracts.
   - Add example-contract tests and document fail-closed operational recovery.

5. **CI and release checks**
   - Add the local verification script, then CI, then tag/release artifact checks.
   - Ensure all automation invokes the same verification entry point.

6. **Supervised live-printer UAT**
   - Execute only after software verification and examples are stable.
   - Record representative routing, sensor, purge, heater, fallback, guarded resume,
     notification, and runtime backup-mutation evidence.
   - Keep the four Phase 1 UAT scenarios explicitly excluded.

## Key Risks To Resolve During Planning

1. **G-Code payload quoting:** structured JSON must survive the real Klipper macro parser
   without permitting command injection. Automated escaping tests are necessary, and the
   Moonraker adapter path requires live verification.
2. **Failure notification recursion:** central blocking logic must attempt failure
   notification once only and record adapter failure locally without re-entering itself.
3. **Completion-state ambiguity:** success notification occurs after durable route
   publication but before resume. A notification failure checkpoint must clearly say
   that fallback hardware/state completion succeeded while notification/resume did not.
4. **Guarded-resume duplication:** normal and heating-timeout recovery currently have
   separate completion tails. They should converge before notification integration to
   avoid inconsistent ordering.
5. **Graph mutation races:** synchronous commands still need explicit conflict guards so
   operators cannot alter backup priority while a checkpoint is recoverable.
6. **Example drift:** printer examples become operational interfaces and need automated
   checks against command and option names.
7. **Hardware claims:** CI and fakes cannot prove physical safety. Release evidence must
   distinguish automated proof from supervised live-printer observations.

## Conclusion

v1.1 should remain an integration milestone, not a redesign. Notifications fit safely
as a structured synchronous adapter boundary owned by the existing checkpoint
coordinator. Runtime backup-list management fits the existing immutable atomic-state
pattern without a schema migration. Examples, CI/release automation, and live-printer
UAT then validate those stable contracts at progressively wider boundaries.

The critical ordering rule is: complete and persist machine state, require the relevant
notification adapter to return successfully, then clear the checkpoint and resume only
when pause ownership permits it. Any incomplete integration step remains paused and
visible.
