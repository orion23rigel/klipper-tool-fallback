# Stack Research: v1.1 Integration & Operations

**Researched:** 2026-06-11
**Scope:** New v1.1 capabilities only
**Recommendation:** Extend the existing dependency-free Klipper extension, pytest fake
suite, Markdown/config examples, and GitHub repository automation. Do not introduce a
new runtime service, Python package framework, or notification client.

## Executive Recommendation

v1.1 needs operational surfaces, not a new technology stack:

| Capability | Recommended stack change |
|---|---|
| External notifications | Invoke the existing configurable `notify_gcode` through Klipper's existing `gcode.run_script_from_command()` adapter boundary. Supply deterministic event parameters to an operator-owned G-Code macro, which may call Moonraker's registered `notify` remote method. |
| Runtime backup mutation | Add immutable `FallbackState` candidate methods and public G-Code commands that reuse schema v1, `StateStore.save()`, canonical tool validation, and workflow guards. |
| Live-printer UAT | Add a manual, evidence-oriented UAT runbook plus representative Klipper/Moonraker configuration examples. Use normal printer console commands, `SHOW_TOOL_FALLBACK_STATE`, status objects, and logs. |
| CI | Add one GitHub Actions workflow using `actions/checkout`, `actions/setup-python`, direct `pytest`, and stdlib `py_compile`. |
| Release verification | Add a documented/tag-gated verification checklist that reruns CI, validates import/compile and expected distributable files, and creates a GitHub release from a verified semantic-version tag. |

The production extension should remain Python-stdlib-only. The only test dependency
remains `pytest`.

## Existing Stack To Preserve

### Runtime

- Klipper Python extension modules in `klippy/extras/`.
- Klipper object lookup, event handlers, reactor timers, G-Code registration, and
  `gcode.run_script_from_command()` for operator-owned adapters.
- Python stdlib dataclasses, immutable replacement via `dataclasses.replace`, JSON,
  filesystem primitives, and `MappingProxyType`.
- Schema-v1 atomic JSON persistence in `tool_fallback_state.StateStore`.

### Verification

- Focused pytest tests using the existing fake printer, G-Code dispatcher, reactor,
  sensors, heaters, and print state.
- Direct configuration examples and Markdown documentation.
- Git tags and GitHub Releases; v1.0.0 establishes the existing release convention.

These choices already cover every v1.1 requirement. New dependencies would mostly
duplicate working boundaries or make deployment onto Klipper hosts harder.

## External Notification Adapter

### Recommended integration

Keep `notify_gcode` as an operator-owned G-Code adapter. Add one private helper in
`klippy/extras/tool_fallback.py`, conceptually:

```python
_notify(event, logical_tool=None, failed_tool=None, selected_tool=None,
        attempted=(), reason=None)
```

The helper should:

1. Build a deterministic, human-readable message and a small fixed event vocabulary.
2. Append adapter parameters to `self.config.global_config.notify_gcode`.
3. Invoke it synchronously through `self.gcode.run_script_from_command()`.
4. Catch adapter failures, report them locally with `respond_info`, and never replace
   the primary workflow outcome with a notification failure.

Recommended event names:

- `FALLBACK_SUCCESS`
- `FALLBACK_FAILURE`
- `TRANSIENT_RECOVERY`

Recommended adapter parameters:

- `EVENT`
- `MESSAGE` as the final parameter
- optionally stable machine-friendly fields such as `LOGICAL`, `FAILED`, and `SELECTED`

Keep values single-line and sanitize values that originate in exception text before
building G-Code. Do not interpolate arbitrary JSON or execute notification text as
G-Code.

### Exact code integration points

- `_complete_transient_runout()`: notify after the transient is confirmed and before
  the optional owned resume attempt. Report a resume failure separately as local
  workflow failure; do not send a false recovery success after resume fails if the
  requirement defines recovery as resumed operation.
- `_on_confirmed_runout()`: notify success only after selection, heating, purge, and
  mapping persistence have completed. The notification may occur immediately before
  owned resume so a resume-adapter failure can still produce a failure event.
- `_block_workflow()`: centralize terminal failure notification here, but suppress
  duplicates when the same blocked checkpoint is re-published or retried.
- `_handle_guarded_resume()`: notify eventual success or failure for a workflow that
  continued after `heating_timeout`.
