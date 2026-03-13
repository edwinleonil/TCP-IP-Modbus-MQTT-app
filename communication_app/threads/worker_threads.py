"""QThread-based worker classes that bridge protocol modules to the Qt event loop."""

import logging

from PySide6.QtCore import QObject, QThread, QRunnable, QThreadPool, Signal, Slot

from communication_app.tcp.tcp_server import TCPServer
from communication_app.tcp.tcp_client import TCPClient
from communication_app.mqtt.mqtt_client import MQTTClientWrapper
from communication_app.mqtt.mqtt_broker_manager import MQTTBrokerManager, BrokerStatus
from communication_app.modbus.modbus_server import ModbusTCPServer
from communication_app.modbus.modbus_client import ModbusTCPClient
from communication_app.modbus.modbus_rtu_server import ModbusRTUServer
from communication_app.modbus.modbus_rtu_client import ModbusRTUClient

logger = logging.getLogger("comm_app.workers")


# ---------------------------------------------------------------------------
# TCP Server Worker
# ---------------------------------------------------------------------------
class TCPServerWorker(QThread):
    client_connected = Signal(str)
    client_disconnected = Signal(str)
    message_received = Signal(str, str)  # client_id, message
    error = Signal(str)
    server_started = Signal()
    server_stopped = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._server = TCPServer()
        self._host = "0.0.0.0"
        self._port = 5000

    @property
    def server(self) -> TCPServer:
        return self._server

    def configure(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    def run(self) -> None:
        self._server.on_client_connected = lambda cid: self.client_connected.emit(cid)
        self._server.on_client_disconnected = lambda cid: self.client_disconnected.emit(cid)
        self._server.on_message_received = lambda cid, msg: self.message_received.emit(cid, msg)
        self._server.on_error = lambda e: self.error.emit(e)
        try:
            self._server.start_server(self._host, self._port)
            self.server_started.emit()
            # Keep thread alive while server runs
            while self._server.is_running:
                self.msleep(200)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.server_stopped.emit()

    def stop(self) -> None:
        self._server.stop_server()
        self.quit()
        self.wait(3000)


# ---------------------------------------------------------------------------
# TCP Client Worker
# ---------------------------------------------------------------------------
class TCPClientWorker(QThread):
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(str)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._client = TCPClient()
        self._host = "127.0.0.1"
        self._port = 5000

    @property
    def client(self) -> TCPClient:
        return self._client

    def configure(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    def run(self) -> None:
        self._client.on_connected = lambda: self.connected.emit()
        self._client.on_disconnected = lambda: self.disconnected.emit()
        self._client.on_message_received = lambda msg: self.message_received.emit(msg)
        self._client.on_error = lambda e: self.error.emit(e)
        try:
            self._client.connect(self._host, self._port)
            while self._client.is_connected:
                self.msleep(200)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self) -> None:
        self._client.disconnect()
        self.quit()
        self.wait(3000)


# ---------------------------------------------------------------------------
# MQTT Client Worker
# ---------------------------------------------------------------------------
class MQTTClientWorker(QThread):
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(str, str)  # topic, payload
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._client = MQTTClientWrapper()
        self._broker = "localhost"
        self._port = 1883
        self._client_id = ""
        self._username = ""
        self._password = ""
        self._running = False

    @property
    def client(self) -> MQTTClientWrapper:
        return self._client

    def configure(self, broker: str, port: int, client_id: str,
                  username: str = "", password: str = "") -> None:
        self._broker = broker
        self._port = port
        self._client_id = client_id
        self._username = username
        self._password = password

    def run(self) -> None:
        self._running = True
        self._client.on_connected = lambda: self.connected.emit()
        self._client.on_disconnected = lambda: self.disconnected.emit()
        self._client.on_message_received = lambda t, p: self.message_received.emit(t, p)
        self._client.on_error = lambda e: self.error.emit(e)
        try:
            self._client.connect(self._broker, self._port, self._client_id,
                                self._username, self._password)
            # Wait for initial connection (up to 10 s)
            attempts = 50
            while self._running and not self._client.is_connected and attempts > 0:
                self.msleep(200)
                attempts -= 1
            # Keep thread alive while running
            while self._running:
                self.msleep(200)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self) -> None:
        self._running = False
        self._client.disconnect()
        self.quit()
        self.wait(3000)


