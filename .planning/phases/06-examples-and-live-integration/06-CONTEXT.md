# Phase 6: Examples And Live Integration - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Provide one internally consistent representative integration bundle and adaptation guide
for the user's Trident, then record supervised, staged, reversible, simulation-only live
evidence for the bounded v1.1 operational scenarios. Evidence remains specific to the
tested printer and does not execute or credit the four explicitly excluded Phase 1 UAT
scenarios.

</domain>

<decisions>
## Implementation Decisions

### Representative Printer Baseline
- **D-01:** Use the user's actual Trident configuration from
  `orion23rigel/Laurion3D_Trident` as the representative printer baseline.
- **D-02:** Bind planning and evidence to Trident revision
  `e7790d022346a62662acfe0b3098ad39eb9eaddc` unless a newer revision is explicitly
  recorded when live evidence is captured.
- **D-03:** Scope the representative integration to the currently enabled `T0` and `T1`
  tools. Treat configured but disabled `T2` through `T6` as out of the representative
  topology.
- **D-04:** Use reciprocal ordered backup routing: `T0 -> T1` and `T1 -> T0`.
- **D-05:** Model each active tool as independently owning its extruder, heater, probe,
  CAN toolboard, and `Tn_sensor` runout sensor.
- **D-06:** Integrate with the Trident's MadMax toolchanger, liftbar, bucket/silicone
  purge flow, and printer-owned Moonraker Discord notification adapter.

### Example Packaging
- **D-07:** Deliver one complete, internally consistent Trident integration bundle plus
  an adaptation guide.
- **D-08:** The bundle must cover installation, rollback, adapters, hooks, ownership
  assumptions, commissioning order, and Trident-specific hazards.
- **D-09:** Keep representative values internally consistent, but redact or replace
  machine-specific identifiers such as MCU serials and private delivery details.
- **D-10:** Clearly distinguish copied/adapted Trident assumptions from values every
  operator must verify on their own printer.

### Live UAT Safety Boundary
- **D-11:** Use controlled simulation only for runout and failure scenarios.
- **D-12:** Do not physically trigger filament runout, detach tools, inject destructive
  hardware faults, or intentionally provoke collisions.
- **D-13:** Every procedure remains supervised, staged, reversible, and stops immediately
  on unexpected motion, heating, tool state, or notification behavior.
- **D-14:** Cover routing, sensor, heater, purge, fallback, guarded-resume, notification,
  and backup-mutation behavior only through safe simulated inputs and observable
  representative-printer behavior.

### Evidence Capture
- **D-15:** Commit a Markdown evidence matrix containing the tested topology, exact
  relevant revisions, procedure, expected result, observed result, and evidence for each
  claim.
- **D-16:** Include concise committed log excerpts sufficient to audit each claim.
- **D-17:** Optional photos or videos may be linked externally, but external media is
  supplementary and must not be required to understand the committed evidence.
- **D-18:** Explicitly state that evidence is bounded to this representative Trident and
  is not a universal compatibility claim.
- **D-19:** Explicitly name the four excluded Phase 1 UAT scenarios and neither execute
  nor credit them:
  `Valid Configuration Startup`, `Persisted State Survives Restart`,
  `Invalid State Blocks Startup Clearly`, and `Read-Only Status Inspection`.

### the agent's Discretion
- Choose the bundle's exact file split and adaptation-guide structure while preserving
  one complete, internally consistent reference configuration.
- Choose safe simulation mechanisms and evidence-matrix row grouping, provided they
  cannot initiate destructive hardware fault injection and satisfy D-11 through D-19.
- Choose log excerpt length and redaction format while retaining enough information to
  audit the claim.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone Contract
- `.planning/ROADMAP.md` — Phase 6 goal, success criteria, phase boundary, and sequencing.
- `.planning/REQUIREMENTS.md` — `EXAMPLE-01`, `UAT-01`, explicit exclusions, and
  representative-hardware evidence boundary.
