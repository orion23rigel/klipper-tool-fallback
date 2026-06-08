import pytest

from conftest import CommandError, FakeFilamentSensor, FakeGCmd, FakePrintStats
from klippy.extras import tool_fallback
from klippy.extras.tool_fallback_state import FallbackState, StateStore


def load_extension(config_factory, prefix_config_factory, printer, state_path,
                   tool_states=None, sensor=None):
    if tool_states is not None:
        StateStore(str(state_path)).save(FallbackState.from_dict({
            "version": 1,
            "tools": tool_states,
            "mappings": {name: name for name in tool_states},
        }))
    extension = tool_fallback.load_config(
        config_factory(state_path=str(state_path)))
    printer.add_object("tool_fallback", extension)
    names = tuple(tool_states or {"T0": None, "T1": None})
    for name in names:
        printer.gcode.register_command(name, lambda gcmd: None)
        options = {"heater": "extruder"}
        if sensor is not None:
            sensor_name = "filament_switch_sensor %s_sensor" % name.lower()
            printer.add_object(sensor_name, sensor)
            options["filament_sensor"] = sensor_name
        tool_fallback.load_config_prefix(
            prefix_config_factory("tool_fallback %s" % name, **options))
    printer.send_event("klippy:ready")
    return extension


def tool_state(loaded=True, purged=False, failed=False):
    return {
        "loaded": loaded,
        "purged": purged,
        "failed": failed,
        "backups": [],
    }


def test_PURGE_TOOL_invokes_distinct_adapter_once_and_publishes_after_success(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        {"T0": tool_state()})

    printer.gcode.invoke_command("PURGE_TOOL", FakeGCmd({"TOOL": "T0"}))

    assert printer.gcode.script_events == ["_TOOL_FALLBACK_PURGE TOOL=T0"]
    assert extension.state.tools["T0"].purged is True
    assert printer.gcode.commands["PURGE_TOOL"] == extension.cmd_PURGE_TOOL


def test_PURGE_TOOL_adapter_failure_leaves_tool_unpurged(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        {"T0": tool_state()})
    printer.gcode.inject_script_failure(
        "_TOOL_FALLBACK_PURGE TOOL=T0", CommandError("adapter failed"))

    with pytest.raises(CommandError, match="adapter failed"):
        printer.gcode.invoke_command("PURGE_TOOL", FakeGCmd({"TOOL": "T0"}))

    assert extension.state.tools["T0"].purged is False


def test_PURGE_TOOL_persistence_failure_leaves_published_tool_unpurged(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        {"T0": tool_state()})
    original = extension.state

    def fail_save(candidate):
        raise OSError("purge save failed")

    monkeypatch.setattr(extension._state_store, "save", fail_save)

    with pytest.raises(CommandError, match="purge save failed"):
        printer.gcode.invoke_command("PURGE_TOOL", FakeGCmd({"TOOL": "T0"}))

    assert extension.state is original
    assert extension.state.tools["T0"].purged is False


def test_PURGE_TOOL_and_MARK_TOOL_PURGED_reject_known_unloaded(
        config_factory, prefix_config_factory, printer, tmp_path):
    sensor = FakeFilamentSensor(enabled=True, filament_detected=False)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        {"T0": tool_state(loaded=False)}, sensor=sensor)
    printer.reactor.advance(1.0)

    for command in ("PURGE_TOOL", "MARK_TOOL_PURGED"):
        with pytest.raises(CommandError, match="confirms unloaded"):
            printer.gcode.invoke_command(command, FakeGCmd({"TOOL": "T0"}))

    assert extension.state.tools["T0"].purged is False
    assert printer.gcode.script_events == []


@pytest.mark.parametrize("command", ["PURGE_TOOL", "MARK_TOOL_PURGED"])
def test_unknown_authority_purge_commands_warn_and_allow(
        command, config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        {"T0": tool_state(loaded=False)})
    gcmd = FakeGCmd({"TOOL": "T0"})

    printer.gcode.invoke_command(command, gcmd)

    assert any("sensor authority is unknown" in response
               for response in gcmd.responses)
    assert extension.state.tools["T0"].loaded is True
    assert extension.state.tools["T0"].purged is True


def test_MARK_TOOL_commands_are_no_op_aware_and_do_not_run_adapter(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        {"T0": tool_state(loaded=True, purged=True)})

    def reject_save(candidate):
        raise AssertionError("exact no-op attempted persistence")

    monkeypatch.setattr(extension._state_store, "save", reject_save)
    printer.gcode.invoke_command(
        "MARK_TOOL_PURGED", FakeGCmd({"TOOL": "T0"}))

    assert printer.gcode.script_events == []


def test_manual_purge_authorization_allows_inactive_but_rejects_selected_printing(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        {"T0": tool_state(), "T1": tool_state()})
    extension._selected_physical_tool = "T0"
    printer.add_object("print_stats", FakePrintStats("printing"))

    printer.gcode.invoke_command(
        "MARK_TOOL_PURGED", FakeGCmd({"TOOL": "T1"}))
    with pytest.raises(CommandError, match="only available while paused"):
        printer.gcode.invoke_command(
            "MARK_TOOL_PURGED", FakeGCmd({"TOOL": "T0"}))

    printer.objects["print_stats"].set_state("paused")
    printer.gcode.invoke_command(
        "MARK_TOOL_PURGED", FakeGCmd({"TOOL": "T0"}))

    assert extension.state.tools["T0"].purged is True
    assert extension.state.tools["T1"].purged is True


def test_MARK_TOOL_UNPURGED_persists_without_running_adapter(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        {"T0": tool_state(loaded=True, purged=True)})

    printer.gcode.invoke_command(
        "MARK_TOOL_UNPURGED", FakeGCmd({"TOOL": "T0"}))

    assert extension.state.tools["T0"].purged is False
    assert printer.gcode.script_events == []


def test_unrelated_scripts_and_manual_extrusion_never_change_purge_state(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        {"T0": tool_state()})

    printer.gcode.run_script_from_command("G1 E10")
    printer.gcode.run_script_from_command("UNRELATED_MACRO")

    assert extension.state.tools["T0"].purged is False
