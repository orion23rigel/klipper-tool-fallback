import json

from conftest import FakeFilamentSensor, FakeGCmd, FakeReactor
from klippy.extras import tool_fallback
from klippy.extras.tool_fallback_state import FallbackState, StateStore


def tool_options(**overrides):
    options = {
        "filament_sensor": "filament_switch_sensor tool_sensor",
        "heater": "extruder",
    }
    options.update(overrides)
    return options


def load_extension(config_factory, prefix_config_factory, printer, state_path,
                   tools=(("T0", {}),)):
    config = config_factory(state_path=str(state_path))
    extension = tool_fallback.load_config(config)
    printer.add_object("tool_fallback", extension)
    for name, overrides in tools:
        printer.gcode.register_command(name, lambda gcmd: None)
        options = tool_options(**overrides)
        if options["filament_sensor"] is None:
            del options["filament_sensor"]
        tool_fallback.load_config_prefix(
            prefix_config_factory("tool_fallback %s" % name, **options))
    return extension


def test_fake_reactor_advances_due_timers_in_stable_order_and_reschedules():
    reactor = FakeReactor()
    events = []

    def first(eventtime):
        events.append(("first", eventtime))
        return reactor.NEVER

    def second(eventtime):
        events.append(("second", eventtime))
        return eventtime + 1.0

    first_timer = reactor.register_timer(first, 2.0)
    reactor.register_timer(second, 2.0)
    reactor.update_timer(first_timer, 1.0)

    reactor.advance(3.0)

    assert events == [("first", 1.0), ("second", 2.0), ("second", 3.0)]
    assert reactor.monotonic() == 3.0


def test_fake_reactor_stale_schedule_can_be_cancelled_before_advancing():
    reactor = FakeReactor()
    calls = []
    timer = reactor.register_timer(lambda eventtime: calls.append(eventtime))

    reactor.update_timer(timer, 1.0)
    reactor.update_timer(timer, reactor.NEVER)
    reactor.advance(2.0)

    assert calls == []


def test_fake_filament_sensor_exposes_mutable_and_failing_status():
    sensor = FakeFilamentSensor(enabled=False, filament_detected=True)

    assert sensor.get_status(1.0) == {
        "enabled": False,
        "filament_detected": True,
    }
    sensor.malformed_status = {"enabled": "yes"}
    assert sensor.get_status(2.0) == {"enabled": "yes"}
    sensor.status_error = RuntimeError("injected sensor failure")
    try:
        sensor.get_status(3.0)
    except RuntimeError as error:
        assert str(error) == "injected sensor failure"
    else:
        raise AssertionError("expected injected sensor failure")


def test_fake_gcmd_integer_parsing_is_strict():
    assert FakeGCmd({"LOADED": "1"}).get_int(
        "LOADED", minval=0, maxval=1) == 1

    for value in ("true", "1.0", "2"):
        command = FakeGCmd({"LOADED": value})
        try:
            command.get_int("LOADED", minval=0, maxval=1)
        except Exception:
            pass
        else:
            raise AssertionError("expected strict integer rejection for %s" % value)


def test_startup_with_available_sensor_reports_verified_authority(
        config_factory, prefix_config_factory, printer, tmp_path):
    sensor = FakeFilamentSensor(enabled=True, filament_detected=True)
    printer.add_object("filament_switch_sensor tool_sensor", sensor)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")

    printer.send_event("klippy:ready")

    status = extension.get_status(0.0)
    assert status["sensor_authority"]["T0"]["authority"] == "unknown"
    printer.reactor.advance(1.0)
    status = extension.get_status(1.0)
    assert status["sensor_authority"]["T0"] == {
        "configured": "filament_switch_sensor tool_sensor",
        "authority": "available",
        "enabled": True,
        "detected": True,
        "outage_acknowledged": False,
    }
    assert sensor.status_calls[-1] == 1.0


