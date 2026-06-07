import pytest

from conftest import CommandError


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
