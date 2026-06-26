# Klipper Tool Fallback — Trident Representative Integration

**Revision:** `e7790d022346a62662acfe0b3098ad39eb9eaddc`
**Active tools:** `T0` and `T1` only. `T2` through `T6` are configured but disabled and remain outside this bundle.
**Scope:** One complete, internally consistent representative integration for the Voron Trident with MadMax toolchanger. This is a starting point requiring adaptation to your specific printer.

---

## 1. Scope and Bounded Compatibility

This bundle is **bounded** to the Trident revision listed above with reciprocal `T0 <-> T1` routing, independent heater/sensor ownership, MadMax physical selection, bucket/silicone purge, and a printer-owned Moonraker Discord notification adapter.

It is **not** a universal compatibility claim. Other toolchangers, different sensor topologies, or non-MadMax physical selection require separate adaptation.

---

## 2. Ownership Table

| Concern | Owner | Representative binding |
|---|---|---|
| Logical routing / fallback | `tool_fallback` extension | `[tool_fallback]` global + `[tool_fallback Tn]` sections |
| Physical tool selection | Trident (MadMax) | `SELECT_TOOL T=0` / `SELECT_TOOL T=1` |
| Filament-state tracking | `tool_fallback` extension | `filament_switch_sensor` hooks delegate to extension |
| Purge / park motion | Trident | `BUCKET_PURGE`, `BUCKET_PARK`, `SILICONE_PARK` |
| Pause / resume | Trident (printer-owned) | `PAUSE` / `RESUME` macros |
| External delivery | Printer / Moonraker | `action_call_remote_method("notify", name="discord", ...)` |
| Sensor fallback ownership | Extension | `TOOL_FALLBACK_RUNOUT` / `TOOL_FALLBACK_INSERT` |

The extension owns logical routing, canonical state, fallback workflow, guarded resume, and runtime backup policy. The Trident owns MadMax `SELECT_TOOL`, liftbar motion, bucket and silicone motion, `PAUSE` / `RESUME`, and the Moonraker notifier destination. Sensor hooks have exactly one fallback owner: the extension.

---

## 3. Representative Assumptions vs. Verify on Your Printer

### Representative assumptions (drawn from the tested Trident)

These values define this example. They are internally consistent with the representative revision but may not match your printer.

| Setting | Value | File |
|---|---|---|
| State persistence path | `~/printer_data/config/tool_fallback_state.json` | `tool_fallback.cfg` |
| T0 heater | `extruder` | `tool_fallback.cfg` |
| T1 heater | `extruder1` | `tool_fallback.cfg` |
| T0 runout sensor | `filament_switch_sensor T0_sensor` | `tool_fallback.cfg` |
| T1 runout sensor | `filament_switch_sensor T1_sensor` | `tool_fallback.cfg` |
| T0 backup | `T1` (reciprocal) | `tool_fallback.cfg` |
| T1 backup | `T0` (reciprocal) | `tool_fallback.cfg` |
| Purge adapter macro | `_TOOL_FALLBACK_TRIDENT_PURGE` | `tool_fallback.cfg` |
| Notify adapter macro | `_TOOL_FALLBACK_TRIDENT_NOTIFY` | `tool_fallback.cfg` |
| Pause on runout | `True` (both sensors) | `sensor_hooks.cfg` |
| Pause owned by extension | `PAUSE_OWNED=1` | `sensor_hooks.cfg` |
| Notification notifier name | `discord` | `tool_fallback_macros.cfg` |

### Verify on your printer (operator-checked values)

These must be verified against your printer before copying.

