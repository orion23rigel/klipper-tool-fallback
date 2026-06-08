import json
from dataclasses import asdict
from dataclasses import dataclass
from types import MappingProxyType

from . import tool_fallback_config
from . import tool_fallback_state


SENSOR_POLL_INTERVAL = 0.25


@dataclass
class SensorRuntime:
    name: object
    sensor: object = None
    authority: str = "unknown"
    enabled: object = None
    detected: object = None
    confirmed_detected: object = None
    debounce_target: object = None
    debounce_generation: int = 0
    debounce_deadline: object = None
    debounce_timer: object = None
    debounce_origin: object = None
    pending_runout_context: bool = False
    outage_acknowledged: bool = False
    poll_timer: object = None


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
        self._sensor_runtime = {}
        self.printer.register_event_handler(
            "klippy:ready", self._handle_ready)
        self.gcode.register_command(
            "SHOW_TOOL_FALLBACK_STATE", self.cmd_SHOW_TOOL_FALLBACK_STATE,
            desc="Show canonical tool fallback state")
        self.gcode.register_command(
            "SELECT_PHYSICAL_TOOL", self.cmd_SELECT_PHYSICAL_TOOL,
            desc="Select a physical tool without changing logical mappings")
        self.gcode.register_command(
            "REMAP_TOOL", self.cmd_REMAP_TOOL,
            desc="Map a logical tool to a physical tool")
        self.gcode.register_command(
            "RESTORE_TOOL", self.cmd_RESTORE_TOOL,
            desc="Restore one logical tool to its identity mapping")
        self.gcode.register_command(
            "RESET_TOOL_MAPPINGS", self.cmd_RESET_TOOL_MAPPINGS,
            desc="Restore all logical tools to identity mappings")
        self.gcode.register_command(
            "TOOL_FALLBACK_RUNOUT", self.cmd_TOOL_FALLBACK_RUNOUT,
            desc="Record a tool fallback filament runout event")
        self.gcode.register_command(
            "TOOL_FALLBACK_INSERT", self.cmd_TOOL_FALLBACK_INSERT,
            desc="Record a tool fallback filament insert event")
        self.gcode.register_command(
            "SET_TOOL_FILAMENT_STATE", self.cmd_SET_TOOL_FILAMENT_STATE,
            desc="Set operator-owned tool fallback filament state")

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
        snapshot["active_logical_tool"] = self._active_logical_tool
        snapshot["selected_physical_tool"] = self._selected_physical_tool
        snapshot["transition_active"] = self._transition_active
        snapshot["sensor_authority"] = self._sensor_status_snapshot()
        return snapshot

    def cmd_SHOW_TOOL_FALLBACK_STATE(self, gcmd):
        snapshot = self.get_status(None)
        gcmd.respond_info(json.dumps(snapshot, indent=2, sort_keys=True))

    def cmd_SELECT_PHYSICAL_TOOL(self, gcmd):
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        if self._print_is_active():
            raise gcmd.error(
                "SELECT_PHYSICAL_TOOL is unavailable while a print is "
                "printing or paused")
        self._select_physical(physical_tool)

    def cmd_REMAP_TOOL(self, gcmd):
        logical_tool = self._require_configured_tool(gcmd, "LOGICAL")
        physical_tool = self._require_configured_tool(gcmd, "PHYSICAL")
        candidate = self.state.with_mapping(logical_tool, physical_tool)
        self._apply_mapping_candidate(gcmd, candidate)

    def cmd_RESTORE_TOOL(self, gcmd):
        logical_tool = self._require_configured_tool(gcmd, "TOOL")
        candidate = self.state.with_identity_mapping(logical_tool)
        self._apply_mapping_candidate(gcmd, candidate)

    def cmd_RESET_TOOL_MAPPINGS(self, gcmd):
        if self.state is None or self._physical_handlers is None:
            raise gcmd.error("Tool fallback routing is not initialized")
        candidate = self.state.with_identity_mappings()
        self._apply_mapping_candidate(gcmd, candidate)

    def cmd_TOOL_FALLBACK_RUNOUT(self, gcmd):
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        self._record_sensor_event(physical_tool, False)

    def cmd_TOOL_FALLBACK_INSERT(self, gcmd):
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        self._record_sensor_event(physical_tool, True)

    def cmd_SET_TOOL_FILAMENT_STATE(self, gcmd):
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        loaded = gcmd.get_int("LOADED", minval=0, maxval=1) == 1
        self._authorize_explicit_tool_state(gcmd, physical_tool)
        runtime = self._sensor_runtime.get(physical_tool)
        if runtime is not None and runtime.authority == "available":
            gcmd.respond_info(
                "Tool %s filament state override may be superseded by its "
                "enabled sensor" % (physical_tool,))
        candidate = (
            self.state.with_filament_loaded(physical_tool)
            if loaded else self.state.with_filament_unloaded(physical_tool)
        )
        if candidate is self.state:
            return
        try:
            self._persist_state(candidate)
        except OSError as error:
            raise gcmd.error(
                "Unable to persist tool fallback filament state: %s" %
                (error,))

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
        self._initialize_sensor_runtime(normalized.tools)

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

    def _route_logical(self, logical_tool, gcmd):
        if self.state is None or self._physical_handlers is None:
            raise gcmd.error("Tool fallback routing is not initialized")
        if self._transition_active:
            raise gcmd.error(
                "Cannot select logical tool %s during an active transition" %
                (logical_tool,))
        physical_tool = self.state.mappings[logical_tool]
        self._select_physical(physical_tool)
        self._active_logical_tool = logical_tool

    def _select_physical(self, physical_tool):
        handler = self._physical_handlers[physical_tool]
        physical_gcmd = self.gcode.create_gcode_command(
            physical_tool, physical_tool, {})
        handler(physical_gcmd)
        self._selected_physical_tool = physical_tool

    def _persist_state(self, candidate):
        self._state_store.save(candidate)
        self.state = candidate

    def _initialize_sensor_runtime(self, tools):
        self._sensor_runtime = {
            name: SensorRuntime(tool.filament_sensor)
            for name, tool in tools.items()
        }
        reactor = self.printer.get_reactor()
        eventtime = reactor.monotonic()
        for name, runtime in self._sensor_runtime.items():
            if runtime.name is not None:
                runtime.sensor = self.printer.lookup_object(
                    runtime.name, None)
            runtime.debounce_timer = reactor.register_timer(
                self._sensor_debounce_handler(name), reactor.NEVER)
            runtime.poll_timer = reactor.register_timer(
                self._sensor_poll_handler(name), reactor.NEVER)
            self._update_sensor_runtime(name, eventtime)
            reactor.update_timer(
                runtime.poll_timer, eventtime + SENSOR_POLL_INTERVAL)

    def _sensor_poll_handler(self, tool):
        def callback(eventtime):
            self._update_sensor_runtime(tool, eventtime)
            return eventtime + SENSOR_POLL_INTERVAL
        return callback

    def _sensor_debounce_handler(self, tool):
        def callback(eventtime):
            runtime = self._sensor_runtime[tool]
            if (runtime.debounce_deadline != eventtime
                    or runtime.debounce_target is None):
                return self.printer.get_reactor().NEVER
            generation = runtime.debounce_generation
            target = runtime.debounce_target
            status = self._read_sensor_status(runtime, eventtime)
            if status is None or not status["enabled"]:
                self._set_sensor_unknown(runtime)
                return self.printer.get_reactor().NEVER
            runtime.enabled = status["enabled"]
            runtime.detected = status["filament_detected"]
            if (runtime.debounce_generation != generation
                    or status["filament_detected"] != target):
                self._observe_sensor_reading(tool, status, eventtime, None)
                return self.printer.get_reactor().NEVER
            candidate = self._build_sensor_filament_candidate(tool, runtime)
            if candidate is not self.state:
                self._persist_state(candidate)
            runtime.authority = "available"
            runtime.confirmed_detected = target
            runtime.debounce_target = None
            runtime.debounce_deadline = None
            runtime.debounce_origin = None
            runtime.pending_runout_context = False
            return self.printer.get_reactor().NEVER
        return callback

    def _build_sensor_filament_candidate(self, tool, runtime):
        if runtime.debounce_target:
            if runtime.debounce_origin == "insert":
                return self.state.with_filament_loaded(tool)
            return self.state.with_reconciled_filament_loaded(tool)
        if runtime.pending_runout_context:
            return self.state.with_failed_runout(tool)
        return self.state.with_filament_unloaded(tool)

    def _update_sensor_runtime(self, tool, eventtime):
        runtime = self._sensor_runtime[tool]
        status = self._read_sensor_status(runtime, eventtime)
        if status is None or not status["enabled"]:
            if status is None:
                runtime.enabled = None
                runtime.detected = None
            else:
                runtime.enabled = status["enabled"]
                runtime.detected = status["filament_detected"]
            self._set_sensor_unknown(runtime)
            return
        self._observe_sensor_reading(tool, status, eventtime, None)

    def _observe_sensor_reading(self, tool, status, eventtime, origin):
        runtime = self._sensor_runtime[tool]
        runtime.enabled = status["enabled"]
        runtime.detected = status["filament_detected"]
        detected = status["filament_detected"]
        if (runtime.authority == "available"
                and runtime.confirmed_detected == detected
                and runtime.debounce_target is None):
            return
        if runtime.debounce_target == detected:
            if origin is not None:
                runtime.debounce_origin = origin
                runtime.pending_runout_context = (
                    origin == "runout"
                    and self._selected_physical_tool == tool
                    and self._print_is_active())
            return
        runtime.debounce_target = detected
        runtime.debounce_generation += 1
        runtime.debounce_deadline = (
            eventtime + self.config.global_config.debounce_time)
        runtime.debounce_origin = origin
        runtime.pending_runout_context = (
            origin == "runout" and self._selected_physical_tool == tool
            and self._print_is_active())
        self.printer.get_reactor().update_timer(
            runtime.debounce_timer, runtime.debounce_deadline)

    def _set_sensor_unknown(self, runtime):
        runtime.authority = "unknown"
        runtime.confirmed_detected = None
        runtime.debounce_target = None
        runtime.debounce_generation += 1
        runtime.debounce_deadline = None
        runtime.debounce_origin = None
        runtime.pending_runout_context = False
        if runtime.debounce_timer is not None:
            self.printer.get_reactor().update_timer(
                runtime.debounce_timer, self.printer.get_reactor().NEVER)

    def _record_sensor_event(self, tool, detected):
        runtime = self._sensor_runtime[tool]
        eventtime = self.printer.get_reactor().monotonic()
        status = self._read_sensor_status(runtime, eventtime)
        if status is None or not status["enabled"]:
            self._set_sensor_unknown(runtime)
            return
        if status["filament_detected"] != detected:
            self._observe_sensor_reading(tool, status, eventtime, None)
            return
        self._observe_sensor_reading(
            tool, status, eventtime, "insert" if detected else "runout")

    def _authorize_explicit_tool_state(self, gcmd, physical_tool):
        print_state = self._get_print_state()
        if (print_state == "printing"
                and physical_tool == self._selected_physical_tool):
            raise gcmd.error(
                "SET_TOOL_FILAMENT_STATE for selected physical tool %s is "
                "only available while paused or outside a print" %
                (physical_tool,))

    def _read_sensor_status(self, runtime, eventtime):
        sensor = runtime.sensor
        if sensor is None or not callable(getattr(sensor, "get_status", None)):
            return None
        try:
            status = sensor.get_status(eventtime)
        except Exception:
            return None
        if type(status) is not dict:
            return None
        enabled = status.get("enabled")
        detected = status.get("filament_detected")
        if type(enabled) is not bool or type(detected) is not bool:
            return None
        return {
            "enabled": enabled,
            "filament_detected": detected,
        }

    def _sensor_status_snapshot(self):
        return {
            tool: {
                "configured": runtime.name,
                "authority": runtime.authority,
                "enabled": runtime.enabled,
                "detected": runtime.detected,
                "outage_acknowledged": runtime.outage_acknowledged,
            }
            for tool, runtime in sorted(
                self._sensor_runtime.items(),
                key=lambda item: int(item[0][1:]))
        }

    def _apply_mapping_candidate(self, gcmd, candidate):
        if candidate is self.state:
            return
        if (self._print_is_active() and self._active_logical_tool is not None
                and candidate.mappings[self._active_logical_tool]
                != self.state.mappings[self._active_logical_tool]):
            self._transition_active_route(gcmd, candidate)
            return
        try:
            self._persist_state(candidate)
        except OSError as error:
            raise gcmd.error(
                "Unable to persist tool fallback mappings: %s" % (error,))

    def _transition_active_route(self, gcmd, candidate):
        if self._transition_active:
            raise gcmd.error("Another tool fallback transition is active")
        logical_tool = self._active_logical_tool
        current_physical = self._selected_physical_tool
        if current_physical is None:
            raise gcmd.error(
                "Cannot transition active logical route %s because the "
                "selected physical tool is unknown" % (logical_tool,))
        requested_physical = candidate.mappings[logical_tool]
        print_state = self._get_print_state()
        owns_pause = False
        self._transition_active = True
        try:
            if print_state == "printing":
                self.gcode.run_script_from_command(
                    self.config.global_config.pause_gcode)
                owns_pause = True
            gcmd.respond_info(
                "Changing active logical %s from physical %s to physical %s" %
                (logical_tool, current_physical, requested_physical))
            self._run_pre_selection_transition_stages(
                logical_tool, current_physical, requested_physical)
            self._select_physical(requested_physical)
            self._run_post_selection_transition_stages(
                logical_tool, current_physical, requested_physical)
            try:
                self._persist_state(candidate)
            except OSError as persist_error:
                try:
                    self._select_physical(current_physical)
                except Exception as rollback_error:
                    raise gcmd.error(
                        "Unable to persist tool fallback mappings: %s; "
                        "physical rollback to %s also failed: %s" %
                        (persist_error, current_physical, rollback_error))
                raise gcmd.error(
                    "Unable to persist tool fallback mappings: %s; physical "
                    "selection rolled back to %s" %
                    (persist_error, current_physical))
            if owns_pause:
                self.gcode.run_script_from_command(
                    self.config.global_config.resume_gcode)
        finally:
            self._transition_active = False

    def _run_pre_selection_transition_stages(
            self, logical_tool, current_physical, requested_physical):
        # Phase 4 integrates temperature-transfer stages here.
        pass

    def _run_post_selection_transition_stages(
            self, logical_tool, current_physical, requested_physical):
        # Phase 3 integrates conditional purge here.
        pass

    def _require_configured_tool(self, gcmd, parameter):
        if self.config is None or self._physical_handlers is None:
            raise gcmd.error("Tool fallback routing is not initialized")
        name = gcmd.get(parameter)
        if name not in self.config.tools:
            raise gcmd.error(
                "%s must name a configured canonical tool; got %s" %
                (parameter, name))
        return name

    def _print_is_active(self):
        return self._get_print_state() in ("printing", "paused")

    def _get_print_state(self):
        print_stats = self.printer.lookup_object("print_stats", None)
        if print_stats is None:
            return None
        eventtime = self.printer.get_reactor().monotonic()
        return print_stats.get_status(eventtime).get("state")

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