- `.planning/phases/05-notifications-integration-and-verification/05-CONTEXT.md` —
  notification payload, final-outcome timing, queued backup mutation, and command
  feedback decisions that the example and evidence must preserve.
- `.planning/phases/05-notifications-integration-and-verification/05-VERIFICATION.md` —
  verified Phase 5 runtime contracts and deterministic evidence baseline.

### Runtime And Existing Documentation
- `README.md` — current installation, configuration, sensor-hook, adapter, and command
  documentation to extend or reference.
- `klippy/extras/tool_fallback.py` — live commands, workflow boundaries, notifications,
  guarded resume, and backup mutation behavior exercised by the representative evidence.
- `klippy/extras/tool_fallback_config.py` — configuration and adapter contract used by
  the representative bundle.
- `klippy/extras/tool_fallback_state.py` — persisted routing and backup-policy state
  behavior relevant to evidence claims.

### Representative Printer
- `https://github.com/orion23rigel/Laurion3D_Trident/tree/e7790d022346a62662acfe0b3098ad39eb9eaddc`
  — exact representative Trident configuration revision.
- `klipper-toolchanger/includes.cfg` in the representative repository — enabled `T0` and
  `T1` topology and disabled `T2` through `T6`.
- `klipper-toolchanger/toolchanger.cfg` and `klipper-toolchanger/tool_0.cfg` through
  `tool_1.cfg` in the representative repository — MadMax paths, liftbar integration,
  tool ownership, sensors, heaters, probes, and dock coordinates.
- `brush_bucket.cfg` and `macros.cfg` in the representative repository — purge,
  silicone-park, notification, and printer-specific safety behavior.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `README.md` configuration example: starting point for the complete Trident integration
  bundle and adaptation guidance.
- Phase 6 will establish the repository's first dedicated representative integration
  example surface; no existing local `examples/` directory constrains its layout.
- Existing deterministic tests and Phase 5 verification report: define expected runtime
  contracts before representative live evidence is credited.

### Established Patterns
- Sensor hooks invoke `TOOL_FALLBACK_RUNOUT TOOL=Tn PAUSE_OWNED=1`; the representative
  integration must adapt the Trident's existing `_TOOL_RUNOUT` hook without creating two
  owners for runout recovery.
- Purge and notification behavior remain printer-owned adapters. The extension invokes
  them but does not own bucket motion or external delivery.
- Runtime backup mutations preserve ordered policies, affect future resolution only, and
  queue during active workflows or transitions.

### Integration Points
- Add a complete Trident reference bundle under the repository's example/documentation
  surface and link it from `README.md`.
- Adapt `T0_sensor` and `T1_sensor`, `BUCKET_PURGE`/`BUCKET_PARK`/`SILICONE_PARK`, tool
  selection, pause/resume, and Moonraker Discord notification behavior.
- Record representative evidence in committed Markdown suitable for Phase 7 release
  verification and example-contract checks.

</code_context>

<specifics>
## Specific Ideas

- Representative topology: Voron Trident, MadMax toolchanger, liftbar, active `T0` and
  `T1`, reciprocal fallback routes, per-tool runout sensors, independent heaters, and
  bucket/silicone purge.
- Principal hazards to document: dock/liftbar collision risk, purge-bucket and silicone
  clearance, rear-left bed exclusion, tool-detachment crash detection, and unexpected
  motion during commissioning.
- External notifications use the printer-owned Moonraker `notify` remote method with the
  Trident's Discord destination; the example must not expose destination secrets.

</specifics>

<deferred>
## Deferred Ideas

- Physical runout and physical/destructive tool-failure testing are excluded from this
  phase's live evidence.
- The four Phase 1 UAT scenarios remain explicitly excluded:
  `Valid Configuration Startup`, `Persisted State Survives Restart`,
  `Invalid State Blocks Startup Clearly`, and `Read-Only Status Inspection`.

</deferred>

---

*Phase: 06-examples-and-live-integration*
*Context gathered: 2026-06-12*
