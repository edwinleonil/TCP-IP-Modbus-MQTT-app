"""Tests for TCP server and client communication."""

import time
import threading

from communication_app.tcp.tcp_server import TCPServer
from communication_app.tcp.tcp_client import TCPClient


def test_server_client_round_trip():
    """Start a server, connect a client, exchange a message, then disconnect."""
    received = []
    server = TCPServer()
    server.on_message_received = lambda cid, msg: received.append((cid, msg))
    server.start_server("127.0.0.1", 0)  # port 0 = OS picks free port

    # Retrieve the actual bound port
    port = server._server_socket.getsockname()[1]

    client = TCPClient()
    client_msgs = []
    client.on_message_received = lambda msg: client_msgs.append(msg)
    client.connect("127.0.0.1", port)
    assert client.is_connected

    # Client sends to server
    client.send_message("hello server")
    time.sleep(0.5)
    assert len(received) == 1
    assert received[0][1] == "hello server"

    # Server broadcasts to client
    server.broadcast("hello client")
    time.sleep(0.5)
    assert len(client_msgs) == 1
    assert client_msgs[0] == "hello client"

    client.disconnect()
    server.stop_server()


def test_multiple_clients():
    """Connect two clients and verify broadcast reaches both."""
    server = TCPServer()
    server.start_server("127.0.0.1", 0)
    port = server._server_socket.getsockname()[1]

    c1_msgs, c2_msgs = [], []
    c1 = TCPClient()
    c1.on_message_received = lambda msg: c1_msgs.append(msg)
    c2 = TCPClient()
    c2.on_message_received = lambda msg: c2_msgs.append(msg)

    c1.connect("127.0.0.1", port)
    c2.connect("127.0.0.1", port)
    time.sleep(0.3)

    server.broadcast("broadcast")
    time.sleep(0.5)

    assert "broadcast" in c1_msgs
    assert "broadcast" in c2_msgs

    c1.disconnect()
    c2.disconnect()
    server.stop_server()
