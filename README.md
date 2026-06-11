# Klipper Tool Fallback

Independent Klipper extension for persistent logical-to-physical tool routing,
filament-state tracking, purge lifecycle management, and automatic backup-tool fallback.

## v1.0 Features

The extension provides strict configuration validation, versioned atomic JSON
persistence, logical `Tn` routing, filament-sensor state tracking, guarded purge
lifecycle management, active-route remapping, and automatic backup-tool fallback.

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
purge_gcode: _TOOL_FALLBACK_PURGE
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

`purge_gcode` must name a distinct implementation macro; it cannot be `PURGE_TOOL`
because `PURGE_TOOL` is the extension's public command. Sensor `runout_gcode` should
invoke `TOOL_FALLBACK_RUNOUT TOOL=Tn PAUSE_OWNED=1` when the sensor's
`pause_on_runout` behavior owns the pause.

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
