"""MQTT protocol panel with broker management, pub/sub, and message viewer."""

import logging
import os
from datetime import datetime

from PySide6.QtCore import Qt, Slot, QTimer
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
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QMessageBox,
    QFileDialog,
)

from communication_app.threads.worker_threads import MQTTClientWorker, MQTTBrokerWorker
from communication_app.mqtt.mqtt_broker_manager import find_mosquitto, install_guidance

logger = logging.getLogger("comm_app.ui.mqtt")


_DEFAULT_CONF = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "config", "mosquitto.conf")
)

_SYS_TOPICS = [
    "$SYS/broker/clients/connected",
    "$SYS/broker/clients/total",
    "$SYS/broker/messages/received",
    "$SYS/broker/messages/sent",
    "$SYS/broker/uptime",
]


class MQTTPanel(QWidget):
    """MQTT broker management, subscribe, publish, and message viewer panel."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker: MQTTClientWorker | None = None
        self._broker_worker: MQTTBrokerWorker | None = None
        self._sys_monitor: MQTTClientWorker | None = None
        self._msg_count_in = 0
        self._msg_count_out = 0
        self._setup_ui()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical)

        # ---- Top half: broker controls + client connection ----
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # --- Broker Control ---
        broker_group = QGroupBox("Broker Control (Mosquitto)")
        broker_layout = QVBoxLayout(broker_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Port:"))
        self.broker_port_input = QSpinBox()
        self.broker_port_input.setRange(1, 65535)
        self.broker_port_input.setValue(1883)
        row1.addWidget(self.broker_port_input)

        row1.addWidget(QLabel("Config:"))
        self.broker_config_input = QLineEdit(_DEFAULT_CONF)
        row1.addWidget(self.broker_config_input)
        self.btn_browse_conf = QPushButton("Browse…")
        self.btn_browse_conf.setMaximumWidth(80)
        row1.addWidget(self.btn_browse_conf)
        broker_layout.addLayout(row1)

        btn_row = QHBoxLayout()
        self.btn_broker_start = QPushButton("Start Broker")
        self.btn_broker_stop = QPushButton("Stop Broker")
        self.btn_broker_stop.setEnabled(False)
        self.btn_broker_restart = QPushButton("Restart")
        self.btn_broker_restart.setEnabled(False)
        btn_row.addWidget(self.btn_broker_start)
        btn_row.addWidget(self.btn_broker_stop)
        btn_row.addWidget(self.btn_broker_restart)
        broker_layout.addLayout(btn_row)

        status_row = QHBoxLayout()
        self.broker_status_label = QLabel("● Stopped")
        self.broker_status_label.setStyleSheet("color: red; font-weight: bold;")
        status_row.addWidget(self.broker_status_label)
        status_row.addStretch()
        self.broker_clients_label = QLabel("Connected clients: –")
        status_row.addWidget(self.broker_clients_label)
        broker_layout.addLayout(status_row)

        self.broker_log = QPlainTextEdit()
        self.broker_log.setReadOnly(True)
        self.broker_log.setMaximumHeight(100)
        self.broker_log.setPlaceholderText("Broker log output…")
        broker_layout.addWidget(self.broker_log)

        top_layout.addWidget(broker_group)

        # --- Connection ---
        conn_group = QGroupBox("Client Connection")
        conn_layout = QVBoxLayout(conn_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Broker:"))
        self.broker_input = QLineEdit("localhost")
        row.addWidget(self.broker_input)
        row.addWidget(QLabel("Port:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(1883)
        row.addWidget(self.port_input)
        row.addWidget(QLabel("Client ID:"))
        self.client_id_input = QLineEdit("comm_app_client")
        row.addWidget(self.client_id_input)
        conn_layout.addLayout(row)

        auth_row = QHBoxLayout()
        auth_row.addWidget(QLabel("Username:"))
        self.mqtt_username_input = QLineEdit()
        self.mqtt_username_input.setPlaceholderText("(optional)")
        auth_row.addWidget(self.mqtt_username_input)
        auth_row.addWidget(QLabel("Password:"))
        self.mqtt_password_input = QLineEdit()
        self.mqtt_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.mqtt_password_input.setPlaceholderText("(optional)")
        auth_row.addWidget(self.mqtt_password_input)
        conn_layout.addLayout(auth_row)

        btn_row2 = QHBoxLayout()
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)
        btn_row2.addWidget(self.btn_connect)
        btn_row2.addWidget(self.btn_disconnect)
        conn_layout.addLayout(btn_row2)

        self.status_label = QLabel("● Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_layout.addWidget(self.status_label)

        top_layout.addWidget(conn_group)
        splitter.addWidget(top)

        # ---- Bottom half: sub/pub + message viewer ----
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        mid_layout = QHBoxLayout()

        # Subscribe
        sub_group = QGroupBox("Subscribe")
        sub_layout = QVBoxLayout(sub_group)
        sub_row = QHBoxLayout()
        self.sub_topic_input = QLineEdit()
        self.sub_topic_input.setPlaceholderText("topic/to/subscribe")
        sub_row.addWidget(self.sub_topic_input)
        self.btn_subscribe = QPushButton("Subscribe")
        self.btn_unsubscribe = QPushButton("Unsubscribe")
        sub_row.addWidget(self.btn_subscribe)
        sub_row.addWidget(self.btn_unsubscribe)
        sub_layout.addLayout(sub_row)

        sub_layout.addWidget(QLabel("Active Subscriptions:"))
        self.sub_list = QListWidget()
        sub_layout.addWidget(self.sub_list)
        mid_layout.addWidget(sub_group)

        # Publish
        pub_group = QGroupBox("Publish")
        pub_layout = QVBoxLayout(pub_group)
        pub_layout.addWidget(QLabel("Topic:"))
        self.pub_topic_input = QLineEdit()
        self.pub_topic_input.setPlaceholderText("topic/to/publish")
        pub_layout.addWidget(self.pub_topic_input)
        pub_layout.addWidget(QLabel("Message:"))
        self.pub_message_input = QTextEdit()
        self.pub_message_input.setMaximumHeight(80)
        pub_layout.addWidget(self.pub_message_input)
        self.btn_publish = QPushButton("Publish")
        pub_layout.addWidget(self.btn_publish)
        mid_layout.addWidget(pub_group)

        bottom_layout.addLayout(mid_layout)

        # Message Viewer
        viewer_group = QGroupBox("Received Messages")
        viewer_layout = QVBoxLayout(viewer_group)
        self.msg_table = QTableWidget(0, 3)
        self.msg_table.setHorizontalHeaderLabels(["Timestamp", "Topic", "Payload"])
        self.msg_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.msg_table.setEditTriggers(QTableWidget.NoEditTriggers)
        viewer_layout.addWidget(self.msg_table)

        self.msg_counter = QLabel("Published: 0 | Received: 0")
        viewer_layout.addWidget(self.msg_counter)

        bottom_layout.addWidget(viewer_group)
        splitter.addWidget(bottom)

        outer.addWidget(splitter)

        # --- Signal connections ---
        self.btn_browse_conf.clicked.connect(self._browse_config)
        self.btn_broker_start.clicked.connect(self._start_broker)
        self.btn_broker_stop.clicked.connect(self._stop_broker)
        self.btn_broker_restart.clicked.connect(self._restart_broker)
        self.btn_connect.clicked.connect(self._connect)
        self.btn_disconnect.clicked.connect(self._disconnect)
        self.btn_subscribe.clicked.connect(self._subscribe)
        self.btn_unsubscribe.clicked.connect(self._unsubscribe)
        self.btn_publish.clicked.connect(self._publish)

    # -------------------------------------------------------- Broker Control
    def _browse_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Mosquitto Config", "", "Config files (*.conf);;All files (*)"
        )
        if path:
            self.broker_config_input.setText(path)

    def _start_broker(self) -> None:
        exe = find_mosquitto()
        if exe is None:
            QMessageBox.warning(self, "Mosquitto Not Found", install_guidance())
            return

        self._broker_worker = MQTTBrokerWorker(self)
        conf = self.broker_config_input.text().strip() or None
        self._broker_worker.configure(
            port=self.broker_port_input.value(),
            config_path=conf,
            exe_path=exe,
        )
        self._broker_worker.broker_started.connect(self._on_broker_started)
        self._broker_worker.broker_stopped.connect(self._on_broker_stopped)
        self._broker_worker.broker_error.connect(self._on_broker_error)
        self._broker_worker.broker_status_changed.connect(self._on_broker_status)
        self._broker_worker.broker_log_message.connect(self._on_broker_log)
        self._broker_worker.start()

        self.btn_broker_start.setEnabled(False)
        self.broker_status_label.setText("● Starting…")
        self.broker_status_label.setStyleSheet("color: orange; font-weight: bold;")

    def _stop_broker(self) -> None:
        self._stop_sys_monitor()
        if self._broker_worker:
            self._broker_worker.stop()
            self._broker_worker = None

    def _restart_broker(self) -> None:
        self._stop_broker()
        # small delay so the port is freed
        QTimer.singleShot(500, self._start_broker)

    @Slot()
    def _on_broker_started(self) -> None:
        self.broker_status_label.setText("● Running")
        self.broker_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.btn_broker_start.setEnabled(False)
        self.btn_broker_stop.setEnabled(True)
        self.btn_broker_restart.setEnabled(True)
        self.broker_port_input.setEnabled(False)
        self.broker_config_input.setEnabled(False)
        self.btn_browse_conf.setEnabled(False)
        self._start_sys_monitor()

    @Slot()
    def _on_broker_stopped(self) -> None:
        self.broker_status_label.setText("● Stopped")
        self.broker_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.btn_broker_start.setEnabled(True)
        self.btn_broker_stop.setEnabled(False)
        self.btn_broker_restart.setEnabled(False)
        self.broker_port_input.setEnabled(True)
        self.broker_config_input.setEnabled(True)
        self.btn_browse_conf.setEnabled(True)
        self.broker_clients_label.setText("Connected clients: –")

    @Slot(str)
    def _on_broker_error(self, error: str) -> None:
        logger.error("Broker error: %s", error)
        self.broker_log.appendPlainText(f"[ERROR] {error}")
        self._on_broker_stopped()

    @Slot(str)
    def _on_broker_status(self, status: str) -> None:
        logger.info("Broker status: %s", status)

    @Slot(str)
    def _on_broker_log(self, line: str) -> None:
        self.broker_log.appendPlainText(line)

    # ---------------------------------------------------- $SYS Monitoring
    def _start_sys_monitor(self) -> None:
        """Connect a hidden MQTT client to subscribe to $SYS topics."""
        self._sys_monitor = MQTTClientWorker(self)
        port = self.broker_port_input.value()
        self._sys_monitor.configure("127.0.0.1", port, "_sys_monitor")
        self._sys_monitor.connected.connect(self._on_sys_connected)
        self._sys_monitor.message_received.connect(self._on_sys_message)
        self._sys_monitor.start()

    def _stop_sys_monitor(self) -> None:
        if self._sys_monitor:
            self._sys_monitor.stop()
            self._sys_monitor = None

    @Slot()
    def _on_sys_connected(self) -> None:
        if self._sys_monitor:
            for topic in _SYS_TOPICS:
                self._sys_monitor.client.subscribe(topic)

    @Slot(str, str)
    def _on_sys_message(self, topic: str, payload: str) -> None:
        if topic == "$SYS/broker/clients/connected":
            self.broker_clients_label.setText(f"Connected clients: {payload}")

    # --------------------------------------------------------- Client Connection
    def _connect(self) -> None:
        self._worker = MQTTClientWorker(self)
        self._worker.configure(
            self.broker_input.text(),
            self.port_input.value(),
            self.client_id_input.text(),
            self.mqtt_username_input.text(),
            self.mqtt_password_input.text(),
        )
        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        self._worker.message_received.connect(self._on_message)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _disconnect(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker = None
            self._on_disconnected()

    @Slot()
    def _on_connected(self):
        self.status_label.setText("● Connected")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.broker_input.setEnabled(False)
        self.port_input.setEnabled(False)
        self.client_id_input.setEnabled(False)

    @Slot()
    def _on_disconnected(self):
        self.status_label.setText("● Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.broker_input.setEnabled(True)
        self.port_input.setEnabled(True)
        self.client_id_input.setEnabled(True)

    # ----------------------------------------------------------- Sub/Pub
    def _subscribe(self) -> None:
        topic = self.sub_topic_input.text().strip()
        if not topic or not self._worker:
            return
        self._worker.client.subscribe(topic)
        if not self.sub_list.findItems(topic, Qt.MatchExactly):
            self.sub_list.addItem(topic)

    def _unsubscribe(self) -> None:
        topic = self.sub_topic_input.text().strip()
        if not topic or not self._worker:
            return
        self._worker.client.unsubscribe(topic)
        items = self.sub_list.findItems(topic, Qt.MatchExactly)
        for item in items:
            self.sub_list.takeItem(self.sub_list.row(item))

    def _publish(self) -> None:
        topic = self.pub_topic_input.text().strip()
        message = self.pub_message_input.toPlainText().strip()
        if not topic or not message or not self._worker:
            return
        self._worker.client.publish(topic, message)
        self._msg_count_out += 1
        self._update_counter()

    @Slot(str, str)
    def _on_message(self, topic: str, payload: str):
        self._msg_count_in += 1
        self._update_counter()
        row = self.msg_table.rowCount()
        self.msg_table.insertRow(row)
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.msg_table.setItem(row, 0, QTableWidgetItem(ts))
        self.msg_table.setItem(row, 1, QTableWidgetItem(topic))
        self.msg_table.setItem(row, 2, QTableWidgetItem(payload))
        self.msg_table.scrollToBottom()

    @Slot(str)
    def _on_error(self, error: str):
        logger.error("MQTT panel error: %s", error)

    def _update_counter(self) -> None:
        self.msg_counter.setText(
            f"Published: {self._msg_count_out} | Received: {self._msg_count_in}"
        )

    def shutdown(self) -> None:
        self._disconnect()
        self._stop_sys_monitor()
        self._stop_broker()
