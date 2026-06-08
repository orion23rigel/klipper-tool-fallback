import pytest

from conftest import CommandError, FakeFilamentSensor, FakeGCmd, FakePrintStats
from klippy.extras import tool_fallback
from klippy.extras.tool_fallback_state import FallbackState, StateStore


def tool_state(loaded=True, purged=True, failed=False, backups=()):
    return {
        "loaded": loaded,
        "purged": purged,
        "failed": failed,
        "backups": list(backups),
    }


def load_extension(config_factory, prefix_config_factory, printer, state_path,
                   tool_states=None, sensors=True):
    tool_states = tool_states or {"T0": tool_state()}
    StateStore(str(state_path)).save(FallbackState.from_dict({
        "version": 1,
        "tools": tool_states,
        "mappings": {name: name for name in tool_states},
    }))
    extension = tool_fallback.load_config(
        config_factory(state_path=str(state_path)))
    printer.add_object("tool_fallback", extension)
    sensor_objects = {}
    for name in tool_states:
        printer.gcode.register_command(name, lambda gcmd: None)
        options = {"heater": "extruder"}
        if sensors:
            sensor_name = "filament_switch_sensor %s_sensor" % name.lower()
            sensor = FakeFilamentSensor(
                enabled=True,
                filament_detected=tool_states[name]["loaded"],
            )
            printer.add_object(sensor_name, sensor)
            sensor_objects[name] = sensor
            options["filament_sensor"] = sensor_name
        tool_fallback.load_config_prefix(
            prefix_config_factory("tool_fallback %s" % name, **options))
    printer.send_event("klippy:ready")
    if sensors:
        printer.reactor.advance(1.0)
    return extension, sensor_objects


def begin_runout(printer, extension, sensor, pause_owned="1"):
    extension._selected_physical_tool = "T0"
    extension._active_logical_tool = "T0"
    sensor.filament_detected = False
    printer.gcode.invoke_command(
        "TOOL_FALLBACK_RUNOUT",
        FakeGCmd({"TOOL": "T0", "PAUSE_OWNED": pause_owned}),
    )


def test_PAUSE_OWNED_parsing_is_strict(
        config_factory, prefix_config_factory, printer, tmp_path):
    printer.add_object("print_stats", FakePrintStats("paused"))
    extension, sensors = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    extension._selected_physical_tool = "T0"

    for value in ("true", "1.0", "2"):
        with pytest.raises(CommandError):
            printer.gcode.invoke_command(
                "TOOL_FALLBACK_RUNOUT",
                FakeGCmd({"TOOL": "T0", "PAUSE_OWNED": value}))

    assert sensors["T0"].filament_detected is True


def test_ownership_requires_explicit_claim_selected_tool_and_paused_state(
        config_factory, prefix_config_factory, printer, tmp_path):
    print_stats = FakePrintStats("printing")
    printer.add_object("print_stats", print_stats)
    extension, sensors = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    extension._selected_physical_tool = "T0"
    sensors["T0"].filament_detected = False

    printer.gcode.invoke_command(
        "TOOL_FALLBACK_RUNOUT",
        FakeGCmd({"TOOL": "T0", "PAUSE_OWNED": "1"}))

    checkpoint = extension._workflow_checkpoint
    assert checkpoint.stage == "debouncing"
    assert checkpoint.pause_owned is False


def test_owned_transient_recovery_resumes_once_after_confirmed_reinsertion(
        config_factory, prefix_config_factory, printer, tmp_path):
    printer.add_object("print_stats", FakePrintStats("paused"))
    extension, sensors = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    begin_runout(printer, extension, sensors["T0"])

    printer.reactor.advance(0.5)
    sensors["T0"].filament_detected = True
    printer.gcode.invoke_command(
        "TOOL_FALLBACK_INSERT", FakeGCmd({"TOOL": "T0"}))
    printer.reactor.advance(1.0)
    printer.reactor.advance(1.0)

    assert extension._workflow_checkpoint is None
    assert printer.gcode.script_events == ["RESUME"]
    assert extension.state.tools["T0"].loaded is True
    assert extension.state.tools["T0"].failed is False


def test_user_owned_transient_recovery_never_resumes(
        config_factory, prefix_config_factory, printer, tmp_path):
    printer.add_object("print_stats", FakePrintStats("paused"))
    extension, sensors = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    begin_runout(printer, extension, sensors["T0"], pause_owned="0")

    sensors["T0"].filament_detected = True
    printer.gcode.invoke_command(
        "TOOL_FALLBACK_INSERT", FakeGCmd({"TOOL": "T0"}))
    printer.reactor.advance(1.0)

    assert extension._workflow_checkpoint is None
    assert printer.gcode.script_events == []


def test_confirmed_runout_persists_failure_before_handoff(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    printer.add_object("print_stats", FakePrintStats("paused"))
    extension, sensors = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    observed = []

    def observe(checkpoint):
        observed.append((
            extension.state.tools["T0"].loaded,
            extension.state.tools["T0"].failed,
            checkpoint.stage,
        ))

    monkeypatch.setattr(extension, "_on_confirmed_runout", observe)
    begin_runout(printer, extension, sensors["T0"])

    assert observed == []
    printer.reactor.advance(1.0)

    assert observed == [(False, True, "confirmed_runout")]
    assert extension._workflow_checkpoint.stage == "confirmed_runout"


def test_conflicting_runout_does_not_replace_active_pending_workflow(
        config_factory, prefix_config_factory, printer, tmp_path):
    states = {
        "T0": tool_state(),
        "T1": tool_state(),
    }
    printer.add_object("print_stats", FakePrintStats("paused"))
    extension, sensors = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        states)
    begin_runout(printer, extension, sensors["T0"])
    original = extension._workflow_checkpoint
    sensors["T1"].filament_detected = False

    printer.gcode.invoke_command(
        "TOOL_FALLBACK_RUNOUT",
        FakeGCmd({"TOOL": "T1", "PAUSE_OWNED": "1"}))

    assert extension._workflow_checkpoint is original
    assert any("another tool fallback workflow is active" in response
               for response in printer.gcode.responses)