| Setting | What to verify | File |
|---|---|---|
| `state_path` | Does your printer use this path? | `tool_fallback.cfg` |
| `pause_gcode` / `resume_gcode` | Do these names match your macros? | `tool_fallback.cfg` |
| `selection_timeout` | Default 120s — appropriate for your workflow? | `tool_fallback.cfg` |
| `heating_timeout` | Default 300s — appropriate for your heaters? | `tool_fallback.cfg` |
| `purge_timeout` | Default 180s — appropriate for your purge? | `tool_fallback.cfg` |
| `pause_on_runout: True` | Does your PAUSE macro behave correctly when invoked from a sensor runout context? | `sensor_hooks.cfg` |
| `PAUSE_OWNED=1` | If your PAUSE macro performs real motion (bucket/silicone, position restoration), verify clearances before using this value. | `sensor_hooks.cfg` |
| `BUCKET_PURGE` macro name | Does your Trident use this exact macro name? | `tool_fallback_macros.cfg` |
| Moonraker notifier `name` | Does your Moonraker config define a notifier with this name? | `tool_fallback_macros.cfg` |

---

## 4. Legacy Owner Removal

The Trident's default configuration includes macros that conflict with the extension's ownership. Before installing the bundle, you must remove or rename these legacy owners:

### Legacy macros to remove or rename

| Legacy macro | Why it conflicts | Action |
|---|---|---|
| `REMAP_TOOL` | The extension owns logical remapping. Having a shipped `REMAP_TOOL` creates duplicate routing ownership. | Remove or rename (e.g., `_LEGACY_REMAP_TOOL`) |
| `BACKUP_SPOOL` | The extension owns backup policy. A shipped `BACKUP_SPOOL` creates duplicate backup ownership. | Remove or rename (e.g., `_LEGACY_BACKUP_SPOOL`) |
| `_TOOL_RUNOUT` | The extension owns sensor fallback via `TOOL_FALLBACK_RUNOUT`. A shipped `_TOOL_RUNOUT` creates duplicate runout ownership. | Remove or rename (e.g., `_LEGACY_TOOL_RUNOUT`) |

### Legacy variables to remove from physical handlers

| Variable | Action |
|---|---|
| `variable_tool` | Remove from `T0` / `T1` macro bodies |
| `variable_remapped` | Remove from `T0` / `T1` macro bodies |
| `_TOOL_RUNOUT` variable writes | Remove from `T0` / `T1` macro bodies |

---

## 5. Installation and Include Order

Place the three example files in your Klipper configuration directory and include them in this order:

```ini
# 1. Sensor hooks — must be loaded first so the extension can capture
#    the physical tool handler definitions at klippy:ready.
[include sensor_hooks.cfg]

# 2. Adapter macros — must be loaded before tool_fallback so the
#    extension can resolve the adapter macro names.
[include tool_fallback_macros.cfg]

# 3. Main tool fallback configuration — declares tools, backups, and
#    references the adapter macros.
[include tool_fallback.cfg]
```

### Important

- **Leave disabled T2–T6 untouched.** Do not add `[tool_fallback T2]` through `[tool_fallback T6]` sections. They are configured but disabled on the representative Trident and must remain outside extension ownership.
- **Do not add these files to another printer without adapting.** The adapter macros reference specific printer-owned macro names and Moonraker notifier configurations that are Trident-specific.

---

## 6. Adapter and Sensor-Hook Explanation

### Purge adapter: `_TOOL_FALLBACK_TRIDENT_PURGE`

The extension invokes this macro after a fallback success. It:

1. Validates the `TOOL` argument is a canonical active tool (`T0` or `T1`).
2. Verifies the requested tool is the currently selected physical tool (using `printer['tool_fallback'].selected_physical_tool`).
3. Delegates once to the Trident's bucket purge flow (`BUCKET_PURGE`).

It does **not**:
- Invoke the public `PURGE_TOOL` command (prevents recursion).
- Select or remap tools.
- Mutate fallback state or persistence.
- Own any fallback behavior.

### Notification adapter: `_TOOL_FALLBACK_TRIDENT_NOTIFY`

The extension invokes this macro with fixed canonical fields after a terminal fallback outcome. It:

1. Accepts the canonical fields: `EVENT`, `GENERATION`, `LOGICAL_TOOL`, `FAILED_TOOL`, `SELECTED_TOOL`, `REASON_CODE`, and optional `REASON_DETAIL`.
2. Formats a bounded printer-owned message.
3. Calls the Moonraker `notify` remote method with notifier name `discord`.

