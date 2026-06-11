---
phase: 05
slug: notifications-integration-and-verification
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-11
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest -q tests/test_tool_fallback_backups.py tests/test_tool_fallback_notifications.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the focused pytest file(s) named by the task.
- **After every plan wave:** Run `pytest -q`.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-T1 | 05-01 | 1 | BACKUP-01, BACKUP-02, BACKUP-03, BACKUP-05 | T-05-03 | Complete immutable candidates reject invalid policy and never expose partial reset state | unit | `pytest -q tests/test_tool_fallback_state.py -k "backup or cycle"` | ✅ | ⬜ pending |
| 05-01-T2 | 05-01 | 1 | BACKUP-01, BACKUP-02, BACKUP-05 | T-05-03 | Immediate commands preserve unrelated state, avoid hardware action, save before publish, and skip no-op writes | integration | `pytest -q tests/test_tool_fallback_backups.py tests/test_tool_fallback_state.py` | ❌ planned | ⬜ pending |
| 05-02-T1 | 05-02 | 2 | BACKUP-04, BACKUP-05 | T-05-03, T-05-04 | FIFO queue retains failed suffixes and safely drains work submitted after blocked terminalization | integration | `pytest -q tests/test_tool_fallback_backups.py -k "queue or queued or fifo or retained or retry or status"` | ❌ planned | ⬜ pending |
| 05-02-T2 | 05-02 | 2 | BACKUP-04, BACKUP-05 | T-05-03, T-05-04 | Terminal and transition drains cannot alter active or completed workflow outcomes | integration | `pytest -q tests/test_tool_fallback_backups.py tests/test_tool_fallback_fallback.py tests/test_tool_fallback_routing.py -k "queue or queued or drain or transition or terminal or heating_timeout"` | ❌ planned | ⬜ pending |
| 05-03-T1 | 05-03 | 3 | NOTIFY-01, NOTIFY-02, NOTIFY-03 | T-05-01, T-05-02, T-05-04 | Adapter input is bounded; generation-level finalization rejects every non-identical event; adapter behavior is safety-neutral | integration | `pytest -q tests/test_tool_fallback_notifications.py` | ❌ planned | ⬜ pending |
| 05-03-T2 | 05-03 | 3 | NOTIFY-01, NOTIFY-02, BACKUP-04 | T-05-02, T-05-04 | Final events latch per generation before notification and queued drains cannot change outcomes | integration | `pytest -q tests/test_tool_fallback_fallback.py tests/test_tool_fallback_notifications.py tests/test_tool_fallback_backups.py tests/test_tool_fallback_routing.py -k "notify or notification or terminal or transient or resume or drain or queue"` | ❌ planned | ⬜ pending |
| 05-03-T3 | 05-03 | 3 | NOTIFY-01, NOTIFY-02, NOTIFY-03, BACKUP-01, BACKUP-02, BACKUP-03, BACKUP-04, BACKUP-05 | T-05-01, T-05-02, T-05-03, T-05-04 | Complete deterministic contract coverage preserves schema v1 and excludes Phase 6 scope | regression | `python3 -m py_compile klippy/extras/tool_fallback*.py && pytest -q && git diff --check` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠ flaky*

---

## Wave 0 Requirements

Existing pytest, fake reactor/G-Code/hardware/persistence fixtures, and syntax/diff
checks cover all phase requirements. Plans 05-01 and 05-03 create the focused backup
and notification test modules before commands that reference them are run.

---

## Manual-Only Verifications

All Phase 5 behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have automated verification or existing test infrastructure.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 30 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-11
