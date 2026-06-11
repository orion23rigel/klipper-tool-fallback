import pytest

from conftest import CommandError, FakeGCmd, FakePrefixConfig, FakePrintStats
from klippy.extras import tool_fallback
from klippy.extras.tool_fallback import resolve_backup_graph
from klippy.extras.tool_fallback_state import StateStore


DEFAULTS = {
    "T0": ("T1", "T2"),
    "T1": ("T2",),
    "T2": (),
}


def load_extension(
        config_factory, prefix_config_factory, printer, state_path,
        defaults=DEFAULTS, events=None):
    events = events if events is not None else []
    extension = tool_fallback.load_config(
        config_factory(state_path=str(state_path)))
    printer.add_object("tool_fallback", extension)
    for name, backups in defaults.items():
        printer.gcode.register_command(
            name, lambda gcmd, selected=name: events.append(selected))
        tool_fallback.load_config_prefix(prefix_config_factory(
            "tool_fallback %s" % name,
            filament_sensor="filament_switch_sensor %s_sensor" % name.lower(),
            heater="extruder",
            backups=",".join(backups),
        ))
    printer.send_event("klippy:ready")
    return extension


def invoke(printer, command, **params):
    gcmd = FakeGCmd(params)
    printer.gcode.invoke_command(command, gcmd)
    return gcmd


def policies(state):
    return {
        tool: value.backups for tool, value in state.tools.items()
    }


def test_backup_commands_are_registered(printer, config_factory, tmp_path):
    extension = tool_fallback.load_config(
        config_factory(state_path=str(tmp_path / "state.json")))

    assert extension is not None
    assert {
        "SET_TOOL_BACKUPS", "RESTORE_TOOL_BACKUPS", "RESET_TOOL_BACKUPS",
    } <= set(printer.gcode.commands)


def test_set_reorders_and_clears_policy_on_disk(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path)

    reordered = invoke(
        printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS=" T2, T1 ")
    cleared = invoke(
        printer, "SET_TOOL_BACKUPS", TOOL="T1", BACKUPS="")

    assert extension.state.tools["T0"].backups == ("T2", "T1")
    assert extension.state.tools["T1"].backups == ()
    assert StateStore(str(path)).load() == extension.state
    assert reordered.responses == ["Tool T0 backups persisted: T2,T1"]
    assert cleared.responses == ["Tool T1 backups persisted: (empty)"]


def test_restore_one_and_reset_all_use_configured_defaults_with_one_reset_save(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    invoke(printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS="T2")
    restored = invoke(printer, "RESTORE_TOOL_BACKUPS", TOOL="T0")
    invoke(printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS="")
    invoke(printer, "SET_TOOL_BACKUPS", TOOL="T1", BACKUPS="")
    saves = []
    real_save = extension._state_store.save

    def count_save(candidate):
        saves.append(candidate)
        return real_save(candidate)

    monkeypatch.setattr(extension._state_store, "save", count_save)

    reset = invoke(printer, "RESET_TOOL_BACKUPS")

    assert restored.responses == ["Tool T0 backups persisted: T1,T2"]
    assert policies(extension.state) == DEFAULTS
    assert len(saves) == 1
    assert reset.responses == [
        "All tool backups persisted: T0=T1,T2; T1=T2; T2=(empty)"
    ]


@pytest.mark.parametrize("print_state", ["printing", "paused"])
def test_immediate_backup_changes_are_available_while_printing_or_paused(
        print_state, config_factory, prefix_config_factory, printer, tmp_path):
    printer.add_object("print_stats", FakePrintStats(print_state))
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")

    invoke(printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS="T2")

    assert extension.state.tools["T0"].backups == ("T2",)
    assert printer.gcode.script_events == []


@pytest.mark.parametrize(("backups", "message"), [
    ("T1,", "empty entries"),
    ("T1,,T2", "empty entries"),
    ("T9", "configured canonical tools"),
    ("t1", "configured canonical tools"),
    ("T1,T1", "duplicate backup"),
    ("T0", "reference itself"),
])
def test_set_strictly_rejects_invalid_complete_lists(
        backups, message, config_factory, prefix_config_factory, printer,
        tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    original = extension.state

    with pytest.raises(CommandError, match=message):
        invoke(printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS=backups)

    assert extension.state is original


@pytest.mark.parametrize(("command", "params"), [
    ("SET_TOOL_BACKUPS", {"TOOL": "T0", "BACKUPS": "T1,T2"}),
    ("RESTORE_TOOL_BACKUPS", {"TOOL": "T0"}),
    ("RESET_TOOL_BACKUPS", {}),
])
def test_exact_no_ops_report_no_write_and_do_not_save(
        command, params, config_factory, prefix_config_factory, printer,
        tmp_path, monkeypatch):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")

    def reject_save(candidate):
        raise AssertionError("no-op backup command attempted persistence")

    monkeypatch.setattr(extension._state_store, "save", reject_save)

    gcmd = invoke(printer, command, **params)

    assert "no write" in gcmd.responses[0]


def test_failed_save_does_not_publish_or_change_disk(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path)
    original = extension.state
    disk_before = StateStore(str(path)).load()

    def fail_save(candidate):
        raise OSError("injected backup save failure")

    monkeypatch.setattr(extension._state_store, "save", fail_save)

    with pytest.raises(CommandError, match="backup save failure"):
        invoke(printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS="T2,T1")

    assert extension.state is original
    assert StateStore(str(path)).load() == disk_before


def test_changed_backup_command_saves_once_before_publication(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    original = extension.state
    saves = []
    real_save = extension._state_store.save

    def observe_save(candidate):
        assert extension.state is original
        saves.append(candidate)
        return real_save(candidate)

    monkeypatch.setattr(extension._state_store, "save", observe_save)

    invoke(printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS="T2,T1")

    assert len(saves) == 1
    assert extension.state is saves[0]


def test_backup_change_preserves_unrelated_state_and_performs_no_hardware_action(
        config_factory, prefix_config_factory, printer, tmp_path):
    events = []
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        events=events)
    before = extension.state

    invoke(printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS="T2")

    assert extension.state.tools["T1"] is before.tools["T1"]
    assert extension.state.tools["T2"] is before.tools["T2"]
    assert extension.state.mappings == before.mappings
    assert extension._selected_physical_tool is None
    assert events == []
    assert printer.gcode.script_events == []
    assert printer.heaters.events == []


def test_changed_priority_affects_only_a_later_resolver_call(
        config_factory, prefix_config_factory, printer, tmp_path):
    events = []
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        events=events)
    candidate = extension.state.with_filament_loaded("T1")
    candidate = candidate.with_filament_loaded("T2")
    extension._persist_state(candidate)

    invoke(printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS="T2,T1")

    assert events == []
    assert resolve_backup_graph(extension.state, "T0").candidate == "T2"


@pytest.mark.parametrize("active", ["workflow", "transition"])
def test_non_immediate_contexts_are_rejected_without_action_until_queue_plan(
        active, config_factory, prefix_config_factory, printer, tmp_path):
    events = []
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        events=events)
    if active == "workflow":
        extension._workflow_checkpoint = tool_fallback.WorkflowCheckpoint(
            "automatic_fallback", "heating", 1)
    else:
        extension._transition_active = True
    original = extension.state

    with pytest.raises(CommandError, match="cannot apply immediately"):
        invoke(printer, "SET_TOOL_BACKUPS", TOOL="T0", BACKUPS="T2")

    assert extension.state is original
    assert events == []
    assert printer.gcode.script_events == []