# ---------------------------------------------------------------------------
# Modbus TCP Server Worker
# ---------------------------------------------------------------------------
class ModbusTCPServerWorker(QThread):
    started = Signal()
    stopped = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._server = ModbusTCPServer()
        self._host = "0.0.0.0"
        self._port = 5020
        self._register_count = 100

    @property
    def server(self) -> ModbusTCPServer:
        return self._server

    def configure(self, host: str, port: int, register_count: int) -> None:
        self._host = host
        self._port = port
        self._register_count = register_count

    def run(self) -> None:
        self._server.on_started = lambda: self.started.emit()
        self._server.on_stopped = lambda: self.stopped.emit()
        self._server.on_error = lambda e: self.error.emit(e)
        try:
            self._server.start_server(self._host, self._port, self._register_count)
            while self._server.is_running:
                self.msleep(200)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.stopped.emit()

    def stop(self) -> None:
        self._server.stop_server()
        self.quit()
        self.wait(5000)


# ---------------------------------------------------------------------------
# Modbus TCP Client Worker (uses QThreadPool for short operations)
# ---------------------------------------------------------------------------
class _ModbusTCPReadTask(QRunnable):
    def __init__(self, client: ModbusTCPClient, address: int, count: int, slave: int, callback):
        super().__init__()
        self._client = client
        self._address = address
        self._count = count
        self._slave = slave
        self._callback = callback

    def run(self):
        result = self._client.read_holding_registers(self._address, self._count, self._slave)
        self._callback(result)


class _ModbusTCPWriteTask(QRunnable):
    def __init__(self, client: ModbusTCPClient, address: int, value: int, slave: int, callback):
        super().__init__()
        self._client = client
        self._address = address
        self._value = value
        self._slave = slave
        self._callback = callback

    def run(self):
        ok = self._client.write_register(self._address, self._value, self._slave)
        self._callback(self._address, self._value, ok)


class ModbusTCPClientWorker(QObject):
    registers_read = Signal(list)
    register_written = Signal(int, int)  # address, value
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._client = ModbusTCPClient()
        self._client.on_connected = lambda: self.connected.emit()
        self._client.on_disconnected = lambda: self.disconnected.emit()
        self._client.on_error = lambda e: self.error.emit(e)

    @property
    def client(self) -> ModbusTCPClient:
        return self._client

    def connect_to_server(self, host: str, port: int) -> None:
        self._client.connect(host, port)

    def disconnect_from_server(self) -> None:
        self._client.disconnect()

    def read_registers(self, address: int, count: int, slave: int = 1) -> None:
        task = _ModbusTCPReadTask(self._client, address, count, slave, self._on_read_done)
        QThreadPool.globalInstance().start(task)

    def _on_read_done(self, result):
        if result is not None:
            self.registers_read.emit(result)

    def write_register(self, address: int, value: int, slave: int = 1) -> None:
        task = _ModbusTCPWriteTask(self._client, address, value, slave, self._on_write_done)
        QThreadPool.globalInstance().start(task)

    def _on_write_done(self, address, value, ok):
        if ok:
            self.register_written.emit(address, value)


