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

## Cross-Milestone Trends

| Milestone | Phases | Tests | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 4 | 260 | Added independent cross-phase audit before archival |
