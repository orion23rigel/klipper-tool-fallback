---
phase: 06
slug: examples-and-live-integration
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-12
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest plus supervised representative-printer runbook |
| **Config file** | existing repository pytest setup |
| **Quick run command** | `pytest -q tests/test_examples.py` |
| **Full suite command** | `python3 -m py_compile klippy/extras/tool_fallback*.py && pytest -q && git diff --check` |
| **Estimated runtime** | automated checks under one minute; live rows operator-paced |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q tests/test_examples.py` when the file
  exists; before Wave 0 creates it, run `pytest -q`.
- **After every plan wave:** Run
  `pytest -q tests/test_examples.py tests/test_tool_fallback_config.py tests/test_tool_fallback_notifications.py`.
- **Before `$gsd-verify-work`:** Full suite must be green and every credited live row
  must contain observed results, evidence, and cleanup.
- **Max automated feedback latency:** 60 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | EXAMPLE-01 | T-06-01 | Example omits private identifiers and has one fallback owner | contract | `pytest -q tests/test_examples.py -k "bundle or redaction or ownership"` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | EXAMPLE-01 | T-06-02 | Installation, rollback, commissioning, and hazards are explicit | contract | `pytest -q tests/test_examples.py -k "documentation or rollback or hazards"` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | EXAMPLE-01, UAT-01 | T-06-01 | Contract tests reject secrets, recursion, legacy owners, and scope overclaims | contract | `pytest -q tests/test_examples.py` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | UAT-01 | T-06-03 | Runbook requires staged simulation, stop conditions, cleanup, evidence, and exclusions | contract | `pytest -q tests/test_examples.py -k "uat or evidence or exclusion"` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 3 | UAT-01 | T-06-04 | Live evidence remains bounded, redacted, and honestly classified | contract + manual | `pytest -q tests/test_examples.py -k "evidence or redaction"` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 3 | UAT-01 | T-06-05 | No live row passes without observed result, evidence, and cleanup | manual | `n/a - supervised representative-printer gate` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Threat Model

| Ref | Threat | Required Control |
|-----|--------|------------------|
| T-06-01 | Private credentials or machine identifiers leak from the representative repository or logs | Ship redacted example values, deterministic secret-pattern checks, and mandatory final human diff review |
| T-06-02 | Two fallback owners or copied machine values create unsafe or inconsistent operation | Document complete legacy-owner removal, exact rollback, and operator-verified values |
| T-06-03 | Runbook instructions provoke collision, unexpected heating, or destructive fault injection | Simulation-only inputs, staged increasing-risk order, explicit preflight/stop/cleanup for every row |
| T-06-04 | Evidence overstates simulated input, notifier receipt, or representative compatibility | Required evidence classes, bounded-claim statement, exact revisions, and explicit limitations |
| T-06-05 | Documentation or empty matrices are credited as completed live evidence | Manual gate requires observed result, committed excerpt, result classification, and cleanup per credited row |

---

## Wave 0 Requirements

- [ ] `tests/test_examples.py` — deterministic bundle, documentation, recursion,
  redaction, evidence-schema, and exclusion checks.
- [ ] `examples/trident/LIVE-UAT.md` — staged manual validation artifact with every row
  initialized as `NOT RUN`.
- [ ] `examples/trident/evidence/phase6-live-log.md` — curated evidence target and
  redaction legend.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MadMax/liftbar tool selection and restore | UAT-01 | Requires the representative physical topology and collision supervision | Follow routing rows in `examples/trident/LIVE-UAT.md`; stop on unexpected motion or attachment state |
| Real heater target transfer | UAT-01 | Requires live independent heaters while preserving Klipper safety | Follow heater row with operator-approved low source target; record targets and cleanup |
| Bucket/silicone purge and resume motion | UAT-01 | Requires physical clearance, loaded filament, and direct observation | Follow purge/resume rows only after bucket, docks, bed, and liftbar preflight |
| Complete simulated-runout fallback | UAT-01 | Requires live printer state, toolchanger motion, heaters, and pause ownership | Use the explicit simulation command from the runbook; do not physically remove filament |
| Guarded resume with queued mutation | UAT-01 | Requires a live recoverable checkpoint and operator-timed continuation | Follow guarded-resume row, record queue receipt/drain, then restore reciprocal defaults |
| Moonraker notifier receipt | UAT-01 | Requires the private representative printer-owned adapter | Capture only sanitized receipt and canonical event fields; do not claim Discord delivery |

---

## Validation Rules

- No live row passes without an observed result, concise committed evidence, and verified
  cleanup.
- `NOT RUN`, `BLOCKED`, and `FAIL` remain honest outcomes and cannot be converted to
  automated-contract evidence.
- External media is supplementary only.
- Final verification distinguishes `automated-contract`,
  `simulated-input/live-output`, and `normal-live-operation` evidence.
- No evidence row executes or credits `Valid Configuration Startup`,
  `Persisted State Survives Restart`, `Invalid State Blocks Startup Clearly`, or
  `Read-Only Status Inspection`.

---

## Validation Sign-Off

- [x] All implementation tasks have automated verification or explicit manual-only gates.
- [x] Sampling continuity: no three consecutive implementation tasks lack automated verification.
- [x] Wave 0 covers all missing automated references.
- [x] No watch-mode flags.
- [x] Automated feedback latency target is under 60 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-12 for planning
