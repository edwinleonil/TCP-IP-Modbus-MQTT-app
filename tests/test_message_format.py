"""Tests for CommMessage serialization."""

from communication_app.core.message_format import CommMessage


def test_round_trip():
    msg = CommMessage.create(source="test", msg_type="sensor_data", value=25.4)
    json_str = msg.to_json()
    restored = CommMessage.from_json(json_str)
    assert restored.source == "test"
    assert restored.type == "sensor_data"
    assert restored.value == 25.4
    assert restored.timestamp == msg.timestamp


def test_create_sets_timestamp():
    msg = CommMessage.create(source="pi", msg_type="heartbeat")
    assert msg.timestamp is not None
    assert len(msg.timestamp) > 0


def test_none_value():
    msg = CommMessage.create(source="x", msg_type="ping")
    assert msg.value is None
    restored = CommMessage.from_json(msg.to_json())
    assert restored.value is None
