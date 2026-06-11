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
| **Quick run command** | `pytest -q tests/test_tool_fallback_state.py tests/test_tool_fallback_fallback.py` |
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
| 05-01-01 | 01 | 1 | BACKUP-01, BACKUP-02, BACKUP-03, BACKUP-05 | T-05-03 | Invalid or failed persistence never publishes policy | unit | `pytest -q tests/test_tool_fallback_state.py` | ✅ | ⬜ pending |
| 05-01-02 | 01 | 1 | BACKUP-01, BACKUP-02, BACKUP-05 | T-05-03 | Commands preserve unrelated state and avoid no-op writes | integration | `pytest -q tests/test_tool_fallback_routing.py tests/test_tool_fallback_state.py` | ✅ | ⬜ pending |
| 05-02-01 | 02 | 2 | BACKUP-04, BACKUP-05 | T-05-04 | Queue cannot alter active workflow and stops safely on failure | integration | `pytest -q tests/test_tool_fallback_fallback.py tests/test_tool_fallback_routing.py` | ✅ | ⬜ pending |
| 05-03-01 | 03 | 2 | NOTIFY-01, NOTIFY-02, NOTIFY-03 | T-05-01, T-05-02 | Adapter input is bounded and adapter behavior is safety-neutral | integration | `pytest -q tests/test_tool_fallback_fallback.py` | ✅ | ⬜ pending |
| 05-03-02 | 03 | 3 | NOTIFY-01, NOTIFY-02, BACKUP-04 | T-05-02, T-05-04 | Terminal events deduplicate and queue drains cannot change outcomes | integration | `pytest -q tests/test_tool_fallback_fallback.py tests/test_tool_fallback_routing.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

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
