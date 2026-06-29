# Milestones

## v1.2 Non-existent Tool Fallback Definition (Shipped: 2026-06-29)

**Phases completed:** 5 phases, 9 plans, 7 tasks

**Key accomplishments:**

- Schema version bumped to 2 with backward-compatible user_defined_backup fields on ToolState and FallbackState, implicit v1→v2 migration in from_dict(), and validation in save() and reconcile()
- _TOOL_FALLBACK_TN wrapper G-code command with T parameter validation, configured-tool routing delegation, and undefined-tool detection via WorkflowCheckpoint
- 1. [Rule 2 - Missing Critical Functionality] Allow DEFINE_TOOL_BACKUP during waiting_for_user stage
- 1. [Rule 3 - Blocking Issue] Synchronous flow changes test structure
- JWT auth with refresh rotation using jose library
- get_status() already exposes user_defined_backups via to_dict(); 5 new tests verify visibility, empty state, undefinition, JSON serialization, and Phase 10 logging.

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
