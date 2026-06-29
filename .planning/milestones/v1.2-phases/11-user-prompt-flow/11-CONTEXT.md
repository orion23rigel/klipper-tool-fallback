# Phase 11: User Prompt Flow - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

## Phase Boundary

This phase implements the user prompt flow: when an undefined tool is detected (Phase 10), the print is paused, the Klipper console displays a prompt, the system waits for the user to define a backup tool, and then resumes. If the user doesn't respond within a configurable timeout, the system falls back to a default tool and resumes.

**Scope anchor:** Prompt flow only — pause, display message, wait for user input or timeout, resume. No detection logic (Phase 10), no routing integration (Phase 12).

## Requirements (locked via REQUIREMENTS.md)

**6 requirements are locked.** See REQUIREMENTS.md for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read REQUIREMENTS.md before planning or implementing.

**In scope (from REQUIREMENTS.md):**
- PROMPT-01: When undefined tool detected, print is paused using existing `pause_gcode` mechanism
- PROMPT-02: Klipper console displays prompt: "Tool Tn not defined. Define a backup tool: `DEFINE_TOOL_BACKUP Tn Tm`"
- PROMPT-03: System waits for user to submit `DEFINE_TOOL_BACKUP`
- PROMPT-04: After backup defined, mapping is applied and print resumes via `resume_gcode`
- PROMPT-05: If user doesn't respond within configurable timeout (`undefined_tool_timeout`), system falls back to default tool and resumes
- PROMPT-06: Timeout events logged via existing notification system

**Out of scope (from REQUIREMENTS.md):**
- User commands (Phase 9) — already implemented
- Undefined tool detection (Phase 10) — triggers this phase
- Fallback integration and observability (Phase 12)

## Implementation Decisions

### Timeout Configuration
- **D-01:** New global config option `undefined_tool_timeout` (float, seconds, default 300.0 / 5 minutes) — added to `GlobalConfig` dataclass in `tool_fallback_config.py`.
- **D-02:** The timeout is a positive finite float, validated with `_positive_finite_float()` — same pattern as `selection_timeout` and `heating_timeout`.
- **D-03:** The timeout applies per-undefined-tool event — each new undefined tool detection starts a fresh timeout countdown.

