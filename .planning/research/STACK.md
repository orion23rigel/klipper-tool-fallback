# Stack Research: Non-existent Tool Fallback

**Researched:** 2026-06-27
**Scope:** v1.2 — non-existent tool detection and user-prompted backup definition
**Recommendation:** Extend the existing dependency-free Klipper extension. No new Python libraries needed.

## Executive Recommendation

v1.2 adds detection and user-prompt capability without changing the technology stack:

| Capability | Stack approach |
|---|---|
| Undefined tool detection | Register a default G-code handler (`cmd_default` wrapper) via Klipper's `gcode.register_command()` with an empty command name, or wrap Klipper's internal dispatch. The existing extension already uses `self.gcode.register_command()` for all public commands. |
| User prompt flow | Reuse the existing `pause_gcode`/`resume_gcode` mechanism. When an undefined tool is detected, trigger a PAUSE, present the prompt via Klipper's console message system, and wait for the user to submit a `DEFINE_TOOL_BACKUP <logical_tool> <backup_tool>` command. |
| Persistence | Leverage the existing `StateStore` (JSON-based) with a new `user_defined_backups` mapping in the schema. Reuse `StateStore.save()` and `StateStore.load_reconciled()`. |
| Fallback application | Extend the existing `resolve_backup_graph()` and `_select_and_conditionally_purge()` to also consider user-defined backup mappings alongside configured backup lists. |

## Stack Additions

### 1. Klipper G-code Default Handler

Klipper's `gcode.py` dispatches unknown commands through `cmd_default`. The extension can intercept Tn commands that fall outside configured tools by:

- Registering a handler for a generic pattern (Klipper does not support regex patterns natively, so a wrapper around the gcode object's command lookup is needed)
- OR: Subclassing/wrapping the gcode object's `get_command` method to catch Tn commands before they reach Klipper's default handler

**Recommended approach:** Register a `_TOOL_FALLBACK_TN` wrapper command that the user calls instead of raw `Tn`. This is the safest, least invasive approach and aligns with how the extension already wraps `RESUME`.

**Alternative approach (more transparent):** Monkey-patch or wrap Klipper's `GcodeCommand._run()` or the `gcode` object's command lookup to intercept unconfigured Tn commands. This is riskier and may break across Klipper versions.

### 2. New G-code Commands

| Command | Purpose |
|---|---|
| `DEFINE_TOOL_BACKUP` | User defines a backup tool mapping for an undefined logical tool |
| `UNDEFINE_TOOL_BACKUP` | User removes a user-defined backup mapping |
| `SHOW_TOOL_BACKUPS` | Show all configured and user-defined backup mappings |

These follow the existing naming convention (all caps, underscore-separated).

### 3. Schema Extension

The existing `tool_fallback_state.py` schema needs one new field:

```python
@dataclass(frozen=True)
class ToolState:
    # existing fields...
    user_defined_backup: object = None  # NEW: logical tool -> physical tool
```

This is additive and backward-compatible. The `load_reconciled()` method should merge user-defined backups with configured backups.

### 4. No New Dependencies

The extension is currently dependency-free (only Python stdlib + Klipper). v1.2 maintains this property.

## What NOT to Add

- **New Python packages** — unnecessary complexity for a Klipper extension
- **Network/HTTP client** — the user prompt is local (Klipper console), not remote
- **New persistence format** — extend existing JSON schema, don't replace it
- **Web UI component** — out of scope for this milestone; the prompt is via Klipper console

## Integration Points

| Existing file | Change |
|---|---|
| `tool_fallback.py` | Add default Tn handler / wrapper, DEFINE_TOOL_BACKUP command, user-defined backup resolution |
| `tool_fallback_config.py` | No changes needed (user-defined backups are runtime, not config-time) |
| `tool_fallback_state.py` | Add `user_defined_backup` field to ToolState schema |
| `tool_fallback_state.py` | Update `load_reconciled()` to merge user-defined backups |
