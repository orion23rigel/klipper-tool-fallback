# Evidence Policy — Trident Representative Live-UAT

## Bounded Scope

These results are bounded to the representative Trident revision
`e7790d022346a62662acfe0b3098ad39eb9eaddc` with active tools `T0` and `T1`.
They are **not** a universal compatibility claim.

## Allowed Evidence Classes

| Class | Description |
|---|---|
| `automated-contract` | Deterministic test output or configuration consistency check |
| `simulated-input/live-output` | Observed printer behavior in response to explicit extension commands (e.g. `TOOL_FALLBACK_RUNOUT`) used as simulated failure inputs; does not prove a physical sensor transition |
| `normal-live-operation` | Observed behavior during controlled, supervised normal hardware operation (e.g. tool selection, purge, guarded resume) |

## Allowed Result States

| State | Credit |
|---|---|
| `PASS` | Creditable — requires observed result, committed evidence excerpt IDs, and verified cleanup |
| `FAIL` | Not creditable — documents an observed failure and cleanup status |
| `BLOCKED` | Not creditable — documents a blocking condition and cleanup status |
| `NOT RUN` | Not creditable — row has not been executed |

Only `PASS` rows are creditable as evidence. `FAIL`, `BLOCKED`, and `NOT RUN`
cannot be converted to automated-contract evidence.

## Limitations

- External media (photos, videos) is supplementary only. Every claim must be
  understandable from committed Markdown without external media.
- A command-simulated runout proves the extension's explicit input path and live
  output, not a physical sensor transition.
- A returned notification adapter call proves an attempt at the Moonraker adapter
  boundary, not downstream Discord delivery.
- A short-timeout guarded-resume scenario proves behavior under that recorded
  temporary configuration only.
- Example-contract tests prove repository consistency, not universal Klipper
  loadability or hardware safety.

## Redaction Legend

Private identifiers and credentials are replaced with stable placeholders:

| Placeholder | Replaces |
|---|---|
| `<TRIDENT_MAIN_MCU>` | Main MCU serial identifier or serial-by-id path |
| `<T0_CAN_UUID>` | T0 toolboard CAN UUID |
| `<T1_CAN_UUID>` | T1 toolboard CAN UUID |
| `<DISCORD_DESTINATION>` | Discord webhook URL or notifier destination |
| `<MOONRAKER_URL>` | Moonraker API endpoint URL |
| `<STATE_PATH>` | Full path to the state persistence file |

## Prohibited Artifacts

Do **not** commit complete raw logs (`klippy.log`, `moonraker.log`), private
configuration files, state files, or command history without human review and
curation. Only committed curated excerpts are permitted.

## Excerpt Format

Each excerpt in `phase6-live-log.md` must include:

- **Excerpt ID** — stable reference such as `EV-UAT-ROUTE-01-A`
- **Timestamp** — when the excerpt was captured
- **Row** — the UAT row ID this excerpt supports
- **Source** — which log or output the excerpt came from
- **Redactions** — which redaction placeholders were applied
- **Ordered commands/events** — the command/event sequence with enough surrounding
  context to audit ordering and outcomes

---

*Evidence policy for Phase 6 representative Trident live-UAT.*
