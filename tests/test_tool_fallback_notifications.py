import pytest

from conftest import CommandError, FakeGCmd
from klippy.extras import tool_fallback
from klippy.extras.tool_fallback import TerminalEvent, WorkflowCheckpoint


def load_extension(config_factory, prefix_config_factory, printer, tmp_path):
    extension = tool_fallback.load_config(config_factory(
        state_path=str(tmp_path / "state.json"),
        notify_gcode="MY_NOTIFY",
    ))
    printer.add_object("tool_fallback", extension)
    for name, backups in (("T0", "T1"), ("T1", "")):
        printer.gcode.register_command(name, lambda gcmd: None)
        tool_fallback.load_config_prefix(prefix_config_factory(
            "tool_fallback %s" % name,
            heater="extruder",
            backups=backups,
        ))
    printer.send_event("klippy:ready")
    return extension


def event(**changes):
    values = {
        "event": "FALLBACK_FAILURE",
        "generation": 7,
        "logical_tool": "T0",
        "failed_tool": "T0",
        "selected_tool": "T1",
        "reason_code": "UNEXPECTED_FAILURE",
        "reason_detail": "unexpected failure",
    }
    values.update(changes)
    return TerminalEvent(**values)


def test_payload_has_fixed_order_sentinel_and_bounded_safe_detail(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path)

    extension._attempt_notification(event(
        logical_tool=None,
        selected_tool=None,
        reason_detail=' bad\n"; RESET_TOOL_BACKUPS # snowman=\u2603 ' * 20,
    ))

    script = printer.gcode.script_events[-1]
    assert script.startswith(
        "MY_NOTIFY EVENT=FALLBACK_FAILURE GENERATION=7 "
        "LOGICAL_TOOL=n/a FAILED_TOOL=T0 SELECTED_TOOL=n/a "
        "REASON_CODE=UNEXPECTED_FAILURE REASON_DETAIL=")
    detail = script.split(" REASON_DETAIL=", 1)[1]
    assert len(detail) <= 160
    assert detail
    assert all(character.isascii() and (
        character.isalnum() or character in "._:/+-")
               for character in detail)
    assert "\n" not in script
    assert ";" not in script
    assert "#" not in script


def test_known_reason_never_transports_detail(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path)

    extension._attempt_notification(event(
        reason_code="PURGE_FAILED", reason_detail="must stay local"))

    assert "REASON_CODE=PURGE_FAILED" in printer.gcode.script_events[-1]
    assert "REASON_DETAIL" not in printer.gcode.script_events[-1]


def test_generation_latches_first_complete_event_and_rejects_conflicts(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path)
    first = event(reason_detail=None, reason_code="GRAPH_EXHAUSTED")

    assert extension._attempt_notification(first) is True
    assert extension._attempt_notification(first) is False
    assert extension._attempt_notification(event(
        event="FALLBACK_SUCCESS", reason_code="SUCCESS",
        reason_detail=None)) is False
    assert extension._attempt_notification(event(
        reason_code="PURGE_FAILED", reason_detail=None)) is False

    assert len(printer.gcode.script_events) == 1
    assert any("conflicting finalized event" in response
               for response in printer.gcode.responses)


def test_adapter_failure_delay_recursion_and_command_reentry_are_isolated(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path)
    original = extension.state
    callback_results = []

    def callback(script):
        callback_results.append(extension._attempt_notification(event(
            generation=8, reason_detail=None)))
        with pytest.raises(CommandError, match="notification delivery"):
            printer.gcode.invoke_command(
                "SET_TOOL_BACKUPS",
                FakeGCmd({"TOOL": "T0", "BACKUPS": ""}))

    printer.gcode.set_script_callback("MY_NOTIFY", callback)
    first = event(reason_detail=None)
    printer.gcode.set_script_duration(
        extension._build_notification_script(first), 2.0)

    assert extension._attempt_notification(first) is True

    assert callback_results == [False]
    assert printer.reactor.monotonic() == 2.0
    assert extension.state is original
    assert extension._backup_operation_queue == []
    assert any("recursive tool fallback notification" in response
               for response in printer.gcode.responses)

    printer.gcode.inject_script_failure(
        "MY_NOTIFY EVENT=FALLBACK_SUCCESS GENERATION=9 LOGICAL_TOOL=n/a "
        "FAILED_TOOL=T0 SELECTED_TOOL=T1 REASON_CODE=SUCCESS",
        CommandError("adapter unavailable"))
    success = event(
        event="FALLBACK_SUCCESS", generation=9, logical_tool=None,
        reason_code="SUCCESS", reason_detail=None)
    assert extension._attempt_notification(success) is True
    assert extension._finalized_events[9] == success
    assert any("adapter failed" in response
               for response in printer.gcode.responses)


