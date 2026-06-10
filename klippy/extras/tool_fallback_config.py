import math
import os
import re
from dataclasses import dataclass
from types import MappingProxyType


TOOL_NAME_RE = re.compile(r"^T(?:0|[1-9][0-9]*)$")


@dataclass(frozen=True)
class GlobalConfig:
    state_path: str
    debounce_time: float
    pause_gcode: str
    resume_gcode: str
    purge_gcode: str
    notify_gcode: str
    selection_timeout: float
    heating_timeout: float
    purge_timeout: float


@dataclass(frozen=True)
class ToolConfig:
    name: str
    filament_sensor: object
    heater: str
    backups: tuple


@dataclass(frozen=True)
class NormalizedConfig:
    global_config: GlobalConfig
    tools: object


def _nonempty(config, option, default=...):
    value = config.get(option, default)
    if not isinstance(value, str) or not value.strip():
        raise config.error("Option '%s' in section '%s' must not be empty" %
                           (option, config.get_name()))
    return value.strip()


def _optional_nonempty(config, option):
    missing = object()
    value = config.get(option, missing)
    if value is missing:
        return None
    if not isinstance(value, str) or not value.strip():
        raise config.error("Option '%s' in section '%s' must not be empty" %
                           (option, config.get_name()))
    return value.strip()


def _purge_adapter(config):
    adapter = _nonempty(config, "purge_gcode", "_TOOL_FALLBACK_PURGE")
    if adapter.split(None, 1)[0].upper() == "PURGE_TOOL":
        raise config.error(
            "Option 'purge_gcode' in section '%s' must not invoke public "
            "PURGE_TOOL" % (config.get_name(),))
    return adapter


def normalize_tool_name(config, name):
    if not TOOL_NAME_RE.match(name):
        raise config.error(
            "Tool identity '%s' must be canonical uppercase T followed by a "
            "non-negative integer" % (name,))
    return name


def _positive_finite_float(config, option, default):
    value = config.getfloat(option, default)
    if not math.isfinite(value):
        raise config.error(
            "Option '%s' in section '%s' must be finite" %
            (option, config.get_name()))
    if value <= 0.0:
        raise config.error(
            "Option '%s' in section '%s' must be above 0.0" %
            (option, config.get_name()))
    return value


def parse_global_config(config):
    state_path = _nonempty(
        config, "state_path",
        "~/printer_data/config/tool_fallback_state.json")
    return GlobalConfig(
        state_path=os.path.abspath(os.path.expanduser(state_path)),
        debounce_time=_positive_finite_float(config, "debounce_time", 1.0),
        pause_gcode=_nonempty(config, "pause_gcode", "PAUSE"),
        resume_gcode=_nonempty(config, "resume_gcode", "RESUME"),
        purge_gcode=_purge_adapter(config),
        notify_gcode=_nonempty(
            config, "notify_gcode", "_TOOL_FALLBACK_NOTIFY"),
        selection_timeout=_positive_finite_float(
            config, "selection_timeout", 120.0),
        heating_timeout=_positive_finite_float(
            config, "heating_timeout", 300.0),
        purge_timeout=_positive_finite_float(
            config, "purge_timeout", 180.0),
    )


def parse_tool_config(config):
    section_parts = config.get_name().split()
    if len(section_parts) != 2 or section_parts[0] != "tool_fallback":
        raise config.error("Section '%s' must be named [tool_fallback Tn]" %
                           (config.get_name(),))
    name = normalize_tool_name(config, section_parts[1])
    raw_backups = config.get("backups", "")
    backups = tuple(
        normalize_tool_name(config, backup.strip())
        for backup in raw_backups.split(",")
        if backup.strip()
    )
    return ToolConfig(
        name=name,
        filament_sensor=_optional_nonempty(config, "filament_sensor"),
        heater=_nonempty(config, "heater"),
        backups=backups,
    )


def finalize_config(global_config, tools, error):
    names = set(tools)
    for tool in tools.values():
        if len(set(tool.backups)) != len(tool.backups):
            raise error("Tool %s contains duplicate backup references" %
                        (tool.name,))
        if tool.name in tool.backups:
            raise error("Tool %s cannot reference itself as a backup" %
                        (tool.name,))
        unknown = [backup for backup in tool.backups if backup not in names]
        if unknown:
            raise error("Tool %s references unknown backup tool(s): %s" %
                        (tool.name, ", ".join(unknown)))
    ordered = dict(sorted(
        tools.items(), key=lambda item: int(item[0][1:])))
    return NormalizedConfig(
        global_config=global_config,
        tools=MappingProxyType(ordered),
    )
