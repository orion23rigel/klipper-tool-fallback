# Phase 2: Command Routing And Manual Remapping - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-06
**Phase:** 02-command-routing-and-manual-remapping
**Areas discussed:** Physical bypass ownership, missing physical handlers, reset during active prints

---

## Physical Bypass Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Physical selection only | Preserve active logical ownership while selecting hardware directly. | ✓ |
| Update active logical tool | Treat direct physical selection as a matching logical selection. | |
| Clear active logical tool | Mark logical ownership unknown after direct physical selection. | |

**User's choice:** Keep physical selection low-level. Internal transitions may use it during a print, but reject direct user use while a print is active.
**Notes:** Direct physical selection remains available outside prints for setup, testing, and maintenance.

---

## Missing Physical Handlers

| Option | Description | Selected |
|--------|-------------|----------|
| Fail startup | Reject configuration immediately if any configured physical tool lacks an existing `Tn` handler. | ✓ |
| Fail on selection | Allow startup and report the missing handler only when that tool is selected. | |

**User's choice:** Fail startup.
**Notes:** Every configured tool may become a mapped route, so unusable tools must be detected before printing.

---

## Reset During Active Prints

| Option | Description | Selected |
|--------|-------------|----------|
| Safe active transition | Reset inactive routes and safely transition the active route to identity. | ✓ |
| Reject during print | Require printing to stop before resetting mappings. | |

**User's choice:** Perform the safe active transition.
**Notes:** Pause immediately and warn before the physical change. No countdown is required. Complete only on success; failures leave the printer paused.

---

## the agent's Discretion

- Exact warning and error wording.
- Internal active logical and selected physical state representation.
- Internal-call authorization mechanism for physical bypass during prints.

## Deferred Ideas

None.
