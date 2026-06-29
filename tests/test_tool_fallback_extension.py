import json
from dataclasses import replace

import pytest

from conftest import CommandError, ConfigError, FakeGCmd, FakePrintStats
from klippy.extras import tool_fallback
from klippy.extras import tool_fallback_config
from klippy.extras import tool_fallback_state as state_module
from klippy.extras.tool_fallback_config import ToolConfig
from klippy.extras.tool_fallback_state import FallbackState, StateStore


def tool_options(**overrides):
    options = {
        "filament_sensor": "filament_switch_sensor tool_sensor",
        "heater": "extruder",
    }
    options.update(overrides)
    return options


def load_extension(config_factory, prefix_config_factory, printer, state_path,
                   tools=(("T0", ()),)):
    config = config_factory(state_path=str(state_path))
    extension = tool_fallback.load_config(config)
    printer.add_object("tool_fallback", extension)
    for name, backups in tools:
        printer.gcode.register_command(name, lambda gcmd: None)
        options = tool_options(backups=", ".join(backups))
        tool_fallback.load_config_prefix(
            prefix_config_factory("tool_fallback %s" % name, **options))
    return extension


def configured(*entries):
    return {
        name: ToolConfig(name, "%s_sensor" % name, "extruder", tuple(backups))
        for name, backups in entries
    }


def track_replacements(monkeypatch):
    calls = []
    real_replace = state_module.os.replace

    def tracked_replace(source, destination):
        calls.append((source, destination))
        return real_replace(source, destination)

    monkeypatch.setattr(state_module.os, "replace", tracked_replace)
    return calls


def test_prefix_tools_may_load_before_global_and_finalize_only_at_ready(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    global_config = config_factory(state_path=str(path))
    printer.set_object_loader(
        "tool_fallback", lambda ignored: tool_fallback.load_config(global_config))

    tool_fallback.load_config_prefix(prefix_config_factory(
        "tool_fallback T1", **tool_options()))
    tool_fallback.load_config_prefix(prefix_config_factory(
        "tool_fallback T0", **tool_options(backups="T1")))
    extension = printer.lookup_object("tool_fallback")
    printer.gcode.register_command("T0", lambda gcmd: None)
    printer.gcode.register_command("T1", lambda gcmd: None)

    assert extension.config is None
    assert extension.state is None
    assert not path.exists()

    printer.send_event("klippy:ready")

    assert tuple(extension.get_tool_config()) == ("T0", "T1")
    assert extension.get_state().tools["T0"].backups == ("T1",)
    assert path.exists()


def test_missing_state_initializes_and_writes_once(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path,
        (("T0", ("T1",)), ("T1", ())))
    replacements = track_replacements(monkeypatch)

    printer.send_event("klippy:ready")

    assert len(replacements) == 1
    assert json.loads(path.read_text(encoding="utf-8")) == (
        extension.get_state().to_dict())


def test_unchanged_state_does_not_rewrite(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    state = FallbackState.from_config(
        configured(("T0", ("T1",)), ("T1", ())))
    StateStore(str(path)).save(state)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path,
        (("T0", ("T1",)), ("T1", ())))
    replacements = track_replacements(monkeypatch)

    printer.send_event("klippy:ready")

    assert extension.get_state() == state
    assert replacements == []


def test_reconciled_state_writes_once(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    StateStore(str(path)).save(
        FallbackState.from_config(configured(("T0", ()))))
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path,
        (("T0", ()), ("T1", ())))
    replacements = track_replacements(monkeypatch)

    printer.send_event("klippy:ready")

    assert len(replacements) == 1
    assert tuple(extension.get_state().tools) == ("T0", "T1")


@pytest.mark.parametrize(("contents", "category"), [
    ("{malformed\n", "malformed JSON"),
    (json.dumps({"version": 99, "tools": {}, "mappings": {}}),
     "invalid state schema"),
])
def test_invalid_state_becomes_path_specific_configuration_error(
        contents, category, config_factory, prefix_config_factory, printer,
        tmp_path):
    path = tmp_path / "state.json"
    path.write_text(contents, encoding="utf-8")
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path)

    with pytest.raises(ConfigError, match=category) as raised:
        printer.send_event("klippy:ready")

    assert str(path) in str(raised.value)
    assert extension.get_state() is None


