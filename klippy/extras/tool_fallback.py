import json
from dataclasses import asdict

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
        try:
            state = store.load_reconciled(normalized.tools)
            store.save(state)
        except json.JSONDecodeError as error:
            self._raise_state_error(state_path, "malformed JSON", error)
        except tool_fallback_state.StateValidationError as error:
            self._raise_state_error(state_path, "invalid state schema", error)
        except OSError as error:
            self._raise_state_error(state_path, "filesystem failure", error)
        self._state_store = store
        self.state = state

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
