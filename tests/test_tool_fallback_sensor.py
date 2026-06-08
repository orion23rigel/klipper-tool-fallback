from conftest import FakeFilamentSensor, FakeGCmd, FakeReactor


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
