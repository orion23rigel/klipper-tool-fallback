import pytest

from conftest import CommandError, ConfigError
from klippy.extras import tool_fallback
from klippy.extras import tool_fallback_state as state_module


def tool_options(**overrides):
    options = {
        "filament_sensor": "filament_switch_sensor tool_sensor",
        "heater": "extruder",
    }
    options.update(overrides)
    return options


def load_extension(config_factory, prefix_config_factory, printer, state_path,
                   tools=("T0", "T1", "T2"), handlers=None):
    extension = tool_fallback.load_config(
        config_factory(state_path=str(state_path)))
    printer.add_object("tool_fallback", extension)
    handlers = handlers or {}
    for name in tools:
        if name in handlers:
            printer.gcode.register_command(name, handlers[name])
        tool_fallback.load_config_prefix(prefix_config_factory(
            "tool_fallback %s" % name, **tool_options()))
    return extension


def public_tool_handlers(printer, names):
    return {name: printer.gcode.commands[name]
            for name in names if name in printer.gcode.commands}


def physical_handler_spy(name, events, failure=None):
    def handler(gcmd):
        events.append({
            "handler": name,
            "command": gcmd.get_command(),
            "commandline": gcmd.get_commandline(),
            "rawparams": gcmd.get_raw_command_parameters(),
            "params": dict(gcmd.params),
        })
        if failure is not None:
            raise failure

    return handler


def test_synthetic_physical_command_exposes_clean_identity(printer):
    command = printer.gcode.create_gcode_command("T2", "T2", {})

    assert command.get_command() == "T2"
    assert command.get_commandline() == "T2"
    assert command.get_raw_command_parameters() == ""
    assert command.params == {}


def test_registered_physical_handler_can_be_invoked_and_observed(printer):
    events = []
    handler = physical_handler_spy("T2", events)
    printer.gcode.register_command("T2", handler)

    printer.gcode.invoke_command("T2")

    assert events == [{
        "handler": "T2",
        "command": "T2",
        "commandline": "T2",
        "rawparams": "",
        "params": {},
    }]


def test_registered_physical_handler_can_inject_failure(printer):
    error = CommandError("injected T2 failure")
    printer.gcode.register_command(
        "T2", physical_handler_spy("T2", [], failure=error))

    with pytest.raises(CommandError, match="injected T2 failure"):
        printer.gcode.invoke_command("T2")


@pytest.mark.parametrize("missing", ["T0", "T2"])
def test_missing_handler_blocks_startup_and_restores_originals(
        missing, config_factory, prefix_config_factory, printer, tmp_path):
    events = []
    handlers = {
        name: physical_handler_spy(name, events)
        for name in ("T0", "T1", "T2") if name != missing
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)

    with pytest.raises(ConfigError, match=missing):
        printer.send_event("klippy:ready")

    assert extension.state is None
    assert extension._state_store is None
    assert extension._physical_handlers is None
    assert public_tool_handlers(printer, ("T0", "T1", "T2")) == handlers


def test_capture_replaces_all_public_handlers(
        config_factory, prefix_config_factory, printer, tmp_path):
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)

    printer.send_event("klippy:ready")

    assert dict(extension._physical_handlers) == handlers
    assert all(printer.gcode.commands[name] is not handlers[name]
               for name in handlers)


def test_wrapper_registration_failure_restores_all_original_handlers(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    real_register = printer.gcode.register_command
    failure_pending = [True]

    def fail_replacement(name, handler, desc=None):
        if (failure_pending[0] and name == "T1" and handler is not None
                and name not in printer.gcode.commands):
            failure_pending[0] = False
            raise RuntimeError("injected replacement failure")
        return real_register(name, handler, desc)

    monkeypatch.setattr(printer.gcode, "register_command", fail_replacement)

    with pytest.raises(RuntimeError, match="replacement failure"):
        printer.send_event("klippy:ready")

    assert public_tool_handlers(printer, handlers) == handlers
    assert extension.state is None
    assert extension._physical_handlers is None


def test_later_ready_failure_restores_all_original_handlers(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)

    def fail_save(self, state):
        raise OSError("injected save failure")

    monkeypatch.setattr(state_module.StateStore, "save", fail_save)

    with pytest.raises(ConfigError, match="filesystem failure"):
        printer.send_event("klippy:ready")

    assert public_tool_handlers(printer, handlers) == handlers
    assert extension.state is None
    assert extension._state_store is None
    assert extension._physical_handlers is None
