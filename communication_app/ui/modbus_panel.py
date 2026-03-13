"""Modbus protocol panel with TCP and RTU modes for both server and client."""

import logging

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTabWidget,
    QSplitter,
)

from communication_app.threads.worker_threads import (
    ModbusTCPServerWorker,
    ModbusTCPClientWorker,
    ModbusRTUServerWorker,
    ModbusRTUClientWorker,
)

logger = logging.getLogger("comm_app.ui.modbus")

BAUDRATES = ["9600", "19200", "38400", "57600", "115200"]
PARITIES = ["N", "E", "O"]
STOPBITS = ["1", "2"]


def _detect_serial_ports() -> list[str]:
    """Return available serial port names."""
    try:
        from serial.tools.list_ports import comports
        return [p.device for p in comports()] or ["COM1"]
    except ImportError:
        return ["COM1"]


class ModbusPanel(QWidget):
    """Modbus panel supporting TCP and RTU modes for server and client."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tcp_server_worker: ModbusTCPServerWorker | None = None
        self._tcp_client_worker: ModbusTCPClientWorker | None = None
        self._rtu_server_worker: ModbusRTUServerWorker | None = None
        self._rtu_client_worker: ModbusRTUClientWorker | None = None
        self._setup_ui()

        # Periodic refresh of server register tables
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_server_tables)
        self._refresh_timer.start(1000)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Mode selector
        self.mode_tabs = QTabWidget()
        self.mode_tabs.addTab(self._build_tcp_tab(), "Modbus TCP")
        self.mode_tabs.addTab(self._build_rtu_tab(), "Modbus RTU")
        layout.addWidget(self.mode_tabs)

    # ============================================================ TCP TAB
    def _build_tcp_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        splitter = QSplitter(Qt.Horizontal)

        # --- TCP Server ---
        srv_group = QGroupBox("TCP Server")
        srv_layout = QVBoxLayout(srv_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Host:"))
        self.tcp_srv_host = QLineEdit("0.0.0.0")
        row.addWidget(self.tcp_srv_host)
        row.addWidget(QLabel("Port:"))
        self.tcp_srv_port = QSpinBox()
        self.tcp_srv_port.setRange(1, 65535)
        self.tcp_srv_port.setValue(5020)
        row.addWidget(self.tcp_srv_port)
        row.addWidget(QLabel("Registers:"))
        self.tcp_srv_reg_count = QSpinBox()
        self.tcp_srv_reg_count.setRange(1, 10000)
        self.tcp_srv_reg_count.setValue(100)
        row.addWidget(self.tcp_srv_reg_count)
        srv_layout.addLayout(row)

        btn_row = QHBoxLayout()
        self.btn_tcp_srv_start = QPushButton("Start Server")
        self.btn_tcp_srv_stop = QPushButton("Stop Server")
        self.btn_tcp_srv_stop.setEnabled(False)
        btn_row.addWidget(self.btn_tcp_srv_start)
        btn_row.addWidget(self.btn_tcp_srv_stop)
        srv_layout.addLayout(btn_row)

        self.tcp_srv_status = QLabel("● Stopped")
        self.tcp_srv_status.setStyleSheet("color: red; font-weight: bold;")
        srv_layout.addWidget(self.tcp_srv_status)

        srv_layout.addWidget(QLabel("Server Registers:"))
        self.tcp_srv_table = QTableWidget(0, 2)
        self.tcp_srv_table.setHorizontalHeaderLabels(["Address", "Value"])
        self.tcp_srv_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        srv_layout.addWidget(self.tcp_srv_table)

        splitter.addWidget(srv_group)

        # --- TCP Client ---
        cli_group = QGroupBox("TCP Client")
        cli_layout = QVBoxLayout(cli_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Server IP:"))
        self.tcp_cli_host = QLineEdit("127.0.0.1")
        row.addWidget(self.tcp_cli_host)
        row.addWidget(QLabel("Port:"))
        self.tcp_cli_port = QSpinBox()
        self.tcp_cli_port.setRange(1, 65535)
        self.tcp_cli_port.setValue(5020)
        row.addWidget(self.tcp_cli_port)
        cli_layout.addLayout(row)

        btn_row = QHBoxLayout()
        self.btn_tcp_cli_connect = QPushButton("Connect")
        self.btn_tcp_cli_disconnect = QPushButton("Disconnect")
        self.btn_tcp_cli_disconnect.setEnabled(False)
        btn_row.addWidget(self.btn_tcp_cli_connect)
        btn_row.addWidget(self.btn_tcp_cli_disconnect)
        cli_layout.addLayout(btn_row)

        self.tcp_cli_status = QLabel("● Disconnected")
        self.tcp_cli_status.setStyleSheet("color: red; font-weight: bold;")
        cli_layout.addWidget(self.tcp_cli_status)

        # Read controls
        read_row = QHBoxLayout()
        read_row.addWidget(QLabel("Addr:"))
        self.tcp_read_addr = QSpinBox()
        self.tcp_read_addr.setRange(0, 9999)
        read_row.addWidget(self.tcp_read_addr)
        read_row.addWidget(QLabel("Count:"))
        self.tcp_read_count = QSpinBox()
        self.tcp_read_count.setRange(1, 125)
        self.tcp_read_count.setValue(10)
        read_row.addWidget(self.tcp_read_count)
        self.btn_tcp_read = QPushButton("Read")
        read_row.addWidget(self.btn_tcp_read)
        cli_layout.addLayout(read_row)

        # Write controls
        write_row = QHBoxLayout()
        write_row.addWidget(QLabel("Addr:"))
        self.tcp_write_addr = QSpinBox()
        self.tcp_write_addr.setRange(0, 9999)
        write_row.addWidget(self.tcp_write_addr)
        write_row.addWidget(QLabel("Value:"))
        self.tcp_write_value = QSpinBox()
        self.tcp_write_value.setRange(0, 65535)
        write_row.addWidget(self.tcp_write_value)
        self.btn_tcp_write = QPushButton("Write")
        write_row.addWidget(self.btn_tcp_write)
        cli_layout.addLayout(write_row)

        cli_layout.addWidget(QLabel("Client Registers:"))
        self.tcp_cli_table = QTableWidget(0, 2)
        self.tcp_cli_table.setHorizontalHeaderLabels(["Address", "Value"])
        self.tcp_cli_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tcp_cli_table.setEditTriggers(QTableWidget.NoEditTriggers)
        cli_layout.addWidget(self.tcp_cli_table)

        splitter.addWidget(cli_group)
        layout.addWidget(splitter)

        # Signals
        self.btn_tcp_srv_start.clicked.connect(self._tcp_start_server)
        self.btn_tcp_srv_stop.clicked.connect(self._tcp_stop_server)
        self.btn_tcp_cli_connect.clicked.connect(self._tcp_connect_client)
        self.btn_tcp_cli_disconnect.clicked.connect(self._tcp_disconnect_client)
        self.btn_tcp_read.clicked.connect(self._tcp_read)
        self.btn_tcp_write.clicked.connect(self._tcp_write)
        self.tcp_srv_table.cellChanged.connect(self._tcp_server_cell_changed)

        return tab

    # ============================================================ RTU TAB
    def _build_rtu_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        splitter = QSplitter(Qt.Horizontal)
        ports = _detect_serial_ports()

        # --- RTU Server ---
        srv_group = QGroupBox("RTU Server")
        srv_layout = QVBoxLayout(srv_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Port:"))
        self.rtu_srv_port = QComboBox()
        self.rtu_srv_port.addItems(ports)
        self.rtu_srv_port.setEditable(True)
        row.addWidget(self.rtu_srv_port)
        row.addWidget(QLabel("Baud:"))
        self.rtu_srv_baud = QComboBox()
        self.rtu_srv_baud.addItems(BAUDRATES)
        row.addWidget(self.rtu_srv_baud)
        srv_layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Parity:"))
        self.rtu_srv_parity = QComboBox()
        self.rtu_srv_parity.addItems(PARITIES)
        row2.addWidget(self.rtu_srv_parity)
        row2.addWidget(QLabel("Stop:"))
        self.rtu_srv_stopbits = QComboBox()
        self.rtu_srv_stopbits.addItems(STOPBITS)
        row2.addWidget(self.rtu_srv_stopbits)
        row2.addWidget(QLabel("Slave ID:"))
        self.rtu_srv_slave = QSpinBox()
        self.rtu_srv_slave.setRange(1, 247)
        self.rtu_srv_slave.setValue(1)
        row2.addWidget(self.rtu_srv_slave)
        row2.addWidget(QLabel("Registers:"))
        self.rtu_srv_reg_count = QSpinBox()
        self.rtu_srv_reg_count.setRange(1, 10000)
        self.rtu_srv_reg_count.setValue(100)
        row2.addWidget(self.rtu_srv_reg_count)
        srv_layout.addLayout(row2)

        btn_row = QHBoxLayout()
        self.btn_rtu_srv_start = QPushButton("Start Server")
        self.btn_rtu_srv_stop = QPushButton("Stop Server")
        self.btn_rtu_srv_stop.setEnabled(False)
        btn_row.addWidget(self.btn_rtu_srv_start)
        btn_row.addWidget(self.btn_rtu_srv_stop)
        srv_layout.addLayout(btn_row)

        self.rtu_srv_status = QLabel("● Stopped")
        self.rtu_srv_status.setStyleSheet("color: red; font-weight: bold;")
        srv_layout.addWidget(self.rtu_srv_status)

        srv_layout.addWidget(QLabel("Server Registers:"))
        self.rtu_srv_table = QTableWidget(0, 2)
        self.rtu_srv_table.setHorizontalHeaderLabels(["Address", "Value"])
        self.rtu_srv_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        srv_layout.addWidget(self.rtu_srv_table)

        splitter.addWidget(srv_group)

        # --- RTU Client ---
        cli_group = QGroupBox("RTU Client")
        cli_layout = QVBoxLayout(cli_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Port:"))
        self.rtu_cli_port = QComboBox()
        self.rtu_cli_port.addItems(ports)
        self.rtu_cli_port.setEditable(True)
        row.addWidget(self.rtu_cli_port)
        row.addWidget(QLabel("Baud:"))
        self.rtu_cli_baud = QComboBox()
        self.rtu_cli_baud.addItems(BAUDRATES)
        row.addWidget(self.rtu_cli_baud)
        cli_layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Parity:"))
        self.rtu_cli_parity = QComboBox()
        self.rtu_cli_parity.addItems(PARITIES)
        row2.addWidget(self.rtu_cli_parity)
        row2.addWidget(QLabel("Stop:"))
        self.rtu_cli_stopbits = QComboBox()
        self.rtu_cli_stopbits.addItems(STOPBITS)
        row2.addWidget(self.rtu_cli_stopbits)
        row2.addWidget(QLabel("Slave ID:"))
        self.rtu_cli_slave = QSpinBox()
        self.rtu_cli_slave.setRange(1, 247)
        self.rtu_cli_slave.setValue(1)
        row2.addWidget(self.rtu_cli_slave)
        cli_layout.addLayout(row2)

        btn_row = QHBoxLayout()
        self.btn_rtu_cli_connect = QPushButton("Connect")
        self.btn_rtu_cli_disconnect = QPushButton("Disconnect")
        self.btn_rtu_cli_disconnect.setEnabled(False)
        btn_row.addWidget(self.btn_rtu_cli_connect)
        btn_row.addWidget(self.btn_rtu_cli_disconnect)
        cli_layout.addLayout(btn_row)

        self.rtu_cli_status = QLabel("● Disconnected")
        self.rtu_cli_status.setStyleSheet("color: red; font-weight: bold;")
        cli_layout.addWidget(self.rtu_cli_status)

        # Read controls
        read_row = QHBoxLayout()
        read_row.addWidget(QLabel("Addr:"))
        self.rtu_read_addr = QSpinBox()
        self.rtu_read_addr.setRange(0, 9999)
        read_row.addWidget(self.rtu_read_addr)
        read_row.addWidget(QLabel("Count:"))
        self.rtu_read_count = QSpinBox()
        self.rtu_read_count.setRange(1, 125)
        self.rtu_read_count.setValue(10)
        read_row.addWidget(self.rtu_read_count)
        self.btn_rtu_read = QPushButton("Read")
        read_row.addWidget(self.btn_rtu_read)
        cli_layout.addLayout(read_row)

        # Write controls
        write_row = QHBoxLayout()
        write_row.addWidget(QLabel("Addr:"))
        self.rtu_write_addr = QSpinBox()
        self.rtu_write_addr.setRange(0, 9999)
        write_row.addWidget(self.rtu_write_addr)
        write_row.addWidget(QLabel("Value:"))
        self.rtu_write_value = QSpinBox()
        self.rtu_write_value.setRange(0, 65535)
        write_row.addWidget(self.rtu_write_value)
        self.btn_rtu_write = QPushButton("Write")
        write_row.addWidget(self.btn_rtu_write)
        cli_layout.addLayout(write_row)

        cli_layout.addWidget(QLabel("Client Registers:"))
        self.rtu_cli_table = QTableWidget(0, 2)
        self.rtu_cli_table.setHorizontalHeaderLabels(["Address", "Value"])
        self.rtu_cli_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rtu_cli_table.setEditTriggers(QTableWidget.NoEditTriggers)
        cli_layout.addWidget(self.rtu_cli_table)

        splitter.addWidget(cli_group)
        layout.addWidget(splitter)

        # Signals
        self.btn_rtu_srv_start.clicked.connect(self._rtu_start_server)
        self.btn_rtu_srv_stop.clicked.connect(self._rtu_stop_server)
        self.btn_rtu_cli_connect.clicked.connect(self._rtu_connect_client)
        self.btn_rtu_cli_disconnect.clicked.connect(self._rtu_disconnect_client)
        self.btn_rtu_read.clicked.connect(self._rtu_read)
        self.btn_rtu_write.clicked.connect(self._rtu_write)
        self.rtu_srv_table.cellChanged.connect(self._rtu_server_cell_changed)

        return tab

    # ========================================================= TCP Server
    def _tcp_start_server(self) -> None:
        self._tcp_server_worker = ModbusTCPServerWorker(self)
        self._tcp_server_worker.configure(
            self.tcp_srv_host.text(),
            self.tcp_srv_port.value(),
            self.tcp_srv_reg_count.value(),
        )
        self._tcp_server_worker.started.connect(self._on_tcp_srv_started)
        self._tcp_server_worker.stopped.connect(self._on_tcp_srv_stopped)
        self._tcp_server_worker.error.connect(lambda e: logger.error(e))
        self._tcp_server_worker.start()

    def _tcp_stop_server(self) -> None:
        if self._tcp_server_worker:
            self._tcp_server_worker.stop()
            self._tcp_server_worker = None

    @Slot()
    def _on_tcp_srv_started(self):
        self.tcp_srv_status.setText("● Running")
        self.tcp_srv_status.setStyleSheet("color: green; font-weight: bold;")
        self.btn_tcp_srv_start.setEnabled(False)
        self.btn_tcp_srv_stop.setEnabled(True)
        self._populate_server_table(self.tcp_srv_table, self.tcp_srv_reg_count.value())

    @Slot()
    def _on_tcp_srv_stopped(self):
        self.tcp_srv_status.setText("● Stopped")
        self.tcp_srv_status.setStyleSheet("color: red; font-weight: bold;")
        self.btn_tcp_srv_start.setEnabled(True)
        self.btn_tcp_srv_stop.setEnabled(False)

    def _tcp_server_cell_changed(self, row: int, col: int) -> None:
        if col != 1 or not self._tcp_server_worker:
            return
        try:
            addr = int(self.tcp_srv_table.item(row, 0).text())
            value = int(self.tcp_srv_table.item(row, 1).text())
            self._tcp_server_worker.server.set_register(addr, value)
        except (ValueError, AttributeError):
            pass

    # ========================================================= TCP Client
    def _tcp_connect_client(self) -> None:
        self._tcp_client_worker = ModbusTCPClientWorker(self)
        self._tcp_client_worker.connected.connect(self._on_tcp_cli_connected)
        self._tcp_client_worker.disconnected.connect(self._on_tcp_cli_disconnected)
        self._tcp_client_worker.registers_read.connect(self._on_tcp_registers_read)
        self._tcp_client_worker.register_written.connect(self._on_tcp_register_written)
        self._tcp_client_worker.error.connect(lambda e: logger.error(e))
        self._tcp_client_worker.connect_to_server(
            self.tcp_cli_host.text(), self.tcp_cli_port.value()
        )

    def _tcp_disconnect_client(self) -> None:
        if self._tcp_client_worker:
            self._tcp_client_worker.disconnect_from_server()
            self._tcp_client_worker = None
            self._on_tcp_cli_disconnected()

    @Slot()
    def _on_tcp_cli_connected(self):
        self.tcp_cli_status.setText("● Connected")
        self.tcp_cli_status.setStyleSheet("color: green; font-weight: bold;")
        self.btn_tcp_cli_connect.setEnabled(False)
        self.btn_tcp_cli_disconnect.setEnabled(True)

    @Slot()
    def _on_tcp_cli_disconnected(self):
        self.tcp_cli_status.setText("● Disconnected")
        self.tcp_cli_status.setStyleSheet("color: red; font-weight: bold;")
        self.btn_tcp_cli_connect.setEnabled(True)
        self.btn_tcp_cli_disconnect.setEnabled(False)

    def _tcp_read(self) -> None:
        if self._tcp_client_worker:
            self._tcp_client_worker.read_registers(
                self.tcp_read_addr.value(), self.tcp_read_count.value()
            )

    def _tcp_write(self) -> None:
        if self._tcp_client_worker:
            self._tcp_client_worker.write_register(
                self.tcp_write_addr.value(), self.tcp_write_value.value()
            )

    @Slot(list)
    def _on_tcp_registers_read(self, values: list):
        start = self.tcp_read_addr.value()
        self._fill_register_table(self.tcp_cli_table, start, values)

    @Slot(int, int)
    def _on_tcp_register_written(self, address: int, value: int):
        logger.info("TCP register %d written: %d", address, value)

    # ========================================================= RTU Server
    def _rtu_start_server(self) -> None:
        self._rtu_server_worker = ModbusRTUServerWorker(self)
        self._rtu_server_worker.configure(
            port=self.rtu_srv_port.currentText(),
            baudrate=int(self.rtu_srv_baud.currentText()),
            parity=self.rtu_srv_parity.currentText(),
            stopbits=int(self.rtu_srv_stopbits.currentText()),
            slave_id=self.rtu_srv_slave.value(),
            register_count=self.rtu_srv_reg_count.value(),
        )
        self._rtu_server_worker.started.connect(self._on_rtu_srv_started)
        self._rtu_server_worker.stopped.connect(self._on_rtu_srv_stopped)
        self._rtu_server_worker.error.connect(lambda e: logger.error(e))
        self._rtu_server_worker.start()

    def _rtu_stop_server(self) -> None:
        if self._rtu_server_worker:
            self._rtu_server_worker.stop()
            self._rtu_server_worker = None

    @Slot()
    def _on_rtu_srv_started(self):
        self.rtu_srv_status.setText("● Running")
        self.rtu_srv_status.setStyleSheet("color: green; font-weight: bold;")
        self.btn_rtu_srv_start.setEnabled(False)
        self.btn_rtu_srv_stop.setEnabled(True)
        self._populate_server_table(self.rtu_srv_table, self.rtu_srv_reg_count.value())

    @Slot()
    def _on_rtu_srv_stopped(self):
        self.rtu_srv_status.setText("● Stopped")
        self.rtu_srv_status.setStyleSheet("color: red; font-weight: bold;")
        self.btn_rtu_srv_start.setEnabled(True)
        self.btn_rtu_srv_stop.setEnabled(False)

    def _rtu_server_cell_changed(self, row: int, col: int) -> None:
        if col != 1 or not self._rtu_server_worker:
            return
        try:
            addr = int(self.rtu_srv_table.item(row, 0).text())
            value = int(self.rtu_srv_table.item(row, 1).text())
            slave = self.rtu_srv_slave.value()
            self._rtu_server_worker.server.set_register(addr, value, slave)
        except (ValueError, AttributeError):
            pass

    # ========================================================= RTU Client
    def _rtu_connect_client(self) -> None:
        self._rtu_client_worker = ModbusRTUClientWorker(self)
        self._rtu_client_worker.connected.connect(self._on_rtu_cli_connected)
        self._rtu_client_worker.disconnected.connect(self._on_rtu_cli_disconnected)
        self._rtu_client_worker.registers_read.connect(self._on_rtu_registers_read)
        self._rtu_client_worker.register_written.connect(self._on_rtu_register_written)
        self._rtu_client_worker.error.connect(lambda e: logger.error(e))
        self._rtu_client_worker.connect_to_server(
            port=self.rtu_cli_port.currentText(),
            baudrate=int(self.rtu_cli_baud.currentText()),
            parity=self.rtu_cli_parity.currentText(),
            stopbits=int(self.rtu_cli_stopbits.currentText()),
        )

    def _rtu_disconnect_client(self) -> None:
        if self._rtu_client_worker:
            self._rtu_client_worker.disconnect_from_server()
            self._rtu_client_worker = None
            self._on_rtu_cli_disconnected()

    @Slot()
    def _on_rtu_cli_connected(self):
        self.rtu_cli_status.setText("● Connected")
        self.rtu_cli_status.setStyleSheet("color: green; font-weight: bold;")
        self.btn_rtu_cli_connect.setEnabled(False)
        self.btn_rtu_cli_disconnect.setEnabled(True)

    @Slot()
    def _on_rtu_cli_disconnected(self):
        self.rtu_cli_status.setText("● Disconnected")
        self.rtu_cli_status.setStyleSheet("color: red; font-weight: bold;")
        self.btn_rtu_cli_connect.setEnabled(True)
        self.btn_rtu_cli_disconnect.setEnabled(False)

    def _rtu_read(self) -> None:
        if self._rtu_client_worker:
            self._rtu_client_worker.read_registers(
                self.rtu_read_addr.value(),
                self.rtu_read_count.value(),
                slave=self.rtu_cli_slave.value(),
            )

    def _rtu_write(self) -> None:
        if self._rtu_client_worker:
            self._rtu_client_worker.write_register(
                self.rtu_write_addr.value(),
                self.rtu_write_value.value(),
                slave=self.rtu_cli_slave.value(),
            )

    @Slot(list)
    def _on_rtu_registers_read(self, values: list):
        start = self.rtu_read_addr.value()
        self._fill_register_table(self.rtu_cli_table, start, values)

    @Slot(int, int)
    def _on_rtu_register_written(self, address: int, value: int):
        logger.info("RTU register %d written: %d", address, value)

    # ========================================================= Helpers
    @staticmethod
    def _populate_server_table(table: QTableWidget, count: int) -> None:
        table.blockSignals(True)
        table.setRowCount(count)
        for i in range(count):
            addr_item = QTableWidgetItem(str(i))
            addr_item.setFlags(addr_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(i, 0, addr_item)
            table.setItem(i, 1, QTableWidgetItem("0"))
        table.blockSignals(False)

    @staticmethod
    def _fill_register_table(
        table: QTableWidget, start_addr: int, values: list
    ) -> None:
        table.setRowCount(len(values))
        for i, val in enumerate(values):
            table.setItem(i, 0, QTableWidgetItem(str(start_addr + i)))
            table.setItem(i, 1, QTableWidgetItem(str(val)))

    def _refresh_server_tables(self) -> None:
        """Refresh server register tables so remote writes are visible."""
        if self._tcp_server_worker and self._tcp_server_worker.server.is_running:
            count = self.tcp_srv_table.rowCount()
            values = self._tcp_server_worker.server.get_registers(0, count)
            if isinstance(values, list):
                self.tcp_srv_table.blockSignals(True)
                for i, val in enumerate(values):
                    item = self.tcp_srv_table.item(i, 1)
                    if item and str(val) != item.text():
                        item.setText(str(val))
                self.tcp_srv_table.blockSignals(False)

    def shutdown(self) -> None:
        self._refresh_timer.stop()
        self._tcp_stop_server()
        if self._tcp_client_worker:
            self._tcp_client_worker.disconnect_from_server()
            self._tcp_client_worker = None
        self._rtu_stop_server()
        if self._rtu_client_worker:
            self._rtu_client_worker.disconnect_from_server()
            self._rtu_client_worker = None
