import json
import os

import pytest

from klippy.extras import tool_fallback_state as state_module
from klippy.extras.tool_fallback_config import ToolConfig
from klippy.extras.tool_fallback_state import (
    FallbackState,
    StateStore,
    StateValidationError,
)


def configured(*entries):
    return {
        name: ToolConfig(name, "%s_sensor" % name, "extruder", tuple(backups))
        for name, backups in entries
    }


def valid_dict():
    return {
        "version": 1,
        "tools": {
            "T0": {
                "loaded": True,
                "purged": True,
                "failed": False,
                "backups": ["T2", "T1"],
            },
            "T1": {
                "loaded": False,
                "purged": False,
                "failed": True,
                "backups": [],
            },
            "T2": {
                "loaded": True,
                "purged": False,
                "failed": False,
                "backups": ["T1"],
            },
        },
        "mappings": {"T0": "T2", "T1": "T1", "T2": "T2"},
    }


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_all_persisted_fields_round_trip_without_reordering_backups():
    decoded = valid_dict()

    state = FallbackState.from_dict(decoded)

    assert state.to_dict() == decoded
    assert state.tools["T0"].backups == ("T2", "T1")
    assert FallbackState.from_dict(state.to_dict()) == state


def test_serialization_sorts_tool_and_mapping_keys():
    decoded = valid_dict()
    decoded["tools"] = dict(reversed(list(decoded["tools"].items())))
    decoded["mappings"] = dict(reversed(list(decoded["mappings"].items())))

    serialized = FallbackState.from_dict(decoded).to_dict()

    assert list(serialized["tools"]) == ["T0", "T1", "T2"]
    assert list(serialized["mappings"]) == ["T0", "T1", "T2"]
    assert serialized["tools"]["T0"]["backups"] == ["T2", "T1"]


def test_missing_file_initializes_from_configuration_and_writes_once(tmp_path):
    path = tmp_path / "nested" / "state.json"
    tools = configured(("T0", ("T1",)), ("T1", ()))
    store = StateStore(str(path))

    state = store.load_reconciled(tools)

    assert state == FallbackState.from_config(tools)
    assert store.save(state) is True
    assert store.save(state) is False
    assert FallbackState.from_dict(json.loads(path.read_text())) == state
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_valid_unchanged_state_is_not_rewritten(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    decoded = valid_dict()
    write_json(path, decoded)
    store = StateStore(str(path))
    replace_calls = []
    monkeypatch.setattr(
        state_module.os, "replace",
        lambda source, destination: replace_calls.append((source, destination)))

    loaded = store.load_reconciled(configured(
        ("T0", ("T1",)), ("T1", ()), ("T2", ())))

    assert store.save(loaded) is False
    assert replace_calls == []


def test_reconcile_adds_new_tool_with_configured_defaults():
    state = FallbackState.from_dict(valid_dict())
    tools = configured(
        ("T0", ("T1",)), ("T1", ()), ("T2", ()), ("T3", ("T1", "T2")))

    reconciled = state.reconcile(tools)

    assert reconciled.tools["T3"].loaded is False
    assert reconciled.tools["T3"].purged is False
    assert reconciled.tools["T3"].failed is False
    assert reconciled.tools["T3"].backups == ("T1", "T2")
    assert reconciled.mappings["T3"] == "T3"


def test_reconcile_removes_stale_tools_backups_and_mappings():
    state = FallbackState.from_dict(valid_dict())

    reconciled = state.reconcile(configured(("T0", ()), ("T1", ())))

    assert set(reconciled.tools) == {"T0", "T1"}
    assert reconciled.tools["T0"].backups == ("T1",)
    assert reconciled.mappings == {"T0": "T0", "T1": "T1"}


def test_persisted_backup_order_takes_precedence_over_configuration():
    state = FallbackState.from_dict(valid_dict())
    tools = configured(("T0", ("T1", "T2")), ("T1", ()), ("T2", ()))

    reconciled = state.reconcile(tools)

    assert reconciled.tools["T0"].backups == ("T2", "T1")


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(version=2),
    lambda value: value.update(version=True),
    lambda value: value.update(extra={}),
    lambda value: value["tools"]["T0"].update(loaded=1),
    lambda value: value["tools"]["T0"].update(purged="yes"),
    lambda value: value["tools"]["T0"].update(backups=["T9"]),
    lambda value: value["tools"]["T0"].update(backups=["T0"]),
    lambda value: value["tools"]["T0"].update(backups=["T1", "T1"]),
    lambda value: value["tools"]["T0"].pop("backups"),
    lambda value: value["mappings"].update(T0="T9"),
    lambda value: value["mappings"].pop("T0"),
    lambda value: value["tools"].update(t0=value["tools"].pop("T0")),
])
def test_strict_parsing_rejects_invalid_state(mutate):
    decoded = valid_dict()
    mutate(decoded)

    with pytest.raises(StateValidationError):
        FallbackState.from_dict(decoded)


