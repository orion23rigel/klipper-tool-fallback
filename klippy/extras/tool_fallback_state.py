from dataclasses import dataclass
from types import MappingProxyType

from .tool_fallback_config import TOOL_NAME_RE


SCHEMA_VERSION = 1


class StateValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ToolState:
    loaded: bool
    purged: bool
    failed: bool
    backups: tuple


@dataclass(frozen=True)
class FallbackState:
    version: int
    tools: object
    mappings: object

    @classmethod
    def from_config(cls, tools):
        tool_states = {
            name: ToolState(False, False, False, tuple(tool.backups))
            for name, tool in tools.items()
        }
        mappings = {name: name for name in tools}
        return cls._canonical(tool_states, mappings)

    @classmethod
    def from_dict(cls, value):
        data = _require_dict(value, "state")
        _require_fields(data, {"version", "tools", "mappings"}, "state")
        version = data["version"]
        if type(version) is not int or version != SCHEMA_VERSION:
            raise StateValidationError(
                "Unsupported state schema version: %r" % (version,))

        raw_tools = _require_dict(data["tools"], "tools")
        tool_states = {}
        for name, raw_tool in raw_tools.items():
            _require_tool_name(name, "tool")
            tool = _require_dict(raw_tool, "tool %s" % (name,))
            _require_fields(
                tool, {"loaded", "purged", "failed", "backups"},
                "tool %s" % (name,))
            backups = _require_tool_list(
                tool["backups"], "tool %s backups" % (name,))
            if name in backups:
                raise StateValidationError(
                    "Tool %s cannot reference itself as a backup" % (name,))
            if len(set(backups)) != len(backups):
                raise StateValidationError(
                    "Tool %s contains duplicate backup references" % (name,))
            tool_states[name] = ToolState(
                _require_bool(tool["loaded"], "tool %s loaded" % (name,)),
                _require_bool(tool["purged"], "tool %s purged" % (name,)),
                _require_bool(tool["failed"], "tool %s failed" % (name,)),
                backups,
            )

        raw_mappings = _require_dict(data["mappings"], "mappings")
        mappings = {}
        for logical, physical in raw_mappings.items():
            _require_tool_name(logical, "logical mapping")
            _require_tool_name(physical, "physical mapping")
            mappings[logical] = physical

        names = set(tool_states)
        _require_exact_references(mappings, tool_states, names)
        return cls._canonical(tool_states, mappings)

    @classmethod
    def _canonical(cls, tools, mappings):
        ordered_tools = dict(sorted(tools.items(), key=_tool_sort_key))
        ordered_mappings = dict(sorted(mappings.items(), key=_tool_sort_key))
        return cls(
            SCHEMA_VERSION,
            MappingProxyType(ordered_tools),
            MappingProxyType(ordered_mappings),
        )

    def to_dict(self):
        return {
            "version": self.version,
            "tools": {
                name: {
                    "loaded": tool.loaded,
                    "purged": tool.purged,
                    "failed": tool.failed,
                    "backups": list(tool.backups),
                }
                for name, tool in self.tools.items()
            },
            "mappings": dict(self.mappings),
        }


def _require_dict(value, description):
    if type(value) is not dict:
        raise StateValidationError("%s must be an object" % (description,))
    return value


def _require_fields(value, expected, description):
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing %s" % (", ".join(missing),))
        if unknown:
            details.append("unknown %s" % (", ".join(unknown),))
        raise StateValidationError(
            "%s has invalid fields: %s" % (description, "; ".join(details)))


def _require_bool(value, description):
    if type(value) is not bool:
        raise StateValidationError("%s must be a boolean" % (description,))
    return value


def _require_tool_name(value, description):
    if type(value) is not str or not TOOL_NAME_RE.fullmatch(value):
        raise StateValidationError(
            "%s must be a canonical tool name" % (description,))
    return value


def _require_tool_list(value, description):
    if type(value) is not list:
        raise StateValidationError("%s must be a list" % (description,))
    return tuple(_require_tool_name(item, description) for item in value)


def _require_exact_references(mappings, tools, names):
    if set(mappings) != names:
        raise StateValidationError(
            "Mappings must contain exactly one entry for every tool")
    for logical, physical in mappings.items():
        if physical not in names:
            raise StateValidationError(
                "Mapping %s references unknown tool %s" % (logical, physical))
    for name, tool in tools.items():
        unknown = [backup for backup in tool.backups if backup not in names]
        if unknown:
            raise StateValidationError(
                "Tool %s references unknown backup tool(s): %s" %
                (name, ", ".join(unknown)))


def _tool_sort_key(item):
    return int(item[0][1:])
