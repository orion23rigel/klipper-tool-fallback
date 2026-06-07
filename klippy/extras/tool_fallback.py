import json
from dataclasses import asdict
from types import MappingProxyType

from . import tool_fallback_config
from . import tool_fallback_state


class ToolFallback:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.global_config = tool_fallback_config.parse_global_config(config)
        self._config_error = config.error
        self._tools = {}
        self.config = None
        self.state = None
        self._state_store = None
        self._physical_handlers = None
        self._active_logical_tool = None
        self._selected_physical_tool = None
        self._transition_active = False
        self.printer.register_event_handler(
            "klippy:ready", self._handle_ready)
        self.gcode.register_command(
            "SHOW_TOOL_FALLBACK_STATE", self.cmd_SHOW_TOOL_FALLBACK_STATE,
            desc="Show canonical tool fallback state")

    def register_tool(self, tool):
        if tool.name in self._tools:
            raise self._config_error("Tool %s is configured more than once" %
                                     (tool.name,))
        self._tools[tool.name] = tool

    def finalize_configuration(self):
        self.config = tool_fallback_config.finalize_config(
            self.global_config, self._tools, self._config_error)
        return self.config

    def get_tool_config(self):
        return None if self.config is None else self.config.tools

    def get_state(self):
        return self.state

    def get_status(self, eventtime):
        if self.state is None:
            return {"initialized": False}
        snapshot = self.state.to_dict()
        snapshot["initialized"] = True
        snapshot["configuration"] = asdict(self.config.global_config)
        return snapshot

    def cmd_SHOW_TOOL_FALLBACK_STATE(self, gcmd):
        snapshot = self.get_status(None)
        gcmd.respond_info(json.dumps(snapshot, indent=2, sort_keys=True))

    def _handle_ready(self):
        normalized = self.finalize_configuration()
        state_path = normalized.global_config.state_path
        store = tool_fallback_state.StateStore(state_path)
        physical_handlers = None
        try:
            state = store.load_reconciled(normalized.tools)
            physical_handlers = self._capture_physical_handlers(
                normalized.tools)
            self._install_logical_handlers(normalized.tools)
            store.save(state)
        except Exception as error:
            if physical_handlers is not None:
                self._restore_physical_handlers(physical_handlers)
            if isinstance(error, json.JSONDecodeError):
                self._raise_state_error(state_path, "malformed JSON", error)
            if isinstance(error, tool_fallback_state.StateValidationError):
                self._raise_state_error(
                    state_path, "invalid state schema", error)
            if isinstance(error, OSError):
                self._raise_state_error(state_path, "filesystem failure", error)
            raise
        self._state_store = store
        self.state = state
        self._physical_handlers = MappingProxyType(physical_handlers)

    def _capture_physical_handlers(self, tools):
        handlers = {}
        try:
            for name in tools:
                handler = self.gcode.register_command(name, None)
                if handler is None:
                    raise self._config_error(
                        "Configured tool %s has no existing G-Code handler" %
                        (name,))
                handlers[name] = handler
        except Exception:
            self._restore_physical_handlers(handlers)
            raise
        return handlers

    def _install_logical_handlers(self, tools):
        for name in tools:
            self.gcode.register_command(name, self._logical_handler(name))

    def _logical_handler(self, logical_tool):
        def handler(gcmd):
            return self._route_logical(logical_tool, gcmd)
        return handler

    def _restore_physical_handlers(self, handlers):
        for name, handler in handlers.items():
            self.gcode.register_command(name, handler)

    def _raise_state_error(self, state_path, category, error):
        raise self._config_error(
            "Unable to initialize tool fallback state at '%s' (%s): %s" %
            (state_path, category, error))


def load_config(config):
    return ToolFallback(config)


def load_config_prefix(config):
    printer = config.get_printer()
    extension = printer.load_object(config, "tool_fallback")
    tool = tool_fallback_config.parse_tool_config(config)
    extension.register_tool(tool)
    return tool