It does **not**:
- Contain the destination URL (that lives in `moonraker.conf`).
- Promise downstream delivery (best-effort only).
- Call any extension mutation commands.

### Sensor hooks: `TOOL_FALLBACK_RUNOUT` and `TOOL_FALLBACK_INSERT`

Each active tool's filament sensor invokes:

```ini
runout_gcode:
    TOOL_FALLBACK_RUNOUT TOOL=Tn PAUSE_OWNED=1
insert_gcode:
    TOOL_FALLBACK_INSERT TOOL=Tn
```

`PAUSE_OWNED=1` tells the extension to own the pause. **This is the critical ownership handoff.** Verify that your printer's `PAUSE` macro is safe to invoke from a sensor runout context before copying `PAUSE_OWNED=1`. If your `PAUSE` macro performs real motion (bucket/silicone, position restoration), ensure clearances are verified.

---

## 7. Staged Commissioning Order

Commission in increasing risk. **Do not combine steps.** Stop immediately on unexpected behavior.

### Step 1: Configuration validation (offline)

Restart Klipper with the new files included. Run:

```
SHOW_TOOL_FALLBACK_STATE
```

Verify:
- Schema version is valid.
- `T0` and `T1` appear with correct heaters, sensors, and backups.
- No errors in the Klipper log about missing macros or invalid configuration.

**Stop condition:** Any configuration error. Fix before proceeding.

### Step 2: Physical tool selection (already-commissioned)

Issue `T0` and `T1` commands. Verify:
- Each delegates to `SELECT_TOOL` without error.
- The toolchanger completes its physical selection cycle.
- `SHOW_TOOL_FALLBACK_STATE` reflects the correct `selected_physical_tool`.

**Stop condition:** Unexpected motion, failure to select, or state mismatch.

### Step 3: Notification adapter receipt (no fallback)

Trigger a benign event that produces a notification (e.g., a manual status query that the extension emits). Verify:
- The notification adapter macro is invoked (check Klipper log).
- The Moonraker `notify` remote method is called with the correct notifier name.
- No extension mutation commands are invoked.

**Stop condition:** Unexpected macro invocation, recursion, or extension mutation.

### Step 4: Immediate backup mutation (offline)

Use the extension's backup mutation commands to change a backup policy. Verify:
- The mutation is recorded in the state file.
- The policy affects future resolution only, not current routing.
- No active workflow or transition is affected.

**Stop condition:** Any change to current routing or active workflow.

### Step 5: Sensor-hook command simulation (safe simulated input)

Use `TOOL_FALLBACK_RUNOUT TOOL=T0` as an explicit command (not a physical sensor trigger). Verify:
- The extension receives the command and enters fallback.
- The selected backup tool is resolved correctly.
- The adapter macros are invoked in the correct order.

**Stop condition:** Unexpected tool selection, adapter recursion, or state corruption.

### Step 6: Controlled heater transfer and purge (live)

After a simulated fallback, verify the purge adapter:
- The purge adapter validates the selected tool.
- The purge delegates to `BUCKET_PURGE` without invoking `PURGE_TOOL`.
- No persistence mutation occurs during purge.

**Stop condition:** Purge to wrong location, unexpected heater transfer, or persistence change.

### Step 7: Guarded resume (live)

After a simulated fallback and purge, resume:
- Verify `RESUME` restores the expected state.
- Verify no queued backup mutation is lost.
- Verify mappings and backup policies are restored to canonical state.

**Stop condition:** State corruption, lost mutations, or incorrect routing after resume.

### Step 8: Final cleanup and claim audit

Restore identity mappings, reciprocal backups, and normal sensor enablement. Verify:
- All state is canonical.
- No residual mutation or queue remains.
- No adapter macros are left in an inconsistent state.

---

## 8. Trident-Specific Hazards and Stop Conditions

### Dock / liftbar collision risk

- Verify liftbar clearance before any physical tool selection during commissioning.
- **Stop immediately** on unexpected liftbar motion or dock collision.

### Purge bucket and silicone clearance

- Verify the purge bucket and silicone station are clear before Step 6.
- **Stop immediately** if the purge adapter targets the wrong location.

