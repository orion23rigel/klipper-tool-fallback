# Plan 04-02: Implement Fail-Closed Heater Transfer Stages

## Objective
Implement safety mechanisms to ensure that when a tool fallback occurs, the source heater is safely shut down and the destination heater is preheated, preventing uncontrolled temperature changes or failures during the transition.

## Implementation Details
- Added `_heaters` mapping to `ToolFallback` to resolve physical heaters for each tool.
- Implemented `_resolve_heaters` to validate heater availability during initialization.
- Implemented `_block_workflow` to provide a standardized way to halt the fallback process if a safety violation is detected.
- Implemented `_capture_and_shutdown_source` to safely turn off the source tool's heater before proceeding to the next stage.
- Implemented `_preheat_requested_tool` to ensure the destination tool's heater is at the target temperature before use.
- Added comprehensive unit tests in `tests/test_tool_fallback_fallback.py` to verify safety logic, error handling, and heater state transitions.

## Verification
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] No modifications to shared orchestrator artifacts
