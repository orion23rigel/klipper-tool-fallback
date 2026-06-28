# Research Summary: Non-existent Tool Fallback (v1.2)

**Synthesized:** 2026-06-27
**Sources:** `PROJECT.md`, `STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md`

## Executive Summary

v1.2 extends the shipped v1.0/v1.1 Klipper tool fallback extension to handle a new failure mode: **when G-code references a tool number that has no configuration on the printer**. Unlike existing automatic backup fallback (which handles sensor failures of configured tools), this feature requires:

1. **Detection** of undefined tool references in G-code
2. **User interaction** to define a backup tool
3. **Persistence** of user-defined backup mappings
4. **Application** of user-defined backups during routing

The recommended approach uses a **wrapper G-code command** (`_TOOL_FALLBACK_TN`) rather than monkey-patching Klipper internals, maintaining the extension's dependency-free property and version stability.

## Key Findings

### Stack
- No new Python dependencies needed
- Extension of existing `StateStore` schema with `user_defined_backups` field
- Three new G-code commands: `DEFINE_TOOL_BACKUP`, `UNDEFINE_TOOL_BACKUP`, `SHOW_TOOL_BACKUPS`
- Detection via wrapper command (safe, version-stable) or optional transparent interception (advanced users)

### Features
- **Table stakes:** Undefined tool detection, pause+prompt, user backup definition command, persistence, routing integration
- **Differentiators:** Auto-apply last-used backup, configurable default fallback, backup listing
- **Anti-features:** No web UI, no network-based prompts, no automatic hardware discovery, no multi-user profiles

### Architecture
- Three files modified: `tool_fallback.py` (new detection layer + commands), `tool_fallback_state.py` (schema extension)
- `tool_fallback_config.py` unchanged (user-defined backups are runtime-only)
- User-defined backups merge with configured backups in `resolve_backup_graph()`
- Build order: schema → commands → reconciliation → detection → prompt flow → observability

### Pitfalls
- **State migration** is the highest risk — existing state files must load without errors
- **User prompt deadlock** requires a configurable timeout
- **Fail-closed safety** must not be bypassed by user-defined backup paths
- **Concurrency** between user commands and automated fallback must be guarded

## Implications for Roadmap

1. **Phase 1:** State schema extension with backward-compatible migration
2. **Phase 2:** User-facing commands (DEFINE/UNDEFINE/SHOW)
3. **Phase 3:** User-defined backup reconciliation into routing
4. **Phase 4:** Undefined tool detection layer (wrapper command)
5. **Phase 5:** User prompt flow with timeout and safety guards

Each phase builds on the previous one. Phase 1 is the foundation — if state migration breaks, nothing else works.

## Sources

- `.planning/PROJECT.md` — v1.2 milestone goals
- `.planning/research/STACK.md` — technology stack decisions
- `.planning/research/FEATURES.md` — feature categories and complexity
- `.planning/research/ARCHITECTURE.md` — component changes and build order
- `.planning/research/PITFALLS.md` — risks and prevention strategies
