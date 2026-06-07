import pytest

from conftest import (CommandError, ConfigError, FakeConfig, FakeGCmd,
                      FakePrefixConfig, FakePrinter, FakePrintStats)
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


def transition_gcmd(params, events):
    gcmd = FakeGCmd(params)

    def respond_info(message):
        events.append("warning:%s" % (message,))
        gcmd.responses.append(message)

    gcmd.respond_info = respond_info
    return gcmd


def record_transition_scripts(printer, events):
    original = printer.gcode.run_script_from_command

    def run_script(script):
        events.append("script:%s" % (script,))
        return original(script)

    printer.gcode.run_script_from_command = run_script


def persist_mapping(path, physical_tool):
    state = state_module.FallbackState.from_dict({
        "version": 1,
        "tools": {
            name: {
                "loaded": False,
                "purged": False,
                "failed": False,
                "backups": [],
            }
            for name in ("T0", "T1", "T2")
        },
        "mappings": {
            "T0": physical_tool,
            "T1": "T1",
            "T2": "T2",
        },
    })
    state_module.StateStore(str(path)).save(state)


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


def test_print_state_fake_distinguishes_printing_paused_and_inactive(printer):
    print_stats = FakePrintStats()
    printer.add_object("print_stats", print_stats)

    assert print_stats.get_status(0.0)["state"] == "standby"
    print_stats.set_state("printing")
    assert print_stats.get_status(1.0)["state"] == "printing"
    print_stats.set_state("paused")
    assert print_stats.get_status(2.0)["state"] == "paused"


def test_pause_and_resume_scripts_record_order_and_update_print_state(printer):
    print_stats = FakePrintStats("printing")
    printer.add_object("print_stats", print_stats)

    printer.gcode.run_script_from_command("PAUSE")
    printer.gcode.run_script_from_command("RESUME")

    assert printer.gcode.script_events == ["PAUSE", "RESUME"]
    assert print_stats.state == "printing"


@pytest.mark.parametrize("script", ["PAUSE", "RESUME"])
def test_pause_and_resume_script_failures_are_independently_injectable(
        script, printer):
    print_stats = FakePrintStats("printing")
    printer.add_object("print_stats", print_stats)
    error = CommandError("injected %s failure" % (script.lower(),))
    printer.gcode.inject_script_failure(script, error)

    with pytest.raises(CommandError, match="injected"):
        printer.gcode.run_script_from_command(script)

    assert printer.gcode.script_events == [script]
    assert print_stats.state == "printing"


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


