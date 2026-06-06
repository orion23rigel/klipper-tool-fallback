# Klipper Tool Fallback

Independent Klipper extension for persistent logical-to-physical tool routing,
filament-state tracking, purge lifecycle management, and automatic backup-tool fallback.

## Phase 1 Foundation

Phase 1 provides strict configuration validation, versioned atomic JSON persistence,
startup reconciliation against configured tools, and read-only state inspection.

Routing, `Tn` command interception, filament-sensor handling, purging, and automatic
fallback are planned but are **not implemented in Phase 1**. Configuring this extension
does not yet change tool-selection or runout behavior.

## Installation

Place these files in Klipper's `klippy/extras` directory:

```text
tool_fallback.py
tool_fallback_config.py
tool_fallback_state.py
```

Restart Klipper after adding the files and configuration. Klipper loads the extension
from the global `[tool_fallback]` section.

## Configuration

```ini
[tool_fallback]
state_path: ~/printer_data/config/tool_fallback_state.json
debounce_time: 1.0
pause_gcode: PAUSE
resume_gcode: RESUME
purge_gcode: PURGE_TOOL
notify_gcode: _TOOL_FALLBACK_NOTIFY
selection_timeout: 120
heating_timeout: 300
purge_timeout: 180

[tool_fallback T0]
filament_sensor: filament_switch_sensor T0_sensor
heater: extruder
backups: T1

[tool_fallback T1]
filament_sensor: filament_switch_sensor T1_sensor
heater: extruder1
backups:
```

Every managed physical tool requires one `[tool_fallback Tn]` section. Tool names must
use canonical uppercase names such as `T0` or `T12`. Backup entries are ordered and must
reference configured tools.

The adapter names and timing values are validated in Phase 1 and reserved for later
workflow phases. In particular, `purge_gcode` configures the future purge adapter but is
not invoked yet.

## Persistent State

At `klippy:ready`, the extension validates all tool sections, loads the configured state
file, reconciles it with configured tools, and writes only when the file is missing or
the canonical state changed.

Schema version 1 persists:

- `loaded`, `purged`, and `failed` flags for each physical tool
- ordered `backups` for each physical tool
- logical-to-physical `mappings`

Writes use a same-directory temporary file, file flush and `fsync`, atomic replacement,
and parent-directory `fsync` where supported. Malformed JSON, unsupported schemas,
invalid state, and filesystem failures block Klipper startup with an error containing
the state path. The extension never silently resets invalid operator state.

## Inspecting State

Run:

```text
SHOW_TOOL_FALLBACK_STATE
```

The command prints deterministic read-only JSON containing initialization status,
schema version, normalized global configuration, canonical tools, and mappings. The same
snapshot is available through Klipper's `printer.tool_fallback` status object.
