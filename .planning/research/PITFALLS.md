# v1.1 Integration & Operations Pitfalls

**Researched:** 2026-06-11
**Scope:** Notification adapters, runtime backup mutation, printer-specific examples,
representative live-printer UAT, CI, and release verification for v1.1.

## Explicit Exclusion

The following four Phase 1 UAT scenarios are intentionally excluded from v1.1 scope and
must not be counted as v1.1 requirements, evidence, blockers, or release-verification
claims:

1. Valid Configuration Startup
2. Persisted State Survives Restart
3. Invalid State Blocks Startup Clearly
4. Read-Only Status Inspection

They remain separately deferred by user direction. Live-printer v1.1 work may incidentally
exercise startup or status surfaces, but that does not complete or absorb these scenarios.

## Recommended Phase Placement

| Placement | Owns | Must prove before advancing |
|-----------|------|-----------------------------|
| **Phase 5A: Notification and mutation contracts** | Notification event model and adapter invocation; pure backup-list mutation helpers; command authorization; workflow conflict guards; automated tests | No notification recursion or unsafe message transport; notification failure cannot undo or falsely complete a safety transition; backup mutations validate the complete candidate graph, save before publish, preserve unrelated state, and fail closed during active workflows/transitions |
| **Phase 5B: Examples and supervised integration UAT** | Printer-specific example macros/configuration; real Klipper/Moonraker transport checks; representative sensor, heater, purge, fallback, guarded-resume UAT | Examples are syntactically loadable and use distinct non-recursive adapters; every hardware claim has recorded environment, procedure, observations, and result; failed/incomplete workflows remain paused |
| **Phase 5C: CI and release verification** | CI workflow, supported Python/Klipper compatibility matrix, packaging/release checks, release checklist and evidence audit | CI reproduces documented local checks from a clean checkout; release evidence separates automated, simulated, and hardware results; artifacts and docs agree with the tagged commit |

Do not combine all three into one implementation pass. Notifications and backup mutation
change runtime behavior and need stable automated contracts before examples and hardware
UAT can provide meaningful evidence. CI and release verification should then encode the
settled checks rather than legitimizing moving targets.

## Critical Pitfalls

### 1. Treating Notification Delivery as a Safety-Critical Workflow Stage

**Mistake:** Call `notify_gcode` inline and let adapter exceptions, Moonraker outages, or
slow external services change whether fallback is considered complete, blocked, or
resumable.

This project currently runs configured adapters synchronously through
`run_script_from_command()`. Selection and purge already use strict fail-closed semantics,
but notification delivery is observability, not hardware truth. Making it a required
success stage can leave a physically successful fallback blocked solely because Discord,
Moonraker, DNS, or a notifier is unavailable. Conversely, sending "success" before mapping
persistence or before guarded resume completion creates a false success claim.

**Warning signs**

- A notify exception reaches `_block_workflow()` after hardware and persistence succeeded.
- Notification success/failure changes mappings, tool flags, pause ownership, or heater
  actions.
- The success notification is emitted before the final durable mapping publication.
- Failure notification code can throw while handling the original failure.
- Tests assert only that a script ran, not that core state is unchanged when it fails.

**Prevention**

- Define notification events at explicit terminal boundaries: transient recovery, durable
  fallback success, and blocked/failed fallback.
- Capture an immutable event payload from the final checkpoint/state; do not let notification
  code read and reinterpret mutable workflow state later.
- Make delivery best-effort and locally visible on failure. Never resume, select, heat,
  purge, persist, clear a blocked checkpoint, or rewrite the original failure reason
  because notification delivery failed.
- Emit at most one external event per terminal outcome and test duplicate callback/stale
  generation paths.
- Preserve the original safety outcome and append or locally report delivery diagnostics.

**Phase placement:** Define and automate in Phase 5A; exercise real Moonraker notifier
failure and recovery in Phase 5B; audit event/outcome evidence in Phase 5C.

### 2. Notification Adapter Recursion or Re-entry

**Mistake:** Permit `notify_gcode` to resolve to a public extension command, directly or
through an example macro, or let a notification macro trigger fallback-affecting commands.

The project already rejects `purge_gcode` forms whose first token is public `PURGE_TOOL`
because public-to-adapter recursion is dangerous. Notification integration needs the same
ownership discipline. A macro that invokes `TOOL_FALLBACK_RUNOUT`, `RESUME`, remapping,
backup mutation, or itself can recursively re-enter a live workflow or alter the outcome
being reported.

