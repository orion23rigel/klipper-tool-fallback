import os
from dataclasses import FrozenInstanceError

import pytest

from conftest import ConfigError
from klippy.extras import tool_fallback


def load_extension(config_factory, printer, **options):
    config = config_factory(**options)
    extension = tool_fallback.load_config(config)
    printer.add_object("tool_fallback", extension)
    return extension, config


def load_tool(prefix_config_factory, name, **options):
    config = prefix_config_factory(name, **options)
    tool = tool_fallback.load_config_prefix(config)
    return tool, config


def tool_options(**overrides):
    options = {
        "filament_sensor": "filament_switch_sensor tool_sensor",
        "heater": "extruder",
    }
    options.update(overrides)
    return options


def test_global_config_uses_design_defaults(config_factory, printer):
    extension, config = load_extension(config_factory, printer)

    normalized = extension.global_config
    assert normalized.state_path == os.path.abspath(os.path.expanduser(
        "~/printer_data/config/tool_fallback_state.json"))
    assert normalized.debounce_time == 1.0
    assert normalized.pause_gcode == "PAUSE"
    assert normalized.resume_gcode == "RESUME"
    assert normalized.purge_gcode == "PURGE_TOOL"
    assert normalized.notify_gcode == "_TOOL_FALLBACK_NOTIFY"
    assert normalized.selection_timeout == 120.0
    assert normalized.heating_timeout == 300.0
    assert normalized.purge_timeout == 180.0
    assert "klippy:ready" in printer.events
    config.assert_all_options_read()


def test_global_config_reads_every_explicit_option(config_factory, printer,
                                                   tmp_path):
    state_path = tmp_path / ".." / "state.json"
    extension, config = load_extension(
        config_factory,
        printer,
        state_path=str(state_path),
        debounce_time="2.5",
        pause_gcode="MY_PAUSE",
        resume_gcode="MY_RESUME",
        purge_gcode="MY_PURGE",
        notify_gcode="MY_NOTIFY",
        selection_timeout="12",
        heating_timeout="34",
        purge_timeout="56",
    )

    normalized = extension.global_config
    assert normalized.state_path == os.path.abspath(str(state_path))
    assert normalized.debounce_time == 2.5
    assert normalized.pause_gcode == "MY_PAUSE"
    assert normalized.resume_gcode == "MY_RESUME"
    assert normalized.purge_gcode == "MY_PURGE"
    assert normalized.notify_gcode == "MY_NOTIFY"
    assert normalized.selection_timeout == 12.0
    assert normalized.heating_timeout == 34.0
    assert normalized.purge_timeout == 56.0
    config.assert_all_options_read()


def test_prefix_sections_parse_canonical_tools_and_preserve_backup_order(
        config_factory, prefix_config_factory, printer):
    extension, _ = load_extension(config_factory, printer)
    tool_0, config_0 = load_tool(
        prefix_config_factory,
        "tool_fallback T0",
        **tool_options(backups=" T12, T3, T1 "),
    )
    tool_12, config_12 = load_tool(
        prefix_config_factory,
        "tool_fallback T12",
        **tool_options(heater="extruder12"),
    )
    load_tool(prefix_config_factory, "tool_fallback T3", **tool_options())
    load_tool(prefix_config_factory, "tool_fallback T1", **tool_options())

    normalized = extension.finalize_configuration()
    assert tool_0.name == "T0"
    assert tool_12.name == "T12"
    assert normalized.tools["T0"].backups == ("T12", "T3", "T1")
    assert tuple(normalized.tools) == ("T0", "T1", "T3", "T12")
    config_0.assert_all_options_read()
    config_12.assert_all_options_read()


def test_normalized_configuration_is_immutable(
        config_factory, prefix_config_factory, printer):
    extension, _ = load_extension(config_factory, printer)
    tool, _ = load_tool(
        prefix_config_factory, "tool_fallback T0", **tool_options())
    normalized = extension.finalize_configuration()

    with pytest.raises(FrozenInstanceError):
        tool.name = "T1"
    with pytest.raises(TypeError):
        normalized.tools["T1"] = tool


@pytest.mark.parametrize("section_name", [
    "tool_fallback t0",
    "tool_fallback T",
    "tool_fallback T01",
    "tool_fallback T-1",
    "tool_fallback T0 extra",
    "other T0",
])
def test_malformed_tool_names_block_startup(
        section_name, config_factory, prefix_config_factory, printer):
    load_extension(config_factory, printer)

    with pytest.raises(ConfigError):
        load_tool(prefix_config_factory, section_name, **tool_options())


def test_duplicate_tools_block_startup(
        config_factory, prefix_config_factory, printer):
    load_extension(config_factory, printer)
    load_tool(prefix_config_factory, "tool_fallback T0", **tool_options())

    with pytest.raises(ConfigError, match="configured more than once"):
        load_tool(prefix_config_factory, "tool_fallback T0", **tool_options())


@pytest.mark.parametrize(("backups", "message"), [
    ("T1,T1", "duplicate backup"),
    ("T0", "reference itself"),
    ("T2", "unknown backup"),
])
def test_invalid_backup_references_block_startup(
        backups, message, config_factory, prefix_config_factory, printer):
    extension, _ = load_extension(config_factory, printer)
    load_tool(
        prefix_config_factory,
        "tool_fallback T0",
        **tool_options(backups=backups),
    )
    load_tool(prefix_config_factory, "tool_fallback T1", **tool_options())

    with pytest.raises(ConfigError, match=message):
        extension.finalize_configuration()


@pytest.mark.parametrize("missing_option", ["filament_sensor", "heater"])
def test_missing_required_tool_values_block_startup(
        missing_option, config_factory, prefix_config_factory, printer):
    load_extension(config_factory, printer)
    options = tool_options()
    del options[missing_option]

    with pytest.raises(ConfigError):
        load_tool(prefix_config_factory, "tool_fallback T0", **options)


@pytest.mark.parametrize("option", ["filament_sensor", "heater"])
def test_empty_required_tool_values_block_startup(
        option, config_factory, prefix_config_factory, printer):
    load_extension(config_factory, printer)
    options = tool_options(**{option: "  "})

    with pytest.raises(ConfigError, match="must not be empty"):
        load_tool(prefix_config_factory, "tool_fallback T0", **options)


@pytest.mark.parametrize("option", [
    "state_path",
    "pause_gcode",
    "resume_gcode",
    "purge_gcode",
    "notify_gcode",
])
def test_empty_global_adapter_values_block_startup(
        option, config_factory, printer):
    with pytest.raises(ConfigError, match="must not be empty"):
        load_extension(config_factory, printer, **{option: " "})


@pytest.mark.parametrize("option", [
    "debounce_time",
    "selection_timeout",
    "heating_timeout",
    "purge_timeout",
])
@pytest.mark.parametrize("value", ["0", "-1"])
def test_nonpositive_timing_values_block_startup(
        option, value, config_factory, printer):
    with pytest.raises(ConfigError, match="must be above"):
        load_extension(config_factory, printer, **{option: value})


@pytest.mark.parametrize("option", [
    "debounce_time",
    "selection_timeout",
    "heating_timeout",
    "purge_timeout",
])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_timing_values_block_startup(
        option, value, config_factory, printer):
    with pytest.raises(ConfigError, match="must be finite"):
        load_extension(config_factory, printer, **{option: value})
