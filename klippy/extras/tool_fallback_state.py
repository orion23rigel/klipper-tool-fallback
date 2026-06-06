import errno
import json
import os
import tempfile
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

    def reconcile(self, configured_tools):
        configured_names = set(configured_tools)
        tool_states = {}
        for name, config in configured_tools.items():
            if name not in self.tools:
                tool_states[name] = ToolState(
                    False, False, False, tuple(config.backups))
                continue
            existing = self.tools[name]
            tool_states[name] = ToolState(
                existing.loaded,
                existing.purged,
                existing.failed,
                tuple(
                    backup for backup in existing.backups
                    if backup in configured_names),
            )

        mappings = {}
        for name in configured_tools:
            target = self.mappings.get(name, name)
            mappings[name] = target if target in configured_names else name
        return self._canonical(tool_states, mappings)


class StateStore:
    def __init__(self, state_path):
        self.path = os.path.abspath(os.path.expanduser(state_path))
        self._persisted_state = None

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as state_file:
                decoded = json.load(state_file)
        except FileNotFoundError:
            self._persisted_state = None
            return None
        state = FallbackState.from_dict(decoded)
        self._persisted_state = state
        return state

    def load_reconciled(self, configured_tools):
        loaded = self.load()
        if loaded is None:
            return FallbackState.from_config(configured_tools)
        return loaded.reconcile(configured_tools)

    def save(self, state):
        if state == self._persisted_state:
            return False
        serialized = json.dumps(
            state.to_dict(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
        self._atomic_write(serialized)
        self._persisted_state = state
        return True

    def _atomic_write(self, serialized):
        parent = os.path.dirname(self.path)
        os.makedirs(parent, exist_ok=True)
        descriptor = None
        temporary_path = None
        try:
            descriptor, temporary_path = tempfile.mkstemp(
                prefix=".tool_fallback_state.", suffix=".tmp", dir=parent)
            with os.fdopen(descriptor, "w", encoding="utf-8") as state_file:
                descriptor = None
                state_file.write(serialized)
                state_file.flush()
                os.fsync(state_file.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
            _fsync_directory(parent)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass


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


def _fsync_directory(path):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    except OSError as error:
        unsupported = {
            errno.EBADF,
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }
        if error.errno not in unsupported:
            raise
    finally:
        os.close(descriptor)
