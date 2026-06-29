# Security Audit — Phase 12: Fallback Integration & Observability

**Audit Date:** 2026-06-29
**ASVS Level:** Standard
**Block Policy:** critical (block on unregistered attack surface)
**Audited Plans:** 12-01 (user-defined backup injection), 12-02 (observability)

## Threat Verification Summary

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-12-01 | Tampering | mitigate | **CLOSED** | `tool_fallback_state.py:347-358`, `tool_fallback.py:1613-1646` |
| T-12-02 | Information Disclosure | accept | **CLOSED** | `tool_fallback_state.py:162`, `tool_fallback.py:288` |
| T-12-SC | Tampering | mitigate | **CLOSED** | Project-level concern; no new package installs in this phase |

## Detailed Findings

### T-12-01: Tampering — user_defined_backups injection

**Disposition:** mitigate
**Status:** CLOSED

**Mitigation Plan:** User-defined backup validated at save time. At routing time, the backup tool must exist in `state.tools` — `resolve_backup_graph()` handles missing tools as unloaded/failed. Fail-closed: if user-defined backup is invalid, it is skipped and configured chain is used.

**Evidence:**

| Checkpoint | Location | Verification |
|------------|----------|--------------|
| Save-time format validation | `tool_fallback_state.py:70-81` (`from_dict`) | TOOL_NAME_RE fullmatch on backup names; self-reference blocked |
| Save-time configured-tool validation | `tool_fallback_state.py:321-325` (`with_user_defined_backup`) | Backup must exist in `self.tools`; self-reference blocked |
| Save-time persistence validation | `tool_fallback_state.py:427` (`StateStore.save`) | `_validate_user_defined_backups()` called before write |
| Save-time CLI validation | `tool_fallback.py:373-378` (`cmd_DEFINE_TOOL_BACKUP`) | LOGICAL validated via TOOL_NAME_RE; BACKUP via `_require_configured_tool` |
| Routing-time injection | `tool_fallback.py:1613-1636` (`_resolve_backup_with_rescan`) | UDD prepended to effective backup list; temporary state created for `resolve_backup_graph` |
| Routing-time fail-closed | `tool_fallback.py:1642-1646` | If first scan (with UDD) yields no candidate, second scan uses original state (configured chain only) |
| Graph traversal safety | `tool_fallback.py:107-110` (`resolve_backup_graph`) | `failed_tool` validated in `state.tools`; backup tools traversed via DFS with loop detection |
| Test coverage | `tests/test_tool_fallback_fallback.py:1240-1362` | 6 tests: UDD priority, UDD failure fallback, UDD unloaded fallback, complete workflow, unknown authority, no-UDD regression |

**Assessment:** The mitigation is fully implemented. Save-time validation ensures only configured tool names can be set as UDD backups. Routing-time injection prepends UDD to the backup chain, and the fail-closed second-scan fallback ensures the configured chain is always available if UDD is unavailable. All fail-closed safety checkpoints (loaded, purged, sensor authority) apply equally to UDD backups because they flow through `resolve_backup_graph()` — no separate fast path.

### T-12-02: Information Disclosure — SHOW_TOOL_FALLBACK_STATE output

**Disposition:** accept
**Status:** CLOSED

**Mitigation Plan:** user_defined_backups is operator-visible state; no PII or sensitive data exposed. Shows only tool names (T0, T1, etc.).

**Evidence:**

| Checkpoint | Location | Verification |
|------------|----------|--------------|
| State serialization | `tool_fallback_state.py:162` (`to_dict`) | `user_defined_backups` returned as `dict(self.user_defined_backups)` — only tool name strings |
| Status snapshot | `tool_fallback.py:288` (`get_status`) | `to_dict()` called; `user_defined_backups` included at top level |
| Command output | `tool_fallback.py:300-302` (`cmd_SHOW_TOOL_FALLBACK_STATE`) | `json.dumps()` output via `respond_info` — standard Klipper log channel |
| Test verification | `tests/test_tool_fallback_extension.py:798-860` | 4 tests: key present, empty state, undefinition reflection, JSON serializable |

**Assessment:** The accept disposition is appropriate. The `user_defined_backups` field contains only canonical tool names (e.g., "T0", "T1") — no PII, no sensitive configuration values, no internal state identifiers. The output is operator-visible by design (FALLBACK-04, OBSERVE-01).

### T-12-SC: Tampering — npm/pip/cargo installs

**Disposition:** mitigate
**Status:** CLOSED (project-level)

**Assessment:** This threat is scoped to project-level dependency management (slopcheck + human checkpoint). Phase 12 introduces no new package installs, no external dependencies, and no code from untrusted sources. Not applicable to this phase.

## Unregistered Flags

No `## Threat Flags` section present in either 12-01-SUMMARY.md or 12-02-SUMMARY.md. No new attack surface was flagged during implementation that lacks threat mapping.

## Conclusion

**All 3 threats resolved: 3/3 CLOSED.**

Phase 12 implements its declared mitigations correctly:
- User-defined backups are validated at save time and safely injected at routing time with fail-closed fallback to the configured chain.
- Observability output contains only tool names — no sensitive data exposure risk.
- No new external dependencies introduced.

The phase is ready to ship from a threat-mitigation perspective.