**Warning signs**

- `notify_gcode` is only checked for non-empty text.
- Example `_TOOL_FALLBACK_NOTIFY` calls an extension public command.
- Notification tests use a fake that only records strings and cannot expose re-entry.
- A notify callback runs while `_workflow_checkpoint` or `_transition_active` is being
  mutated without a re-entry policy.

**Prevention**

- Reserve one distinct notification adapter command and reject direct first-token recursion.
- Document that notifier macros are side-effect-free with respect to this extension.
- Add a narrow notification-delivery re-entry guard; suppress/reject duplicate delivery
  rather than replacing the active checkpoint.
- Test direct recursion, adapter exception, adapter-triggered public command re-entry,
  stale callbacks, and duplicate terminal events.
- Keep `RESUME` ownership and guarded-resume logic entirely outside notifier macros.

**Phase placement:** Phase 5A contract and tests; Phase 5B verifies the shipped example
against real macro expansion.

### 3. Building G-code by Concatenating Untrusted or Free-Form Messages

**Mistake:** Construct a script such as
`_TOOL_FALLBACK_NOTIFY MESSAGE=<free-form failure_reason>` and assume spaces, quotes,
newlines, comments, or G-code-looking text remain one inert parameter.

Existing adapter construction is safe for canonical `TOOL=Tn`, but notification payloads
contain attempted tools and exception text. Free-form exception messages may contain
quotes, line breaks, semicolons, braces, or command-like text. Klipper G-code parsing and
Jinja macro evaluation are separate parsing layers; ad hoc quoting across both is brittle.
The example design's `params.MESSAGE` also loses structure and encourages unsafe string
transport.

**Warning signs**

- Notification scripts are formed with `%s`, `.format()`, or f-strings containing raw
  exception text.
- Tests cover only alphanumeric messages.
- The macro expects one `MESSAGE` parameter containing JSON without a defined encoding.
- Newlines or quotes create additional commands, truncate messages, or fail macro parsing.
- External notification content exposes filesystem paths or arbitrary exception detail
  without an explicit policy.

**Prevention**

- Prefer a structured internal notification event and a transport contract with a small,
  fixed event code plus canonical tool identifiers.
- If free-form detail must cross G-code, define one reversible encoding with a bounded
  character set and length, then decode only at the receiving boundary. Do not invent
  per-call quoting.
- Keep operator-facing local diagnostics richer than external messages when transport
  cannot safely carry full detail.
- Bound payload size and redact/control exception detail; external notifiers are not a
  lossless diagnostic channel.
- Test spaces, quotes, apostrophes, backslashes, braces, `#`, semicolons, Unicode,
  newlines, very long reasons, and command-looking text on real Klipper/Moonraker.

**Phase placement:** Transport contract in Phase 5A; real parser and Moonraker verification
in Phase 5B; release examples checked in Phase 5C.

### 4. Publishing Backup Mutations Before Durable Persistence

**Mistake:** Mutate `ToolState.backups` in place, assign `self.state` before `StateStore.save`,
or perform multiple writes while building one requested order.

`FallbackState` is intentionally immutable and canonical. `StateStore.save()` writes a
same-directory temporary file, fsyncs it, atomically replaces the destination, and only
then updates its persisted snapshot. Runtime backup commands must preserve this
save-before-publish contract. A partial reorder can immediately change automatic resolution
policy and survive inconsistently across restart.

**Warning signs**

- Commands edit `self.state.tools[tool].backups` or convert mapping proxies to mutable
  long-lived structures.
- One command performs several incremental persists for a single final list.
- Persistence failure leaves `self.state` showing the requested backups.
- No-op reorder writes the file.
- Tests assert only final happy-path JSON, not failure preservation and unrelated fields.

**Prevention**

- Add pure `FallbackState` backup mutation helpers that return a complete canonical
  candidate or the existing object for an exact no-op.
- Validate the entire candidate before one atomic save; publish `self.state` only after
  save succeeds.
- Preserve all loaded/purged/failed flags, mappings, other tools, and exact requested
  priority order.
- Reuse `StateStore`; do not create a second persistence path or bypass its atomic write.
- Test pre-replace failure, replace failure, no-op behavior, round trip, restart load, and
  preservation of unrelated state.

