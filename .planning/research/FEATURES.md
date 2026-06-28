# Feature Research: Non-existent Tool Fallback

**Researched:** 2026-06-27
**Scope:** v1.2 — features for detecting undefined tools and prompting user for backup

## Feature Categories

### Table Stakes (must have)

| Feature | Complexity | Dependencies |
|---|---|---|
| **Undefined tool detection** | Medium | G-code interception layer |
| **Pause + prompt on undefined tool** | Low | Existing pause/resume mechanism |
| **User command to define backup** | Low | State persistence |
| **Persist user-defined backup mapping** | Low | StateStore extension |
| **Apply user-defined backup during routing** | Medium | Existing backup graph resolution |

### Differentiators (nice to have)

| Feature | Complexity | Dependencies |
|---|---|---|
| **Auto-apply last-used backup** | Low | Persisted state |
| **Configurable default fallback** | Low | Global config extension |
| **List available user-defined backups** | Low | SHOW_TOOL_BACKUPS command |

### Anti-features (explicitly avoid)

| Feature | Why excluded |
|---|---|
| **Automatic tool discovery** | Requires hardware probing; out of scope for a software-only extension |
| **Web UI for backup definition** | Adds frontend dependency; console commands suffice for v1.2 |
| **Multi-user backup profiles** | Klipper is single-user; profiles add unnecessary complexity |
| **Network-based prompt** | Local Klipper console is the interaction surface; network adds attack surface and latency |

## Key Observations from Codebase

1. **The extension only intercepts configured tools.** `_install_logical_handlers` iterates over `self.config.tools` keys. If G-code references `T7` and no `[tool_fallback T7]` exists, the extension never sees it.

2. **Detection requires a new interception layer.** Options:
   - A wrapper command the user calls instead of raw `Tn` (safest)
   - Monkey-patching Klipper's G-code dispatch (riskier, version-dependent)
   - A Klipper macro that the user's slicer/post-processor wraps `Tn` calls with

3. **The existing pause/resume mechanism is the right primitive.** The extension already uses `pause_gcode`/`resume_gcode` for workflow transitions. A user-prompt flow can piggyback on this.

4. **User-defined backups are runtime-only.** They don't need config-file entries; they're persisted in the JSON state file and survive restarts.

5. **The backup graph resolution (`resolve_backup_graph`) is the right place to merge user-defined backups.** It already traverses configured backup lists; adding user-defined mappings as an additional fallback tier is straightforward.

## Complexity Notes

- **Undefined tool detection** is the hardest part because Klipper's G-code dispatch is not designed for wildcard interception. The safest approach is a wrapper command.
- **User prompt flow** is straightforward — it reuses existing pause/resume primitives.
- **Persistence and fallback application** are low-complexity extensions to existing code.
