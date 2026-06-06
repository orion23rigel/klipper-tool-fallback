---
phase: "01"
slug: extension-foundation-and-persistence
verified: 2026-06-06T07:37:46-04:00
status: passed
score: 10/10
requirements_verified:
  - ROUTE-01
  - STATE-01
  - STATE-02
  - STATE-04
  - ADAPT-01
gaps: []
human_verification: []
---

# Phase 01: Extension Foundation And Persistence Verification

## Result

**Status:** PASSED

Phase 01 achieved its roadmap goal. The codebase contains a substantive Klipper
extension foundation, strict normalized configuration, schema-versioned canonical
state, configuration reconciliation, failure-safe atomic JSON persistence, ready-time
lifecycle integration, and deterministic read-only status surfaces.

The implementation also respects the phase boundary: command interception, sensor
debounce, purge execution, and automatic fallback are not implemented prematurely.

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every managed physical tool is explicitly declared by a `[tool_fallback Tn]` section. | VERIFIED | `load_config_prefix()` parses and registers prefixed tool sections; canonical names and required sensor/heater values are enforced in `tool_fallback_config.py:73-90`. |
| 2 | Invalid tool identities, backup references, and adapter configuration prevent startup. | VERIFIED | Configuration parsing/finalization rejects malformed names, duplicate tools/backups, self/unknown backups, empty adapters, and non-positive timing values; covered by `tests/test_tool_fallback_config.py`. |
| 3 | Core configuration logic is testable without a running Klipper process. | VERIFIED | Pure configuration module plus focused fakes exercise all configuration contracts in the passing test suite. |
| 4 | Loaded, purged, failed, mappings, and ordered backups round-trip through schema version 1. | VERIFIED | `FallbackState.from_dict()` and `to_dict()` preserve every field and backup order in `tool_fallback_state.py:41-107`; round-trip tests pass. |
| 5 | Malformed or unsupported persisted state never silently resets operator state. | VERIFIED | Strict schema/type/reference validation raises errors, and malformed/unsupported-file preservation tests pass. |
| 6 | State writes use same-directory temporary files, file fsync, atomic replacement, and parent-directory fsync. | VERIFIED | Atomic write sequence is implemented in `tool_fallback_state.py:169-192` and ordering/failure cleanup tests pass. |
| 7 | Configured tool additions and removals reconcile to valid canonical state. | VERIFIED | `FallbackState.reconcile()` adds defaults, removes stale records/references, and resets stale targets in `tool_fallback_state.py:109-131`; reconciliation tests pass. |
| 8 | The extension loads, validates, reconciles, and persists only after all configured tools are known. | VERIFIED | Exactly one `klippy:ready` handler finalizes configuration before state load/reconcile/save in `tool_fallback.py:18-19,53-67`; lifecycle tests pass. |
| 9 | Persistence and validation failures become actionable Klipper configuration errors. | VERIFIED | JSON, schema, and filesystem errors are translated with the configured state path in `tool_fallback.py:60-72`; integration failure tests pass. |
| 10 | Users can inspect deterministic complete fallback state without mutating it. | VERIFIED | `get_status()` and `SHOW_TOOL_FALLBACK_STATE` share the canonical snapshot in `tool_fallback.py:41-51`; tests prove deterministic pre/post-ready output and reject status-triggered writes. |

## Requirement Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| ROUTE-01 | SATISFIED | Explicit canonical `[tool_fallback Tn]` parsing, registration, finalization, and validation are implemented and tested. |
| STATE-01 | SATISFIED | StateStore uses deterministic JSON, same-directory temporary files, fsync-before-replace, atomic `os.replace`, parent fsync, and cleanup on failure. |
| STATE-02 | SATISFIED | Schema v1 persists loaded, purged, failed, mappings, and ordered backups; round-trip and restart-oriented lifecycle tests pass. |
| STATE-04 | SATISFIED | G-code and Klipper status APIs expose complete canonical state read-only. |
| ADAPT-01 | SATISFIED | Pause, resume, purge, and notification adapter names are normalized configurable data with no specific toolchanger dependency. Their execution is intentionally deferred to later workflow phases. |

No orphaned Phase 01 requirements were found.

## Wiring And Boundary Checks

- `load_config_prefix()` loads the global object and registers normalized tools.
- `klippy:ready` finalizes all tools before constructing, loading, reconciling, and
  saving the state store.
- State is published only after load/reconciliation/persistence succeeds.
- Both status interfaces read the same canonical in-memory state.
- The only registered G-code command is `SHOW_TOOL_FALLBACK_STATE`.
- No `Tn` command capture/replacement, sensor lookup/debounce, purge invocation,
  heating, pause/resume workflow, backup traversal, or automatic fallback exists.

## Automated Verification

| Command | Result |
|---------|--------|
| `pytest -q` | PASS: 65 passed |
| `python3 -m py_compile klippy/extras/tool_fallback*.py` | PASS |
| `git diff --check` | PASS |
| Anti-pattern scan for `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, and placeholders | PASS: no product-code debt markers |
| Later-phase behavior scan | PASS: no premature routing, sensor, purge, or fallback implementation |

The `gsd-sdk verify.artifacts` and `verify.key-links` helpers could not parse the plans'
string-form must-have entries, so artifact substance and wiring were verified manually
against the code and tests.

## Security And Residual Risk

Verified controls:

- Untrusted persisted JSON is strictly type-, field-, name-, and reference-validated
  before publication.
- Invalid or unsupported state blocks startup instead of silently resetting state.
- Atomic replacement preserves the prior file on pre-replace and replace failures.
- Status renders only validated in-memory state and does not read arbitrary file content
  or invoke persistence.
- Configured adapter names remain data and are not executed in Phase 01.

Residual risks:

- Tests use focused Klipper fakes; compatibility with a representative live Klipper
  installation remains intentionally deferred to Phase 05.
- `state_path` is trusted administrator configuration and can designate any path the
  Klipper process may write. This is consistent with the design but should remain
  documented as later installation guidance expands.
- Parent-directory fsync may be unsupported on some filesystems; the implementation
  tolerates only recognized unsupported-operation errors.

No material high-severity threat remains within the Phase 01 scope.

## Human Verification

None required for Phase 01. Real-printer integration is explicitly scheduled for Phase
05 after routing and sensor behavior exist.