**Phase placement:** Phase 5A implementation and fault-injection tests; Phase 5C regression
gate. The excluded Phase 1 restart UAT remains excluded even if automated mutation restart
tests are added.

### 5. Validating Only the Edited Backup Entry Instead of the Whole Candidate

**Mistake:** Check only syntax or the newly added tool, allowing self-reference, unknown
tools, duplicates, or accidental order changes into durable state.

Startup validation rejects unknown, self, and duplicate backups. Runtime mutation must
enforce at least the same invariants before persistence. Cross-tool cycles are currently
allowed and contained by the resolver, so silently introducing a stricter "no cycles"
runtime rule would create a conflicting policy.

**Warning signs**

- Runtime commands accept values that `FallbackState.from_dict()` would reject.
- Mutation uses a set and destroys priority order.
- Runtime mutation rejects every graph cycle despite current resolver semantics.
- Configuration reload later fails on state written by a runtime command.

**Prevention**

- Centralize candidate validation with existing canonical state rules.
- Preserve ordered tuples; use sets only for duplicate detection.
- Explicitly decide and document whether cycles remain allowed. For v1.1, align with the
  existing loop-safe resolver unless the persisted-state contract is deliberately migrated.
- Test unknown, self, duplicate, empty, reordered, cyclic, and unchanged lists.

**Phase placement:** Phase 5A.

### 6. Mutating Backup Policy During an Active or Recoverable Workflow

**Mistake:** Allow backup add/remove/reorder while fallback debounce, automatic fallback,
heating timeout, blocked recovery, or active route transition is in progress.

The resolver intentionally reads immutable snapshots and may perform one fresh rescan.
Changing durable graph policy mid-workflow makes reports and selected candidates difficult
to reason about, especially after the source heater is off or a backup has been selected.
The existing `_guard_workflow_operation()` blocks route operations whenever a checkpoint
exists, and `_transition_active` separately guards synchronous route transitions. Backup
mutation should follow the same exclusion model.

**Warning signs**

- A backup command checks only `print_stats` and ignores `_workflow_checkpoint`.
- Mutations are allowed at `heating_timeout` because the printer is paused.
- A command can run from a purge, pause, resume, or notification adapter during transition.
- Graph report and persisted backup order disagree after completion.

**Prevention**

- Reject all backup mutation whenever `_workflow_checkpoint` exists or
  `_transition_active` is true, including blocked and heating-timeout checkpoints.
- Do not infer safety from `paused`; pause ownership and workflow ownership are distinct.
- Build candidates only after authorization succeeds, then persist atomically.
- Test re-entry from each configured adapter and every checkpoint class.
- Do not retrofit in-flight workflows to consume a newly mutated graph.

**Phase placement:** Phase 5A, before live UAT.

### 7. Letting Examples Become Executable Recursion or Unsafe Defaults

**Mistake:** Publish copy-paste examples that use public commands as adapters, claim generic
toolchanger compatibility, omit pause ownership, or perform real heating/purge movement
without conspicuous printer-specific placeholders and prerequisites.

Examples are operational code. A syntactically plausible notifier, purge macro, or sensor
hook can recurse, auto-resume a user pause, extrude cold, move into hardware, or notify a
wrong destination.

**Warning signs**

- `purge_gcode: PURGE_TOOL` or `notify_gcode` points to a public extension command.
- Sensor examples omit the `PAUSE_OWNED=1` integration contract or imply it is always safe.
- Examples contain coordinates, temperatures, or toolchange commands presented as universal.
- No distinction exists between illustrative snippets and hardware-validated configurations.
- Example macros accept raw notification messages without transport guidance.

**Prevention**

- Make adapters distinct and narrowly owned: `_TOOL_FALLBACK_PURGE` and
  `_TOOL_FALLBACK_NOTIFY`.
- Mark printer-specific motion, temperature, notifier name, heater, and sensor values as
  required substitutions.
- Include preflight checks, dry-run mode/procedure, supervision requirements, and stop
  conditions.
- Validate examples by loading them in a real or faithful Klipper configuration environment,
  not only by visual review.
- State exactly which example was hardware-tested and on what topology.

**Phase placement:** Draft after Phase 5A contracts; validate in Phase 5B; freeze and audit
in Phase 5C.

### 8. Treating Simulated Tests as Hardware Evidence

