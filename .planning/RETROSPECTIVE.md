# Project Retrospective

## Milestone: v1.0 - MVP

**Shipped:** 2026-06-11  
**Phases:** 4 | **Plans:** 12

### What Was Built

- Persistent logical-to-physical tool routing and atomic canonical state.
- Sensor authority, debounce, filament state, and purge lifecycle management.
- Safe active-route transitions and complete automatic backup fallback.
- Fail-closed checkpoints, guarded heating-timeout recovery, and regression coverage.

### What Worked

- Phase plans maintained explicit safety invariants and requirement identifiers.
- Deterministic Klipper fakes enabled fast full-suite verification.
- Independent milestone integration review found cross-stage defects missed by the green suite.

### What Was Inefficient

- Milestone state was marked complete before `04-03-SUMMARY.md` and Phase 4 verification existed.
- Early tests covered stage helpers and happy paths but missed blocked-stage continuation.
- Requirements, roadmap, README, and design drifted from the implemented milestone.

### Patterns Established

- Every helper returning a blocked workflow checkpoint must be treated as terminal.
- Synchronous adapters enforce timeouts by rejecting post-return elapsed-time overruns.
- Milestone completion requires cross-phase flow review, not only a passing full suite.

### Key Lessons

1. Test failure containment at every caller boundary, not only inside stage helpers.
2. Do not mark a milestone complete until summaries, phase verification, requirements,
   documentation, and integration audit agree.

### Quality

- 260 automated tests passing.
- 27/27 v1.0 requirements satisfied.
- Four Phase 1 UAT scenarios and representative hardware UAT intentionally deferred.

---

## Milestone: v1.2 — Non-existent Tool Fallback Definition

**Shipped:** 2026-06-29
**Phases:** 5 | **Plans:** 9

### What Was Built

- Schema v2 with backward-compatible `user_defined_backup` fields on ToolState and FallbackState.
- `DEFINE_TOOL_BACKUP`, `UNDEFINE_TOOL_BACKUP`, and `SHOW_TOOL_BACKUPS` G-code commands.
- `_TOOL_FALLBACK_TN` wrapper command for undefined tool detection via WorkflowCheckpoint.
- User prompt flow: pause, prompt, wait (with configurable 5-minute timeout), resume.
- User-defined backup injection into `_resolve_backup_with_rescan()` effective backup list.
- `SHOW_TOOL_FALLBACK_STATE` exposes user-defined backups via `get_status()`.

### What Worked

- TDD RED-GREEN cycle across all phases — every feature had failing tests first.
- Wrapper command pattern for undefined tool detection avoided Klipper version dependency.
- Caller-side injection of user-defined backups kept `resolve_backup_graph()` pure.
- Synchronous prompt flow with `reactor.advance(0.1)` polling was simpler than timer callbacks.
- Implicit migration in `from_dict()` handled v1→v2 state files without a separate migration step.

### What Was Inefficient

- Phase 9 UAT file had 23 pending scenarios — UAT was not completed before milestone close.
- Milestone audit found 18/28 requirements unsatisfied due to missing VERIFICATION.md files for phases 9, 10, 11, 12.
- State schema extension had 5 auto-fix bugs during implementation, mostly from adding a 5th field to ToolState.
- Phase 12 plan 02 required zero code changes — verification was straightforward but plan overestimated effort.

### Patterns Established

- Frozen dataclass mutation via `with_*` methods returning new instances (never mutates in place).
- Workflow checkpoint signaling with `source` + `stage` + `generation` for cross-phase communication.
- Guard-then-parse-then-validate-then-act command structure for all G-code handlers.
- Sentinel-flag coordination between prompt flow and DEFINE_TOOL_BACKUP command.

### Key Lessons

1. Always run VERIFICATION.md for every phase — skipping it creates systemic audit gaps.
2. Adding fields to dataclasses used across many `with_*` mutation methods cascades bugs — consider builder patterns for complex state.
3. UAT should be completed during the phase, not deferred to milestone close.
4. Synchronous prompt flows in Klipper require careful handling of reactor timing — use short `advance()` intervals.

### Cost Observations

- Model mix: heavy use of opus for implementation phases, sonnet for planning and review.
- Sessions: ~15 sessions across 5 phases over 2 days.
- Notable: TDD cycle (RED-GREEN) caught bugs early in every phase, reducing fix cost.

---

## Cross-Milestone Trends

| Milestone | Phases | Tests | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 4 | 260 | Added independent cross-phase audit before archival |
| v1.2 | 5 | 424 | TDD RED-GREEN cycle, wrapper command pattern, implicit schema migration |