- `tests/conftest.py::FakeGCode`: the existing `script_events` and injectable failures
  already provide the right test surface; extend assertions rather than add a mock HTTP
  client.

### Operator adapter example

Use a Klipper macro to bridge into Moonraker:

```ini
[gcode_macro _TOOL_FALLBACK_NOTIFY]
gcode:
  {action_call_remote_method(
      "notify",
      name="tool_fallback",
      message=params.MESSAGE)}
```

Moonraker owns notifier credentials, destinations, templates, and network delivery.
Klipper officially exposes `action_call_remote_method()`, and Moonraker documents
calling its `notify` method from a Klipper G-Code macro.

### Failure policy

Notifications are observability, not a safety authority:

- Never block fallback progress, persistence, pausing, or resume solely because a
  notifier is unavailable.
- Never retry network delivery inside the extension.
- Never persist notification delivery state in schema v1.
- Always retain local `respond_info` diagnostics.

## Runtime Backup-List Mutation

### Recommended command surface

Use replace/restore semantics rather than incremental graph editing:

```text
SET_TOOL_BACKUPS TOOL=T0 BACKUPS=T2,T1
RESTORE_TOOL_BACKUPS TOOL=T0
RESET_TOOL_BACKUPS
```

- `SET_TOOL_BACKUPS` atomically replaces one ordered list; an empty `BACKUPS` value
  clears it.
- `RESTORE_TOOL_BACKUPS` restores one tool's configured startup list.
- `RESET_TOOL_BACKUPS` restores every configured startup list in one persisted
  transaction.

This matches the existing `REMAP_TOOL` / `RESTORE_TOOL` / `RESET_TOOL_MAPPINGS`
command family and avoids ambiguous ordering and partial outcomes from separate
add/remove commands.

### Exact code integration points

- `tool_fallback_state.FallbackState`: add pure `with_backups(tool, backups)`,
  `with_configured_backups(tool, configured_tools)`, and
  `with_all_configured_backups(configured_tools)` candidate helpers, or equivalent
  narrowly named methods.
- Reuse `_canonical()`, `ToolState`, `StateValidationError`, and exact no-op identity
  behavior.
- `ToolFallback.__init__()`: register the three public commands.
- `ToolFallback`: parse comma-separated canonical names, then validate against
  `self.config.tools`; reject self-reference, duplicates, and unknown tools.
- Reuse `_guard_workflow_operation()` so a backup graph cannot change during
  debouncing, resolution, fallback, blocked recovery, or guarded resume.
- Persist through `_persist_state()` and publish only after `StateStore.save()`
  succeeds.
- `SHOW_TOOL_FALLBACK_STATE` already exposes the resulting ordered lists; no new status
  object is needed.

Schema version 1 already defines `backups` as durable ordered state and gives persisted
lists precedence over configuration during reconciliation. Runtime mutation therefore
does **not** require a schema migration.

### Mutation safety policy

- Allow a policy-only backup-list replacement while no fallback workflow is active,
  including during an ordinary print, because it performs no hardware movement.
- Reject mutation while any workflow checkpoint exists. Mutating a graph during a
  blocked workflow would make status and guarded continuation disagree about policy.
- Validate the complete replacement before persistence; never apply a partial list.
- Configuration remains the reset/default source, while persisted state remains the
  live source used by `resolve_backup_graph()`.

## Live-Printer UAT And Integration Examples

### Recommended artifacts

Add documentation/config artifacts, not a hardware-test framework:

- A live-printer UAT runbook with prerequisites, explicit safety setup, commands,
  expected state snapshots, expected logs, and pass/fail evidence fields.
- A minimal shared example for the extension, filament sensor hooks, purge adapter, and
  notification adapter.
- Representative printer-specific examples for the actual validated hardware
  architectures. Prefer examples such as independent dual extruders and a
  macro-selected toolchanger only after each is exercised on that architecture.
- A release verification record linking the printer model/config revision, Klipper
  revision, Moonraker revision, extension tag/commit, and UAT results.

### UAT stack

Use native operational interfaces:

- Klipper console/G-Code commands for setup and fault injection.
- `SHOW_TOOL_FALLBACK_STATE` and `printer.tool_fallback` for state evidence.
- `klippy.log` and Moonraker logs for adapter and failure evidence.
- Existing printer macros for physical selection, pause/resume, purge, and
  notifications.

