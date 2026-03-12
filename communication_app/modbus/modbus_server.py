"""Modbus TCP Server using pymodbus."""

import logging
import threading

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusDeviceContext,
    ModbusServerContext,
)
from pymodbus.server import StartTcpServer, ServerStop

logger = logging.getLogger("comm_app.modbus.tcp_server")


class ModbusTCPServer:
    """Modbus TCP server with configurable holding registers."""

    def __init__(self):
        self._context: ModbusServerContext | None = None
        self._slave_context: ModbusDeviceContext | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._host = ""
        self._port = 0

        # Callbacks
        self.on_started: callable = None
        self.on_stopped: callable = None
        self.on_error: callable = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start_server(
        self, host: str = "0.0.0.0", port: int = 5020, register_count: int = 100
    ) -> None:
        if self._running:
            return
        # Build data store – holding registers initialised to 0
        block = ModbusSequentialDataBlock(0, [0] * register_count)
        self._slave_context = ModbusDeviceContext(
            di=block, co=block, hr=block, ir=block, zero_mode=True
        )
        self._context = ModbusServerContext(
            slaves=self._slave_context, single=True
        )
        self._host = host
        self._port = port
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Modbus TCP server starting on %s:%d", host, port)
        if self.on_started:
            self.on_started()

    def _run(self) -> None:
        try:
            StartTcpServer(
                context=self._context,
                address=(self._host, self._port),
            )
        except Exception as e:
            logger.error("Modbus TCP server error: %s", e)
            if self.on_error:
                self.on_error(str(e))
        finally:
            self._running = False

    def set_register(self, address: int, value: int) -> None:
        if self._slave_context:
            self._slave_context.setValues(3, address, [value])  # 3 = holding register

    def get_register(self, address: int) -> int | None:
        if self._slave_context:
            values = self._slave_context.getValues(3, address, count=1)
            return values[0] if values else None
        return None

    def get_registers(self, address: int, count: int) -> list[int]:
        if self._slave_context:
            return self._slave_context.getValues(3, address, count=count)
        return []

    def stop_server(self) -> None:
        if not self._running:
            return
        self._running = False
        try:
            ServerStop()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self._context = None
        self._slave_context = None
        logger.info("Modbus TCP server stopped")
        if self.on_stopped:
            self.on_stopped()
