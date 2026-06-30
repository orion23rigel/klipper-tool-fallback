# Milestones

## v1.2 Non-existent Tool Fallback Definition (Shipped: 2026-06-29)

**Phases completed:** 5 phases (8-12), 9 plans, 424 tests passing

**Key accomplishments:**

- Schema v2 with backward-compatible `user_defined_backup` fields on ToolState and FallbackState, implicit v1→v2 migration, and save()/reconcile() validation
- `DEFINE_TOOL_BACKUP`, `UNDEFINE_TOOL_BACKUP`, `SHOW_TOOL_BACKUPS` G-code commands with workflow guards and sentinel coordination
- `_TOOL_FALLBACK_TN` wrapper command for undefined tool detection via WorkflowCheckpoint — avoids Klipper version dependency
- User prompt flow: pause, prompt with configurable 5-min timeout, DEFINE_TOOL_BACKUP response, resume; timeout falls back to first configured tool
- User-defined backups injected into `_resolve_backup_with_rescan()` effective backup list at caller side, preserving fail-closed safety
- `SHOW_TOOL_FALLBACK_STATE` exposes user_defined_backups via `get_status()`
- Full cross-phase integration verified: 12 connections, 0 orphaned exports, 4 E2E flows complete, 28/28 requirements satisfied

---

## v1.1 Integration & Operations (Shipped: 2026-06-12)

**Phases completed:** 3 phases (5-7), 6 plans

**Key accomplishments:**

- Safety-neutral external outcome notifications with at-most-once delivery and adapter failure isolation
- Atomic runtime backup policy management (replace/clear/restore configured backups)
- Representative printer integration example covering installation, rollback, adapters, hooks, and commissioning
- Clean-checkout CI automation for syntax, tests, example-contract checks, and `git diff --check`

---

## v1.0 MVP (Shipped: 2026-06-11)

**Phases completed:** 4 phases, 12 plans, 18 tasks

**Key accomplishments:**

- Strict Klipper configuration loaders with immutable normalized tool models and 31 startup-contract tests
- Strict schema-v1 state with deterministic reconciliation and failure-safe atomic JSON persistence
- Ready-time canonical state publication with path-specific failure handling and deterministic read-only inspection
- Fail-closed public Tn interception with recursion-free mapped physical selection and transient ownership
- Canonical persistent mapping commands with authorized physical bypass and fail-closed active-print route protection
- Guarded active-route transitions with pause ownership, persistence rollback, and failure containment
- Graceful sensor authority, immutable durable transitions, and purge-adapter recursion prevention
- Trustworthy sensor-derived filament state with guarded macro authority and graceful outage handling
- Recursion-free durable purge authority integrated with ordinary selection and active-route transitions
- Fail-closed ownership, deterministic backup resolution, and visible runtime workflow state
- Complete ordered automatic fallback with guarded recovery and fail-closed containment

---
