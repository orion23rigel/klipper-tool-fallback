# Roadmap: Klipper Tool Fallback

## Phase 1: Extension Foundation And Persistence

Create the Klipper extension skeleton, configuration model, atomic JSON state store,
state schema/versioning, startup reconciliation interfaces, and status commands.

Covers: ROUTE-01, STATE-01, STATE-02, STATE-04, ADAPT-01

### Plans

**Wave 1**
- [x] `01-01-PLAN.md` - Configuration And Test Foundation

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] `01-02-PLAN.md` - Versioned State And Atomic Persistence

**Wave 3** *(blocked on Waves 1 and 2 completion)*
- [ ] `01-03-PLAN.md` - Lifecycle Persistence And Status Surface

## Phase 2: Command Routing And Manual Remapping

Capture and intercept configured `Tn` handlers, implement physical bypass selection,
persistent mappings, manual remap/restore/reset commands, and active-print transition
ownership.

Covers: ROUTE-02, ROUTE-03, ROUTE-04, ROUTE-05

## Phase 3: Sensor State And Purge Lifecycle

Implement explicit sensor hooks, symmetric debounce, startup reconciliation, failed-state
semantics, dedicated purge workflow, and active-print purge checks.

Covers: STATE-03, SENS-01 through SENS-04, PURGE-01 through PURGE-05

## Phase 4: Automatic Fallback Workflow

Implement immediate-pause ownership, transient recovery, recursive ordered backup
resolution, temperature transfer, failed-heater shutdown, stage timeouts, conditional
purge, persistent remapping, safe resume, and recoverable failures.

Covers: FALL-01 through FALL-08

## Phase 5: Notifications, Integration, And Verification

Add notification adapters and meaningful messages, example configurations, comprehensive
unit/workflow tests, installation documentation, and validation against a representative
Klipper configuration.

Covers: ADAPT-02, ADAPT-03, TEST-01 through TEST-03

---
*Roadmap created: 2026-06-06*