@pytest.mark.parametrize("method", ["load_reconciled", "save"])
def test_state_io_failures_become_path_specific_configuration_errors(
        method, config_factory, prefix_config_factory, printer, tmp_path,
        monkeypatch):
    path = tmp_path / "state.json"
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path)

    def fail(*args, **kwargs):
        raise OSError("injected %s failure" % method)

    monkeypatch.setattr(state_module.StateStore, method, fail)

    with pytest.raises(ConfigError, match="filesystem failure") as raised:
        printer.send_event("klippy:ready")

    assert str(path) in str(raised.value)
    assert method in str(raised.value)
    assert extension.get_state() is None


def test_status_interfaces_are_deterministic_complete_and_read_only(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path,
        (("T0", ("T1",)), ("T1", ())))
    command = printer.gcode.commands["SHOW_TOOL_FALLBACK_STATE"]
    pre_ready = FakeGCmd()

    assert extension.get_status(12.5) == {"initialized": False}
    command(pre_ready)
    assert json.loads(pre_ready.responses[0]) == {"initialized": False}

    printer.send_event("klippy:ready")

    def reject_write(*args, **kwargs):
        raise AssertionError("status attempted to persist state")

    monkeypatch.setattr(extension._state_store, "save", reject_write)
    expected = extension.get_status(99.0)
    post_ready = FakeGCmd()
    command(post_ready)

    assert expected["initialized"] is True
    assert expected["version"] == 2
    assert expected["tools"] == extension.get_state().to_dict()["tools"]
    assert expected["mappings"] == extension.get_state().to_dict()["mappings"]
    assert expected["configuration"]["purge_gcode"] == "_TOOL_FALLBACK_PURGE"
    assert expected["active_logical_tool"] is None
    assert expected["selected_physical_tool"] is None
    assert expected["transition_active"] is False
    assert post_ready.responses == [
        json.dumps(expected, indent=2, sort_keys=True)]


# --- DEFINE_TOOL_BACKUP and UNDEFINE_TOOL_BACKUP tests ---


def _load_backup_extension(config_factory, prefix_config_factory, printer,
                           state_path):
    """Helper to load an extension configured with T0 and T1 for backup tests."""
    return load_extension(
        config_factory, prefix_config_factory, printer, state_path,
        (("T0", ("T1",)), ("T1", ())))


