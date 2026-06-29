import json
import math
import re
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import replace
from types import MappingProxyType

from . import tool_fallback_config
from . import tool_fallback_state


SENSOR_POLL_INTERVAL = 0.25
NOTIFICATION_DETAIL_LIMIT = 160
NOTIFICATION_EVENTS = frozenset((
    "FALLBACK_SUCCESS", "FALLBACK_FAILURE", "TRANSIENT_RECOVERY",
))
REASON_CODES = frozenset((
    "SUCCESS", "TRANSIENT_CLEARED", "GRAPH_EXHAUSTED", "PURGE_FAILED",
    "HEATING_TIMEOUT", "MAPPING_PERSIST_FAILED", "RESUME_FAILED",
    "UNEXPECTED_FAILURE",
))


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
    outage_acknowledged: bool = False
    outage_pause_suppressed: bool = False
    outage_pause_pending: bool = False
    poll_timer: object = None


@dataclass(frozen=True)
class WorkflowCheckpoint:
    source: str
    stage: str
    generation: int
    logical_tool: object = None
    current_physical_tool: object = None
    requested_physical_tool: object = None
    pause_owned: bool = False
    target_temperature: object = None
    stage_deadline: object = None
    graph_report: object = None
    failure_reason: object = None


@dataclass(frozen=True)
class TerminalEvent:
    event: str
    generation: int
    logical_tool: object = None
    failed_tool: object = None
    selected_tool: object = None
    reason_code: str = "UNEXPECTED_FAILURE"
    reason_detail: object = None


@dataclass(frozen=True)
class GraphResolution:
    candidate: object
    evaluated: tuple
    unloaded: tuple
    failed: tuple
    looped: tuple
    unknown_authority_eligible: tuple
    scan_count: int = 1

    def to_dict(self):
        return {
            "candidate": self.candidate,
            "evaluated": list(self.evaluated),
            "unloaded": list(self.unloaded),
            "failed": list(self.failed),
            "looped": list(self.looped),
            "unknown_authority_eligible": list(
                self.unknown_authority_eligible),
            "scan_count": self.scan_count,
        }


@dataclass(frozen=True)
class BackupOperation:
    operation: str
    tool: object = None
    backups: object = None


@dataclass(frozen=True)
class QueuedBackupOperation:
    sequence: int
    operation: BackupOperation


