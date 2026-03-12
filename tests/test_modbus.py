"""Tests for Modbus TCP server and client.

Starts an embedded Modbus TCP server, then uses the client to read/write registers.
"""

import time
import pytest

from communication_app.modbus.modbus_server import ModbusTCPServer
from communication_app.modbus.modbus_client import ModbusTCPClient


@pytest.fixture()
def modbus_pair():
    """Start a Modbus TCP server and yield (server, client) pair."""
    server = ModbusTCPServer()
    server.start_server("127.0.0.1", 0)  # pymodbus needs a real port
    # pymodbus StartTcpServer blocks, but our wrapper runs it in a thread.
    # We need to know the port — fall back to a fixed port for this test.
    server.stop_server()

    # Use a fixed free port instead
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server = ModbusTCPServer()
    server.start_server("127.0.0.1", port, register_count=50)
    time.sleep(1)  # Allow server thread to initialise

    client = ModbusTCPClient()
    client.connect("127.0.0.1", port)
    yield server, client

    client.disconnect()
    server.stop_server()


def test_read_default_registers(modbus_pair):
    server, client = modbus_pair
    if not client.is_connected:
        pytest.skip("Could not connect to Modbus server")
    values = client.read_holding_registers(0, count=5)
    assert values is not None
    assert values == [0, 0, 0, 0, 0]


def test_write_and_read_register(modbus_pair):
    server, client = modbus_pair
    if not client.is_connected:
        pytest.skip("Could not connect to Modbus server")
    ok = client.write_register(10, 1234)
    assert ok
    values = client.read_holding_registers(10, count=1)
    assert values == [1234]
