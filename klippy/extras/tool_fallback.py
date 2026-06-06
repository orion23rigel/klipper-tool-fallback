from . import tool_fallback_config


class ToolFallback:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.global_config = tool_fallback_config.parse_global_config(config)
        self._config_error = config.error
        self._tools = {}
        self.config = None
        self.printer.register_event_handler(
            "klippy:ready", self._handle_ready)

    def register_tool(self, tool):
        if tool.name in self._tools:
            raise self._config_error("Tool %s is configured more than once" %
                                     (tool.name,))
        self._tools[tool.name] = tool

    def finalize_configuration(self):
        self.config = tool_fallback_config.finalize_config(
            self.global_config, self._tools, self._config_error)
        return self.config

    def _handle_ready(self):
        self.finalize_configuration()


def load_config(config):
    return ToolFallback(config)


def load_config_prefix(config):
    printer = config.get_printer()
    extension = printer.load_object(config, "tool_fallback")
    tool = tool_fallback_config.parse_tool_config(config)
    extension.register_tool(tool)
    return tool