# ---------------------------------------------------------------------------
# Modbus RTU Server Worker
# ---------------------------------------------------------------------------
class ModbusRTUServerWorker(QThread):
    started = Signal()
    stopped = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._server = ModbusRTUServer()
        self._port = "COM1"
        self._baudrate = 9600
        self._parity = "N"
        self._stopbits = 1
        self._slave_id = 1
        self._register_count = 100

    @property
    def server(self) -> ModbusRTUServer:
        return self._server

    def configure(
        self,
        port: str,
        baudrate: int,
        parity: str,
        stopbits: int,
        slave_id: int,
        register_count: int,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._parity = parity
        self._stopbits = stopbits
        self._slave_id = slave_id
        self._register_count = register_count

    def run(self) -> None:
        self._server.on_started = lambda: self.started.emit()
        self._server.on_stopped = lambda: self.stopped.emit()
        self._server.on_error = lambda e: self.error.emit(e)
        try:
            self._server.start_server(
                port=self._port,
                baudrate=self._baudrate,
                parity=self._parity,
                stopbits=self._stopbits,
                slave_id=self._slave_id,
                register_count=self._register_count,
            )
            while self._server.is_running:
                self.msleep(200)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.stopped.emit()

    def stop(self) -> None:
        self._server.stop_server()
        self.quit()
        self.wait(5000)


# ---------------------------------------------------------------------------
# Modbus RTU Client Worker (uses QThreadPool for short operations)
# ---------------------------------------------------------------------------
class _ModbusRTUReadTask(QRunnable):
    def __init__(self, client: ModbusRTUClient, address: int, count: int, slave: int, callback):
        super().__init__()
        self._client = client
        self._address = address
        self._count = count
        self._slave = slave
        self._callback = callback

    def run(self):
        result = self._client.read_holding_registers(self._address, self._count, self._slave)
        self._callback(result)


class _ModbusRTUWriteTask(QRunnable):
    def __init__(self, client: ModbusRTUClient, address: int, value: int, slave: int, callback):
        super().__init__()
        self._client = client
        self._address = address
        self._value = value
        self._slave = slave
        self._callback = callback

    def run(self):
        ok = self._client.write_register(self._address, self._value, self._slave)
        self._callback(self._address, self._value, ok)


class ModbusRTUClientWorker(QObject):
    registers_read = Signal(list)
    register_written = Signal(int, int)
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._client = ModbusRTUClient()
        self._client.on_connected = lambda: self.connected.emit()
        self._client.on_disconnected = lambda: self.disconnected.emit()
        self._client.on_error = lambda e: self.error.emit(e)

    @property
    def client(self) -> ModbusRTUClient:
        return self._client

    def connect_to_server(
        self, port: str, baudrate: int, parity: str, stopbits: int
    ) -> None:
        self._client.connect(port, baudrate, parity, stopbits)

    def disconnect_from_server(self) -> None:
        self._client.disconnect()

    def read_registers(self, address: int, count: int, slave: int = 1) -> None:
        task = _ModbusRTUReadTask(self._client, address, count, slave, self._on_read_done)
        QThreadPool.globalInstance().start(task)

    def _on_read_done(self, result):
        if result is not None:
            self.registers_read.emit(result)

    def write_register(self, address: int, value: int, slave: int = 1) -> None:
        task = _ModbusRTUWriteTask(self._client, address, value, slave, self._on_write_done)
        QThreadPool.globalInstance().start(task)

    def _on_write_done(self, address, value, ok):
        if ok:
            self.register_written.emit(address, value)


# ---------------------------------------------------------------------------
# MQTT Broker Worker
# ---------------------------------------------------------------------------
class MQTTBrokerWorker(QThread):
    broker_started = Signal()
    broker_stopped = Signal()
    broker_error = Signal(str)
    broker_status_changed = Signal(str)  # BrokerStatus.value
    broker_log_message = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._manager = MQTTBrokerManager()
        self._port = 1883
        self._config_path: str | None = None

    @property
    def manager(self) -> MQTTBrokerManager:
        return self._manager

    def configure(self, port: int, config_path: str | None = None,
                  exe_path: str | None = None) -> None:
        self._port = port
        self._config_path = config_path
        if exe_path:
            self._manager.executable_path = exe_path

    def run(self) -> None:
        self._manager.on_status_changed = self._on_status
        self._manager.on_log_message = lambda msg: self.broker_log_message.emit(msg)
        self._manager.on_error = lambda err: self.broker_error.emit(err)
        self._manager.start(self._port, self._config_path)
        # Keep thread alive while broker runs
        while self._manager.is_running:
            self.msleep(300)

    def _on_status(self, status: BrokerStatus) -> None:
        self.broker_status_changed.emit(status.value)
        if status == BrokerStatus.RUNNING:
            self.broker_started.emit()
        elif status == BrokerStatus.STOPPED:
            self.broker_stopped.emit()

    def stop(self) -> None:
        self._manager.stop()
        self.quit()
        self.wait(5000)
