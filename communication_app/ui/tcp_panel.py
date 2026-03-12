"""TCP/IP protocol panel with server and client controls."""

import logging
from datetime import datetime

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QPushButton,
    QListWidget,
    QTextEdit,
    QSplitter,
)
from PySide6.QtCore import Qt

from communication_app.threads.worker_threads import TCPServerWorker, TCPClientWorker

logger = logging.getLogger("comm_app.ui.tcp")


class TCPPanel(QWidget):
    """Combined TCP server and client panel."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._server_worker: TCPServerWorker | None = None
        self._client_worker: TCPClientWorker | None = None
        self._msg_count_in = 0
        self._msg_count_out = 0
        self._setup_ui()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        # --- Server group ---
        server_group = QGroupBox("TCP Server")
        srv_layout = QVBoxLayout(server_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Host:"))
        self.srv_host = QLineEdit("0.0.0.0")
        row.addWidget(self.srv_host)
        row.addWidget(QLabel("Port:"))
        self.srv_port = QSpinBox()
        self.srv_port.setRange(1, 65535)
        self.srv_port.setValue(5000)
        row.addWidget(self.srv_port)
        srv_layout.addLayout(row)

        btn_row = QHBoxLayout()
        self.btn_start_srv = QPushButton("Start Server")
        self.btn_stop_srv = QPushButton("Stop Server")
        self.btn_stop_srv.setEnabled(False)
        btn_row.addWidget(self.btn_start_srv)
        btn_row.addWidget(self.btn_stop_srv)
        srv_layout.addLayout(btn_row)

        self.srv_status = QLabel("● Stopped")
        self.srv_status.setStyleSheet("color: red; font-weight: bold;")
        srv_layout.addWidget(self.srv_status)

        srv_layout.addWidget(QLabel("Connected Clients:"))
        self.client_list = QListWidget()
        srv_layout.addWidget(self.client_list)

        splitter.addWidget(server_group)

        # --- Client group ---
        client_group = QGroupBox("TCP Client")
        cli_layout = QVBoxLayout(client_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Server IP:"))
        self.cli_host = QLineEdit("127.0.0.1")
        row.addWidget(self.cli_host)
        row.addWidget(QLabel("Port:"))
        self.cli_port = QSpinBox()
        self.cli_port.setRange(1, 65535)
        self.cli_port.setValue(5000)
        row.addWidget(self.cli_port)
        cli_layout.addLayout(row)

        btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)
        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_disconnect)
        cli_layout.addLayout(btn_row)

        self.cli_status = QLabel("● Disconnected")
        self.cli_status.setStyleSheet("color: red; font-weight: bold;")
        cli_layout.addWidget(self.cli_status)

        splitter.addWidget(client_group)
        main_layout.addWidget(splitter)

        # --- Messaging ---
        msg_group = QGroupBox("Messages")
        msg_layout = QVBoxLayout(msg_group)

        send_row = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Type a message…")
        send_row.addWidget(self.msg_input)
        self.btn_send = QPushButton("Send")
        send_row.addWidget(self.btn_send)
        msg_layout.addLayout(send_row)

        self.msg_log = QTextEdit()
        self.msg_log.setReadOnly(True)
        msg_layout.addWidget(self.msg_log)

        self.msg_counter = QLabel("Sent: 0 | Received: 0")
        msg_layout.addWidget(self.msg_counter)

        main_layout.addWidget(msg_group)

        # --- Connections ---
        self.btn_start_srv.clicked.connect(self._start_server)
        self.btn_stop_srv.clicked.connect(self._stop_server)
        self.btn_connect.clicked.connect(self._connect_client)
        self.btn_disconnect.clicked.connect(self._disconnect_client)
        self.btn_send.clicked.connect(self._send_message)
        self.msg_input.returnPressed.connect(self._send_message)

    # -------------------------------------------------------------- Server
    def _start_server(self) -> None:
        self._server_worker = TCPServerWorker(self)
        self._server_worker.configure(
            self.srv_host.text(), self.srv_port.value()
        )
        self._server_worker.client_connected.connect(self._on_client_connected)
        self._server_worker.client_disconnected.connect(self._on_client_disconnected)
        self._server_worker.message_received.connect(self._on_server_message)
        self._server_worker.server_started.connect(self._on_server_started)
        self._server_worker.server_stopped.connect(self._on_server_stopped)
        self._server_worker.error.connect(self._on_error)
        self._server_worker.start()

    def _stop_server(self) -> None:
        if self._server_worker:
            self._server_worker.stop()
            self._server_worker = None

    @Slot()
    def _on_server_started(self):
        self.srv_status.setText("● Running")
        self.srv_status.setStyleSheet("color: green; font-weight: bold;")
        self.btn_start_srv.setEnabled(False)
        self.btn_stop_srv.setEnabled(True)
        self.srv_host.setEnabled(False)
        self.srv_port.setEnabled(False)

    @Slot()
    def _on_server_stopped(self):
        self.srv_status.setText("● Stopped")
        self.srv_status.setStyleSheet("color: red; font-weight: bold;")
        self.btn_start_srv.setEnabled(True)
        self.btn_stop_srv.setEnabled(False)
        self.srv_host.setEnabled(True)
        self.srv_port.setEnabled(True)
        self.client_list.clear()

    @Slot(str)
    def _on_client_connected(self, client_id: str):
        self.client_list.addItem(client_id)
        self._append_log(f"[SERVER] Client connected: {client_id}")

    @Slot(str)
    def _on_client_disconnected(self, client_id: str):
        items = self.client_list.findItems(client_id, Qt.MatchExactly)
        for item in items:
            self.client_list.takeItem(self.client_list.row(item))
        self._append_log(f"[SERVER] Client disconnected: {client_id}")

    @Slot(str, str)
    def _on_server_message(self, client_id: str, message: str):
        self._msg_count_in += 1
        self._update_counter()
        self._append_log(f"[SERVER ← {client_id}] {message}")

    # -------------------------------------------------------------- Client
    def _connect_client(self) -> None:
        self._client_worker = TCPClientWorker(self)
        self._client_worker.configure(
            self.cli_host.text(), self.cli_port.value()
        )
        self._client_worker.connected.connect(self._on_connected)
        self._client_worker.disconnected.connect(self._on_disconnected)
        self._client_worker.message_received.connect(self._on_client_message)
        self._client_worker.error.connect(self._on_error)
        self._client_worker.start()

    def _disconnect_client(self) -> None:
        if self._client_worker:
            self._client_worker.stop()
            self._client_worker = None

    @Slot()
    def _on_connected(self):
        self.cli_status.setText("● Connected")
        self.cli_status.setStyleSheet("color: green; font-weight: bold;")
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.cli_host.setEnabled(False)
        self.cli_port.setEnabled(False)

    @Slot()
    def _on_disconnected(self):
        self.cli_status.setText("● Disconnected")
        self.cli_status.setStyleSheet("color: red; font-weight: bold;")
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.cli_host.setEnabled(True)
        self.cli_port.setEnabled(True)

    @Slot(str)
    def _on_client_message(self, message: str):
        self._msg_count_in += 1
        self._update_counter()
        self._append_log(f"[CLIENT ←] {message}")

    # ----------------------------------------------------------- Messaging
    def _send_message(self) -> None:
        text = self.msg_input.text().strip()
        if not text:
            return
        # Send via client if connected, else broadcast via server
        if self._client_worker and self._client_worker.client.is_connected:
            self._client_worker.client.send_message(text)
            self._append_log(f"[CLIENT →] {text}")
        elif self._server_worker and self._server_worker.server.is_running:
            self._server_worker.server.broadcast(text)
            self._append_log(f"[SERVER →] {text}")
        else:
            self._append_log("[ERROR] Not connected")
            return
        self._msg_count_out += 1
        self._update_counter()
        self.msg_input.clear()

    # ----------------------------------------------------------- Utilities
    @Slot(str)
    def _on_error(self, error: str):
        self._append_log(f"[ERROR] {error}")
        logger.error(error)

    def _append_log(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.msg_log.append(f"[{ts}] {text}")

    def _update_counter(self) -> None:
        self.msg_counter.setText(
            f"Sent: {self._msg_count_out} | Received: {self._msg_count_in}"
        )

    def shutdown(self) -> None:
        """Stop all active workers."""
        self._stop_server()
        self._disconnect_client()
