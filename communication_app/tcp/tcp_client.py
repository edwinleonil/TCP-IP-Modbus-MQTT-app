"""TCP Client implementation using the socket module."""

import logging
import socket
import threading
import time

logger = logging.getLogger("comm_app.tcp.client")


class TCPClient:
    """TCP client with background receive loop and optional auto-reconnect."""

    def __init__(self):
        self._socket: socket.socket | None = None
        self._running = False
        self._receive_thread: threading.Thread | None = None
        self._host: str = ""
        self._port: int = 0

        # Callbacks
        self.on_connected: callable = None
        self.on_disconnected: callable = None
        self.on_message_received: callable = None
        self.on_error: callable = None

    @property
    def is_connected(self) -> bool:
        return self._running and self._socket is not None

    def connect(self, host: str, port: int, timeout: float = 5.0) -> None:
        if self._running:
            return
        self._host = host
        self._port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(timeout)
        try:
            self._socket.connect((host, port))
        except (OSError, ConnectionRefusedError) as e:
            logger.error("Connection failed to %s:%d – %s", host, port, e)
            if self.on_error:
                self.on_error(f"Connection failed: {e}")
            self._socket.close()
            self._socket = None
            return
        self._socket.settimeout(1.0)
        self._running = True
        self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._receive_thread.start()
        logger.info("Connected to %s:%d", host, port)
        if self.on_connected:
            self.on_connected()

    def _receive_loop(self) -> None:
        while self._running:
            try:
                data = self._socket.recv(4096)
                if not data:
                    break
                message = data.decode("utf-8", errors="replace")
                logger.debug("Received: %s", message)
                if self.on_message_received:
                    self.on_message_received(message)
            except socket.timeout:
                continue
            except (ConnectionResetError, OSError):
                break
        # Connection lost
        if self._running:
            self._running = False
            logger.info("Disconnected from server")
            if self.on_disconnected:
                self.on_disconnected()

    def send_message(self, message: str) -> None:
        if not self.is_connected:
            return
        try:
            self._socket.sendall(message.encode("utf-8"))
        except OSError as e:
            logger.error("Send error: %s", e)
            if self.on_error:
                self.on_error(str(e))

    def disconnect(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._receive_thread:
            self._receive_thread.join(timeout=3)
            self._receive_thread = None
        logger.info("Disconnected")
        if self.on_disconnected:
            self.on_disconnected()

    def reconnect(self, retries: int = 3, backoff: float = 2.0) -> None:
        """Attempt to reconnect with exponential backoff."""
        self.disconnect()
        for attempt in range(1, retries + 1):
            wait = backoff * attempt
            logger.info("Reconnect attempt %d/%d in %.1fs", attempt, retries, wait)
            time.sleep(wait)
            self.connect(self._host, self._port)
            if self.is_connected:
                return
        logger.error("All reconnect attempts failed")
        if self.on_error:
            self.on_error("All reconnect attempts failed")