def test_strict_parsing_rejects_purged_unloaded_tool():
    decoded = valid_dict()
    decoded["tools"]["T0"].update(loaded=False, purged=True)

    with pytest.raises(StateValidationError, match="purged while unloaded"):
        FallbackState.from_dict(decoded)


@pytest.mark.parametrize("duplicate_json", [
    '{"version":1,"version":1,"tools":{},"mappings":{}}',
    (
        '{"version":1,"tools":{'
        '"T0":{"loaded":false,"purged":false,"failed":false,"backups":[]},'
        '"T0":{"loaded":false,"purged":false,"failed":false,"backups":[]}'
        '},"mappings":{"T0":"T0"}}'
    ),
    (
        '{"version":1,"tools":{"T0":{'
        '"loaded":false,"loaded":true,"purged":false,"failed":false,'
        '"backups":[]}},"mappings":{"T0":"T0"}}'
    ),
    (
        '{"version":1,"tools":{"T0":{'
        '"loaded":false,"purged":false,"failed":false,"backups":[]}},'
        '"mappings":{"T0":"T0","T0":"T0"}}'
    ),
])
def test_state_store_rejects_duplicate_json_keys_at_every_nesting_level(
        duplicate_json, tmp_path):
    path = tmp_path / "state.json"
    path.write_text(duplicate_json, encoding="utf-8")

    with pytest.raises(StateValidationError, match="duplicate object key"):
        StateStore(str(path)).load()


def test_malformed_json_does_not_replace_existing_file(tmp_path):
    path = tmp_path / "state.json"
    original = "{malformed json\n"
    path.write_text(original, encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        StateStore(str(path)).load()

    assert path.read_text(encoding="utf-8") == original


def test_unsupported_state_does_not_replace_existing_file(tmp_path):
    path = tmp_path / "state.json"
    decoded = valid_dict()
    decoded["version"] = 99
    write_json(path, decoded)
    original = path.read_bytes()

    with pytest.raises(StateValidationError):
        StateStore(str(path)).load()

    assert path.read_bytes() == original


def test_atomic_write_fsyncs_file_before_replace_and_parent_after(
        tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    state = FallbackState.from_config(configured(("T0", ())))
    events = []
    real_fsync = os.fsync
    real_replace = os.replace

    def tracked_fsync(descriptor):
        events.append("fsync")
        return real_fsync(descriptor)

    def tracked_replace(source, destination):
        with open(source, encoding="utf-8") as temporary_file:
            assert json.load(temporary_file) == state.to_dict()
        events.append("replace")
        return real_replace(source, destination)

    monkeypatch.setattr(state_module.os, "fsync", tracked_fsync)
    monkeypatch.setattr(state_module.os, "replace", tracked_replace)

    StateStore(str(path)).save(state)

    assert events == ["fsync", "replace", "fsync"]


def test_pre_replace_failure_preserves_original_and_cleans_temporary_file(
        tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text("original\n", encoding="utf-8")
    state = FallbackState.from_config(configured(("T0", ())))

    def fail_fsync(descriptor):
        raise OSError("injected file fsync failure")

    monkeypatch.setattr(state_module.os, "fsync", fail_fsync)

    with pytest.raises(OSError, match="injected"):
        StateStore(str(path)).save(state)

    assert path.read_text(encoding="utf-8") == "original\n"
    assert list(tmp_path.glob(".tool_fallback_state.*.tmp")) == []


def test_replace_failure_preserves_original_and_cleans_temporary_file(
        tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text("original\n", encoding="utf-8")
    state = FallbackState.from_config(configured(("T0", ())))

    def fail_replace(source, destination):
        raise OSError("injected replace failure")

    monkeypatch.setattr(state_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="injected"):
        StateStore(str(path)).save(state)

    assert path.read_text(encoding="utf-8") == "original\n"
    assert list(tmp_path.glob(".tool_fallback_state.*.tmp")) == []


def test_parent_directory_unsupported_fsync_is_tolerated(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    state = FallbackState.from_config(configured(("T0", ())))
    real_fsync = os.fsync
    calls = 0

    def unsupported_parent_fsync(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError(state_module.errno.EINVAL, "unsupported")
        return real_fsync(descriptor)

    monkeypatch.setattr(state_module.os, "fsync", unsupported_parent_fsync)

    assert StateStore(str(path)).save(state) is True
    assert path.exists()
