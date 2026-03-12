"""Tests for MQTT client wrapper.

These tests require an MQTT broker running on localhost:1883.
They are skipped automatically if no broker is available.
"""

import time
import pytest

from communication_app.mqtt.mqtt_client import MQTTClientWrapper


def _broker_available() -> bool:
    """Quick check if localhost:1883 is reachable."""
    import socket
    try:
        s = socket.create_connection(("localhost", 1883), timeout=1)
        s.close()
        return True
    except OSError:
        return False


needs_broker = pytest.mark.skipif(
    not _broker_available(), reason="No MQTT broker on localhost:1883"
)


@needs_broker
def test_connect_disconnect():
    client = MQTTClientWrapper()
    connected_flag = []
    client.on_connected = lambda: connected_flag.append(True)
    client.connect("localhost", 1883, "test_client_1")
    time.sleep(1)
    assert client.is_connected
    assert connected_flag
    client.disconnect()
    assert not client.is_connected


@needs_broker
def test_pub_sub_round_trip():
    received = []
    client = MQTTClientWrapper()
    client.on_message_received = lambda t, p: received.append((t, p))
    client.connect("localhost", 1883, "test_client_2")
    time.sleep(1)

    client.subscribe("test/topic")
    time.sleep(0.5)

    client.publish("test/topic", "hello mqtt")
    time.sleep(1)

    assert any(p == "hello mqtt" for _, p in received)
    client.disconnect()
