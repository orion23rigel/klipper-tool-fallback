import pytest

from conftest import (CommandError, FakeFilamentSensor, FakeGCmd, FakePrintStats,
                      FakeSnapshotSequence)
from klippy.extras import tool_fallback
from klippy.extras.tool_fallback import resolve_backup_graph
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


def fallback_state(tool_states):
    return FallbackState.from_dict({
        "version": 1,
        "tools": tool_states,
        "mappings": {name: name for name in tool_states},
    })


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


def test_resolver_uses_depth_first_priority_and_traverses_failed_intermediary():
    state = fallback_state({
        "T0": tool_state(loaded=False, purged=False, failed=True,
                         backups=("T1", "T3")),
        "T1": tool_state(loaded=True, failed=True, backups=("T2",)),
        "T2": tool_state(),
        "T3": tool_state(),
    })

    result = resolve_backup_graph(state, "T0")

    assert result.candidate == "T2"
    assert result.evaluated == ("T1", "T2")
    assert result.failed == ("T1",)


def test_resolver_traverses_unloaded_intermediary_and_suppresses_duplicates():
    state = fallback_state({
        "T0": tool_state(loaded=False, purged=False, failed=True,
                         backups=("T1", "T2")),
        "T1": tool_state(loaded=False, purged=False, backups=("T2",)),
        "T2": tool_state(loaded=False, purged=False, backups=("T3",)),
        "T3": tool_state(),
    })

    result = resolve_backup_graph(state, "T0")

    assert result.candidate == "T3"
    assert result.evaluated == ("T1", "T2", "T3")
    assert result.unloaded == ("T1", "T2")


def test_resolver_contains_path_local_loop_and_continues_unrelated_branch():
    state = fallback_state({
        "T0": tool_state(loaded=False, purged=False, failed=True,
                         backups=("T1", "T3")),
        "T1": tool_state(loaded=False, purged=False, backups=("T2",)),
        "T2": tool_state(loaded=False, purged=False, backups=("T1",)),
        "T3": tool_state(),
    })

    result = resolve_backup_graph(state, "T0")

    assert result.candidate == "T3"
    assert result.evaluated == ("T1", "T2", "T3")
    assert result.looped == ("T0->T1->T2->T1",)


def test_resolver_uses_persisted_eligibility_despite_unknown_authority():
    state = fallback_state({
        "T0": tool_state(loaded=False, purged=False, failed=True,
                         backups=("T1",)),
        "T1": tool_state(),
    })

    result = resolve_backup_graph(state, "T0", unknown_authority=("T1",))

    assert result.candidate == "T1"
    assert result.unknown_authority_eligible == ("T1",)


def test_rescan_orchestration_requests_fresh_snapshot_once_after_exhaustion(
        config_factory, prefix_config_factory, printer, tmp_path):
    initial = fallback_state({
        "T0": tool_state(loaded=False, purged=False, failed=True,
                         backups=("T1",)),
        "T1": tool_state(loaded=False, purged=False),
    })
    refreshed = fallback_state({
        "T0": tool_state(loaded=False, purged=False, failed=True,
                         backups=("T1",)),
        "T1": tool_state(),
    })
    extension, _ = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        initial.to_dict()["tools"], sensors=False)
    snapshots = FakeSnapshotSequence(initial, refreshed)

    result = extension._resolve_backup_with_rescan("T0", snapshots)

    assert result.candidate == "T1"
    assert result.scan_count == 2
    assert snapshots.calls == 2


def test_rescan_orchestration_stops_after_exactly_two_exhausted_scans(
        config_factory, prefix_config_factory, printer, tmp_path):
    state = fallback_state({
        "T0": tool_state(loaded=False, purged=False, failed=True,
                         backups=("T1",)),
        "T1": tool_state(loaded=False, purged=False),
    })
    extension, _ = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        state.to_dict()["tools"], sensors=False)
    snapshots = FakeSnapshotSequence(state, state, state)

    result = extension._resolve_backup_with_rescan("T0", snapshots)

    assert result.candidate is None
    assert result.scan_count == 2
    assert result.evaluated == ("T1",)
    assert result.unloaded == ("T1",)
    assert snapshots.calls == 2
