import json

import pytest

from conftest import ConfigError, FakeGCmd
from klippy.extras import tool_fallback
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
    assert expected["version"] == 1
    assert expected["tools"] == extension.get_state().to_dict()["tools"]
    assert expected["mappings"] == extension.get_state().to_dict()["mappings"]
    assert expected["configuration"]["purge_gcode"] == "PURGE_TOOL"
    assert expected["active_logical_tool"] is None
    assert expected["selected_physical_tool"] is None
    assert expected["transition_active"] is False
    assert post_ready.responses == [
        json.dumps(expected, indent=2, sort_keys=True)]