def test_unknown_sensor_status_preserves_durable_filament_history(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    state = FallbackState.from_dict({
        "version": 1,
        "tools": {
            "T0": {
                "loaded": True,
                "purged": True,
                "failed": False,
                "backups": [],
            },
        },
        "mappings": {"T0": "T0"},
    })
    StateStore(str(path)).save(state)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path)

    printer.send_event("klippy:ready")

    status = extension.get_status(0.0)
    assert status["tools"]["T0"] == {
        "loaded": True,
        "purged": True,
        "failed": False,
        "backups": [],
    }
    assert status["sensor_authority"]["T0"]["authority"] == "unknown"
    assert status["sensor_authority"]["T0"]["enabled"] is None
    assert status["sensor_authority"]["T0"]["detected"] is None


def test_missing_sensor_configuration_reaches_ready_with_unknown_authority(
        config_factory, prefix_config_factory, printer, tmp_path):
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json",
        tools=(("T0", {"filament_sensor": None}),))

    printer.send_event("klippy:ready")

    assert extension.get_status(0.0)["sensor_authority"]["T0"] == {
        "configured": None,
        "authority": "unknown",
        "enabled": None,
        "detected": None,
        "outage_acknowledged": False,
    }
    assert printer.gcode.commands["T0"].__name__ == "handler"


def test_disabled_sensor_reaches_ready_as_unknown_but_exposes_raw_status(
        config_factory, prefix_config_factory, printer, tmp_path):
    printer.add_object(
        "filament_switch_sensor tool_sensor",
        FakeFilamentSensor(enabled=False, filament_detected=True),
    )
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")

    printer.send_event("klippy:ready")

    assert extension.get_status(0.0)["sensor_authority"]["T0"] == {
        "configured": "filament_switch_sensor tool_sensor",
        "authority": "unknown",
        "enabled": False,
        "detected": True,
        "outage_acknowledged": False,
    }


def test_malformed_and_failing_sensors_reach_ready_with_unknown_authority(
        config_factory, prefix_config_factory, printer, tmp_path):
    sensor = FakeFilamentSensor()
    sensor.malformed_status = {"enabled": True, "filament_detected": 1}
    printer.add_object("filament_switch_sensor tool_sensor", sensor)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")

    printer.send_event("klippy:ready")
    assert extension.get_status(0.0)["sensor_authority"]["T0"]["authority"] == (
        "unknown")

    sensor.malformed_status = None
    sensor.status_error = RuntimeError("status failed")
    printer.reactor.advance(0.25)
    assert extension.get_status(0.25)["sensor_authority"]["T0"] == {
        "configured": "filament_switch_sensor tool_sensor",
        "authority": "unknown",
        "enabled": None,
        "detected": None,
        "outage_acknowledged": False,
    }


def test_sensor_status_exception_reaches_ready_with_unknown_authority(
        config_factory, prefix_config_factory, printer, tmp_path):
    sensor = FakeFilamentSensor()
    sensor.status_error = RuntimeError("status failed")
    printer.add_object("filament_switch_sensor tool_sensor", sensor)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")

    printer.send_event("klippy:ready")

    assert extension.get_status(0.0)["sensor_authority"]["T0"]["authority"] == (
        "unknown")
    assert printer.gcode.commands["T0"].__name__ == "handler"