### Pause Mechanism
- **D-04:** Pause uses the existing `pause_gcode` from global config: `self.gcode.run_script_from_command(self.config.global_config.pause_gcode)` — same as `_on_confirmed_runout` does.
- **D-05:** The pause is triggered by the prompt flow handler (not Phase 10's detection). Phase 10 sets a checkpoint; Phase 11's flow reads it and pauses.
- **D-06:** The prompt flow creates a new `_workflow_checkpoint` with `source="undefined_tool_prompt"` and `stage="waiting_for_user"` — tracking the prompt lifecycle separately from the detection checkpoint.

### Console Message
- **D-07:** Message format: `gcmd.respond_info("Tool T{n} not defined. Define a backup tool: `DEFINE_TOOL_BACKUP T{n} T{m}`")` — exactly as specified in PROMPT-02.
- **D-08:** The tool number `{n}` is the undefined tool from Phase 10's detection. The `{m}` placeholder indicates any configured tool the user could choose as backup.
- **D-09:** The message is displayed via `self.gcode.respond_info()` — Klipper console output visible in the web interface and serial console.

### Waiting for User Input
- **D-10:** The "wait" is implemented as a polling loop in the Klipper reactor — the prompt flow registers a timer callback that checks whether `DEFINE_TOOL_BACKUP` has been called.
- **D-11:** The prompt flow monitors `self.state.user_defined_backups` for a new entry matching the undefined tool — when `DEFINE_TOOL_BACKUP` is called, the entry appears and the flow proceeds.
- **D-12:** Alternatively (and preferred): the prompt flow sets a sentinel flag `self._undefined_tool_pending = True` that `cmd_DEFINE_TOOL_BACKUP` checks and clears when it successfully defines a backup for the pending tool. This is cleaner than polling the state dict.
- **D-13:** The waiting loop uses `self.printer.get_reactor().advance()` with small intervals (0.1s) — same pattern as `_wait_for_heater_readiness()` in the existing code.

### Resume After User Response
- **D-14:** After `DEFINE_TOOL_BACKUP` is called and the mapping is applied, the prompt flow resumes the print: `self.gcode.run_script_from_command(self.config.global_config.resume_gcode)`.
- **D-15:** The prompt flow must ensure the mapping is persisted before resuming — `cmd_DEFINE_TOOL_BACKUP` already handles persistence (CMD-04), so the prompt flow just needs to detect the change.
- **D-16:** The prompt flow clears the checkpoint and calls `_finalize_fallback_success()` or a new `_finalize_undefined_tool_success()` — consistent with existing terminal event handling.

### Timeout Fallback
- **D-17:** When the timeout expires, the prompt flow falls back to a "default tool" — the first configured tool on the printer (T0, or the tool with the lowest number). This is the safest default.
- **D-18:** The timeout fallback automatically defines the mapping: `self.state = self.state.with_user_defined_backup(undefined_tool, default_tool)`, then persists and resumes.
- **D-19:** The timeout event is logged via the existing notification system — `self._attempt_notification()` with a new event type "UNDEFINED_TOOL_TIMEOUT" or by reusing "FALLBACK_FAILURE" with a specific reason code.
- **D-20:** The timeout message is displayed: `self.gcode.respond_info("Tool T{n} prompt timed out; falling back to T{m}")`.

### Integration with Phase 10 Detection
- **D-21:** Phase 10's `_TOOL_FALLBACK_TN` creates a checkpoint with `source="undefined_tool"`. Phase 11's prompt flow is triggered by a new handler that monitors for this checkpoint.
- **D-22:** The prompt flow is NOT a separate G-code command — it's an internal state machine in the `ToolFallback` class that reacts to the undefined-tool checkpoint.
- **D-23:** The prompt flow should be triggered from within `_TOOL_FALLBACK_TN` itself (after detecting the undefined tool), not from a separate reactor event. This keeps the flow contained.

### the agent's Discretion
- **D-24:** Exact implementation of the "wait" mechanism — reactor timer callback vs. polling loop. The polling loop (like `_wait_for_heater_readiness`) is simpler and more consistent with existing code.
- **D-25:** Whether the default tool for timeout fallback is T0 (lowest number) or the first configured tool — both are equivalent if tools are numbered from T0.
- **D-26:** Whether to use a new notification event type or reuse an existing one for timeout logging.

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source Code
- `klippy/extras/tool_fallback.py` — Main extension, `_wait_for_heater_readiness()` (polling pattern), `_on_confirmed_runout()` (pause/resume pattern), `_attempt_notification()` (notification pattern), `_finalize_fallback_success()` (terminal event pattern)
- `klippy/extras/tool_fallback_config.py` — `GlobalConfig` dataclass, `_positive_finite_float()` validation
- `klippy/extras/tool_fallback_state.py` — `FallbackState.with_user_defined_backup()` (from Phase 9), `StateStore.save()`

### Requirements
- `.planning/REQUIREMENTS.md` — v1.2 requirements, PROMPT-01 through PROMPT-06

### Prior Phase Context
- `.planning/phases/10-undefined-tool-detection/10-CONTEXT.md` — Phase 10 checkpoint design
- `.planning/phases/09-user-commands/09-CONTEXT.md` — Phase 9 command patterns
- `.planning/phases/08-state-schema-extension/08-CONTEXT.md` — Phase 8 state schema

### Design
- `.planning/ROADMAP.md` — Phase 11 goal, dependencies, and success criteria

## Existing Code Insights

### Reusable Assets
- `_wait_for_heater_readiness(self, checkpoint)` (`tool_fallback.py:1122`) — Polling loop with reactor.advance() and timeout deadline — ideal pattern for waiting for user input
- `_on_confirmed_runout(self, checkpoint)` (`tool_fallback.py:950`) — Pause print, process, resume pattern
- `_attempt_notification(self, event)` (`tool_fallback.py:556`) — Notification system for logging events
- `_finalize_fallback_success(self, checkpoint)` (`tool_fallback.py:607`) — Terminal event finalization
- `self.gcode.run_script_from_command()` — Pause/resume script execution

### Established Patterns
- **Polling with timeout:** Monotonic deadline + reactor.advance() loop — same as heater readiness
- **Pause/resume:** `run_script_from_command(pause_gcode)` → work → `run_script_from_command(resume_gcode)`
- **Checkpoint lifecycle:** Create → advance stages → clear on completion → terminal event
- **Notification events:** `TerminalEvent` with event type + reason code → `_attempt_notification()`

### Integration Points
- `self.config.global_config.pause_gcode` / `resume_gcode` — Klipper pause/resume scripts
- `self._workflow_checkpoint` — State tracking for prompt flow
- `self.state.user_defined_backups` — Monitored for user's `DEFINE_TOOL_BACKUP` response
- `self._attempt_notification()` — Timeout event logging

## Specific Ideas

No specific requirements — open to standard approaches consistent with existing architecture.

## Deferred Ideas

None — discussion stayed within phase scope

---

*Phase: 11-User Prompt Flow*
*Context gathered: 2026-06-29*