### Rear-left bed exclusion

- The representative Trident's rear-left bed area may be excluded from safe motion.
- Do not issue tool selection or purge commands that could move tools into this zone.

### Tool-detachment crash detection

- The extension does not own crash detection. If a tool detaches unexpectedly, the physical toolchanger must handle it.
- **Stop immediately** if a tool detachment is suspected.

### Real PAUSE / RESUME motion

- If your `PAUSE` macro performs real motion, ensure clearances are verified before using `PAUSE_OWNED=1`.
- **Stop immediately** on unexpected motion during pause or resume.

### Heating

- Heater transfer during fallback targets the backup tool's heater. Verify the heater assignment is correct.
- **Stop immediately** on unexpected heater targets.

### Purge extrusion

- The purge adapter delegates to `BUCKET_PURGE`. Ensure the bucket is positioned correctly.
- **Stop immediately** if extrusion occurs outside the bucket.

---

## 9. Exact Rollback

To fully rollback the extension bundle:

### Step 1: Remove the includes

Remove these three lines from your main configuration file:

```ini
[include sensor_hooks.cfg]
[include tool_fallback_macros.cfg]
[include tool_fallback.cfg]
```

### Step 2: Restore legacy macros

Restore your previous `REMAP_TOOL`, `BACKUP_SPOOL`, and `_TOOL_RUNOUT` macros from backup. If you renamed them (e.g., `_LEGACY_REMAP_TOOL`), rename them back.

### Step 3: Restore physical handlers

Restore your previous `T0` and `T1` macro bodies that include the legacy `variable_tool`, `variable_remapped`, and `_TOOL_RUNOUT` writes.

### Step 4: Restore sensor hooks

Restore your previous `[filament_switch_sensor T0_sensor]` and `[filament_switch_sensor T1_sensor]` sections with their original `runout_gcode` and `insert_gcode` values.

### Step 5: Restore the state file (optional)

If you backed up `tool_fallback_state.json` before installation, restore it. Otherwise, delete the file — the extension will create a fresh one on next load.

### Step 6: Verify rollback

Restart Klipper and run:

```
SHOW_TOOL_FALLBACK_STATE
```

Verify:
- No errors about missing extension configuration.
- The legacy macros are restored and functional.
- The toolchanger operates as it did before installation.

**Important:** Configuration restart is **not** evidence for any acceptance scenario. It is only a rollback verification step.

---

## 10. Live UAT and Evidence

Live evidence for `EXAMPLE-01` and `UAT-01` is captured in:

- `examples/trident/LIVE-UAT.md` — staged supervised runbook and evidence matrix.
- `examples/trident/evidence/` — evidence policy and curated log excerpts.

All live rows start as `NOT RUN`. Evidence is bounded to the representative Trident and is not a universal compatibility claim.

---

## 11. Explicitly Excluded Phase 1 Scenarios

The following four Phase 1 UAT scenarios are **EXCLUDED — NOT EXECUTED / NOT CREDITED**:

1. **Valid Configuration Startup**
2. **Persisted State Survives Restart**
3. **Invalid State Blocks Startup Clearly**
4. **Read-Only Status Inspection**

Incidental startup, restart, or state display used during setup or observation must not be represented as completion of these scenarios. Configuration restart is not evidence for any excluded scenario.

---

## 12. Known Limitations

- This bundle is revision-bound to Trident revision `e7790d022346a62662acfe0b3098ad39eb9eaddc`. A newer or different Trident revision may require adaptation.
- Only `T0` and `T1` are active. `T2` through `T6` are outside this bundle.
- The example does not execute or credit any of the four excluded Phase 1 UAT scenarios.
- Live evidence is bounded to the representative printer and is not a universal compatibility claim.
- The adapter macros reference Trident-specific macro names and Moonraker notifier configurations. Do not copy to another printer without adaptation.

---

*Revision: e7790d022346a62662acfe0b3098ad39eb9eaddc*
*Active tools: T0, T1*
*Scope: Representative Trident integration bundle — requires adaptation*