The runbook should cover routing, sensor insertion/runout and authority loss, purge
state, fallback success, backup exhaustion/failure, transient recovery, guarded resume,
runtime backup mutation, notification delivery, restart persistence, and restoration
to a known-safe configuration.

Examples must clearly mark printer-specific names and movement macros as placeholders
unless they were validated on that exact printer. They should not imply that copying a
tool-change or purge motion sequence is mechanically safe across printers.

## CI And Release Verification

### GitHub Actions

Add `.github/workflows/ci.yml` for pushes and pull requests:

1. Check out the repository.
2. Set up an explicit Python matrix.
3. Install only `pytest`.
4. Run stdlib compilation/import checks.
5. Run `pytest`.

Recommended initial matrix: Python 3.9, 3.11, and 3.13 on `ubuntu-latest`. This samples
common Raspberry Pi OS generations and a forward-compatibility interpreter without
multiplying low-value jobs. The project should document this as its tested matrix, not
claim support for every Python version.

Representative checks:

```text
python -m py_compile klippy/extras/tool_fallback.py \
  klippy/extras/tool_fallback_config.py \
  klippy/extras/tool_fallback_state.py
pytest
```

Keep CI deterministic and hardware-free. Live-printer UAT is a separate release gate,
not a GitHub-hosted runner job.

### Release gate

For `v1.1.0` and later:

- Require a clean tagged commit whose CI passed.
- Re-run the exact local verification commands documented for contributors.
- Verify the three extension modules and supported examples/docs are present.
- Verify installation instructions and configuration defaults match code.
- Record completed representative live-printer UAT.
- Create the GitHub Release from the version tag and include concise upgrade notes,
  especially the new commands and notification adapter contract.

Do not publish a wheel: this project is installed as Klipper `klippy/extras` modules,
not imported as a general Python package.

## What Not To Add

| Do not add | Reason |
|---|---|
| `requests`, `httpx`, MQTT clients, Discord/Telegram SDKs, or direct Moonraker HTTP calls | Duplicates Moonraker notifier support, introduces credentials/network policy into Klipper, and makes notification failures capable of destabilizing the extension. |
| A notification queue, delivery database, or schema-v1 notification fields | Delivery is owned by the external adapter; persisted delivery state does not improve fallback safety. |
| A new backup graph store or schema version | Ordered backups are already canonical durable schema-v1 state. |
| Incremental `ADD_BACKUP` / `REMOVE_BACKUP` commands initially | Replace semantics are easier to validate atomically and preserve deterministic order. |
| Runtime changes to configured tool identities, sensors, heaters, or physical handlers | These objects are resolved transactionally at `klippy:ready`; changing them live would invalidate captured handlers and safety assumptions. |
| A generic plugin/event bus abstraction | There is one external adapter and existing Klipper G-Code adapter patterns already cover it. |
| `tox`, `nox`, Poetry, Hatch, setuptools packaging, Docker, or a custom test runner | The repository has three stdlib runtime modules and a direct pytest suite; these tools add maintenance without improving the requested verification. |
| Hardware simulation in CI presented as live UAT | Existing fakes cover deterministic logic; only a real printer validates wiring, macros, motion, heater behavior, and notification delivery. |
| Automatic release publishing before live UAT evidence exists | v1.1 explicitly includes representative hardware verification as a release gate. |
| Unvalidated brand/printer config snippets | Tool-change and purge macros can move or heat hardware; examples must be scoped to validated architectures and clearly identify operator-owned motion. |

## Primary Sources

- Klipper command templates and `action_call_remote_method()`:
  <https://www.klipper3d.org/Command_Templates.html#actions>
- Moonraker notifier configuration and notifying from Klipper:
  <https://moonraker.readthedocs.io/en/latest/configuration/#notifier>
- GitHub Actions Python build/test guidance:
  <https://docs.github.com/en/actions/tutorials/build-and-test-code/python>
- GitHub Releases and tag-based release workflow:
  <https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository>

## Planning Implications

The implementation can remain one phase if plans are split by responsibility:

1. Notification helper, event placement, failure policy, and pytest coverage.
2. Immutable backup mutation candidates, commands, validation, persistence, and tests.
3. Integration examples and live-printer UAT execution/evidence.
4. CI workflow, release checklist, and final release verification.

The first two are code changes inside existing boundaries. The latter two are
operational deliverables and should not be used to justify new runtime dependencies.