def test_logical_route_invokes_saved_physical_handler_without_recursion(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    persist_mapping(path, "T2")
    events = []
    handlers = {
        name: physical_handler_spy(name, events)
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path, handlers=handlers)
    printer.send_event("klippy:ready")

    printer.gcode.invoke_command("T0")

    assert events == [{
        "handler": "T2",
        "command": "T2",
        "commandline": "T2",
        "rawparams": "",
        "params": {},
    }]
    assert extension._active_logical_tool == "T0"
    assert extension._selected_physical_tool == "T2"


def test_physical_handler_failure_preserves_previous_ownership(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    persist_mapping(path, "T2")
    events = []
    failure = CommandError("injected physical handler failure")
    handlers = {
        "T0": physical_handler_spy("T0", events),
        "T1": physical_handler_spy("T1", events),
        "T2": physical_handler_spy("T2", events, failure=failure),
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path, handlers=handlers)
    printer.send_event("klippy:ready")
    printer.gcode.invoke_command("T1")

    with pytest.raises(CommandError, match="physical handler failure"):
        printer.gcode.invoke_command("T0")

    assert extension._active_logical_tool == "T1"
    assert extension._selected_physical_tool == "T1"


def test_logical_selection_does_not_write_state(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    events = []
    handlers = {
        name: physical_handler_spy(name, events)
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")

    def reject_write(*args, **kwargs):
        raise AssertionError("logical selection attempted to persist state")

    monkeypatch.setattr(extension._state_store, "save", reject_write)

    printer.gcode.invoke_command("T0")

    assert extension._active_logical_tool == "T0"
    assert extension._selected_physical_tool == "T0"


def test_logical_selection_rejects_pre_ready_and_active_transition(
        config_factory, prefix_config_factory, printer, tmp_path):
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)

    with pytest.raises(CommandError, match="not initialized"):
        extension._route_logical("T0", FakeGCmd())

    printer.send_event("klippy:ready")
    extension._transition_active = True

    with pytest.raises(CommandError, match="active transition"):
        printer.gcode.invoke_command("T0")


def test_physical_bypass_invokes_saved_handler_and_preserves_policy_and_logical(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    persist_mapping(path, "T2")
    events = []
    handlers = {
        name: physical_handler_spy(name, events)
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path, handlers=handlers)
    printer.send_event("klippy:ready")
    printer.gcode.invoke_command("T0")
    original_state = extension.state
    events.clear()

    printer.gcode.invoke_command(
        "SELECT_PHYSICAL_TOOL", FakeGCmd({"TOOL": "T1"}))

    assert events == [{
        "handler": "T1",
        "command": "T1",
        "commandline": "T1",
        "rawparams": "",
        "params": {},
    }]
    assert extension._active_logical_tool == "T0"
    assert extension._selected_physical_tool == "T1"
    assert extension.state is original_state
    assert extension.state.mappings["T0"] == "T2"


@pytest.mark.parametrize("tool", ["T9", "t0", "T00"])
def test_physical_bypass_rejects_unknown_or_noncanonical_tool(
        tool, config_factory, prefix_config_factory, printer, tmp_path):
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")

    with pytest.raises(CommandError, match="configured canonical tool"):
        printer.gcode.invoke_command(
            "SELECT_PHYSICAL_TOOL", FakeGCmd({"TOOL": tool}))


@pytest.mark.parametrize("print_state", ["printing", "paused"])
def test_physical_bypass_rejects_active_print_states(
        print_state, config_factory, prefix_config_factory, printer, tmp_path):
    events = []
    handlers = {
        name: physical_handler_spy(name, events)
        for name in ("T0", "T1", "T2")
    }
    print_stats = FakePrintStats(print_state)
    printer.add_object("print_stats", print_stats)
    printer.reactor.monotonic_time = 12.5
    load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")

    with pytest.raises(CommandError, match="printing or paused"):
        printer.gcode.invoke_command(
            "SELECT_PHYSICAL_TOOL", FakeGCmd({"TOOL": "T1"}))

    assert events == []
    assert print_stats.eventtimes == [12.5]


def test_persist_state_publishes_only_after_success(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")
    original = extension.state
    candidate = original.with_mapping("T0", "T2")

    def fail_save(state):
        raise OSError("injected command save failure")

    monkeypatch.setattr(extension._state_store, "save", fail_save)

    with pytest.raises(OSError, match="command save failure"):
        extension._persist_state(candidate)

    assert extension.state is original


def test_remap_restore_and_reset_persist_requested_mappings(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path, handlers=handlers)
    printer.send_event("klippy:ready")

    printer.gcode.invoke_command(
        "REMAP_TOOL", FakeGCmd({"LOGICAL": "T0", "PHYSICAL": "T2"}))
    assert extension.state.mappings["T0"] == "T2"
    assert state_module.StateStore(str(path)).load().mappings["T0"] == "T2"

    printer.gcode.invoke_command("RESTORE_TOOL", FakeGCmd({"TOOL": "T0"}))
    assert extension.state.mappings["T0"] == "T0"

    printer.gcode.invoke_command(
        "REMAP_TOOL", FakeGCmd({"LOGICAL": "T1", "PHYSICAL": "T2"}))
    printer.gcode.invoke_command(
        "REMAP_TOOL", FakeGCmd({"LOGICAL": "T2", "PHYSICAL": "T0"}))
    printer.gcode.invoke_command("RESET_TOOL_MAPPINGS")

    assert extension.state.mappings == {"T0": "T0", "T1": "T1", "T2": "T2"}
    assert state_module.StateStore(str(path)).load() == extension.state


@pytest.mark.parametrize(("command", "params"), [
    ("REMAP_TOOL", {"LOGICAL": "T9", "PHYSICAL": "T0"}),
    ("REMAP_TOOL", {"LOGICAL": "T0", "PHYSICAL": "t1"}),
    ("RESTORE_TOOL", {"TOOL": "T00"}),
])
def test_remap_and_restore_reject_invalid_tools(
        command, params, config_factory, prefix_config_factory, printer,
        tmp_path):
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")
    original = extension.state

    with pytest.raises(CommandError, match="configured canonical tool"):
        printer.gcode.invoke_command(command, FakeGCmd(params))

    assert extension.state is original


@pytest.mark.parametrize(("command", "params"), [
    ("REMAP_TOOL", {"LOGICAL": "T0", "PHYSICAL": "T0"}),
    ("RESTORE_TOOL", {"TOOL": "T0"}),
    ("RESET_TOOL_MAPPINGS", {}),
])
def test_remap_restore_and_reset_no_ops_do_not_save_or_select(
        command, params, config_factory, prefix_config_factory, printer,
        tmp_path, monkeypatch):
    events = []
    handlers = {
        name: physical_handler_spy(name, events)
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")

    def reject_save(candidate):
        raise AssertionError("no-op command attempted a state-store write")

    monkeypatch.setattr(extension._state_store, "save", reject_save)

    printer.gcode.invoke_command(command, FakeGCmd(params))

    assert events == []


@pytest.mark.parametrize(("command", "params"), [
    ("REMAP_TOOL", {"LOGICAL": "T0", "PHYSICAL": "T2"}),
    ("RESTORE_TOOL", {"TOOL": "T0"}),
    ("RESET_TOOL_MAPPINGS", {}),
])
def test_remap_restore_and_reset_save_failures_preserve_published_state(
        command, params, config_factory, prefix_config_factory, printer,
        tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    if command != "REMAP_TOOL":
        persist_mapping(path, "T2")
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path, handlers=handlers)
    printer.send_event("klippy:ready")
    original = extension.state

    def fail_save(candidate):
        raise OSError("injected mapping save failure")

    monkeypatch.setattr(extension._state_store, "save", fail_save)

    with pytest.raises(CommandError, match="mapping save failure"):
        printer.gcode.invoke_command(command, FakeGCmd(params))

    assert extension.state is original


@pytest.mark.parametrize(("command", "params"), [
    ("REMAP_TOOL", {"LOGICAL": "T0", "PHYSICAL": "T2"}),
    ("RESTORE_TOOL", {"TOOL": "T0"}),
    ("RESET_TOOL_MAPPINGS", {}),
])
def test_changed_active_route_commands_use_ordered_transition_during_print(
        command, params, config_factory, prefix_config_factory, printer,
        tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    if command != "REMAP_TOOL":
        persist_mapping(path, "T2")
    events = []
    handlers = {
        name: (lambda selected: lambda gcmd: events.append(
            "select:%s" % (selected,)))(name)
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path, handlers=handlers)
    printer.send_event("klippy:ready")
    printer.gcode.invoke_command("T0")
    events.clear()
    printer.add_object("print_stats", FakePrintStats("printing"))
    record_transition_scripts(printer, events)
    original_save = extension._state_store.save

    def record_save(candidate):
        events.append("persist")
        return original_save(candidate)

    monkeypatch.setattr(extension._state_store, "save", record_save)

    printer.gcode.invoke_command(command, transition_gcmd(params, events))

    assert events[0] == "script:PAUSE"
    assert events[1].startswith("warning:Changing active logical T0")
    assert events[2:] == ["select:T0" if command != "REMAP_TOOL"
                         else "select:T2", "persist", "script:RESUME"]
    assert extension._transition_active is False


def test_already_paused_active_transition_does_not_pause_or_resume(
        config_factory, prefix_config_factory, printer, tmp_path):
    events = []
    handlers = {
        name: (lambda selected: lambda gcmd: events.append(
            "select:%s" % (selected,)))(name)
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")
    printer.gcode.invoke_command("T0")
    events.clear()
    printer.add_object("print_stats", FakePrintStats("paused"))
    record_transition_scripts(printer, events)

    printer.gcode.invoke_command(
        "REMAP_TOOL",
        transition_gcmd({"LOGICAL": "T0", "PHYSICAL": "T2"}, events))

    assert events[0].startswith("warning:Changing active logical T0")
    assert events[1:] == ["select:T2"]
    assert printer.gcode.script_events == []


def test_active_transition_rejects_unknown_selected_physical_ownership(
        config_factory, prefix_config_factory, printer, tmp_path):
    events = []
    handlers = {
        name: physical_handler_spy(name, events)
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")
    extension._active_logical_tool = "T0"
    printer.add_object("print_stats", FakePrintStats("printing"))

    with pytest.raises(CommandError, match="selected physical tool is unknown"):
        printer.gcode.invoke_command(
            "REMAP_TOOL", FakeGCmd({"LOGICAL": "T0", "PHYSICAL": "T2"}))

    assert events == []
    assert printer.gcode.script_events == []


def test_reentrant_active_transition_is_rejected_before_selection(
        config_factory, prefix_config_factory, printer, tmp_path):
    events = []
    handlers = {
        name: physical_handler_spy(name, events)
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")
    printer.gcode.invoke_command("T0")
    events.clear()
    printer.add_object("print_stats", FakePrintStats("printing"))
    original_pause = printer.gcode.run_script_from_command

    def reenter_during_pause(script):
        original_pause(script)
        printer.gcode.invoke_command(
            "REMAP_TOOL", FakeGCmd({"LOGICAL": "T0", "PHYSICAL": "T1"}))

    printer.gcode.run_script_from_command = reenter_during_pause

    with pytest.raises(CommandError, match="transition is active"):
        printer.gcode.invoke_command(
            "REMAP_TOOL", FakeGCmd({"LOGICAL": "T0", "PHYSICAL": "T2"}))

    assert events == []
    assert extension._transition_active is False


def test_inactive_route_change_persists_during_active_print(
        config_factory, prefix_config_factory, printer, tmp_path):
    events = []
    handlers = {
        name: physical_handler_spy(name, events)
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")
    printer.gcode.invoke_command("T0")
    events.clear()
    printer.add_object("print_stats", FakePrintStats("printing"))

    printer.gcode.invoke_command(
        "REMAP_TOOL", FakeGCmd({"LOGICAL": "T1", "PHYSICAL": "T2"}))

    assert extension.state.mappings["T1"] == "T2"
    assert extension.state.mappings["T0"] == "T0"
    assert events == []


def test_active_route_exact_no_op_remains_no_op_during_paused_print(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        handlers=handlers)
    printer.send_event("klippy:ready")
    printer.gcode.invoke_command("T0")
    printer.add_object("print_stats", FakePrintStats("paused"))

    def reject_save(candidate):
        raise AssertionError("active-route no-op attempted persistence")

    monkeypatch.setattr(extension._state_store, "save", reject_save)

    printer.gcode.invoke_command(
        "REMAP_TOOL", FakeGCmd({"LOGICAL": "T0", "PHYSICAL": "T0"}))


def test_successful_remap_survives_extension_restart(tmp_path):
    path = tmp_path / "state.json"
    first_printer = FakePrinter()
    first_handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    first = load_extension(
        lambda **options: FakeConfig(first_printer, options=options),
        lambda name, **options: FakePrefixConfig(first_printer, name, options),
        first_printer, path, handlers=first_handlers)
    first_printer.send_event("klippy:ready")
    first_printer.gcode.invoke_command(
        "REMAP_TOOL", FakeGCmd({"LOGICAL": "T0", "PHYSICAL": "T2"}))

    second_printer = FakePrinter()
    second_handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    second = load_extension(
        lambda **options: FakeConfig(second_printer, options=options),
        lambda name, **options: FakePrefixConfig(second_printer, name, options),
        second_printer, path, handlers=second_handlers)
    second_printer.send_event("klippy:ready")

    assert second.state.mappings["T0"] == "T2"


def test_status_reports_transient_ownership_and_restart_forgets_it(tmp_path):
    path = tmp_path / "state.json"
    first_printer = FakePrinter()
    first_handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    first = load_extension(
        lambda **options: FakeConfig(first_printer, options=options),
        lambda name, **options: FakePrefixConfig(
            first_printer, name, options),
        first_printer, path, handlers=first_handlers)
    first_printer.send_event("klippy:ready")
    first_printer.gcode.invoke_command("T0")

    assert first.get_status(None)["active_logical_tool"] == "T0"
    assert first.get_status(None)["selected_physical_tool"] == "T0"

    second_printer = FakePrinter()
    second_handlers = {
        name: physical_handler_spy(name, [])
        for name in ("T0", "T1", "T2")
    }
    second = load_extension(
        lambda **options: FakeConfig(second_printer, options=options),
        lambda name, **options: FakePrefixConfig(
            second_printer, name, options),
        second_printer, path, handlers=second_handlers)
    second_printer.send_event("klippy:ready")

    assert second.get_status(None)["active_logical_tool"] is None
    assert second.get_status(None)["selected_physical_tool"] is None
    assert second.get_status(None)["transition_active"] is False