def test_terminal_failure_is_visible_before_notification_and_drain(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path)
    observed = []
    extension._workflow_checkpoint = WorkflowCheckpoint(
        "automatic_fallback", "heating", 3,
        logical_tool="T0", current_physical_tool="T0",
        requested_physical_tool="T1")

    def callback(script):
        observed.append((
            extension._workflow_checkpoint.stage,
            len(extension._backup_operation_queue),
        ))

    printer.gcode.set_script_callback("MY_NOTIFY", callback)
    printer.gcode.invoke_command(
        "SET_TOOL_BACKUPS", FakeGCmd({"TOOL": "T0", "BACKUPS": ""}))

    extension._block_workflow(
        extension._workflow_checkpoint, "no backup", "GRAPH_EXHAUSTED")

    assert observed == [("blocked", 1)]
    assert extension._backup_operation_queue == []
    assert "EVENT=FALLBACK_FAILURE" in printer.gcode.script_events[-1]
    assert "REASON_CODE=GRAPH_EXHAUSTED" in printer.gcode.script_events[-1]


def test_adapter_exception_does_not_prevent_terminal_queue_drain(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path)
    checkpoint = WorkflowCheckpoint(
        "automatic_fallback", "heating", 11,
        logical_tool="T0", current_physical_tool="T0",
        requested_physical_tool="T1")
    extension._workflow_checkpoint = checkpoint
    printer.gcode.invoke_command(
        "SET_TOOL_BACKUPS", FakeGCmd({"TOOL": "T0", "BACKUPS": ""}))

    def fail_adapter(script):
        raise CommandError("injected adapter failure")

    printer.gcode.set_script_callback("MY_NOTIFY", fail_adapter)

    extension._block_workflow(
        checkpoint, "purge failed", "PURGE_FAILED")

    assert extension._workflow_checkpoint.stage == "blocked"
    assert extension._workflow_checkpoint.failure_reason == "purge failed"
    assert extension.state.tools["T0"].backups == ()
    assert extension._backup_operation_queue == []
    assert extension._finalized_events[11].reason_code == "PURGE_FAILED"
    assert any("adapter failed" in response
               for response in printer.gcode.responses)


def test_manual_transition_failure_does_not_emit_fallback_event(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path)
    checkpoint = WorkflowCheckpoint(
        "manual_route", "heating", 12,
        logical_tool="T0", current_physical_tool="T0",
        requested_physical_tool="T1")

    extension._block_workflow(checkpoint, "manual route failed")

    assert extension._workflow_checkpoint.stage == "blocked"
    assert printer.gcode.script_events == []
    assert extension._finalized_events == {}


def test_finalized_notification_state_is_runtime_only(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path)

    extension._attempt_notification(event(reason_detail=None))

    persisted = extension.state.to_dict()
    assert "notification" not in persisted
    assert "finalized_events" not in persisted
    assert persisted["version"] == 1


def test_heating_timeout_is_nonterminal_until_guarded_finalization(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path)
    checkpoint = WorkflowCheckpoint(
        "automatic_fallback", "heating_timeout", 5,
        logical_tool="T0", current_physical_tool="T0",
        requested_physical_tool="T1", pause_owned=True)
    extension._workflow_checkpoint = checkpoint

    assert printer.gcode.script_events == []

    extension._finalize_fallback_success(checkpoint)

    assert len(printer.gcode.script_events) == 1
    assert "EVENT=FALLBACK_SUCCESS" in printer.gcode.script_events[0]
