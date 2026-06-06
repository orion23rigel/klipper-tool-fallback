# Requirements: Klipper Tool Fallback

**Defined:** 2026-06-06
**Core Value:** A print can recover automatically from filament runout by selecting a known-loaded backup tool without losing track of routing, purge state, or safety.

## v1 Requirements

### Configuration And Routing

- [x] **ROUTE-01**: User can explicitly configure each managed physical tool with `[tool_fallback Tn]`.
- [ ] **ROUTE-02**: Existing logical `Tn` commands are intercepted and routed through persistent mappings.
- [ ] **ROUTE-03**: Original physical `Tn` handlers remain callable without routing recursion.
- [ ] **ROUTE-04**: User can manually remap, restore, and reset logical tool mappings.
- [ ] **ROUTE-05**: Manual remapping of an active print tool performs the complete safe transition workflow.

### Persistent State

- [x] **STATE-01**: Structured state is persisted using atomic JSON writes.
- [x] **STATE-02**: Loaded, purged, failed, mappings, and ordered backups survive restarts.
- [ ] **STATE-03**: Startup reconciles persisted state with debounced sensor state.
- [ ] **STATE-04**: User can inspect all fallback state through a G-code command.

### Filament Sensors

- [ ] **SENS-01**: Loaded state is derived from explicitly configured filament sensor hooks.
- [ ] **SENS-02**: Insertions and removals require one continuous configurable debounce interval.
- [ ] **SENS-03**: Confirmed unloading clears loaded and purged state.
- [ ] **SENS-04**: Confirmed insertion sets loaded, clears failed, and marks unpurged.

### Purging

- [ ] **PURGE-01**: Dedicated `PURGE_TOOL` marks purged only after successful completion.
- [ ] **PURGE-02**: Manual extrusion never changes purged state.
- [ ] **PURGE-03**: Selecting an unpurged tool during an active print automatically purges it.
- [ ] **PURGE-04**: Selecting an unpurged tool outside an active print reports status without auto-purging.
- [ ] **PURGE-05**: User can explicitly mark a loaded tool purged or unpurged.

### Automatic Fallback

- [ ] **FALL-01**: Standard filament sensor handling pauses immediately on runout.
- [ ] **FALL-02**: Automatic fallback begins only after confirmed debounced runout.
- [ ] **FALL-03**: A transient runout automatically resumes only after confirmed reinsertion and only when extension-owned.
- [ ] **FALL-04**: Backup resolution recursively traverses ordered backup graphs with loop detection.
- [ ] **FALL-05**: Only loaded and non-failed tools are automatically eligible.
- [ ] **FALL-06**: Fallback captures target temperature, turns off the failed heater, selects backup, heats, conditionally purges, persists mapping, and resumes.
- [ ] **FALL-07**: Selection, heating, and purge stages enforce configurable timeouts.
- [ ] **FALL-08**: Any incomplete fallback leaves the printer paused.

### Notifications And Adapters

- [x] **ADAPT-01**: Pause, resume, purge, and notification behavior is configurable without depending on a specific toolchanger.
- [ ] **ADAPT-02**: Success, failure, and transient recovery notifications contain meaningful event context.
- [ ] **ADAPT-03**: Routine state changes do not send external notifications.

### Verification

- [ ] **TEST-01**: Unit tests cover state persistence, migrations, debounce, graph traversal, and command routing.
- [ ] **TEST-02**: Workflow tests cover transient recovery, successful fallback, exhausted backups, stage failures, and manual remapping.
- [ ] **TEST-03**: Example configuration documents integration with standard filament sensors and Moonraker notifier macros.

## v2 Requirements

### Extended Compatibility

- **COMP-01**: Optional adapters for non-`Tn` logical command naming.
- **COMP-02**: Optional material compatibility policies.
- **COMP-03**: Optional fan-state transfer adapters.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Specific toolchanger dependency | Project must remain selection-implementation independent |
| Mechanical tool-presence validation | Owned by physical selection implementation |
| Restarted-print recovery | Klipper restart interrupts cannot resume the original print |
| Purge inference from extrusion | Dedicated purge workflow is the only reliable signal |
| Material matching for backups | Backups are configured before slicer material context and intentionally ignore it |

## Traceability

Traceability will be populated when the roadmap is finalized.

---
*Requirements defined: 2026-06-06*
*Last updated: 2026-06-06 after Phase 1 Plan 02*