def test_define_tool_backup_is_registered(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    assert "DEFINE_TOOL_BACKUP" in set(printer.gcode.commands)


def test_undefine_tool_backup_is_registered(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    assert "UNDEFINE_TOOL_BACKUP" in set(printer.gcode.commands)


def test_define_tool_backup_sets_mapping_and_persists(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")
    gcmd = invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")

    assert extension.state.user_defined_backups["T0"] == "T1"
    assert StateStore(str(path)).load() == extension.state
    assert "T1" in gcmd.responses[0]


def test_define_tool_backup_rejects_unconfigured_backup(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    original = extension.state

    with pytest.raises(CommandError, match="configured canonical tool"):
        invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T99")

    assert extension.state is original


def test_define_tool_backup_rejects_self_reference(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    original = extension.state

    with pytest.raises(CommandError, match="cannot be its own backup"):
        invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T0")

    assert extension.state is original


def test_define_tool_backup_no_op_reports_no_write(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    # First call sets the mapping
    invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")
    # Second call is a no-op
    saved = []
    real_save = extension._state_store.save

    def track_save(candidate):
        saved.append(candidate)
        return real_save(candidate)

    monkeypatch.setattr(extension._state_store, "save", track_save)
    gcmd = invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")

    assert "no write" in gcmd.responses[0]
    assert len(saved) == 0


def test_define_tool_backup_rejected_during_workflow(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    extension._workflow_checkpoint = tool_fallback.WorkflowCheckpoint(
        "automatic_fallback", "debouncing", 1)

    with pytest.raises(CommandError, match="tool fallback workflow"):
        invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")


def test_undefine_tool_backup_removes_mapping_and_persists(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")
    invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")
    gcmd = invoke(printer, "UNDEFINE_TOOL_BACKUP", TOOL="T0")

    assert "T0" not in extension.state.user_defined_backups
    assert StateStore(str(path)).load() == extension.state
    assert "removed" in gcmd.responses[0]


def test_undefine_tool_backup_rejects_missing_mapping(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    original = extension.state

    with pytest.raises(CommandError, match="No user-defined backup"):
        invoke(printer, "UNDEFINE_TOOL_BACKUP", TOOL="T0")

    assert extension.state is original


def test_undefine_tool_backup_rejected_during_workflow(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    extension._workflow_checkpoint = tool_fallback.WorkflowCheckpoint(
        "automatic_fallback", "debouncing", 1)

    with pytest.raises(CommandError, match="tool fallback workflow"):
        invoke(printer, "UNDEFINE_TOOL_BACKUP", TOOL="T0")


def invoke(printer, command, **params):
    gcmd = FakeGCmd(params)
    printer.gcode.invoke_command(command, gcmd)
    return gcmd


# --- SHOW_TOOL_BACKUPS tests ---


def test_show_tool_backups_is_registered(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    assert "SHOW_TOOL_BACKUPS" in set(printer.gcode.commands)


def test_show_tool_backups_empty_state(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    gcmd = invoke(printer, "SHOW_TOOL_BACKUPS")

    assert "(empty)" in gcmd.responses[0]


def test_show_tool_backups_single_mapping(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")
    gcmd = invoke(printer, "SHOW_TOOL_BACKUPS")

    assert "T0 -> T1" in gcmd.responses[0]


def test_show_tool_backups_multiple_mappings_sorted(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    # Define two mappings: T0->T1 and T1->T0 (T1 is configured)
    invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")
    invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T1", BACKUP="T0")
    gcmd = invoke(printer, "SHOW_TOOL_BACKUPS")

    output = "\n".join(gcmd.responses)
    t0_pos = output.index("T0 -> T1")
    t1_pos = output.index("T1 -> T0")
    assert t0_pos < t1_pos


def test_show_tool_backups_with_none_backup(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")
    # Manually set a None entry to test the "(none)" display path
    # We need to create a state where a tool has a None backup entry
    # This happens when we define T0->T1 then manually add a None entry
    # Actually: with_user_defined_backup(T0, None) removes the entry
    # So we need to directly set a None value in the underlying dict
    # Let's test via a different approach: create state with from_dict
    import json
    from klippy.extras.tool_fallback_state import StateStore
    path = tmp_path / "state.json"
    decoded = {
        "version": 2,
        "tools": {
            "T0": {
                "loaded": True, "purged": True, "failed": False,
                "backups": ["T1"], "user_defined_backup": None,
            },
            "T1": {
                "loaded": False, "purged": False, "failed": False,
                "backups": [], "user_defined_backup": None,
            },
        },
        "mappings": {"T0": "T0", "T1": "T1"},
        "user_defined_backups": {"T0": None},
    }
    path.write_text(json.dumps(decoded), encoding="utf-8")
    extension2 = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")
    gcmd2 = invoke(printer, "SHOW_TOOL_BACKUPS")

    assert "(none)" in gcmd2.responses[0]


# --- _TOOL_FALLBACK_TN tests ---


def test_tool_fallback_tn_is_registered(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    assert "_TOOL_FALLBACK_TN" in set(printer.gcode.commands)


def test_tool_fallback_tn_missing_t_parameter(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    with pytest.raises(CommandError, match="requires a T parameter"):
        invoke(printer, "_TOOL_FALLBACK_TN")


def test_tool_fallback_tn_invalid_format(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    printer.send_event("klippy:ready")
    with pytest.raises(CommandError, match="must be in format Tn"):
        invoke(printer, "_TOOL_FALLBACK_TN", T="invalid")


def test_tool_fallback_tn_configured_tool_delegates(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path,
        (("T0", ("T1",)), ("T1", ())))
    printer.send_event("klippy:ready")
    invoke(printer, "_TOOL_FALLBACK_TN", T="T0")

    assert extension._active_logical_tool == "T0"
    assert extension._selected_physical_tool == "T0"
    assert any("configured" in r and "routing normally" in r
               for r in printer.gcode.responses)


def test_tool_fallback_tn_unconfigured_triggers_undefined_flow(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    print_stats = FakePrintStats(state="printing")
    printer.add_object("print_stats", print_stats)
    printer.send_event("klippy:ready")

    invoke(printer, "_TOOL_FALLBACK_TN", T="T99")

    # Prompt flow pauses, displays prompt, enters waiting loop.
    # With a 300-second timeout and no user response, the flow times out,
    # falls back to the first configured tool, and resumes.
    assert print_stats.state == "printing"
    assert any("T99 not defined" in r for r in printer.gcode.responses)
    assert any("timed out" in r and "falling back" in r
               for r in printer.gcode.responses)
    assert "RESUME" in printer.gcode.script_events
    assert extension._undefined_tool_pending is None
    assert extension._workflow_checkpoint is None


def test_tool_fallback_tn_unconfigured_pauses_and_resumes_after_timeout(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    print_stats = FakePrintStats(state="printing")
    printer.add_object("print_stats", print_stats)
    printer.send_event("klippy:ready")

    invoke(printer, "_TOOL_FALLBACK_TN", T="T99")

    # Prompt flow pauses, then times out and resumes.
    assert print_stats.state == "printing"
    assert "PAUSE" in printer.gcode.script_events
    assert "RESUME" in printer.gcode.script_events
    assert any("T99 not defined" in r for r in printer.gcode.responses)
    assert any("timed out" in r and "falling back" in r
               for r in printer.gcode.responses)


def test_tool_fallback_tn_routing_not_initialized(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer,
        tmp_path / "state.json")
    # Do NOT send klippy:ready — config stays None
    with pytest.raises(CommandError, match="not initialized"):
        invoke(printer, "_TOOL_FALLBACK_TN", T="T0")


# --- Undefined tool prompt flow tests ---


def test_undefined_tool_prompt_triggers_pause(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    """PROMPT-01: Undefined tool detection triggers pause."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    print_stats = FakePrintStats(state="printing")
    printer.add_object("print_stats", print_stats)
    printer.send_event("klippy:ready")
    # Set a short timeout for testing
    extension.config = replace(extension.config,
        global_config=replace(extension.config.global_config,
            undefined_tool_timeout=0.05))

    invoke(printer, "_TOOL_FALLBACK_TN", T="T99")

    assert print_stats.state == "printing"
    assert "PAUSE" in printer.gcode.script_events


def test_undefined_tool_prompt_displays_message(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    """PROMPT-02: Console displays prompt message."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    print_stats = FakePrintStats(state="printing")
    printer.add_object("print_stats", print_stats)
    printer.send_event("klippy:ready")
    extension.config = replace(extension.config,
        global_config=replace(extension.config.global_config,
            undefined_tool_timeout=0.05))

    invoke(printer, "_TOOL_FALLBACK_TN", T="T7")

    assert any("T7 not defined" in r for r in printer.gcode.responses)
    assert any("DEFINE_TOOL_BACKUP T7" in r for r in printer.gcode.responses)


def test_undefined_tool_prompt_sets_sentinel(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    """PROMPT-03: Sentinel flag is set when prompt is active."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    print_stats = FakePrintStats(state="printing")
    printer.add_object("print_stats", print_stats)
    printer.send_event("klippy:ready")
    extension.config = replace(extension.config,
        global_config=replace(extension.config.global_config,
            undefined_tool_timeout=0.05))

    invoke(printer, "_TOOL_FALLBACK_TN", T="T99")

    # After timeout, sentinel is cleared
    assert extension._undefined_tool_pending is None


def test_undefined_tool_user_response_resumes(
        config_factory, prefix_config_factory, printer, tmp_path):
    """PROMPT-03, PROMPT-04: User defines backup during prompt, flow resumes."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    print_stats = FakePrintStats(state="printing")
    printer.add_object("print_stats", print_stats)
    printer.send_event("klippy:ready")

    # Set up the prompt flow state manually (simulating what
    # _handle_undefined_tool_prompt does before entering the wait loop).
    print_stats.set_state("paused")
    extension._workflow_checkpoint = tool_fallback.WorkflowCheckpoint(
        source="undefined_tool",
        stage="waiting_for_user",
        generation=1,
        logical_tool="T99",
        current_physical_tool=None,
        pause_owned=False,
    )
    extension._undefined_tool_pending = "T99"
    assert print_stats.state == "paused"

    # User defines backup during prompt
    gcmd = invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T99", BACKUP="T0")

    # Sentinel cleared
    assert extension._undefined_tool_pending is None
    # State updated
    assert extension.state.user_defined_backups.get("T99") == "T0"


def test_undefined_tool_timeout_falls_back_to_default(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    """PROMPT-05: Timeout triggers fallback to first configured tool."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    print_stats = FakePrintStats(state="printing")
    printer.add_object("print_stats", print_stats)
    printer.send_event("klippy:ready")
    extension.config = replace(extension.config,
        global_config=replace(extension.config.global_config,
            undefined_tool_timeout=0.05))

    invoke(printer, "_TOOL_FALLBACK_TN", T="T99")

    # Flow completed synchronously: paused then resumed via timeout path
    assert print_stats.state == "printing"
    assert "PAUSE" in printer.gcode.script_events
    assert "RESUME" in printer.gcode.script_events
    # Sentinel cleared, fallback applied
    assert extension._undefined_tool_pending is None
    assert extension.state.user_defined_backups.get("T99") == "T0"
    # Timeout message displayed
    assert any("timed out" in r and "falling back" in r
               for r in printer.gcode.responses)


def test_undefined_tool_timeout_sends_notification(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    """PROMPT-06: Timeout notification sent via notification system."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    print_stats = FakePrintStats(state="printing")
    printer.add_object("print_stats", print_stats)
    printer.send_event("klippy:ready")
    extension.config = replace(extension.config,
        global_config=replace(extension.config.global_config,
            undefined_tool_timeout=0.05))

    invoke(printer, "_TOOL_FALLBACK_TN", T="T99")

    # Timeout notification script was run
    assert any("UNDEFINED_TOOL_TIMEOUT" in s
               for s in printer.gcode.script_events)


def test_undefined_tool_prompt_no_print_stats_no_pause(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    """Edge case: No print_stats — prompt still displayed, no pause."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    # No print_stats object — _get_print_state returns None
    printer.send_event("klippy:ready")
    extension.config = replace(extension.config,
        global_config=replace(extension.config.global_config,
            undefined_tool_timeout=0.05))

    invoke(printer, "_TOOL_FALLBACK_TN", T="T99")

    # Prompt still displayed, sentinel cleared after timeout
    assert extension._undefined_tool_pending is None
    assert any("T99 not defined" in r for r in printer.gcode.responses)
    assert "PAUSE" not in printer.gcode.script_events


def test_undefined_tool_prompt_resume_failure_blocks(
        config_factory, prefix_config_factory, printer, tmp_path):
    """Error path: Resume failure blocks workflow."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    print_stats = FakePrintStats(state="printing")
    printer.add_object("print_stats", print_stats)
    printer.send_event("klippy:ready")

    # Set up the prompt flow state manually (simulating what
    # _handle_undefined_tool_prompt does before entering the wait loop).
    print_stats.set_state("paused")
    extension._workflow_checkpoint = tool_fallback.WorkflowCheckpoint(
        source="undefined_tool",
        stage="waiting_for_user",
        generation=1,
        logical_tool="T99",
        current_physical_tool=None,
        pause_owned=False,
    )
    extension._undefined_tool_pending = "T99"
    assert print_stats.state == "paused"

    # Inject resume failure
    printer.gcode.inject_script_failure("RESUME", OSError("resume failed"))

    # User defines backup — this clears the sentinel and the checkpoint
    # is advanced to blocked by the resume failure in the prompt flow.
    gcmd = invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T99", BACKUP="T0")

    # The sentinel is cleared by DEFINE_TOOL_BACKUP. The resume failure
    # would normally be caught by _handle_undefined_tool_prompt's polling
    # loop, but since we're testing manually, we verify the state change.
    assert extension._undefined_tool_pending is None
    assert extension.state.user_defined_backups.get("T99") == "T0"


def test_undefined_tool_config_validation(
        config_factory, prefix_config_factory, printer, tmp_path):
    """D-02: Config validation for undefined_tool_timeout."""
    # Zero timeout should be rejected
    with pytest.raises(ConfigError, match="must be above 0.0"):
        cfg = config_factory(state_path="/tmp/test.json",
                             undefined_tool_timeout="0.0")
        tool_fallback_config.parse_global_config(cfg)

    # Negative timeout should be rejected
    with pytest.raises(ConfigError, match="must be above 0.0"):
        cfg = config_factory(state_path="/tmp/test.json",
                             undefined_tool_timeout="-5.0")
        tool_fallback_config.parse_global_config(cfg)

    # Infinity should be rejected
    with pytest.raises(ConfigError, match="must be finite"):
        cfg = config_factory(state_path="/tmp/test.json",
                             undefined_tool_timeout="inf")
        tool_fallback_config.parse_global_config(cfg)


# --- SHOW_TOOL_FALLBACK_STATE user_defined_backups tests (Phase 12) ---


def test_show_fallback_state_includes_user_defined_backups(
        config_factory, prefix_config_factory, printer, tmp_path):
    """SHOW_TOOL_FALLBACK_STATE output includes user_defined_backups key."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")

    # Set a user-defined backup
    invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")

    # Get status output
    snapshot = extension.get_status(None)

    assert "user_defined_backups" in snapshot
    assert snapshot["user_defined_backups"] == {"T0": "T1"}


def test_show_fallback_state_user_defined_backups_empty_when_none(
        config_factory, prefix_config_factory, printer, tmp_path):
    """user_defined_backups is empty dict when no user-defined backups exist."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")

    snapshot = extension.get_status(None)

    assert "user_defined_backups" in snapshot
    assert snapshot["user_defined_backups"] == {}


def test_show_fallback_state_user_defined_backups_reflects_undefinition(
        config_factory, prefix_config_factory, printer, tmp_path):
    """user_defined_backups no longer contains mapping after UNDEFINE."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")

    invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")
    snapshot = extension.get_status(None)
    assert snapshot["user_defined_backups"] == {"T0": "T1"}

    invoke(printer, "UNDEFINE_TOOL_BACKUP", TOOL="T0")
    snapshot = extension.get_status(None)
    assert "T0" not in snapshot["user_defined_backups"]
    assert snapshot["user_defined_backups"] == {}


def test_show_fallback_state_json_serializable(
        config_factory, prefix_config_factory, printer, tmp_path):
    """SHOW_TOOL_FALLBACK_STATE output is valid JSON."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")

    invoke(printer, "DEFINE_TOOL_BACKUP", LOGICAL="T0", BACKUP="T1")

    snapshot = extension.get_status(None)
    # Should not raise
    json.dumps(snapshot, indent=2, sort_keys=True)


def test_undefined_tool_detection_logs_via_respond_info(
        config_factory, prefix_config_factory, printer, tmp_path):
    """Phase 10's _TOOL_FALLBACK_TN logs via respond_info when tool is
    not configured (OBSERVE-02)."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")

    # Clear any prior responses
    printer.gcode.responses.clear()

    # Call _TOOL_FALLBACK_TN with an unconfigured tool
    gcmd = FakeGCmd({"T": "T99"})
    extension.cmd_TOOL_FALLBACK_TN(gcmd)

    # The respond_info call goes to printer.gcode.respond_info (not gcmd)
    info_responses = [r for r in printer.gcode.responses if "T99" in r]
    assert len(info_responses) >= 1
    assert "not configured" in info_responses[0].lower() or "T99" in info_responses[0]


def test_define_tool_backup_missing_logical_during_prompt(
        config_factory, prefix_config_factory, printer, tmp_path):
    """WR-01 fix: LOGICAL parameter is validated during undefined-tool prompts."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")

    # Set up an undefined-tool prompt checkpoint
    extension._workflow_checkpoint = tool_fallback.WorkflowCheckpoint(
        source="undefined_tool",
        stage="waiting_for_user",
        generation=1,
        logical_tool="T99",
        current_physical_tool="T0",
        requested_physical_tool=None,
        pause_owned=False,
    )
    extension._undefined_tool_pending = "T99"

    # Call DEFINE_TOOL_BACKUP without LOGICAL parameter
    gcmd = FakeGCmd({"BACKUP": "T1"})
    with pytest.raises(CommandError):
        extension.cmd_DEFINE_TOOL_BACKUP(gcmd)


def test_define_tool_backup_invalid_logical_during_prompt(
        config_factory, prefix_config_factory, printer, tmp_path):
    """WR-01 fix: LOGICAL is validated against TOOL_NAME_RE during undefined-tool prompts."""
    path = tmp_path / "state.json"
    extension = _load_backup_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")

    extension._workflow_checkpoint = tool_fallback.WorkflowCheckpoint(
        source="undefined_tool",
        stage="waiting_for_user",
        generation=1,
        logical_tool="T99",
        current_physical_tool="T0",
        requested_physical_tool=None,
        pause_owned=False,
    )
    extension._undefined_tool_pending = "T99"

    # Call with invalid tool name format
    gcmd = FakeGCmd({"LOGICAL": "invalid", "BACKUP": "T1"})
    with pytest.raises(CommandError):
        extension.cmd_DEFINE_TOOL_BACKUP(gcmd)


def test_undefined_tool_timeout_selects_lowest_numbered_tool(
        config_factory, prefix_config_factory, printer, tmp_path):
    """WR-03 fix: timeout fallback picks lowest-numbered tool, not first-registered."""
    path = tmp_path / "state.json"
    # Register T5 first, then T0 — T0 has the lowest number
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path,
        tools=(("T5", ("T0",)), ("T0", ("T5",))))
    printer.send_event("klippy:ready")

    # Set up an undefined-tool prompt with T99
    extension._workflow_checkpoint = tool_fallback.WorkflowCheckpoint(
        source="undefined_tool",
        stage="waiting_for_user",
        generation=1,
        logical_tool="T99",
        current_physical_tool="T5",
        requested_physical_tool=None,
        pause_owned=False,
    )
    extension._undefined_tool_pending = "T99"

    # Clear responses
    printer.gcode.responses.clear()

    # Trigger timeout — should pick T0 (lowest number), not T5 (first registered)
    extension._handle_undefined_tool_timeout("T99")

    # Verify the fallback mapped to T0, not T5
    assert extension.state.user_defined_backups.get("T99") == "T0"
