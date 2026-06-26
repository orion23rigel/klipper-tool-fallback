---
phase: "06"
plan: "06-01"
title: "Representative Trident Bundle And Ownership Migration"
status: in_progress
started: 2026-06-25T21:43:00Z
completed:
---

## Objective

Create one complete redacted representative integration bundle for the user's T0/T1
Voron Trident and document the ownership migration required to adopt it safely.

## Tasks

| # | Task | Status |
|---|------|--------|
| 06-01-T1 | Build the complete redacted T0/T1 Trident configuration bundle | ✓ Complete |
| 06-01-T2 | Document adaptation, ownership migration, commissioning, hazards, and rollback | Pending |

## Key Files Created

- `examples/trident/tool_fallback.cfg` - Global section with T0/T1 reciprocal backups and private adapters
- `examples/trident/tool_fallback_macros.cfg` - Narrow printer-owned purge and notification adapters
- `examples/trident/sensor_hooks.cfg` - Replacement physical handlers and one-owner sensor hooks

## Key Decisions

- All values redacted: no pins, CAN UUIDs, serial paths, URLs, or tokens included
- Adapters delegate once to printer-owned behavior; no public-command recursion
- No runtime source files modified
- Legacy REMAP_TOOL, BACKUP_SPOOL, and _TOOL_RUNOUT removal documented in config comments

## Self-Check: PASSED

## Issues

- Task 2 (documentation) not yet completed. Plan requires re-execution to finish README.md and root README link.
