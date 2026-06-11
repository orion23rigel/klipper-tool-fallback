# Phase 5: Runtime Contracts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-06-11
**Phase:** 05-notifications-integration-and-verification
**Areas discussed:** Notification Payload, Notification Outcome Timing, Backup Mutation Availability, Command Feedback

---

## Notification Payload

| Decision | Alternatives considered | Selected |
|----------|-------------------------|----------|
| Fields | Compact canonical, minimal, detailed, agent decides | Compact canonical |
| Missing values | Stable sentinel, empty, omitted, agent decides | Stable sentinel `n/a` |
| Reason codes | Specific stable codes, broad categories, none, agent decides | Specific stable codes |
| Unexpected failure detail | Internal code only, unknown code only, sanitized detail, agent decides | Sanitized bounded detail |

**Notes:** Every event uses stable canonical fields. Unexpected failures retain a stable
reason code while exposing bounded sanitized detail externally.

## Notification Outcome Timing

| Decision | Alternatives considered | Selected |
|----------|-------------------------|----------|
| Heating timeout | Final only, timeout plus final, timeout only, agent decides | Final only |
| Terminal failure | Immediate, operator acknowledgement, pre-selection only, agent decides | Immediate |
| Transient recovery | Fallback avoided, immediate detection, after print resume, agent decides | Fallback avoided |
| Resume failure | Failure, success, both, agent decides | `FALLBACK_FAILURE` / `RESUME_FAILED` |

**Notes:** Externally visible events describe final workflow outcomes, not recoverable
intermediate stages.

## Backup Mutation Availability

| Decision | Alternatives considered | Selected |
|----------|-------------------------|----------|
| Printing/paused availability | Allow, paused only, block both, agent decides | Allow |
| Active workflow behavior | Reject, queue, ignore, agent decides | Queue |
| Queue drain timing | Any terminal outcome, success only, operator clear, agent decides | Any terminal outcome |
| Same-tool queued commands | Latest wins, apply all in order, reject extras, agent decides | Apply all in order |
| Queue application failure | Stop, continue, discard all, agent decides | Stop |

**Notes:** The user deliberately chose queueing after being shown that it conflicts with
the original `BACKUP-04` rejection requirement. The requirement was revised accordingly.

## Command Feedback

| Decision | Alternatives considered | Selected |
|----------|-------------------------|----------|
| Immediate success | Canonical policy, brief confirmation, silent, agent decides | Canonical policy |
| Exact no-op | Explicit unchanged policy, ordinary success, silent, agent decides | Explicit unchanged policy |
| Queue receipt | Detailed receipt, brief queued, silent, agent decides | Detailed receipt |
| Queue results | Per-command plus summary, summary only, failures only, agent decides | Per-command plus summary |

**Notes:** Operator feedback must make persistence, no-op behavior, queue placement, and
queue processing outcomes auditable.

## the agent's Discretion

- Bounded encoding and length for sanitized reason detail.
- Complete stable reason-code vocabulary.
- Internal queue representation and reboot/shutdown handling within the locked visible
  behavior and safety constraints.

## Deferred Ideas

None.
