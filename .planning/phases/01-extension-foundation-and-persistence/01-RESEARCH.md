# Phase 1: Extension Foundation And Persistence - Research

**Researched:** 2026-06-06
**Status:** Complete

## Phase Boundary

Phase 1 establishes the independently testable core of the extension:

- Klipper-facing global and `[tool_fallback Tn]` configuration loading
- immutable normalized tool configuration
- versioned in-memory state and reconciliation against configured tools
- atomic JSON persistence
- a read-only status surface through `get_status()` and
  `SHOW_TOOL_FALLBACK_STATE`

Command interception, sensor debounce, purge behavior, and fallback workflows remain in
later phases. Phase 1 should expose interfaces they can call without implementing them.

## Klipper Integration Findings

### Extension loading and configuration

- Klipper discovers `klippy/extras/tool_fallback.py` by section name.
- `load_config(config)` constructs the global `[tool_fallback]` object.
- `load_config_prefix(config)` constructs each `[tool_fallback Tn]` section.
- Prefix instances should register themselves with the global object obtained through
  `printer.load_object(config, "tool_fallback")`.
- `config.get_name().split()[1]` is the established way to obtain the suffix from a
  prefixed section.
- All supported options must be read through the config helper. Klipper's config
  validator then rejects misspelled or unsupported options automatically.
- Invalid tool names, duplicate logical identities, unknown backup references, self
  backups, and invalid numeric ranges should raise `config.error(...)` during startup.

### Lifecycle and status

- Store `printer`, `reactor`, and `gcode` references from the config/printer helpers.
- Register `klippy:ready` for work that requires all prefixed sections to have loaded.
- Expose a JSON-serializable `get_status(eventtime)` dictionary for
  `printer.tool_fallback`.
- Register `SHOW_TOOL_FALLBACK_STATE` during global object construction. The command is
  read-only and should render deterministic JSON through `gcmd.respond_info`.
- Phase 1's ready handler finalizes configuration, loads/reconciles state, and persists
  any deterministic initialization changes. It must not perform blocking loops or sleep.

### Future command interception contract

Klipper's `gcode.register_command(command, None)` unregisters a command and returns its
previous ready-state handler. Re-registering the same command with the extension handler
then enables interception while retaining the physical handler. Phase 1 should define
normalized tool identities and ownership boundaries that Phase 2 can use, but should not
capture `Tn` handlers yet.

## State And Persistence Design

### Schema version 1

Use a canonical state model with no transient workflow fields:

```json
{
  "version": 1,
  "tools": {
    "T0": {
      "loaded": false,
      "purged": false,
      "failed": false,
      "backups": ["T1"]
    }
  },
  "mappings": {
    "T0": "T0"
  }
}
```

The store owns serialization and filesystem behavior. A separate state model owns
validation, normalization, and configuration reconciliation.

### Reconciliation decisions

- Missing state file: initialize canonical state from configured tools and persist it.
- Existing valid v1 state: normalize and preserve user-managed backup order.
- Newly configured tool: add default flags, configured backups, and identity mapping.
- Removed configured tool: remove its tool record, remove its logical mapping, reset any
  remaining mapping targeting it to identity, and remove it from backup lists.
- Configuration backups initialize only a new tool or a missing backups field; they do
  not overwrite an existing persisted backups list.
- Mapping targets and backup entries must always reference currently configured tools.
- Unknown or future schema version: fail startup with an actionable configuration error.
- Malformed JSON, invalid types, or invalid invariants: fail startup with an actionable
  configuration error. Never silently discard recoverable operator state.

### Atomic write contract

Write compact deterministic JSON to a temporary file in the destination directory,
flush and `fsync` the file, apply `os.replace` to the destination, then `fsync` the
parent directory where supported. Clean up a leftover temporary file after failed writes.
Create the parent directory only when explicitly absent and report failures as Klipper
command/configuration errors at the integration boundary.

Persist only when the normalized state differs from the loaded state. Keep serialization
and atomic replacement injectable enough for failure-path unit tests.

## Recommended Project Structure

```text
klippy/extras/tool_fallback.py          # Klipper adapter and status command
klippy/extras/tool_fallback_config.py   # normalized config/tool definitions
klippy/extras/tool_fallback_state.py    # schema, reconciliation, atomic store
tests/conftest.py                       # lightweight Klipper config/gcode fakes
tests/test_tool_fallback_config.py
tests/test_tool_fallback_state.py
tests/test_tool_fallback_extension.py
```

Keep pure state/config logic independent of a running Klipper process. The adapter should
translate pure exceptions into `config.error` or `gcmd.error`.

## Error Policy

| Condition | Behavior |
|-----------|----------|
| Invalid or incomplete extension configuration | Fail Klipper configuration |
| Unknown backup or self-backup | Fail Klipper configuration |
| Missing state file | Initialize and persist canonical state |
| Malformed/unsupported/invalid persisted state | Fail Klipper configuration |
| Atomic write failure during startup | Fail Klipper configuration |
| Status serialization/rendering failure | Raise command error; do not mutate state |

Warnings are not appropriate for invariant violations because later routing and fallback
behavior depends on trustworthy state.

## Validation Architecture

### Test approach

Use `pytest` with lightweight fakes for `printer`, `config`, `gcode`, and `gcmd`.
Pure state and persistence tests should use `tmp_path` and avoid importing the full
Klipper runtime. Extension integration tests should verify the adapter calls and error
translation against fakes.

### Fast feedback commands

```bash
python3 -m py_compile klippy/extras/tool_fallback*.py
pytest -q tests/test_tool_fallback_state.py
pytest -q tests/test_tool_fallback_config.py tests/test_tool_fallback_extension.py
pytest -q
```

### Required coverage

- valid global/prefixed configuration normalization
- invalid names, duplicate tools, self/unknown backups, and bad ranges
- missing-file initialization and deterministic serialization
- valid-state round trip
- malformed JSON, unsupported version, invalid type/invariant failures
- additions/removals/stale mappings/stale backup reconciliation
- atomic write ordering and replacement failure behavior
- `get_status()` and deterministic `SHOW_TOOL_FALLBACK_STATE` output
- ready-handler load/reconcile/persist integration and error translation

## Planning Risks

- Klipper objects are loaded in section order. Final cross-tool validation must happen at
  `klippy:ready`, after all prefixed sections are registered.
- Directly coupling the state model to Klipper error classes would make failure paths
  harder to test and reuse in later phases.
- Silently resetting malformed state would violate the project's safety premise.
- Phase 1 must avoid implementing command interception early; doing so would entangle
  persistence work with Phase 2 lifecycle behavior.

## Sources

- Klipper `klippy/configfile.py`: config helper and unused-option validation patterns
- Klipper `klippy/gcode.py`: command registration, unregistration, and response behavior
- Klipper `klippy/extras/delayed_gcode.py`: prefixed config and ready/timer patterns
- Klipper `klippy/extras/save_variables.py`: startup persistence error translation and
  status exposure pattern
- Klipper `klippy/extras/exclude_object.py`: extension lifecycle and status patterns

## Validation Architecture

Nyquist coverage is defined by the required coverage and fast feedback commands above.
Every plan task must include a narrow automated verification command, and final phase
verification must run the complete pytest suite.

