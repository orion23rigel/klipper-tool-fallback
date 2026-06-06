# Klipper Tool Fallback

## What This Is

Klipper Tool Fallback is an independent Klipper Python extension for routing logical
tool commands to physical tools, tracking filament and purge state, and automatically
failing over to configured backup tools after confirmed filament runout.

It is designed for multi-tool printers but does not depend on a particular toolchanger
implementation. Existing `T0`, `T1`, and similar commands are intercepted while their
original handlers remain available internally for physical selection.

## Core Value

A print can recover automatically from filament runout by selecting a known-loaded
backup tool without losing track of routing, purge state, or safety.

## Requirements

### Validated

(None yet - ship to validate)

### Active

- [ ] Explicit `[tool_fallback Tn]` configuration for every managed physical tool
- [ ] Persistent logical-to-physical mappings and ordered backup graphs
- [ ] Debounced filament-loaded state derived from filament sensors
- [ ] Persistent purged state that clears after confirmed unloading
- [ ] Immediate runout pause followed by confirmed automatic fallback
- [ ] Temperature transfer, failed-heater shutdown, conditional purge, and safe resume
- [ ] Recursive backup resolution with priority ordering and loop prevention
- [ ] Manual remap, restore, state inspection, and backup-management commands
- [ ] Meaningful Moonraker notifier integration through configurable G-code
- [ ] Recoverable paused state on selection, heating, purge, or timeout failures

### Out of Scope

- Direct dependency on `klipper-toolchanger` - selection is adapter-based and existing
  `Tn` handlers are captured.
- Material compatibility enforcement - backup eligibility intentionally ignores material.
- Resuming an interrupted print after Klipper restart - mappings persist, print recovery does not.
- Inferring purge state from manual extrusion - only the dedicated purge workflow marks purged.
- Mechanical tool-presence validation - the printer's selection implementation owns this.

## Context

The originating printer uses per-tool filament switch sensors, custom `Tn` macros,
Moonraker's `discord` notifier, and first-use purge behavior. Existing macro-only backup
remapping is too fragile for recursive graph traversal, debounce timers, persistent
structured state, workflow ownership, and failure recovery.

## Constraints

- **Compatibility**: Must support printers whose only physical selection interface is
  existing `T0`, `T1`, and similar commands.
- **Independence**: Must not import or require a specific toolchanger extension.
- **Persistence**: Structured state must use an atomic extension-managed JSON file.
- **Safety**: Automatic resume is allowed only when this extension caused the pause.
- **Sensor authority**: Loaded state is derived from explicitly hooked filament sensors.
- **Klipper conventions**: Extension behavior must remain reactor-safe and avoid blocking
  Klipper's main thread.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use a Python extension with thin macro adapters | Macro-only orchestration is fragile for timers, graphs, and persistence | Pending |
| Configure tools as `[tool_fallback Tn]` | Concise and consistent with Klipper prefixed sections | Pending |
| Intercept logical `Tn` commands | Slicer G-code remains unchanged | Pending |
| Preserve original `Tn` handlers internally | Supports printers without lower-level selection commands | Pending |
| Use ordered recursive backup graphs | Supports priority, chains, and shared backups | Pending |
| Use symmetric one-second sensor debounce | Prevents transient sensor noise from corrupting state | Pending |
| Persist mappings, backups, loaded, purged, and failed state | State remains coherent across restarts | Pending |
| Keep `failed` specific to confirmed runout | Mechanical selection failures must not corrupt filament state | Pending |

---
*Last updated: 2026-06-06 after initial design discussion*
