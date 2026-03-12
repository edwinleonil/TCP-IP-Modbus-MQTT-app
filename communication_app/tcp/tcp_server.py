"""TCP Server implementation using the socket module."""

import logging
import socket
import threading

logger = logging.getLogger("comm_app.tcp.server")


class TCPServer:
    """Multi-client TCP server with callback-based event notification."""

    def __init__(self):
        self._server_socket: socket.socket | None = None
        self._clients: dict[str, socket.socket] = {}
        self._running = False
        self._accept_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Callbacks – set by the worker / caller
        self.on_client_connected: callable = None
        self.on_client_disconnected: callable = None
        self.on_message_received: callable = None
        self.on_error: callable = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start_server(self, host: str = "0.0.0.0", port: int = 5000) -> None:
        if self._running:
            return
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.settimeout(1.0)
        self._server_socket.bind((host, port))
        self._server_socket.listen(5)
        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_clients, daemon=True)
        self._accept_thread.start()
        logger.info("TCP server started on %s:%d", host, port)

    def _accept_clients(self) -> None:
        while self._running:
            try:
                conn, addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            client_id = f"{addr[0]}:{addr[1]}"
            with self._lock:
                self._clients[client_id] = conn
            logger.info("Client connected: %s", client_id)
            if self.on_client_connected:
                self.on_client_connected(client_id)
            handler = threading.Thread(
                target=self._handle_client, args=(conn, client_id), daemon=True
            )
            handler.start()

    def _handle_client(self, conn: socket.socket, client_id: str) -> None:
        try:
            while self._running:
                data = conn.recv(4096)
                if not data:
                    break
                message = data.decode("utf-8", errors="replace")
                logger.debug("Received from %s: %s", client_id, message)
                if self.on_message_received:
                    self.on_message_received(client_id, message)
        except (ConnectionResetError, OSError):
            pass
        finally:
            self._remove_client(client_id)

    def _remove_client(self, client_id: str) -> None:
        with self._lock:
            conn = self._clients.pop(client_id, None)
        if conn:
            try:
                conn.close()
            except OSError:
                pass
        logger.info("Client disconnected: %s", client_id)
        if self.on_client_disconnected:
            self.on_client_disconnected(client_id)

    def send_to(self, client_id: str, message: str) -> None:
        with self._lock:
            conn = self._clients.get(client_id)
        if conn is None:
            return
        try:
            conn.sendall(message.encode("utf-8"))
        except OSError as e:
            logger.error("Send error to %s: %s", client_id, e)
            if self.on_error:
                self.on_error(str(e))

    def broadcast(self, message: str) -> None:
        with self._lock:
            clients = list(self._clients.items())
        for client_id, conn in clients:
            try:
                conn.sendall(message.encode("utf-8"))
            except OSError:
                self._remove_client(client_id)

    def stop_server(self) -> None:
        if not self._running:
            return
        self._running = False
        # Close all client connections
        with self._lock:
            for conn in self._clients.values():
                try:
                    conn.close()
                except OSError:
                    pass
            self._clients.clear()
        # Close server socket
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        if self._accept_thread:
            self._accept_thread.join(timeout=3)
            self._accept_thread = None
        logger.info("TCP server stopped")

    def get_client_ids(self) -> list[str]:
        with self._lock:
            return list(self._clients.keys())
