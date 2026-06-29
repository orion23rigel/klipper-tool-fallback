import errno
import json
import os
import tempfile
from dataclasses import dataclass
from types import MappingProxyType

from .tool_fallback_config import TOOL_NAME_RE


SCHEMA_VERSION = 2


class StateValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ToolState:
    loaded: bool
    purged: bool
    failed: bool
    backups: tuple
    user_defined_backup: str | None = None


@dataclass(frozen=True)
class FallbackState:
    version: int
    tools: object
    mappings: object
    user_defined_backups: object

    @classmethod
    def from_config(cls, tools):
        tool_states = {
            name: ToolState(False, False, False, tuple(tool.backups), None)
            for name, tool in tools.items()
        }
        mappings = {name: name for name in tools}
        return cls._canonical(
            tool_states, mappings, MappingProxyType({}))

    @classmethod
    def from_dict(cls, value):
        data = _require_dict(value, "state")
        for required in ("version", "tools", "mappings"):
            if required not in data:
                raise StateValidationError(
                    "state missing required field: %s" % (required,))
        allowed_fields = {"version", "tools", "mappings", "user_defined_backups"}
        unknown = set(data) - allowed_fields
        if unknown:
            raise StateValidationError(
                "state has invalid fields: unknown %s" %
                (", ".join(sorted(unknown)),))
        version = data["version"]
        if type(version) is not int or version not in (1, 2):
            raise StateValidationError(
                "Unsupported state schema version: %r" % (version,))

        is_v2 = version == 2 or "user_defined_backups" in data

        if is_v2:
            raw_user_defined_backups = data.get("user_defined_backups", {})
            if type(raw_user_defined_backups) is not dict:
                raise StateValidationError(
                    "user_defined_backups must be an object")
            user_defined_backups = {}
            for logical, backup in raw_user_defined_backups.items():
                _require_tool_name(logical, "user_defined_backup")
                if backup is not None:
                    if type(backup) is not str or not TOOL_NAME_RE.fullmatch(
                            backup):
                        raise StateValidationError(
                            "user_defined_backup %s must be a canonical "
                            "tool name or null" % (logical,))
                    if logical == backup:
                        raise StateValidationError(
                            "user_defined_backup %s cannot reference itself" %
                            (logical,))
                user_defined_backups[logical] = backup
        else:
            user_defined_backups = {}

        raw_tools = _require_dict(data["tools"], "tools")
        tool_states = {}
        for name, raw_tool in raw_tools.items():
            _require_tool_name(name, "tool")
            tool = _require_dict(raw_tool, "tool %s" % (name,))
            for required in ("loaded", "purged", "failed", "backups"):
                if required not in tool:
                    raise StateValidationError(
                        "tool %s missing required field: %s" % (name, required))
            backups = _require_tool_list(
                tool["backups"], "tool %s backups" % (name,))
            if name in backups:
                raise StateValidationError(
                    "Tool %s cannot reference itself as a backup" % (name,))
            if len(set(backups)) != len(backups):
                raise StateValidationError(
                    "Tool %s contains duplicate backup references" % (name,))
            loaded = _require_bool(
                tool["loaded"], "tool %s loaded" % (name,))
            purged = _require_bool(
                tool["purged"], "tool %s purged" % (name,))
            failed = _require_bool(
                tool["failed"], "tool %s failed" % (name,))
            if purged and not loaded:
                raise StateValidationError(
                    "Tool %s cannot be purged while unloaded" % (name,))
            user_defined_backup = tool.get("user_defined_backup", None)
            if user_defined_backup is not None:
                if type(user_defined_backup) is not str or not TOOL_NAME_RE.fullmatch(user_defined_backup):
                    raise StateValidationError(
                        "tool %s user_defined_backup must be a canonical "
                        "tool name or null" % (name,))
            tool_states[name] = ToolState(
                loaded, purged, failed, backups, user_defined_backup)

        raw_mappings = _require_dict(data["mappings"], "mappings")
        mappings = {}
        for logical, physical in raw_mappings.items():
            _require_tool_name(logical, "logical mapping")
            _require_tool_name(physical, "physical mapping")
            mappings[logical] = physical

        names = set(tool_states)
        _require_exact_references(mappings, tool_states, names)
        return cls._canonical(
            tool_states, mappings, MappingProxyType(user_defined_backups))

    @classmethod
    def _canonical(cls, tools, mappings, user_defined_backups):
        ordered_tools = dict(sorted(tools.items(), key=_tool_sort_key))
        ordered_mappings = dict(sorted(mappings.items(), key=_tool_sort_key))
        if type(user_defined_backups) is MappingProxyType:
            user_defined_backups = dict(user_defined_backups)
        user_defined_backups = MappingProxyType(
            dict(sorted(user_defined_backups.items(), key=_tool_sort_key)))
        return cls(
            SCHEMA_VERSION,
            MappingProxyType(ordered_tools),
            MappingProxyType(ordered_mappings),
            user_defined_backups,
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
                    "user_defined_backup": tool.user_defined_backup,
                }
                for name, tool in self.tools.items()
            },
            "mappings": dict(self.mappings),
            "user_defined_backups": dict(self.user_defined_backups),
        }

    def reconcile(self, configured_tools):
        configured_names = set(configured_tools)
        tool_states = {}
        for name, config in configured_tools.items():
            if name not in self.tools:
                tool_states[name] = ToolState(
                    False, False, False, tuple(config.backups), None)
                continue
            existing = self.tools[name]
            tool_states[name] = ToolState(
                existing.loaded,
                existing.purged,
                existing.failed,
                tuple(
                    backup for backup in existing.backups
                    if backup in configured_names),
                existing.user_defined_backup,
            )

        mappings = {}
        for name in configured_tools:
            target = self.mappings.get(name, name)
            mappings[name] = target if target in configured_names else name
        filtered_backups = {
            logical: backup
            for logical, backup in self.user_defined_backups.items()
            if logical in configured_names
        }
        return self._canonical(
            tool_states, mappings, MappingProxyType(filtered_backups))

    def with_mapping(self, logical, physical):
        if logical not in self.tools:
            raise StateValidationError(
                "Logical route references unknown tool %s" % (logical,))
        if physical not in self.tools:
            raise StateValidationError(
                "Physical route references unknown tool %s" % (physical,))
        if self.mappings[logical] == physical:
            return self
        mappings = dict(self.mappings)
        mappings[logical] = physical
        return self._canonical(
            self.tools, mappings, self.user_defined_backups)

    def with_identity_mapping(self, logical):
        return self.with_mapping(logical, logical)

    def with_identity_mappings(self):
        if all(logical == physical
               for logical, physical in self.mappings.items()):
            return self
        mappings = {name: name for name in self.tools}
        return self._canonical(
            self.tools, mappings, self.user_defined_backups)

    def with_backups(self, physical, ordered_backups):
        current = self._require_tool(physical)
        backups = self._validate_backups(physical, ordered_backups)
        return self._replace_tool(
            physical,
            ToolState(
                current.loaded, current.purged, current.failed, backups,
                current.user_defined_backup),
        )

    def with_all_backups(self, backups_by_tool):
        if type(backups_by_tool) is not dict:
            raise StateValidationError(
                "All-tool backups must be an object")
        if set(backups_by_tool) != set(self.tools):
            raise StateValidationError(
                "All-tool backups must contain exactly one entry for every "
                "tool")
        normalized = {
            physical: self._validate_backups(
                physical, backups_by_tool[physical])
            for physical in self.tools
        }
        if all(self.tools[physical].backups == normalized[physical]
               for physical in self.tools):
            return self
        tools = {
            physical: ToolState(
                current.loaded,
                current.purged,
                current.failed,
                normalized[physical],
                current.user_defined_backup,
            )
            for physical, current in self.tools.items()
        }
        return self._canonical(
            tools, self.mappings, self.user_defined_backups)

    def with_filament_loaded(self, physical):
        current = self._require_tool(physical)
        return self._replace_tool(
            physical,
            ToolState(True, False, False, current.backups,
                      current.user_defined_backup),
        )

    def with_reconciled_filament_loaded(self, physical):
        current = self._require_tool(physical)
        return self._replace_tool(
            physical,
            ToolState(True, current.purged if current.loaded else False,
                      False, current.backups,
                      current.user_defined_backup),
        )

    def with_filament_unloaded(self, physical):
        current = self._require_tool(physical)
        return self._replace_tool(
            physical,
            ToolState(False, False, current.failed, current.backups,
                      current.user_defined_backup),
        )

    def with_failed_runout(self, physical):
        current = self._require_tool(physical)
        return self._replace_tool(
            physical,
            ToolState(False, False, True, current.backups,
                      current.user_defined_backup),
        )

    def with_tool_purged(self, physical):
        current = self._require_tool(physical)
        if not current.loaded:
            raise StateValidationError(
                "Tool %s cannot be marked purged while unloaded" %
                (physical,))
        return self._replace_tool(
            physical,
            ToolState(True, True, current.failed, current.backups,
                      current.user_defined_backup),
        )

    def with_tool_unpurged(self, physical):
        current = self._require_tool(physical)
        return self._replace_tool(
            physical,
            ToolState(current.loaded, False, current.failed, current.backups,
                      current.user_defined_backup),
        )

    def _require_tool(self, physical):
        if physical not in self.tools:
            raise StateValidationError(
                "Physical tool references unknown tool %s" % (physical,))
        return self.tools[physical]

    def _validate_user_defined_backups(self):
        configured_names = set(self.tools)
        for logical, backup in self.user_defined_backups.items():
            if backup is not None:
                if logical == backup:
                    raise StateValidationError(
                        "user_defined_backup %s cannot reference itself" %
                        (logical,))
                if backup not in configured_names:
                    raise StateValidationError(
                        "user_defined_backup %s references unknown tool %s" %
                        (logical, backup))

    def _validate_backups(self, physical, ordered_backups):
        self._require_tool(physical)
        try:
            backups = tuple(ordered_backups)
        except TypeError:
            raise StateValidationError(
                "Tool %s backups must be a collection" % (physical,))
        malformed = [
            backup for backup in backups
            if type(backup) is not str or not TOOL_NAME_RE.fullmatch(backup)
        ]
        if malformed:
            raise StateValidationError(
                "Tool %s backups must contain canonical tool names" %
                (physical,))
        unknown = [backup for backup in backups if backup not in self.tools]
        if unknown:
            raise StateValidationError(
                "Tool %s references unknown backup tool(s): %s" %
                (physical, ", ".join(str(item) for item in unknown)))
        if physical in backups:
            raise StateValidationError(
                "Tool %s cannot reference itself as a backup" % (physical,))
        if len(set(backups)) != len(backups):
            raise StateValidationError(
                "Tool %s contains duplicate backup references" % (physical,))
        return backups

    def _replace_tool(self, physical, replacement):
        current = self._require_tool(physical)
        if replacement.purged and not replacement.loaded:
            raise StateValidationError(
                "Tool %s cannot be purged while unloaded" % (physical,))
        if replacement == current:
            return self
        tools = dict(self.tools)
        tools[physical] = replacement
        return self._canonical(
            tools, self.mappings, self.user_defined_backups)


class StateStore:
    def __init__(self, state_path):
        self.path = os.path.abspath(os.path.expanduser(state_path))
        self._persisted_state = None

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as state_file:
                decoded = json.load(
                    state_file, object_pairs_hook=_reject_duplicate_keys)
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
        state._validate_user_defined_backups()
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


def _reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise StateValidationError(
                "State JSON contains duplicate object key: %s" % (key,))
        value[key] = item
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
