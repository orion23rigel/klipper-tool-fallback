---
status: testing
phase: 01-extension-foundation-and-persistence
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md]
started: 2026-06-06T18:15:00Z
updated: 2026-06-06T18:15:00Z
---

## Current Test

number: 1
name: Valid Configuration Startup
expected: |
  With `[tool_fallback]` and canonical `[tool_fallback Tn]` sections configured,
  Klipper reaches ready state and creates or reconciles the configured JSON state
  file containing every managed tool, its mapping, and ordered backups.
awaiting: user response

## Tests

### 1. Valid Configuration Startup
expected: With `[tool_fallback]` and canonical `[tool_fallback Tn]` sections configured, Klipper reaches ready state and creates or reconciles the configured JSON state file containing every managed tool, its mapping, and ordered backups.
result: [pending]

### 2. Persisted State Survives Restart
expected: After restarting Klipper, valid persisted mappings and operator-managed backup order remain intact while newly configured tools are added and removed tools or stale references are removed.
result: [pending]

### 3. Invalid State Blocks Startup Clearly
expected: If the persisted JSON is corrupt, unsupported, or inconsistent, Klipper startup fails instead of silently resetting state, and the error identifies the configured state path and failure category.
result: [pending]

### 4. Read-Only Status Inspection
expected: `SHOW_TOOL_FALLBACK_STATE` and Klipper's `tool_fallback` status expose the same deterministic canonical snapshot, and repeated inspection does not modify the state file.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

[none yet]
