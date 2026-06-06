# Klipper Tool Fallback Design

## Configuration

```ini
[tool_fallback]
state_path: ~/printer_data/config/tool_fallback_state.json
debounce_time: 1.0
pause_gcode: PAUSE
resume_gcode: RESUME
notify_gcode: _TOOL_FALLBACK_NOTIFY
selection_timeout: 120
heating_timeout: 300
purge_timeout: 180

[tool_fallback T0]
filament_sensor: filament_switch_sensor T0_sensor
heater: extruder
backups: T1, T3

[tool_fallback T1]
filament_sensor: filament_switch_sensor T1_sensor
heater: extruder1
backups: T2
```

Each sensor must explicitly hook the extension:

```ini
[filament_switch_sensor T0_sensor]
pause_on_runout: True
runout_gcode:
  TOOL_FALLBACK_RUNOUT TOOL=T0
insert_gcode:
  TOOL_FALLBACK_INSERT TOOL=T0
```

## Persistent State

```json
{
  "version": 1,
  "tools": {
    "T0": {
      "loaded": true,
      "purged": true,
      "failed": false,
      "backups": ["T1", "T3"]
    }
  },
  "mappings": {
    "T0": "T1"
  }
}
```

Writes use a temporary file, flush/fsync, and atomic replacement. Configuration backup
lists initialize missing state but do not silently overwrite user-managed persisted lists.

## State Semantics

- `loaded`: last confirmed debounced sensor state.
- `purged`: physical tool has completed `PURGE_TOOL` since its current filament load.
- `failed`: physical tool has experienced confirmed runout and remains ineligible.
- `mapping`: persistent logical tool to physical tool route.
- `backups`: ordered physical-tool fallback candidates.

Confirmed unloading sets `loaded=false`, `purged=false`, and preserves `failed` until
refill. Confirmed insertion sets `loaded=true`, `purged=false`, and clears `failed`.

At startup:

- Sensor loaded and persisted loaded: preserve purged state and clear failed after debounce.
- Sensor loaded and persisted unloaded: set loaded, clear failed, and mark unpurged.
- Sensor unloaded: set loaded false and purged false after debounce.

## Command Interception

At ready time, the extension captures configured existing `Tn` handlers and replaces
them with logical routing handlers. An intercepted `T0` resolves its persisted mapping,
then directly invokes the saved original handler for the target physical tool.

`SELECT_PHYSICAL_TOOL TOOL=Tn` directly invokes the captured original handler and bypasses
logical mappings.

## Runout Workflow

1. Standard filament sensor behavior pauses immediately.
2. `TOOL_FALLBACK_RUNOUT` records whether the extension owns the pause and starts the
   one-second unloaded debounce.
3. If loaded state returns and remains stable for one second, send a transient-recovery
   notification and resume only when the extension owns the pause.
4. On confirmed runout:
   - mark the failed physical tool unloaded, unpurged, and failed;
   - capture its target temperature and fan state where available;
   - turn off its heater;
   - resolve a backup recursively from the failed physical tool's ordered graph;
   - require candidate `loaded=true` and `failed=false`;
   - persist the logical route's new mapping;
   - select the backup through its captured physical handler;
   - apply and wait for the captured target temperature;
   - run `PURGE_TOOL` if the physical backup is unpurged;
   - restore applicable state, notify success, and resume only if extension-owned.
5. Any failure or timeout sends a failure notification and leaves the printer paused.

Recursive resolution is depth-first by configured order. It tracks visited and attempted
tools to prevent loops and duplicate attempts.

## Purge Workflow

`PURGE_TOOL TOOL=Tn` is the only operation that marks a physical tool purged.

- During an active print, selecting an unpurged mapped physical tool automatically invokes
  the configured purge adapter and marks it purged only after successful completion.
- Outside an active print, selection succeeds and reports unpurged status without automatic
  heating or purging.
- Manual extrusion does not change purge state.
- `MARK_TOOL_PURGED` and `MARK_TOOL_UNPURGED` provide narrow manual overrides.

## Manual Routing

- `REMAP_TOOL LOGICAL=T0 PHYSICAL=T2`: persist mapping; if logical T0 is active during a
  print, perform the full pause, temperature-transfer, selection, conditional-purge, resume
  workflow.
- `RESTORE_TOOL TOOL=T0`: map logical T0 back to physical T0 using the same active-print
  workflow when applicable.
- `RESET_TOOL_MAPPINGS`: restore all identity mappings.
- `SET_TOOL_BACKUPS TOOL=T0 BACKUPS=T1,T3,T2`
- `ADD_TOOL_BACKUP TOOL=T0 BACKUP=T4`
- `REMOVE_TOOL_BACKUP TOOL=T0 BACKUP=T3`
- `CLEAR_TOOL_BACKUPS TOOL=T0`
- `SHOW_TOOL_FALLBACK_STATE`

## Notifications

The extension invokes configurable `notify_gcode` only for:

- successful automatic fallback;
- failed automatic fallback;
- automatic recovery from transient runout.

The originating printer adapter uses Moonraker's existing notifier:

```ini
[gcode_macro _TOOL_FALLBACK_NOTIFY]
gcode:
  {action_call_remote_method("notify",
      name="discord",
      message=params.MESSAGE)}
```

Messages include logical route, failed physical tool, selected backup, attempted tools,
and failure reason where relevant.

## Safety Invariants

- Never auto-resume a pause the extension did not initiate.
- Never select an unloaded or runout-failed backup automatically.
- Never mark purged before the dedicated purge operation succeeds.
- Never guess a missing/zero failed-tool target temperature for fallback purging.
- Never recurse indefinitely through backup graphs.
- Never mark a tool failed for selection or mechanical errors.
- Leave the printer paused after every incomplete fallback workflow.
