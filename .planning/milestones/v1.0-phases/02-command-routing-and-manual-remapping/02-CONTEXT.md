# Phase 2: Command Routing And Manual Remapping - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Capture and replace configured logical `Tn` commands, preserve their original
handlers for recursion-free physical selection, route logical commands through
persistent mappings, expose manual remap/restore/reset operations, and own the
safe transition required when an active logical route changes during a print.

Sensor debounce, purge lifecycle implementation, automatic runout fallback,
backup graph management, and external notifications remain in later phases.

</domain>

<decisions>
## Implementation Decisions

### Existing Routing Contract
- **D-01:** At ready time, capture every configured existing `Tn` handler and replace it with a logical routing handler.
- **D-02:** An intercepted logical `Tn` resolves its persisted mapping and directly invokes the saved original handler for the mapped physical tool.
- **D-03:** `SELECT_PHYSICAL_TOOL TOOL=Tn` invokes the saved original physical handler and bypasses logical mappings.
- **D-04:** `REMAP_TOOL` persists a logical-to-physical mapping; `RESTORE_TOOL` restores one identity mapping; `RESET_TOOL_MAPPINGS` restores all identity mappings.
- **D-05:** Remapping or restoring the active logical tool during a print uses the complete safe transition workflow.

### Physical Bypass Ownership
- **D-06:** Direct physical selection does not change or clear active logical ownership.
- **D-07:** Internal transition workflows may use the physical bypass during an active print.
- **D-08:** Reject direct user-issued `SELECT_PHYSICAL_TOOL` while a print is active. Allow it outside prints for setup, testing, and maintenance.

### Handler Validation
- **D-09:** Klipper startup fails with a configuration error if any configured physical tool lacks an existing `Tn` handler. Unusable physical routes must not enter runtime routing.

### Reset During Active Prints
- **D-10:** During an active print, `RESET_TOOL_MAPPINGS` resets inactive routes and safely transitions the active logical tool to its identity physical tool.
- **D-11:** The active-print reset completes only if the active route transition succeeds.
- **D-12:** Before the physical change, pause immediately and report a warning describing the planned logical and physical transition. Proceed without a countdown.
- **D-13:** Any failed active-print reset transition leaves the printer paused and reports the failure.

### the agent's Discretion
- Exact command error and warning wording, provided it identifies the logical route, current physical tool, and requested physical tool.
- Internal representation of active logical and selected physical state.
- How internal workflow calls are distinguished from direct user-issued physical bypass commands.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product And Scope
- `.planning/PROJECT.md` — Core value, compatibility constraints, safety constraints, and project-level routing decisions.
- `.planning/ROADMAP.md` — Phase boundary and requirement allocation.
- `.planning/REQUIREMENTS.md` — ROUTE-02 through ROUTE-05 acceptance requirements and later-phase boundaries.
- `.planning/STATE.md` — Decisions and verified foundation carried forward from Phase 1.

### Behavioral Design
- `.planning/DESIGN.md` — Canonical command interception, manual routing, purge, and transition workflow behavior.

### Foundation Contracts
- `.planning/phases/01-extension-foundation-and-persistence/01-VERIFICATION.md` — Verified Phase 1 behavior and explicit Phase 2 boundary.
- `.planning/phases/01-extension-foundation-and-persistence/01-RESEARCH.md` — Klipper command capture contract and foundation integration notes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `klippy/extras/tool_fallback.py`: Existing ready handler, command registration, normalized configuration, state store ownership, and read-only status command.
- `klippy/extras/tool_fallback_state.py`: Immutable canonical `FallbackState`, mapping validation, deterministic ordering, and atomic `StateStore.save()`.
- `klippy/extras/tool_fallback_config.py`: Canonical `Tn` validation and normalized configured-tool registry.
- `tests/conftest.py`: `FakeGCode.register_command()` already returns replaced or unregistered handlers, enabling command-capture tests.

### Established Patterns
- Ready-time initialization must finish successfully before canonical runtime state is published.
- Configuration and state failures fail closed with categorized, actionable errors.
- Persisted state remains immutable; mutations should produce a new canonical state and save atomically.
- Tool names are strict canonical uppercase `Tn` identities.

### Integration Points
- Extend `ToolFallback._handle_ready()` after configuration and state initialization to validate, capture, and replace configured handlers.
- Register Phase 2 manual routing and physical bypass commands from `ToolFallback`.
- Add focused state mutation helpers without weakening schema validation or atomic persistence.
- Extend the fake printer/G-code harness for command invocation, active-print state, pause ownership, warnings, and transition failures.

</code_context>

<specifics>
## Specific Ideas

- Active-print reset warnings should clearly resemble: `Resetting mappings: active logical T0 will move from physical T2 to T0`.
- Physical bypass is a low-level mechanism, not a second user-facing routing model.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-command-routing-and-manual-remapping*
*Context gathered: 2026-06-06*
