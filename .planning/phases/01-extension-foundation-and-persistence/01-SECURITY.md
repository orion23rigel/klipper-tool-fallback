---
phase: 01
slug: extension-foundation-and-persistence
status: verified
threats_open: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: 2026-06-06
verified: 2026-06-06
---

# Phase 01 - Security

> Per-phase security contract: verify only the threats registered in the Phase 01
> plan-time threat models.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Klipper configuration to extension | Administrator-supplied paths, adapter names, timing values, tools, and backup references enter the extension. | Trusted configuration requiring normalization and validation |
| Persistent state file to canonical memory | JSON state may be malformed, stale, interrupted, or externally modified before startup. | Untrusted persisted routing and tool-state data |
| Canonical memory to status clients | Validated state and normalized configuration are exposed through G-code and Klipper status APIs. | Read-only operational state |
| Extension to filesystem | Canonical state is persisted to the configured path during ready-time initialization. | Deterministic JSON and filesystem operations |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T01 | Tampering | Global configuration | mitigate | Normalize `state_path`, reject empty adapter/path values, and retain adapter names as inert configuration data. | closed |
| T02 | Tampering / Denial of Service | Tool and timing configuration | mitigate | Reject malformed names, duplicate tools/backups, self/unknown backup references, and non-positive or non-finite timing values before ready. | closed |
| T03 | Tampering | Persisted state parser | mitigate | Require exact schema fields and types, canonical tool names, state invariants, unique JSON keys, and valid cross-references before publication. | closed |
| T04 | Denial of Service | State persistence | mitigate | Write an implementation-owned same-directory temporary file, flush and fsync it, atomically replace the destination, then fsync the parent where supported. | closed |
| T05 | Elevation of Privilege / Tampering | State persistence path handling | mitigate | Normalize the configured path, create only its parent, use an implementation-owned same-directory temporary path, and never derive paths from persisted JSON. | closed |
| T06 | Information Disclosure / Tampering | Status interfaces | mitigate | Render only the validated canonical in-memory snapshot; both status interfaces are read-only. | closed |
| T07 | Denial of Service | Ready-time lifecycle | mitigate | Finalize, load, reconcile, and persist in order; publish state only after success and convert failures into startup errors. | closed |

*Status: open / closed*
*Disposition: mitigate (implementation required) / accept (documented risk) / transfer (third-party)*

---

## Threat Verification Evidence

| Threat ID | Implementation Evidence | Test / Documentation Evidence |
|-----------|-------------------------|-------------------------------|
| T01 | `tool_fallback_config.py:38-43,67-85` rejects empty values and normalizes the configured path. Adapter values are stored in `GlobalConfig`; Phase 01 contains no adapter invocation path. | `test_tool_fallback_config.py:50-77,183-193`; `README.md:57-59` |
| T02 | `tool_fallback_config.py:46-64,88-125` validates canonical names, positive finite timing, duplicates, self references, and unknown references; `tool_fallback.py:24-27` rejects duplicate tool sections. | `test_tool_fallback_config.py:118-159,196-219` |
| T03 | `tool_fallback_state.py:42-86,200-262` validates schema, exact fields/types, canonical names, invariants, duplicate JSON keys, mappings, and backups before returning canonical state. | `test_tool_fallback_state.py:139-194`; review fixes and reverification recorded in `01-REVIEW.md` and `01-VERIFICATION.md` |
| T04 | `tool_fallback_state.py:174-197,269-284` performs same-directory `mkstemp`, flush/fsync, `os.replace`, parent fsync, and failure cleanup. | `test_tool_fallback_state.py:221-299`; `README.md:73-76` |
| T05 | `tool_fallback_config.py:67-72` and `tool_fallback_state.py:138-140` normalize only the configured path; `tool_fallback_state.py:174-181` creates only the parent and an implementation-owned temporary path in that directory. Persisted JSON parsing at `tool_fallback_state.py:42-86` has no path field or filesystem call. | `test_tool_fallback_config.py:50-77`; `test_tool_fallback_state.py:221-280` |
| T06 | `tool_fallback.py:41-51` builds both outputs from `self.state.to_dict()` and normalized in-memory configuration without loading or saving state. | `test_tool_fallback_extension.py:165-194`; `README.md:78-88` |
| T07 | `tool_fallback.py:53-67` finalizes, loads/reconciles, saves, and only then assigns `_state_store` and `state`; JSON, validation, and filesystem failures become startup configuration errors. | `test_tool_fallback_extension.py:52-73,124-162` |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T05 | `state_path` is trusted administrator configuration and may intentionally designate any path writable by the Klipper process. Phase 01 prevents persisted JSON from choosing paths but does not sandbox administrator configuration. | Project design | 2026-06-06 |
| AR-02 | T04 | Parent-directory fsync may be unsupported on some filesystems. The implementation tolerates only known unsupported-operation errors after atomic replacement; this preserves portability while retaining the strongest available durability guarantee. | Project design | 2026-06-06 |

---

## Threat Flags

No unregistered threat flags were reported by the Phase 01 summaries. This audit did
not scan for unrelated new threats.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By | Verification |
|------------|---------------|--------|------|--------|--------------|
| 2026-06-06 | 7 | 7 | 0 | Codex / gsd-security-auditor workflow | `pytest -q tests/test_tool_fallback_config.py tests/test_tool_fallback_state.py tests/test_tool_fallback_extension.py`: 82 passed |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted residual risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-06
