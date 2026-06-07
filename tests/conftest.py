import pytest


class ConfigError(Exception):
    pass


class CommandError(Exception):
    pass


class FakeReactor:
    def __init__(self):
        self.monotonic_time = 0.0

    def monotonic(self):
        return self.monotonic_time


class FakePrintStats:
    def __init__(self, state="standby"):
        self.state = state
        self.eventtimes = []

    def get_status(self, eventtime):
        self.eventtimes.append(eventtime)
        return {"state": self.state}


class FakeGCode:
    def __init__(self):
        self.commands = {}
        self.responses = []

    def register_command(self, name, handler, desc=None):
        previous = self.commands.get(name)
        if handler is None:
            self.commands.pop(name, None)
        else:
            self.commands[name] = handler
        return previous

    def create_gcode_command(self, command, commandline, params):
        return FakeGCmd(
            params=params, command=command, commandline=commandline,
            rawparams="")

    def invoke_command(self, name, gcmd=None):
        command = gcmd or self.create_gcode_command(name, name, {})
        return self.commands[name](command)

    def respond_info(self, message):
        self.responses.append(message)


class FakePrinter:
    def __init__(self):
        self.reactor = FakeReactor()
        self.gcode = FakeGCode()
        self.objects = {"gcode": self.gcode}
        self.object_loaders = {}
        self.events = {}

    def get_reactor(self):
        return self.reactor

    def add_object(self, name, value):
        self.objects[name] = value

    def set_object_loader(self, name, loader):
        self.object_loaders[name] = loader

    def lookup_object(self, name, default=...):
        if name in self.objects:
            return self.objects[name]
        if default is not ...:
            return default
        raise KeyError("Unexpected object lookup: %s" % (name,))

    def load_object(self, config, name):
        if name in self.objects:
            return self.objects[name]
        if name not in self.object_loaders:
            raise KeyError("Unexpected object load: %s" % (name,))
        value = self.object_loaders[name](config)
        self.objects[name] = value
        return value

    def register_event_handler(self, event, handler):
        self.events.setdefault(event, []).append(handler)

    def send_event(self, event, *args):
        return [handler(*args) for handler in self.events.get(event, ())]


class FakeConfig:
    def __init__(self, printer, name="tool_fallback", options=None):
        self.printer = printer
        self.name = name
        self.options = dict(options or {})
        self.read_options = set()

    def get_printer(self):
        return self.printer

    def get_name(self):
        return self.name

    def error(self, message):
        return ConfigError(message)

    def get(self, option, default=...):
        self.read_options.add(option)
        if option in self.options:
            return self.options[option]
        if default is not ...:
            return default
        raise self.error("Option '%s' in section '%s' must be specified" %
                         (option, self.name))

    def getfloat(self, option, default=..., above=None, minval=None, maxval=None):
        raw = self.get(option, default)
        if raw is default:
            return raw
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise self.error("Option '%s' in section '%s' must be a number" %
                             (option, self.name))
        if above is not None and value <= above:
            raise self.error("Option '%s' in section '%s' must be above %s" %
                             (option, self.name, above))
        if minval is not None and value < minval:
            raise self.error("Option '%s' in section '%s' must be at least %s" %
                             (option, self.name, minval))
        if maxval is not None and value > maxval:
            raise self.error("Option '%s' in section '%s' must be at most %s" %
                             (option, self.name, maxval))
        return value

    def unread_options(self):
        return set(self.options) - self.read_options

    def assert_all_options_read(self):
        unread = self.unread_options()
        assert not unread, "Unread options in %s: %s" % (
            self.name, ", ".join(sorted(unread)))


class FakePrefixConfig(FakeConfig):
    pass


class FakeGCmd:
    def __init__(self, params=None, command=None, commandline=None,
                 rawparams=""):
        self.params = dict(params or {})
        self.command = command
        self.commandline = commandline
        self.rawparams = rawparams
        self.responses = []

    def error(self, message):
        return CommandError(message)

    def get_command(self):
        return self.command

    def get_commandline(self):
        return self.commandline

    def get_raw_command_parameters(self):
        return self.rawparams

    def get(self, name, default=...):
        if name in self.params:
            return self.params[name]
        if default is not ...:
            return default
        raise self.error("Parameter '%s' must be specified" % (name,))

    def respond_info(self, message):
        self.responses.append(message)


@pytest.fixture
def printer():
    return FakePrinter()


@pytest.fixture
def config_factory(printer):
    def make_config(name="tool_fallback", **options):
        return FakeConfig(printer, name, options)

    return make_config


@pytest.fixture
def prefix_config_factory(printer):
    def make_config(name, **options):
        return FakePrefixConfig(printer, name, options)

    return make_config
