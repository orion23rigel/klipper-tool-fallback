import pytest


class ConfigError(Exception):
    pass


class CommandError(Exception):
    pass


class FakeReactor:
    NEVER = float("inf")

    def __init__(self):
        self.monotonic_time = 0.0
        self.timers = []
        self._timer_order = 0

    def monotonic(self):
        return self.monotonic_time

    def register_timer(self, callback, waketime=NEVER):
        timer = {
            "callback": callback,
            "waketime": waketime,
            "order": self._timer_order,
        }
        self._timer_order += 1
        self.timers.append(timer)
        return timer

    def update_timer(self, timer, waketime):
        timer["waketime"] = waketime

    def advance(self, seconds):
        target = self.monotonic_time + seconds
        while True:
            due = [
                timer for timer in self.timers
                if timer["waketime"] <= target
            ]
            if not due:
                break
            timer = min(due, key=lambda item: (
                item["waketime"], item["order"]))
            eventtime = timer["waketime"]
            timer["waketime"] = self.NEVER
            self.monotonic_time = eventtime
            next_waketime = timer["callback"](eventtime)
            if next_waketime is not None:
                timer["waketime"] = next_waketime
        self.monotonic_time = target


class FakeFilamentSensor:
    def __init__(self, enabled=True, filament_detected=False):
        self.enabled = enabled
        self.filament_detected = filament_detected
        self.status_calls = []
        self.malformed_status = None
        self.status_error = None

    def get_status(self, eventtime):
        self.status_calls.append(eventtime)
        if self.status_error is not None:
            raise self.status_error
        if self.malformed_status is not None:
            return self.malformed_status
        return {
            "enabled": self.enabled,
            "filament_detected": self.filament_detected,
        }


class FakeHeater:
    def __init__(self, name, temperature=200.0, target=200.0, ready=True,
                 events=None):
        self.name = name
        self.temperature = temperature
        self.target = target
        self.ready = ready
        self.events = events if events is not None else []
        self.status_error = None
        self.busy_error = None

    def get_temp(self, eventtime):
        self.events.append(("heater_status", self.name, eventtime))
        if self.status_error is not None:
            raise self.status_error
        return self.temperature, self.target

    def check_busy(self, eventtime):
        self.events.append(("heater_busy", self.name, eventtime))
        if self.busy_error is not None:
            raise self.busy_error
        return not self.ready


class FakeHeaters:
    def __init__(self, reactor, heaters=None, events=None):
        self.reactor = reactor
        self.events = events if events is not None else []
        self.heaters = dict(heaters or {})
        self.set_error = None

    def add_heater(self, heater):
        self.heaters[heater.name] = heater
        return heater

    def lookup_heater(self, name):
        if name not in self.heaters:
            raise ConfigError("Unknown heater '%s'" % (name,))
        return self.heaters[name]

    def set_temperature(self, heater, target, wait=False):
        self.events.append(("set_temperature", heater.name, target, wait))
        if self.set_error is not None:
            raise self.set_error
        heater.target = target


class FakePrintStats:
    def __init__(self, state="standby"):
        self.state = state
        self.eventtimes = []

    def set_state(self, state):
        self.state = state

    def get_status(self, eventtime):
        self.eventtimes.append(eventtime)
        return {"state": self.state}


class FakeSnapshotSequence:
    def __init__(self, *snapshots):
        self.snapshots = list(snapshots)
        self.calls = 0

    def __call__(self):
        snapshot = self.snapshots[min(self.calls, len(self.snapshots) - 1)]
        self.calls += 1
        return snapshot


class FakeGCode:
    def __init__(self):
        self.commands = {}
        self.responses = []
        self.script_events = []
        self.script_failures = {}
        self.workflow_events = []
        self.printer = None
        self.script_durations = {}

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

    def inject_script_failure(self, script, error):
        self.script_failures[script] = error

    def set_script_duration(self, script, duration):
        self.script_durations[script] = duration

    def run_script_from_command(self, script):
        self.script_events.append(script)
        error = self.script_failures.get(script)
        if error is not None:
            raise error
        duration = self.script_durations.get(script, 0.0)
        if duration:
            self.printer.get_reactor().advance(duration)
        print_stats = self.printer.lookup_object("print_stats", None)
        if print_stats is not None:
            if script == "PAUSE":
                print_stats.set_state("paused")
            elif script == "RESUME":
                print_stats.set_state("printing")

    def respond_info(self, message):
        self.responses.append(message)

    def error(self, message):
        return CommandError(message)

    def record_workflow_event(self, event, **details):
        self.workflow_events.append((event, details))


class FakePrinter:
    def __init__(self):
        self.reactor = FakeReactor()
        self.gcode = FakeGCode()
        self.gcode.printer = self
        heater = FakeHeater("extruder")
        self.heaters = FakeHeaters(
            self.reactor, {"extruder": heater}, heater.events)
        self.objects = {"gcode": self.gcode, "heaters": self.heaters}
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

    def get_int(self, name, default=..., minval=None, maxval=None):
        raw = self.get(name, default)
        if raw is default:
            return raw
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise self.error("Parameter '%s' must be an integer" % (name,))
        if str(value) != str(raw).strip():
            raise self.error("Parameter '%s' must be an integer" % (name,))
        if minval is not None and value < minval:
            raise self.error("Parameter '%s' must be at least %s" %
                             (name, minval))
        if maxval is not None and value > maxval:
            raise self.error("Parameter '%s' must be at most %s" %
                             (name, maxval))
        return value

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
