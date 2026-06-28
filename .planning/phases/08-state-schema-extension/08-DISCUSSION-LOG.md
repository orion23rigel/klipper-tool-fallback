# Phase 08: State Schema Extension - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-28
**Phase:** 08-State Schema Extension
**Areas discussed:** Storage design, Schema version, User-defined backup semantics, Data model type

---

## Storage Design

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level dict on FallbackState | Add `user_defined_backups` as a dict at the FallbackState level | ✓ |
| Embedded in each ToolState | Add `user_defined_backup` as a field on each ToolState | |

**User's choice:** "choose when you deem to be the best solution for this"
**Notes:** Agent selected top-level dict based on STATE-02 wording and clean data model. `ToolState.user_defined_backup` is a derived convenience accessor.

## Schema Version

| Option | Description | Selected |
|--------|-------------|----------|
| Bump to version 2 | Explicit version bump with migration | ✓ |
| Keep version 1, add optional field | Backward-compatible without version bump | |
| Let the agent decide | Trust agent to pick best approach | ✓ |

**User's choice:** "Let the agent decide"
**Notes:** Agent selected version 2 bump. Explicit version change makes migration visible and clean.

## User-Defined Backup Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| User-defined overrides configured | User backup replaces configured backup | ✓ |
| User-defined merges with configured | User backup prepended/appended to configured list | |
| Let the agent decide | Trust agent to pick best approach | ✓ |

**User's choice:** "Let the agent decide"
**Notes:** Agent selected override semantics. Matches phase purpose: user explicitly defines backup for non-existent tool.

## Data Model Type

| Option | Description | Selected |
|--------|-------------|----------|
| Single tool (one backup per tool) | `user_defined_backup` is a single string | ✓ |
| List of tools (multiple backups) | `user_defined_backup` is a list | |

**User's choice:** "you decide what is best"
**Notes:** Agent selected single tool. Simplest model satisfying all STATE requirements. `ToolState.user_defined_backup` is a single optional string.

---

## Agent Decisions Made

| Decision | Rationale |
|----------|-----------|
| `user_defined_backups` stored as top-level dict on `FallbackState` | Matches STATE-02 wording, clean data model |
| Schema version bumped to 2 | Explicit schema change signal |
| User-defined overrides configured backups | User intent is authoritative for non-existent tools |
| Single string per `ToolState.user_defined_backup` | Simplest model, matches STATE-01 singular |
| Implicit migration during `from_dict()` | Minimal risk, no file rewrite needed |
| `to_dict()` always includes `user_defined_backups` | Deterministic output, consistent with existing patterns |

## Deferred Ideas

None — discussion stayed within phase scope.