**Mistake:** Claim that green pytest coverage proves physical sensor polarity, toolchanger
motion, heater transfer, purge geometry, Moonraker notification delivery, or guarded resume
on a real printer.

The fakes deliberately model commands, elapsed time, heater readiness, and print state
deterministically. They are strong software evidence but do not execute Klipper's real
parser, reactor scheduling, MCU timing, Moonraker transport, macros, wiring, or mechanics.

**Warning signs**

- Release notes say "hardware verified" based only on `pytest`.
- A UAT result lacks printer identity/topology, Klipper/Moonraker revisions, configuration,
  procedure, and observed output.
- Tests use injected `ready=True` as evidence a real heater reached safe readiness.
- Real-printer tests are unsupervised or begin with destructive failure cases.

**Prevention**

- Label evidence as automated unit/integration, simulated workflow, configuration load,
  dry run, or supervised hardware UAT.
- Use a staged live procedure: configuration/parser checks; idle command routing; sensors;
  heater target transfer; purge; manual active transition; transient runout; automatic
  fallback; failure/timeout; guarded resume.
- Begin with heaters/motion disabled or constrained where possible, then increase risk only
  after prior stages pass.
- Record expected and actual observations, local status, durable state, notifications,
  pause ownership, and whether human intervention occurred.
- A failed or skipped live scenario remains failed or skipped; do not convert it into a
  pass from adjacent automated coverage.

**Phase placement:** Phase 5B execution and evidence capture; Phase 5C audits claims.

### 9. Running Dangerous Live UAT Without Fail-Closed Preconditions

**Mistake:** Trigger runout or fallback on a live print before verifying tool identity,
sensor authority, heater mapping, physical selection handlers, safe purge behavior, and
emergency stop/recovery procedure.

Automatic fallback intentionally shuts down the failed source heater, preheats another
heater, physically selects once, and never automatically rolls back to the failed tool.
A bad UAT setup can therefore create real collision, cold extrusion, overheating, or
unrecoverable material path problems.

**Warning signs**

- The first live test is a full automatic runout.
- No operator is present at the printer.
- UAT expects automatic retry after physical selection failure.
- The procedure assumes a blocked checkpoint is safe to clear with ordinary `RESUME`.
- Purge or tool-selection macros have not been tested independently.

**Prevention**

- Require supervised execution, verified emergency stop, conservative temperatures, safe
  motion envelope, and disposable material/test job.
- Verify each physical `Tn` handler, sensor polarity/enable behavior, heater association,
  pause/resume adapter, purge adapter, and notifier independently first.
- Confirm every incomplete path remains paused and that guarded `RESUME` only continues a
  ready heating-timeout checkpoint.
- Treat physical selection as a point of no automatic alternate selection or failed-tool
  rollback, matching existing safety policy.
- Capture printer logs and state before and after each scenario.

**Phase placement:** Phase 5B only, after Phase 5A automated gates pass.

### 10. Creating CI That Is Green but Not Representative

**Mistake:** Run only a subset of tests, use an accidental developer environment, ignore
syntax/import checks, or present fake-only CI as Klipper compatibility verification.

This repository has no current CI or dependency lock/configuration beyond `pytest.ini`.
Local results also report environment-level `pytest-asyncio` deprecation warnings.
CI must make its environment and limitations explicit.

**Warning signs**

- CI runs `pytest` from a directory or Python version different from documented support.
- It omits `python3 -m py_compile klippy/extras/tool_fallback*.py` or `git diff --check`.
- Dependencies float without an intentional policy.
- Warnings are globally suppressed, hiding new project warnings with environment noise.
- A workflow tests only changed files and misses cross-phase regression behavior.
- CI status is described as live Klipper, Moonraker, or hardware verification.

**Prevention**

- Start from a clean checkout and run the same documented full-suite, syntax, and whitespace
  checks used for release verification.
- Pin or deliberately matrix supported Python/test dependencies; record the policy.
- Separate project warning failures from acknowledged external warning debt.
- Add focused jobs only as diagnostics; keep the full regression suite as a required gate.
- If testing against upstream Klipper, pin the tested revision and make compatibility
  failures visible. Do not silently track a moving branch in a release gate.
- State plainly that CI cannot replace Phase 5B hardware UAT.

**Phase placement:** Phase 5C, after implementation and examples settle.

### 11. Releasing From Evidence That Does Not Match the Tagged Commit

