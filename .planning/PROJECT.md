# Klipper Tool Fallback

## Overview
Independent Klipper extension for persistent logical-to-physical tool routing, filament-state tracking, purge lifecycle management, and automatic backup-tool fallback.

## Status
v1.0 shipped: Phases 1-4 complete with 258 automated tests passing.
v1.1 shipped: Phases 5-7 complete with notifications, backup-list management, and CI automation.
v1.2 shipped: Phases 8-12 complete with non-existent tool fallback definition.

## Core Purpose
Ensure that tool selection and filament runout handling can fallback to a secondary tool automatically when the primary tool or sensor fails.

## Current State

The extension implements persistent routing, sensor and purge lifecycle management,
safe active-route transitions, and automatic backup fallback with fail-closed runtime
checkpoints. Hardware UAT, external notifications, and runtime backup-list management
were shipped in v1.1. The v1.2 milestone added graceful handling of G-code calling a
tool that doesn't exist on the printer: a wrapper command detects undefined tools, pauses
the print, prompts the user to define a backup tool, and resumes once defined or after a
configurable timeout.

### Shipped Milestones

<details>
<summary>v1.0 MVP (Phases 1-4) — Shipped 2026-06-11</summary>

Configuration schema, state persistence, tool routing and fallback, runtime safety and purge. 367 tests passing.

</details>

<details>
<summary>v1.1 Integration & Operations (Phases 5-7) — Shipped 2026-06-12</summary>

Runtime contracts (notifications, backup policy), examples and live integration, CI and release verification.

</details>

<details>
<summary>v1.2 Non-existent Tool Fallback Definition (Phases 8-12) — Shipped 2026-06-29</summary>

State schema v2 with backward-compatible user-defined backup fields, DEFINE_TOOL_BACKUP/UNDEFINE_TOOL_BACKUP/SHOW_TOOL_BACKUPS G-code commands, _TOOL_FALLBACK_TN wrapper command for undefined tool detection, user prompt flow with configurable timeout, and user-defined backup injection into the fallback resolution pipeline. 417 tests passing.

</details>

## Next Milestone Goals

- Hardware UAT with live printer evidence
- Web UI for backup-tool definition and management
- Automatic tool discovery/probing
- Multi-user backup profiles (if Klipper supports multi-user in the future)

## Requirements

### Validated

- ✓ Configuration schema with immutable normalized tool models — v1.0
- ✓ Deterministic state reconciliation with failure-safe atomic JSON persistence — v1.0
- ✓ Fail-closed tool selection with automatic backup fallback — v1.0
- ✓ Guarded active-route transitions with purge lifecycle management — v1.0
- ✓ Trustworthy sensor-derived filament state — v1.0
- ✓ Complete ordered automatic fallback — v1.0
- ✓ Safety-neutral external outcome notifications — v1.1
- ✓ Atomic runtime backup policy management — v1.1
- ✓ Representative printer integration example — v1.1
- ✓ Clean-checkout CI automation — v1.1
- ✓ Schema v2 with backward-compatible user-defined backup fields — v1.2
- ✓ DEFINE_TOOL_BACKUP, UNDEFINE_TOOL_BACKUP, SHOW_TOOL_BACKUPS commands — v1.2
- ✓ _TOOL_FALLBACK_TN wrapper command for undefined tool detection — v1.2
- ✓ User prompt flow with configurable timeout — v1.2
- ✓ User-defined backup injection into fallback resolution pipeline — v1.2
- ✓ SHOW_TOOL_FALLBACK_STATE includes user-defined backups — v1.2

### Active

- [ ] Hardware UAT with live printer evidence
- [ ] Web UI for backup-tool definition
- [ ] Automatic tool discovery/probing

### Out of Scope

| Feature | Reason |
|---|---|
| Transparent G-code interception (monkey-patching) | Higher risk, version-dependent; wrapper command is safer |
| Multi-user backup profiles | Klipper is single-user; profiles add unnecessary complexity |
| Network-based prompts | Local Klipper console is the interaction surface |

## Context

Shipped v1.0 (4 phases, 12 plans), v1.1 (3 phases), and v1.2 (5 phases, 9 plans) with 417 automated tests passing.
Tech stack: Python (Klipper extension), pytest, Klipper FakePrinter harness.
Key pattern: fail-closed safety enforced at every state transition and backup resolution path.

## Key Decisions

| Decision | Outcome |
|----------|---------|
| Use wrapper command `_TOOL_FALLBACK_TN` for undefined tool detection (not monkey-patching) | ✓ Good — avoids version-dependent Klipper internals |
| Schema version bumped from 1 to 2 with implicit migration in `from_dict()` | ✓ Good — existing state files load without migration step |
| `user_defined_backups` stored as `MappingProxyType` | ✓ Good — consistent with tools/mappings pattern |
| User-defined backups injected at caller side (`_resolve_backup_with_rescan`), not in `resolve_backup_graph()` | ✓ Good — keeps graph function pure |
| User-defined backups flow through `_select_and_conditionally_purge()` — no separate fast path | ✓ Good — same fail-closed safety checkpoints apply |
| Prompt flow runs synchronously with `reactor.advance(0.1)` polling | ✓ Good — simpler than timer callbacks, consistent with existing code |
| `undefined_tool_timeout` defaults to 300s (5 minutes) | ✓ Good — reasonable default, configurable |
| Default tool for timeout = first configured tool (lowest number) | ✓ Good — deterministic, no user input needed |
| None backup value removes entry from dict (not sets to None) | ✓ Good — cleaner semantics |

## Constraints

- Must remain compatible with Klipper's extension API
- Fail-closed safety must never be bypassed
- State schema changes must be backward-compatible
- All user-defined backup paths must flow through the same safety checkpoints as configured backups

---
*Last updated: 2026-06-29 after v1.2 milestone*