def test_sensor_polling_restores_authority_without_persisting_runtime_status(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    sensor = FakeFilamentSensor(enabled=False, filament_detected=False)
    printer.add_object("filament_switch_sensor tool_sensor", sensor)
    path = tmp_path / "state.json"
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")

    def reject_save(candidate):
        raise AssertionError("sensor polling attempted to persist state")

    monkeypatch.setattr(extension._state_store, "save", reject_save)
    sensor.enabled = True
    sensor.filament_detected = False
    printer.reactor.advance(0.25)

    status = extension.get_status(0.25)
    assert status["sensor_authority"]["T0"]["authority"] == "unknown"
    assert status["sensor_authority"]["T0"]["detected"] is False
    assert "poll_timer" not in json.dumps(status, sort_keys=True)


def test_startup_reconciliation_waits_for_full_symmetric_debounce(
        config_factory, prefix_config_factory, printer, tmp_path):
    sensor = FakeFilamentSensor(enabled=True, filament_detected=True)
    printer.add_object("filament_switch_sensor tool_sensor", sensor)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    printer.send_event("klippy:ready")

    printer.reactor.advance(0.99)
    assert extension.state.tools["T0"].loaded is False
    assert extension.get_status(0.99)["sensor_authority"]["T0"]["authority"] == (
        "unknown")

    printer.reactor.advance(0.01)
    assert extension.state.tools["T0"].loaded is True
    assert extension.state.tools["T0"].purged is False
    assert extension.get_status(1.0)["sensor_authority"]["T0"]["authority"] == (
        "available")


def test_repeated_equal_polling_does_not_extend_debounce_deadline(
        config_factory, prefix_config_factory, printer, tmp_path):
    sensor = FakeFilamentSensor(enabled=True, filament_detected=True)
    printer.add_object("filament_switch_sensor tool_sensor", sensor)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    printer.send_event("klippy:ready")

    printer.reactor.advance(1.0)

    assert extension.state.tools["T0"].loaded is True
    assert extension._sensor_runtime["T0"].debounce_deadline is None


def test_oscillation_invalidates_stale_debounce_candidate_symmetrically(
        config_factory, prefix_config_factory, printer, tmp_path):
    sensor = FakeFilamentSensor(enabled=True, filament_detected=False)
    printer.add_object("filament_switch_sensor tool_sensor", sensor)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    printer.send_event("klippy:ready")
    printer.reactor.advance(1.0)

    sensor.filament_detected = True
    printer.reactor.advance(0.25)
    sensor.filament_detected = False
    printer.reactor.advance(0.25)
    sensor.filament_detected = True
    printer.reactor.advance(1.24)
    assert extension.state.tools["T0"].loaded is False

    printer.reactor.advance(0.01)
    assert extension.state.tools["T0"].loaded is True

    sensor.filament_detected = False
    printer.reactor.advance(0.25)
    printer.reactor.advance(0.99)
    assert extension.state.tools["T0"].loaded is True
    printer.reactor.advance(0.01)
    assert extension.state.tools["T0"].loaded is False


def test_startup_loaded_reconciliation_preserves_purged_and_clears_failed(
        config_factory, prefix_config_factory, printer, tmp_path):
    path = tmp_path / "state.json"
    StateStore(str(path)).save(FallbackState.from_dict({
        "version": 1,
        "tools": {
            "T0": {
                "loaded": True,
                "purged": True,
                "failed": True,
                "backups": [],
            },
        },
        "mappings": {"T0": "T0"},
    }))
    sensor = FakeFilamentSensor(enabled=True, filament_detected=True)
    printer.add_object("filament_switch_sensor tool_sensor", sensor)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, path)
    printer.send_event("klippy:ready")

    printer.reactor.advance(1.0)

    assert extension.state.tools["T0"].loaded is True
    assert extension.state.tools["T0"].purged is True
    assert extension.state.tools["T0"].failed is False


def test_persistence_failure_never_publishes_reconciled_candidate(
        config_factory, prefix_config_factory, printer, tmp_path, monkeypatch):
    sensor = FakeFilamentSensor(enabled=True, filament_detected=True)
    printer.add_object("filament_switch_sensor tool_sensor", sensor)
    extension = load_extension(
        config_factory, prefix_config_factory, printer, tmp_path / "state.json")
    printer.send_event("klippy:ready")
    original = extension.state

    def fail_save(candidate):
        raise OSError("injected reconciliation failure")

    monkeypatch.setattr(extension._state_store, "save", fail_save)
    try:
        printer.reactor.advance(1.0)
    except OSError as error:
        assert str(error) == "injected reconciliation failure"
    else:
        raise AssertionError("expected injected reconciliation failure")

    assert extension.state is original
    assert extension.get_status(1.0)["sensor_authority"]["T0"]["authority"] == (
        "unknown")