**Mistake:** Tag a release because CI is green on a branch, while examples, planning
claims, hardware evidence, or generated artifacts refer to a different commit.

The v1.0 retrospective already identified milestone state being marked complete before
all summaries and verification artifacts existed. v1.1 adds more evidence classes, making
scope drift easier.

**Warning signs**

- Release verification does not print or record the exact commit/tag.
- Hardware UAT predates behavior-changing notification or mutation commits.
- README examples differ from the configuration used in UAT.
- Release notes merge automated, simulated, and hardware claims into one "verified" label.
- The release includes unrelated work or attributes deferred Phase 1 UAT to v1.1.

**Prevention**

- Verify from a clean checkout of the exact release candidate commit.
- Record commit, dependency versions, Klipper/Moonraker versions, commands, and hardware
  evidence references.
- Re-run affected UAT after any behavior or example change; do not reuse stale evidence.
- Audit requirements, roadmap, README, examples, test results, and release notes for the
  same scope and commit.
- Keep the four excluded Phase 1 UAT scenarios explicitly separate.
- Reject unrelated files and claims from the release diff.

**Phase placement:** Phase 5C release gate.

### 12. Misattributing Scope, Evidence, or Scheduling Decisions

**Mistake:** Claim that the user deferred all live-printer verification, that Phase 5
completes Phase 1 UAT, or that existing local warnings count as external notification
delivery.

Project artifacts distinguish these boundaries: representative hardware UAT,
notifications, runtime backup mutation, examples, and CI belong to v1.1; only the four
Phase 1 UAT scenarios are separately user-deferred. Prior verification also distinguishes
local `respond_info` messages from external notifications.

**Warning signs**

- A plan says "user-deferred" without naming the exact four scenarios.
- Existing Phase 4 local warnings are credited as v1.1 notification completion.
- A live printer startup observation is used to mark an excluded Phase 1 scenario complete.
- Hardware UAT is described as optional despite being a stated v1.1 target.
- Release verification claims behavior outside the files and scenarios actually tested.

**Prevention**

- Maintain an evidence matrix with one row per v1.1 requirement and columns for implementation,
  automated proof, simulated proof, live proof, and release proof.
- Use exact attribution: user-deferred, milestone-deferred, automated-only, hardware-tested,
  skipped, or not applicable.
- Keep local diagnostics, external delivery, and durable state as separate outcomes.
- Review scope language during planning, after Phase 5B UAT, and before release.

**Phase placement:** Enforced across all phases; final audit in Phase 5C.

## Cross-Cutting Verification Checklist

### Notification adapters

- Distinct adapter; direct recursion and re-entry are contained.
- Terminal event is emitted once from an immutable payload.
- Free-form content has a defined bounded transport encoding or is not transported.
- Adapter failure cannot alter safety outcome, persistence, pause ownership, or original
  failure reason.
- Real Klipper/Moonraker parser and notifier behavior is tested separately from fakes.

### Runtime backup mutation

- Pure immutable candidate construction and complete invariant validation.
- Exact order preserved; exact no-op performs no write.
- One atomic save before publication; persistence failure preserves old state and file.
- Unrelated tools, flags, and mappings are preserved.
- Mutation is rejected during every active checkpoint and active transition.
- Existing loop-safe resolver policy remains explicit.

### Live-printer UAT and examples

- Examples load and use distinct adapters with printer-specific hazards called out.
- Staged, supervised, conservative procedure with stop/recovery conditions.
- Evidence records exact software/configuration/hardware context and actual observations.
- Simulated, parser/configuration, and hardware claims remain separate.
- The four Phase 1 UAT scenarios remain excluded.

### CI and release verification

- Clean-checkout full suite, syntax checks, and `git diff --check`.
- Intentional Python/dependency/upstream-Klipper version policy.
- No warning suppression that hides project regressions.
- Exact release candidate commit and matching artifacts/evidence.
- Release notes make no hardware, transport, or deferred-scope claims beyond evidence.

## Project-Specific Bottom Line

The v1.1 work sits around a mature fail-closed workflow. The largest integration mistake
would be allowing operational features to weaken that core: notifications must observe
outcomes without controlling them; backup mutation must be durable policy changed only
outside active workflows; examples and live UAT must be treated as potentially dangerous
executable operations; and CI/release verification must report exactly what was proved.