def resolve_backup_graph(state, failed_tool, unknown_authority=()):
    unknown_authority = frozenset(unknown_authority)
    evaluated = []
    evaluated_set = set()
    unloaded = []
    failed = []
    looped = []
    unknown_eligible = []

    def visit(tool, ancestry):
        if tool in ancestry:
            looped.append("->".join(ancestry + (tool,)))
            return None
        if tool in evaluated_set:
            return None
        evaluated_set.add(tool)
        evaluated.append(tool)
        tool_state = state.tools[tool]
        if not tool_state.loaded:
            unloaded.append(tool)
        if tool_state.failed:
            failed.append(tool)
        if tool_state.loaded and not tool_state.failed:
            if tool in unknown_authority:
                unknown_eligible.append(tool)
            return tool
        next_ancestry = ancestry + (tool,)
        for backup in tool_state.backups:
            candidate = visit(backup, next_ancestry)
            if candidate is not None:
                return candidate
        return None

    candidate = None
    for backup in state.tools[failed_tool].backups:
        candidate = visit(backup, (failed_tool,))
        if candidate is not None:
            break
    return GraphResolution(
        candidate=candidate,
        evaluated=tuple(evaluated),
        unloaded=tuple(unloaded),
        failed=tuple(failed),
        looped=tuple(looped),
        unknown_authority_eligible=tuple(unknown_eligible),
    )


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
        self._heaters = {}
        self._workflow_checkpoint = None
        self._workflow_generation = 0
        self._backup_operation_queue = []
        self._backup_operation_sequence = 0
        self._backup_drain_in_progress = False
        self._last_backup_drain_failure = None
        self._notification_in_progress = False
        self._finalized_events = {}
        self.printer.register_event_handler(
            "klippy:ready", self._handle_ready)
        self.printer.register_event_handler(
            "klippy:disconnect", self._handle_disconnect)
        self.gcode.register_command(
            "SHOW_TOOL_FALLBACK_STATE", self.cmd_SHOW_TOOL_FALLBACK_STATE,
            desc="Show canonical tool fallback state")
        # Re-entrancy guard for guarded resume handler
        self._resume_in_progress = False
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
            "SET_TOOL_BACKUPS", self.cmd_SET_TOOL_BACKUPS,
            desc="Replace one physical tool's ordered backup policy")
        self.gcode.register_command(
            "RESTORE_TOOL_BACKUPS", self.cmd_RESTORE_TOOL_BACKUPS,
            desc="Restore one physical tool's configured backup policy")
        self.gcode.register_command(
            "RESET_TOOL_BACKUPS", self.cmd_RESET_TOOL_BACKUPS,
            desc="Restore every physical tool's configured backup policy")
        self.gcode.register_command(
            "DEFINE_TOOL_BACKUP", self.cmd_DEFINE_TOOL_BACKUP,
            desc="Define a user backup mapping for a logical tool")
        self.gcode.register_command(
            "UNDEFINE_TOOL_BACKUP", self.cmd_UNDEFINE_TOOL_BACKUP,
            desc="Remove a user-defined backup mapping for a logical tool")
        self.gcode.register_command(
            "TOOL_FALLBACK_RUNOUT", self.cmd_TOOL_FALLBACK_RUNOUT,
            desc="Record a tool fallback filament runout event")
        self.gcode.register_command(
            "TOOL_FALLBACK_INSERT", self.cmd_TOOL_FALLBACK_INSERT,
            desc="Record a tool fallback filament insert event")
        self.gcode.register_command(
            "SET_TOOL_FILAMENT_STATE", self.cmd_SET_TOOL_FILAMENT_STATE,
            desc="Set operator-owned tool fallback filament state")
        self.gcode.register_command(
            "PURGE_TOOL", self.cmd_PURGE_TOOL,
            desc="Purge a physical tool and record durable purge state")
        self.gcode.register_command(
            "MARK_TOOL_PURGED", self.cmd_MARK_TOOL_PURGED,
            desc="Mark a physical tool purged")
        self.gcode.register_command(
            "MARK_TOOL_UNPURGED", self.cmd_MARK_TOOL_UNPURGED,
            desc="Mark a physical tool unpurged")
        # Wrap the global resume gcode with a guarded handler so that a
        # user-invoked RESUME can trigger guarded recovery from a
        # 'heating_timeout' checkpoint.  Keep a reference to the original
        # resume handler so normal resume behavior is preserved when no
        # guarded recovery is required.
        try:
            self._resume_original = self.gcode.register_command(
                self.global_config.resume_gcode,
                self._cmd_resume_wrapper,
                desc="Guarded resume for tool fallback")
        except Exception:
            # Best-effort: if registering fails, silently continue
            self._resume_original = None

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
        snapshot["workflow"] = self._workflow_status_snapshot()
        snapshot["backup_operation_queue"] = (
            self._backup_queue_status_snapshot())
        return snapshot

    def cmd_SHOW_TOOL_FALLBACK_STATE(self, gcmd):
        snapshot = self.get_status(None)
        gcmd.respond_info(json.dumps(snapshot, indent=2, sort_keys=True))

    def cmd_SELECT_PHYSICAL_TOOL(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        self._guard_workflow_operation(gcmd.error, "physical tool selection")
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        if self._print_is_active():
            raise gcmd.error(
                "SELECT_PHYSICAL_TOOL is unavailable while a print is "
                "printing or paused")
        self._select_physical(physical_tool)

    def cmd_REMAP_TOOL(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        self._guard_workflow_operation(gcmd.error, "tool remapping")
        logical_tool = self._require_configured_tool(gcmd, "LOGICAL")
        physical_tool = self._require_configured_tool(gcmd, "PHYSICAL")
        candidate = self.state.with_mapping(logical_tool, physical_tool)
        self._apply_mapping_candidate(gcmd, candidate)

    def cmd_RESTORE_TOOL(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        self._guard_workflow_operation(gcmd.error, "tool mapping restore")
        logical_tool = self._require_configured_tool(gcmd, "TOOL")
        candidate = self.state.with_identity_mapping(logical_tool)
        self._apply_mapping_candidate(gcmd, candidate)

    def cmd_RESET_TOOL_MAPPINGS(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        self._guard_workflow_operation(gcmd.error, "tool mapping reset")
        if self.state is None or self._physical_handlers is None:
            raise gcmd.error("Tool fallback routing is not initialized")
        candidate = self.state.with_identity_mappings()
        self._apply_mapping_candidate(gcmd, candidate)

    def cmd_SET_TOOL_BACKUPS(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        operation = BackupOperation(
            "set", physical_tool,
            self._parse_backup_list(gcmd, physical_tool),
        )
        self._apply_backup_operation(gcmd, operation)

    def cmd_RESTORE_TOOL_BACKUPS(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        operation = BackupOperation("restore", physical_tool)
        self._apply_backup_operation(gcmd, operation)

    def cmd_RESET_TOOL_BACKUPS(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        if self.state is None or self._physical_handlers is None:
            raise gcmd.error("Tool fallback routing is not initialized")
        self._apply_backup_operation(gcmd, BackupOperation("reset"))

    def cmd_DEFINE_TOOL_BACKUP(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        self._guard_workflow_operation(
            gcmd.error, "tool backup definition")
        logical_tool = self._require_configured_tool(gcmd, "LOGICAL")
        backup_tool = self._require_configured_tool(gcmd, "BACKUP")
        if logical_tool == backup_tool:
            raise gcmd.error(
                "Tool %s cannot be its own backup" % (logical_tool,))
        candidate = self.state.with_user_defined_backup(
            logical_tool, backup_tool)
        if candidate is self.state:
            gcmd.respond_info(
                "Tool %s backup unchanged: %s -> %s (no write)" %
                (logical_tool,
                 self.state.user_defined_backups.get(logical_tool, "(none)"),
                 backup_tool))
            return
        try:
            self._persist_state(candidate)
        except OSError as error:
            raise gcmd.error(
                "Unable to persist tool fallback backup mapping: %s" %
                (error,))
        gcmd.respond_info(
            "Tool %s user backup set to %s" % (logical_tool, backup_tool))

    def cmd_UNDEFINE_TOOL_BACKUP(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        self._guard_workflow_operation(
            gcmd.error, "tool backup undefinition")
        logical_tool = self._require_configured_tool(gcmd, "TOOL")
        if logical_tool not in self.state.user_defined_backups:
            raise gcmd.error(
                "No user-defined backup for tool %s" % (logical_tool,))
        candidate = self.state.with_user_defined_backup(
            logical_tool, None)
        try:
            self._persist_state(candidate)
        except OSError as error:
            raise gcmd.error(
                "Unable to persist tool fallback backup mapping: %s" %
                (error,))
        gcmd.respond_info(
            "Tool %s user backup removed" % (logical_tool,))

    def cmd_TOOL_FALLBACK_RUNOUT(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        pause_owned = gcmd.get_int(
            "PAUSE_OWNED", 0, minval=0, maxval=1) == 1
        self._record_sensor_event(
            physical_tool, False, requested_ownership=pause_owned)

    def cmd_TOOL_FALLBACK_INSERT(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        self._record_sensor_event(physical_tool, True)

    def cmd_SET_TOOL_FILAMENT_STATE(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        loaded = gcmd.get_int("LOADED", minval=0, maxval=1) == 1
        self._authorize_explicit_tool_state(
            gcmd, physical_tool, "SET_TOOL_FILAMENT_STATE")
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

    def cmd_PURGE_TOOL(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        self._purge_physical_tool(
            physical_tool, gcmd.error, gcmd.respond_info, force=True)

    def cmd_MARK_TOOL_PURGED(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        self._authorize_explicit_tool_state(
            gcmd, physical_tool, "MARK_TOOL_PURGED")
        self._warn_unknown_purge_authority(physical_tool, gcmd.respond_info)
        candidate = self._purged_candidate(physical_tool, gcmd.error)
        self._persist_purge_candidate(gcmd, candidate)

    def cmd_MARK_TOOL_UNPURGED(self, gcmd):
        self._guard_notification_operation(gcmd.error)
        physical_tool = self._require_configured_tool(gcmd, "TOOL")
        self._authorize_explicit_tool_state(
            gcmd, physical_tool, "MARK_TOOL_UNPURGED")
        candidate = self.state.with_tool_unpurged(physical_tool)
        self._persist_purge_candidate(gcmd, candidate)

    def _handle_ready(self):
        normalized = self.finalize_configuration()
        state_path = normalized.global_config.state_path
        store = tool_fallback_state.StateStore(state_path)
        physical_handlers = None
        try:
            state = store.load_reconciled(normalized.tools)
            heaters = self._resolve_heaters(normalized.tools)
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
        self._heaters = MappingProxyType(heaters)
        self._initialize_sensor_runtime(normalized.tools)

    def _handle_disconnect(self):
        if self._backup_operation_queue:
            self.gcode.respond_info(
                "Discarding %d queued tool fallback backup operation(s) on "
                "disconnect; resubmit them after restart" %
                (len(self._backup_operation_queue),))

    def _resolve_heaters(self, tools):
        manager = self.printer.lookup_object("heaters")
        heaters = {}
        for tool, tool_config in tools.items():
            try:
                heaters[tool] = manager.lookup_heater(tool_config.heater)
            except Exception as error:
                raise self._config_error(
                    "Configured tool %s heater '%s' is unavailable: %s" %
                    (tool, tool_config.heater, error))
        return heaters

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
        self._guard_notification_operation(gcmd.error)
        if self.state is None or self._physical_handlers is None:
            raise gcmd.error("Tool fallback routing is not initialized")
        self._guard_workflow_operation(gcmd.error, "logical tool selection")
        if self._transition_active:
            raise gcmd.error(
                "Cannot select logical tool %s during an active transition" %
                (logical_tool,))
        physical_tool = self.state.mappings[logical_tool]
        self._select_and_conditionally_purge(
            physical_tool, gcmd.error, gcmd.respond_info)
        self._active_logical_tool = logical_tool

    def _select_and_conditionally_purge(
            self, physical_tool, error_factory, respond_info,
            already_guarded=False):
        print_state = self._get_print_state()
        needs_purge = not self.state.tools[physical_tool].purged
        owns_pause = False
        if needs_purge and print_state == "printing" and not already_guarded:
            self.gcode.run_script_from_command(
                self.config.global_config.pause_gcode)
            owns_pause = True
        self._select_physical(physical_tool)
        if needs_purge:
            if print_state in ("printing", "paused"):
                self._purge_physical_tool(
                    physical_tool, error_factory, respond_info)
            else:
                respond_info(
                    "Tool %s is selected but remains unpurged outside an "
                    "active print" % (physical_tool,))
        if owns_pause:
            self.gcode.run_script_from_command(
                self.config.global_config.resume_gcode)

    def _select_physical(self, physical_tool):
        runtime = self._sensor_runtime.get(physical_tool)
        if runtime is not None and runtime.authority == "unknown":
            self.gcode.respond_info(
                "Tool %s sensor authority is unknown; selection will "
                "continue but sensor-triggered fallback is unavailable" %
                (physical_tool,))
        handler = self._physical_handlers[physical_tool]
        physical_gcmd = self.gcode.create_gcode_command(
            physical_tool, physical_tool, {})
        handler(physical_gcmd)
        self._selected_physical_tool = physical_tool

    def _persist_state(self, candidate):
        self._state_store.save(candidate)
        self.state = candidate

    def _block_workflow(
            self, checkpoint, reason, reason_code="UNEXPECTED_FAILURE"):
        blocked = replace(
            checkpoint, stage="blocked", stage_deadline=None,
            failure_reason=reason)
        self._workflow_checkpoint = blocked
        self.gcode.respond_info(reason)
        if blocked.source == "automatic_fallback":
            self._finalize_fallback_failure(
                blocked, reason_code, reason)
        return blocked

    def _after_terminal_workflow(self):
        self._drain_backup_operations()

    def _sanitize_reason_detail(self, detail):
        value = str(detail).encode("ascii", "replace").decode("ascii")
        value = re.sub(r"[^A-Za-z0-9._:/+-]+", "_", value).strip("_")
        return (value or "n/a")[:NOTIFICATION_DETAIL_LIMIT]

    def _build_notification_script(self, event):
        def token(value):
            return "n/a" if value is None else str(value)

        fields = (
            ("EVENT", event.event),
            ("GENERATION", event.generation),
            ("LOGICAL_TOOL", event.logical_tool),
            ("FAILED_TOOL", event.failed_tool),
            ("SELECTED_TOOL", event.selected_tool),
            ("REASON_CODE", event.reason_code),
        )
        script = self.config.global_config.notify_gcode + " " + " ".join(
            "%s=%s" % (name, token(value)) for name, value in fields)
        if (event.reason_code == "UNEXPECTED_FAILURE"
                and event.reason_detail is not None):
            script += " REASON_DETAIL=%s" % (
                self._sanitize_reason_detail(event.reason_detail),)
        return script

    def _attempt_notification(self, event):
        if event.event not in NOTIFICATION_EVENTS:
            self.gcode.respond_info(
                "Suppressing unknown tool fallback notification event %s" %
                (event.event,))
            return False
        if event.reason_code not in REASON_CODES:
            self.gcode.respond_info(
                "Suppressing unknown tool fallback reason code %s" %
                (event.reason_code,))
            return False
        if self._notification_in_progress:
            self.gcode.respond_info(
                "Suppressing recursive tool fallback notification")
            return False
        existing = self._finalized_events.get(event.generation)
        if existing is not None:
            if existing != event:
                self.gcode.respond_info(
                    "Suppressing conflicting finalized event for workflow "
                    "generation %s" % (event.generation,))
            return False
        self._finalized_events[event.generation] = event
        self._notification_in_progress = True
        try:
            self.gcode.run_script_from_command(
                self._build_notification_script(event))
        except Exception as error:
            self.gcode.respond_info(
                "Tool fallback notification adapter failed: %s" % (error,))
        finally:
            self._notification_in_progress = False
        return True

    def _terminal_event(
            self, checkpoint, event, reason_code, reason_detail=None):
        return TerminalEvent(
            event=event,
            generation=checkpoint.generation,
            logical_tool=checkpoint.logical_tool,
            failed_tool=checkpoint.current_physical_tool,
            selected_tool=checkpoint.requested_physical_tool,
            reason_code=reason_code,
            reason_detail=reason_detail,
        )

    def _finalize_transient_outcome(self, checkpoint):
        self._attempt_notification(self._terminal_event(
            checkpoint, "TRANSIENT_RECOVERY", "TRANSIENT_CLEARED"))
        self._after_terminal_workflow()

    def _finalize_fallback_success(self, checkpoint):
        self._attempt_notification(self._terminal_event(
            checkpoint, "FALLBACK_SUCCESS", "SUCCESS"))
        self._after_terminal_workflow()

    def _finalize_fallback_failure(
            self, checkpoint, reason_code, reason_detail=None):
        detail = reason_detail if reason_code == "UNEXPECTED_FAILURE" else None
        self._attempt_notification(self._terminal_event(
            checkpoint, "FALLBACK_FAILURE", reason_code, detail))
        self._after_terminal_workflow()

    def _workflow_stage_failed(self, checkpoint):
        return checkpoint is None or checkpoint.stage == "blocked"

    def _capture_and_shutdown_source(self, checkpoint):
        source = checkpoint.current_physical_tool
        heater = self._heaters.get(source)
        if heater is None:
            return self._block_workflow(
                checkpoint, "Tool %s has no resolved source heater" % source)
        eventtime = self.printer.get_reactor().monotonic()
        try:
            unused_temperature, target = heater.get_temp(eventtime)
        except Exception as error:
            return self._block_workflow(
                checkpoint, "Unable to read tool %s source heater target: %s" %
                (source, error))
        if (not isinstance(target, (int, float))
                or isinstance(target, bool)
                or not math.isfinite(target)
                or target <= 0.0):
            return self._block_workflow(
                checkpoint,
                "Tool %s source heater target must be finite and above 0.0; "
                "got %r" % (source, target))
        try:
            self.printer.lookup_object("heaters").set_temperature(
                heater, 0.0, wait=False)
        except Exception as error:
            return self._block_workflow(
                checkpoint, "Unable to disable tool %s source heater: %s" %
                (source, error))
        advanced = replace(
            checkpoint, stage="source_shutdown",
            target_temperature=float(target), failure_reason=None)
        self._workflow_checkpoint = advanced
        return advanced

    def _preheat_requested_tool(self, checkpoint):
        requested = checkpoint.requested_physical_tool
        target = checkpoint.target_temperature
        heater = self._heaters.get(requested)
        if heater is None:
            return self._block_workflow(
                checkpoint, "Tool %s has no resolved destination heater" %
                requested)
        try:
            self.printer.lookup_object("heaters").set_temperature(
                heater, target, wait=False)
        except Exception as error:
            return self._block_workflow(
                checkpoint, "Unable to preheat tool %s: %s" %
                (requested, error))
        advanced = replace(
            checkpoint, stage="preheated", failure_reason=None)
        self._workflow_checkpoint = advanced
        return advanced

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
                self._set_sensor_unknown(tool, runtime)
                return self.printer.get_reactor().NEVER
            runtime.enabled = status["enabled"]
            runtime.detected = status["filament_detected"]
            # If the sensor reading changed or this is not the expected target,
            # normally observe the new reading and restart debounce. However,
            # when the debounce was explicitly seeded by a TOOL_FALLBACK_RUNOUT
            # command (debounce_origin == "runout"), honor the commanded
            # target instead of requiring the physical sensor to match it.
            if runtime.debounce_generation != generation:
                self._observe_sensor_reading(tool, status, eventtime, None)
                return self.printer.get_reactor().NEVER
            if status["filament_detected"] != target:
                if runtime.debounce_origin != "runout":
                    self._observe_sensor_reading(tool, status, eventtime, None)
                    return self.printer.get_reactor().NEVER
                # else: commanded runout was given; proceed using the commanded target
            candidate = self._build_sensor_filament_candidate(tool, runtime)
            if candidate is not self.state:
                self._persist_state(candidate)
            pending = self._pending_runout_checkpoint(tool)
            runtime.authority = "available"
            runtime.confirmed_detected = target
            runtime.outage_acknowledged = False
            runtime.outage_pause_suppressed = False
            runtime.outage_pause_pending = False
            runtime.debounce_target = None
            runtime.debounce_deadline = None
            runtime.debounce_origin = None
            if pending is not None:
                if target:
                    self._complete_transient_runout(pending)
                else:
                    self._confirmed_runout(pending)
            return self.printer.get_reactor().NEVER
        return callback

    def _build_sensor_filament_candidate(self, tool, runtime):
        if runtime.debounce_target:
            if runtime.debounce_origin == "insert":
                return self.state.with_filament_loaded(tool)
            return self.state.with_reconciled_filament_loaded(tool)
        if self._pending_runout_checkpoint(tool) is not None:
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
            self._set_sensor_unknown(tool, runtime)
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
            return
        runtime.debounce_target = detected
        runtime.debounce_generation += 1
        runtime.debounce_deadline = (
            eventtime + self.config.global_config.debounce_time)
        runtime.debounce_origin = origin
        self.printer.get_reactor().update_timer(
            runtime.debounce_timer, runtime.debounce_deadline)

    def _set_sensor_unknown(self, tool, runtime):
        newly_unknown = runtime.authority == "available"
        runtime.authority = "unknown"
        runtime.confirmed_detected = None
        runtime.debounce_target = None
        runtime.debounce_generation += 1
        runtime.debounce_deadline = None
        runtime.debounce_origin = None
        if runtime.debounce_timer is not None:
            self.printer.get_reactor().update_timer(
                runtime.debounce_timer, self.printer.get_reactor().NEVER)
        if newly_unknown:
            self.gcode.respond_info(
                "Tool %s sensor authority became unknown; sensor-triggered "
                "fallback is unavailable until authority is restored" %
                (tool,))
            if tool == self._selected_physical_tool:
                print_state = self._get_print_state()
                runtime.outage_pause_suppressed = print_state == "paused"
                runtime.outage_pause_pending = print_state == "printing"
        self._handle_selected_sensor_outage(tool, runtime)

    def _handle_selected_sensor_outage(self, tool, runtime):
        if (not runtime.outage_pause_pending
                or tool != self._selected_physical_tool
                or runtime.outage_acknowledged
                or runtime.outage_pause_suppressed
                or self._get_print_state() != "printing"):
            return
        try:
            self.gcode.run_script_from_command(
                self.config.global_config.pause_gcode)
        except Exception as error:
            self.gcode.respond_info(
                "Unable to pause after tool %s sensor authority loss: %s" %
                (tool, error))
            return
        runtime.outage_acknowledged = True
        runtime.outage_pause_pending = False

    def _record_sensor_event(
            self, tool, detected, requested_ownership=False):
        runtime = self._sensor_runtime[tool]
        eventtime = self.printer.get_reactor().monotonic()
        status = self._read_sensor_status(runtime, eventtime)
        if status is None or not status["enabled"]:
            self._set_sensor_unknown(tool, runtime)
            return
        if status["filament_detected"] != detected:
            origin = "runout" if not detected else "insert"
            # If this was an explicit TOOL_FALLBACK_RUNOUT/INSERT command and
            # the physical sensor disagrees, treat the command as authoritative
            # only when the caller explicitly claimed ownership (PAUSE_OWNED=1).
            if requested_ownership:
                # Seed debounce with the commanded target (not the current sensor
                # reading) so an explicit TOOL_FALLBACK_RUNOUT/INSERT command can
                # initiate debounce toward the commanded state.
                runtime.enabled = status["enabled"]
                runtime.detected = status["filament_detected"]
                runtime.debounce_target = detected
                runtime.debounce_generation += 1
                runtime.debounce_deadline = (
                    eventtime + self.config.global_config.debounce_time)
                runtime.debounce_origin = origin
                self.printer.get_reactor().update_timer(
                    runtime.debounce_timer, runtime.debounce_deadline)
                # Begin pending runout immediately for commanded runout events.
                if not detected:
                    self._begin_pending_runout(tool, requested_ownership)
                    # Persist failed-runout state immediately since the
                    # command is authoritative and we're bypassing the
                    # normal sensor-debounce persistence path.
                    pending = self._pending_runout_checkpoint(tool)
                    if pending is not None:
                        candidate = self.state.with_failed_runout(tool)
                        if candidate is not self.state:
                            try:
                                self._persist_state(candidate)
                            except OSError as error:
                                self._block_workflow(pending, "Unable to persist failed-runout state: %s" % (error,))
                                return
                        self._confirmed_runout(pending)
                return
            # Non-authoritative commands fall back to standard sensor observation
            # behavior: observe the current sensor reading and let debounce run
            # normally.
            self._observe_sensor_reading(tool, status, eventtime, None)
            return
        if not detected:
            self._begin_pending_runout(tool, requested_ownership)
        self._observe_sensor_reading(
            tool, status, eventtime, "insert" if detected else "runout")

    def _begin_pending_runout(self, physical_tool, requested_ownership):
        if self._workflow_checkpoint is not None:
            if (self._workflow_checkpoint.source == "automatic_fallback"
                    and self._workflow_checkpoint.stage == "debouncing"
                    and self._workflow_checkpoint.current_physical_tool
                    == physical_tool):
                return
            self.gcode.respond_info(
                "Ignoring runout for %s because another tool fallback "
                "workflow is active" % (physical_tool,))
            return
        print_state = self._get_print_state()
        selected = self._selected_physical_tool == physical_tool
        active_context = print_state in ("printing", "paused")
        if not selected or not active_context:
            return
        pause_owned = bool(requested_ownership and selected)
        self._workflow_generation += 1
        self._workflow_checkpoint = WorkflowCheckpoint(
            source="automatic_fallback",
            stage="debouncing",
            generation=self._workflow_generation,
            logical_tool=self._logical_for_physical(physical_tool),
            current_physical_tool=physical_tool,
            pause_owned=pause_owned,
        )

    def _pending_runout_checkpoint(self, physical_tool):
        checkpoint = self._workflow_checkpoint
        if (checkpoint is None
                or checkpoint.source != "automatic_fallback"
                or checkpoint.stage != "debouncing"
                or checkpoint.current_physical_tool != physical_tool):
            return None
        return checkpoint

    def _complete_transient_runout(self, checkpoint):
        if not self._checkpoint_matches(
                checkpoint.generation, "debouncing"):
            return
        self.gcode.respond_info(
            "Tool %s runout cleared before confirmation" %
            (checkpoint.current_physical_tool,))
        self._workflow_checkpoint = None
        if not checkpoint.pause_owned:
            self._finalize_transient_outcome(checkpoint)
            return
        try:
            self.gcode.run_script_from_command(
                self.config.global_config.resume_gcode)
        except Exception as error:
            self._block_workflow(
                checkpoint,
                "Unable to resume after transient runout: %s" % (error,),
                "RESUME_FAILED")
            return
        self._finalize_transient_outcome(checkpoint)

    def _confirmed_runout(self, checkpoint):
        advanced = self._advance_workflow_checkpoint(
            checkpoint.generation, "debouncing", "confirmed_runout")
        if advanced is None:
            return
        self._on_confirmed_runout(advanced)

    def _on_confirmed_runout(self, checkpoint):
        reactor = self.printer.get_reactor()
        eventtime = reactor.monotonic()

        # 0. Pause the print if active (before any fallback actions).
        if self._print_is_active():
            try:
                self.gcode.run_script_from_command(
                    self.config.global_config.pause_gcode)
            except Exception as error:
                self._block_workflow(
                    checkpoint,
                    "Unable to pause print before fallback: %s" % (error,))
                return

        # 1. Identify active logical route for the failed physical tool.
        logical_tool = self._logical_route_for_physical(
            checkpoint.current_physical_tool)
        if logical_tool is None:
            self._block_workflow(
                checkpoint,
                "Automatic fallback requires a known active logical "
                "route for the failed tool; cannot proceed")
            return

        # 2. Capture target and shut down failed heater.
        advanced = self._capture_and_shutdown_source(checkpoint)
        if self._workflow_stage_failed(advanced):
            return

        # 3. Resolve backup graph with one fresh rescan on exhaustion.
        resolution = self._resolve_backup_with_rescan(
            checkpoint.current_physical_tool)
        if resolution.candidate is None:
            report = resolution.to_dict() if resolution else None
            self._block_workflow(
                advanced,
                "No eligible backup tool found after one re-scan; "
                "backups exhausted" if report else "Backup graph "
                "resolution failed",
                "GRAPH_EXHAUSTED")
            if report:
                self._workflow_checkpoint = replace(
                    self._workflow_checkpoint, graph_report=report)
            return

        selected = resolution.candidate
        self._workflow_checkpoint = replace(
            advanced,
            stage="resolving",
            logical_tool=logical_tool,
            requested_physical_tool=selected,
            graph_report=resolution,
        )

        # 4. Preheat backup before physical selection.
        preheated = self._preheat_requested_tool(self._workflow_checkpoint)
        if self._workflow_stage_failed(preheated):
            return

        # 5. Select backup physically (once, no retry).
        selection_deadline = (
            eventtime + self.config.global_config.selection_timeout)
        try:
            self._select_physical(selected)
        except Exception as error:
            self._block_workflow(
                preheated,
                "Physical selection of backup tool %s failed: %s" %
                (selected, error))
            return
        if reactor.monotonic() > selection_deadline:
            self._block_workflow(
                preheated,
                "Physical selection of backup tool %s exceeded "
                "timeout" % (selected,))
            return

        self._workflow_checkpoint = replace(
            preheated, stage="selected", failure_reason=None)

        # 6. Wait for heater readiness with timeout.
        heating_deadline = (
            eventtime + self.config.global_config.heating_timeout)
        self._workflow_checkpoint = replace(
            self._workflow_checkpoint,
            stage="heating", stage_deadline=heating_deadline)
        self._wait_for_heater_readiness(self._workflow_checkpoint)
        if (self._workflow_checkpoint is None
                or self._workflow_checkpoint.stage in (
                    "blocked", "heating_timeout")):
            return

        # 7. Conditionally purge the backup tool.
        backup_state = self.state.tools[selected]
        if not backup_state.purged:
            try:
                self._purge_physical_tool(
                    selected,
                    self.gcode.error,
                    self.gcode.respond_info)
            except Exception as error:
                self._block_workflow(
                    self._workflow_checkpoint,
                    "Purge of backup tool %s failed: %s" %
                    (selected, error),
                    "PURGE_FAILED")
                return

        # 8. Merge and persist logical mapping from current canonical state.
        candidate = self.state.with_mapping(logical_tool, selected)
        try:
            self._persist_state(candidate)
        except OSError as error:
            self._block_workflow(
                self._workflow_checkpoint,
                "Unable to persist tool fallback mapping after "
                "fallback: %s" % (error,),
                "MAPPING_PERSIST_FAILED")
            return

        # 9. Clear checkpoint and resume only when owned.
        completed = self._workflow_checkpoint
        self._workflow_checkpoint = None
        if checkpoint.pause_owned:
            try:
                self.gcode.run_script_from_command(
                    self.config.global_config.resume_gcode)
            except Exception as error:
                self._block_workflow(
                    completed,
                    "Resume after fallback failed: %s" % (error,),
                    "RESUME_FAILED")
                return
        self._finalize_fallback_success(completed)

    def _checkpoint_matches(self, generation, stage):
        checkpoint = self._workflow_checkpoint
        return (
            checkpoint is not None
            and checkpoint.generation == generation
            and checkpoint.stage == stage
        )

    def _advance_workflow_checkpoint(
            self, generation, expected_stage, next_stage, **changes):
        if not self._checkpoint_matches(generation, expected_stage):
            return None
        self._workflow_checkpoint = replace(
            self._workflow_checkpoint, stage=next_stage, **changes)
        return self._workflow_checkpoint

    def _logical_for_physical(self, physical_tool):
        if self._active_logical_tool is not None:
            if self.state.mappings.get(
                    self._active_logical_tool) == physical_tool:
                return self._active_logical_tool
        return None

    def _logical_route_for_physical(self, physical_tool):
        """Identify the active logical route for a given physical tool.

        Returns the logical tool name if one is currently mapped to the
        given physical tool and is the active logical tool, otherwise
        returns None.
        """
        if self._active_logical_tool is not None:
            if self.state.mappings.get(
                    self._active_logical_tool) == physical_tool:
                return self._active_logical_tool
        return None

    def _wait_for_heater_readiness(self, checkpoint):
        """Synchronously wait for the selected backup heater to reach
        readiness, enforcing the configured heating timeout.

        Polls heater.check_busy() and advances the reactor so that
        timer-based callbacks can fire.  On timeout, the checkpoint
        is left at heating_timeout for guarded RESUME recovery.
        """
        reactor = self.printer.get_reactor()
        deadline = checkpoint.stage_deadline
        requested = checkpoint.requested_physical_tool
        heater = self._heaters.get(requested)
        if heater is None:
            return self._block_workflow(
                checkpoint,
                "Tool %s has no resolved destination heater" % requested)

        while True:
            eventtime = reactor.monotonic()
            if eventtime >= deadline:
                self._workflow_checkpoint = replace(
                    checkpoint, stage="heating_timeout",
                    failure_reason=None)
                return
            try:
                if not heater.check_busy(eventtime):
                    break
            except Exception as error:
                self._block_workflow(
                    checkpoint,
                    "Heater readiness check for tool %s failed: %s" %
                    (requested, error))
                return
            reactor.advance(SENSOR_POLL_INTERVAL)

    def _cmd_resume_wrapper(self, gcmd):
        """Registered wrapper for the global resume gcode.

        If there is a recoverable 'heating_timeout' checkpoint, perform a
        guarded recovery sequence instead of performing a normal resume.
        Otherwise delegate to the original resume handler when present.
        """
        self._guard_notification_operation(gcmd.error)
        # Prevent re-entrant guarded resume attempts
        if self._resume_in_progress:
            if getattr(self, "_resume_original", None):
                return self._resume_original(gcmd)
            return None

        if self._workflow_checkpoint is None or self._workflow_checkpoint.stage != "heating_timeout":
            if getattr(self, "_resume_original", None):
                return self._resume_original(gcmd)
            return None
        # Handle guarded resume for heating_timeout
        try:
            self._resume_in_progress = True
            return self._handle_guarded_resume(gcmd)
        except Exception as error:
            raise gcmd.error(str(error))
        finally:
            self._resume_in_progress = False

    def _handle_guarded_resume(self, gcmd):
        """Attempt guarded recovery from a heating_timeout checkpoint.

        This will re-run the heater readiness wait and, if successful,
        continue the normal purge/persist/clear/resume continuation.
        On persistent timeout, the checkpoint is left unchanged and
        resume is deferred.
        """
        checkpoint = self._workflow_checkpoint
        if checkpoint is None or checkpoint.stage != "heating_timeout":
            # Nothing to do; fall back to original handler if present
            if getattr(self, "_resume_original", None):
                return self._resume_original(gcmd)
            return None

        if not checkpoint.pause_owned:
            raise gcmd.error("Resume is not owned by fallback; refusing guarded resume")

        # A guarded operator retry gets a fresh configured heating window.
        checkpoint = replace(
            checkpoint,
            stage="heating",
            stage_deadline=(
                self.printer.get_reactor().monotonic()
                + self.config.global_config.heating_timeout),
            failure_reason=None)
        self._workflow_checkpoint = checkpoint
        self._wait_for_heater_readiness(checkpoint)
        if (self._workflow_checkpoint is not None
                and self._workflow_checkpoint.stage == "blocked"):
            return None
        # If still timed out, do not resume
        if self._workflow_checkpoint is not None and self._workflow_checkpoint.stage == "heating_timeout":
            self.gcode.respond_info("Selected backup heater not ready; resume deferred")
            return None

        # Proceed with purge of backup if needed
        requested = checkpoint.requested_physical_tool
        backup_state = self.state.tools[requested]
        if not backup_state.purged:
            try:
                self._purge_physical_tool(
                    requested, self.gcode.error, self.gcode.respond_info)
            except Exception as error:
                self._block_workflow(
                    self._workflow_checkpoint,
                    "Purge of backup tool %s failed: %s" % (requested, error),
                    "PURGE_FAILED")
                return None

        # Persist mapping candidate
        candidate = self.state.with_mapping(
            checkpoint.logical_tool, requested)
        try:
            self._persist_state(candidate)
        except OSError as error:
            self._block_workflow(
                self._workflow_checkpoint,
                "Unable to persist tool fallback mapping after "
                "fallback: %s" % (error,),
                "MAPPING_PERSIST_FAILED")
            return None

        # Clear checkpoint and resume when owned
        self._workflow_checkpoint = None
        if checkpoint.pause_owned:
            try:
                # Use run_script_from_command to ensure script durations are
                # respected in tests (FakeGCode advances reactor time)
                self.gcode.run_script_from_command(
                    self.config.global_config.resume_gcode)
            except Exception as error:
                # Re-create a blocked checkpoint from the saved checkpoint
                blocked = replace(checkpoint, stage="blocked",
                                  failure_reason="Resume after fallback failed: %s" % (error,))
                self._block_workflow(blocked,
                                     "Resume after fallback failed: %s" % (error,),
                                     "RESUME_FAILED")
                return None
        self._finalize_fallback_success(checkpoint)
        return None

    def _resolve_backup_with_rescan(self, failed_tool, snapshot_provider=None):
        provider = snapshot_provider or self._canonical_state_snapshot
        unknown_authority = self._unknown_sensor_authority()
        first = resolve_backup_graph(
            provider(), failed_tool, unknown_authority)
        if first.candidate is not None:
            return first
        second = resolve_backup_graph(
            provider(), failed_tool, self._unknown_sensor_authority())
        return replace(second, scan_count=2)

    def _canonical_state_snapshot(self):
        return self.state

    def _unknown_sensor_authority(self):
        return frozenset(
            tool for tool, runtime in self._sensor_runtime.items()
            if runtime.authority == "unknown")

    def _workflow_status_snapshot(self):
        checkpoint = self._workflow_checkpoint
        if checkpoint is None:
            return None
        graph_report = checkpoint.graph_report
        if isinstance(graph_report, GraphResolution):
            graph_report = graph_report.to_dict()
        return {
            "source": checkpoint.source,
            "stage": checkpoint.stage,
            "generation": checkpoint.generation,
            "logical_tool": checkpoint.logical_tool,
            "current_physical_tool": checkpoint.current_physical_tool,
            "requested_physical_tool": checkpoint.requested_physical_tool,
            "pause_owned": checkpoint.pause_owned,
            "target_temperature": checkpoint.target_temperature,
            "stage_deadline": checkpoint.stage_deadline,
            "graph_report": graph_report,
            "failure_reason": checkpoint.failure_reason,
        }

    def _guard_workflow_operation(self, error_factory, operation):
        checkpoint = self._workflow_checkpoint
        if checkpoint is None:
            return
        raise error_factory(
            "Cannot perform %s while tool fallback workflow generation %s "
            "is %s" % (
                operation, checkpoint.generation, checkpoint.stage))

    def _guard_notification_operation(self, error_factory):
        if self._notification_in_progress:
            raise error_factory(
                "Tool fallback command is unavailable during notification "
                "delivery")

    def _authorize_explicit_tool_state(
            self, gcmd, physical_tool, command_name):
        print_state = self._get_print_state()
        if (print_state == "printing"
                and physical_tool == self._selected_physical_tool):
            raise gcmd.error(
                "%s for selected physical tool %s is "
                "only available while paused or outside a print" %
                (command_name, physical_tool))

    def _purge_physical_tool(
            self, physical_tool, error_factory, respond_info, force=False):
        self._warn_unknown_purge_authority(physical_tool, respond_info)
        candidate = self._purged_candidate(physical_tool, error_factory)
        if candidate is self.state and not force:
            return
        adapter = "%s TOOL=%s" % (
            self.config.global_config.purge_gcode, physical_tool)
        reactor = self.printer.get_reactor()
        deadline = (
            reactor.monotonic() + self.config.global_config.purge_timeout)
        self.gcode.run_script_from_command(adapter)
        if reactor.monotonic() > deadline:
            raise error_factory(
                "Purge of tool %s exceeded timeout" % (physical_tool,))
        if candidate is self.state:
            return
        try:
            self._persist_state(candidate)
        except OSError as error:
            raise error_factory(
                "Unable to persist tool fallback purge state: %s" % (error,))

    def _purged_candidate(self, physical_tool, error_factory):
        runtime = self._sensor_runtime.get(physical_tool)
        authority_unknown = (
            runtime is not None and runtime.authority == "unknown")
        if not self.state.tools[physical_tool].loaded and not authority_unknown:
            raise error_factory(
                "Tool %s cannot be purged while its sensor confirms unloaded" %
                (physical_tool,))
        base = self.state
        if authority_unknown and not base.tools[physical_tool].loaded:
            base = base.with_filament_loaded(physical_tool)
        return base.with_tool_purged(physical_tool)

    def _warn_unknown_purge_authority(self, physical_tool, respond_info):
        runtime = self._sensor_runtime.get(physical_tool)
        if runtime is not None and runtime.authority == "unknown":
            respond_info(
                "Tool %s sensor authority is unknown; purge will continue "
                "using operator authority" % (physical_tool,))

    def _persist_purge_candidate(self, gcmd, candidate):
        if candidate is self.state:
            return
        try:
            self._persist_state(candidate)
        except OSError as error:
            raise gcmd.error(
                "Unable to persist tool fallback purge state: %s" % (error,))

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

    def _parse_backup_list(self, gcmd, physical_tool):
        raw_backups = gcmd.get("BACKUPS")
        if type(raw_backups) is not str:
            raise gcmd.error("BACKUPS must be a comma-separated tool list")
        stripped = raw_backups.strip()
        if not stripped:
            return ()
        backups = tuple(item.strip() for item in stripped.split(","))
        if any(not item for item in backups):
            raise gcmd.error(
                "BACKUPS must not contain empty entries")
        unknown = [item for item in backups if item not in self.config.tools]
        if unknown:
            raise gcmd.error(
                "BACKUPS must contain configured canonical tools; got %s" %
                (", ".join(unknown),))
        if physical_tool in backups:
            raise gcmd.error(
                "Tool %s cannot reference itself as a backup" %
                (physical_tool,))
        if len(set(backups)) != len(backups):
            raise gcmd.error(
                "Tool %s contains duplicate backup references" %
                (physical_tool,))
        return backups

    def _backup_candidate(self, operation):
        if operation.operation == "set":
            return self.state.with_backups(operation.tool, operation.backups)
        if operation.operation == "restore":
            return self.state.with_backups(
                operation.tool, self.config.tools[operation.tool].backups)
        if operation.operation == "reset":
            return self.state.with_all_backups({
                tool: config.backups
                for tool, config in self.config.tools.items()
            })
        raise tool_fallback_state.StateValidationError(
            "Unknown backup operation %s" % (operation.operation,))

    def _apply_backup_operation(self, gcmd, operation):
        if getattr(self, "_notification_in_progress", False):
            raise gcmd.error(
                "Backup policy change is unavailable during notification "
                "delivery")
        if (self._workflow_checkpoint is not None
                or self._transition_active
                or self._backup_operation_queue):
            self._enqueue_backup_operation(gcmd, operation)
            return
        self._apply_immediate_backup_operation(gcmd, operation)

    def _apply_immediate_backup_operation(self, gcmd, operation):
        try:
            candidate = self._backup_candidate(operation)
        except tool_fallback_state.StateValidationError as error:
            raise gcmd.error(str(error))
        if candidate is self.state:
            gcmd.respond_info(
                "%s unchanged: %s (no write)" %
                (self._backup_operation_subject(operation),
                 self._format_backup_policy(operation)))
            return
        try:
            self._persist_state(candidate)
        except OSError as error:
            raise gcmd.error(
                "Unable to persist tool fallback backup policy: %s" %
                (error,))
        gcmd.respond_info(
            "%s persisted: %s" %
            (self._backup_operation_subject(operation),
             self._format_backup_policy(operation)))

    def _enqueue_backup_operation(self, gcmd, operation):
        self._backup_operation_sequence += 1
        queued = QueuedBackupOperation(
            self._backup_operation_sequence, operation)
        self._backup_operation_queue.append(queued)
        checkpoint = self._workflow_checkpoint
        if checkpoint is not None:
            active_stage = checkpoint.stage
        elif self._transition_active:
            active_stage = "route_transition"
        else:
            active_stage = "retained_queue"
        gcmd.respond_info(
            "Queued backup operation position=%d sequence=%d operation=%s "
            "target=%s stage=%s" %
            (len(self._backup_operation_queue), queued.sequence,
             operation.operation, operation.tool or "all", active_stage))
        self._drain_backup_operations()

    def _backup_drain_is_safe(self):
        checkpoint = self._workflow_checkpoint
        return (
            not self._transition_active
            and not getattr(self, "_notification_in_progress", False)
            and not self._backup_drain_in_progress
            and (checkpoint is None or checkpoint.stage == "blocked")
        )

    def _drain_backup_operations(self):
        if not self._backup_operation_queue or not self._backup_drain_is_safe():
            return
        applied = 0
        no_op = 0
        failed = 0
        self._backup_drain_in_progress = True
        try:
            while self._backup_operation_queue:
                queued = self._backup_operation_queue[0]
                operation = queued.operation
                try:
                    candidate = self._backup_candidate(operation)
                    if candidate is self.state:
                        no_op += 1
                        result = "no-op"
                    else:
                        self._persist_state(candidate)
                        applied += 1
                        result = "applied"
                except Exception as error:
                    failed = 1
                    self._last_backup_drain_failure = {
                        "sequence": queued.sequence,
                        "operation": operation.operation,
                        "target": operation.tool or "all",
                        "error": str(error),
                    }
                    self.gcode.respond_info(
                        "Queued backup operation sequence=%d operation=%s "
                        "target=%s failed: %s; remaining=%d" %
                        (queued.sequence, operation.operation,
                         operation.tool or "all", error,
                         len(self._backup_operation_queue)))
                    break
                self._backup_operation_queue.pop(0)
                self._last_backup_drain_failure = None
                self.gcode.respond_info(
                    "Queued backup operation sequence=%d operation=%s "
                    "target=%s %s: %s" %
                    (queued.sequence, operation.operation,
                     operation.tool or "all", result,
                     self._format_backup_policy(operation)))
        finally:
            self._backup_drain_in_progress = False
        self.gcode.respond_info(
            "Backup queue drain totals: applied=%d no_op=%d failed=%d "
            "remaining=%d" %
            (applied, no_op, failed, len(self._backup_operation_queue)))

    def _backup_queue_status_snapshot(self):
        oldest_sequence = (
            self._backup_operation_queue[0].sequence
            if self._backup_operation_queue else None)
        return {
            "depth": len(self._backup_operation_queue),
            "oldest_sequence": oldest_sequence,
            "next_sequence": self._backup_operation_sequence + 1,
            "drain_in_progress": self._backup_drain_in_progress,
            "last_failure": (
                None if self._last_backup_drain_failure is None
                else dict(self._last_backup_drain_failure)),
        }

    def _backup_operation_subject(self, operation):
        if operation.operation == "reset":
            return "All tool backups"
        return "Tool %s backups" % (operation.tool,)

    def _format_backup_policy(self, operation):
        if operation.operation == "reset":
            return "; ".join(
                "%s=%s" % (tool, self._format_backup_list(
                    self.state.tools[tool].backups))
                for tool in self.state.tools
            )
        return self._format_backup_list(self.state.tools[operation.tool].backups)

    def _format_backup_list(self, backups):
        return ",".join(backups) if backups else "(empty)"

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
        self._guard_workflow_operation(gcmd.error, "active route transition")
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
                gcmd, logical_tool, current_physical, requested_physical)
            self._select_physical(requested_physical)
            self._run_post_selection_transition_stages(
                gcmd, logical_tool, current_physical, requested_physical)
            candidate = self._merge_mapping_candidate(candidate)
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
            self._drain_backup_operations()

    def _run_pre_selection_transition_stages(
            self, gcmd, logical_tool, current_physical, requested_physical):
        # Phase 4 integrates temperature-transfer stages here.
        # If heaters are not configured for either the source or requested
        # physical tools, remain a no-op to preserve pre-Phase-4 behavior
        # for tests that do not configure heaters.
        if current_physical not in self._heaters or requested_physical not in self._heaters:
            return

        # Build a transient checkpoint to reuse existing helpers. Use a
        # generation marker independent of the automatic workflow to avoid
        # colliding with any running automatic fallback.
        generation = self._workflow_generation + 1
        checkpoint = WorkflowCheckpoint(
            source=current_physical,
            stage="transition",
            generation=generation,
            logical_tool=logical_tool,
            current_physical_tool=current_physical,
            requested_physical_tool=requested_physical,
            pause_owned=(self._get_print_state() == "printing"),
        )

        # 1. Capture target temperature from source and shut it down.
        advanced = self._capture_and_shutdown_source(checkpoint)
        if self._workflow_stage_failed(advanced):
            # _capture_and_shutdown_source will have set a blocked checkpoint
            # when appropriate; surface a CLI-visible error to abort the
            # transition.
            raise gcmd.error(advanced.failure_reason)

        # 2. Preheat requested tool to captured target.
        # Copy requested_physical_tool into the checkpoint expected by
        # _preheat_requested_tool.
        advanced = replace(advanced, requested_physical_tool=requested_physical)
        preheated = self._preheat_requested_tool(advanced)
        if self._workflow_stage_failed(preheated):
            raise gcmd.error(preheated.failure_reason)

        # 3. Wait for heater readiness, enforcing heating_timeout.
        heating_deadline = (
            self.printer.get_reactor().monotonic()
            + self.config.global_config.heating_timeout)
        preheated = replace(preheated, stage="preheated", stage_deadline=heating_deadline)
        self._workflow_checkpoint = preheated
        self._wait_for_heater_readiness(preheated)
        if (self._workflow_checkpoint is not None
                and self._workflow_checkpoint.stage == "blocked"):
            raise gcmd.error(self._workflow_checkpoint.failure_reason)
        if (self._workflow_checkpoint is not None
                and self._workflow_checkpoint.stage == "heating_timeout"):
            raise gcmd.error("Selected backup heater did not reach readiness before timeout")

        # Clear the transient checkpoint now that preselection stages completed
        self._workflow_checkpoint = None
        return

    def _run_post_selection_transition_stages(
            self, gcmd, logical_tool, current_physical, requested_physical):
        if not self.state.tools[requested_physical].purged:
            self._purge_physical_tool(
                requested_physical, gcmd.error, gcmd.respond_info)

    def _merge_mapping_candidate(self, requested_candidate):
        candidate = self.state
        for logical_tool, physical_tool in requested_candidate.mappings.items():
            candidate = candidate.with_mapping(logical_tool, physical_tool)
        return candidate

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
