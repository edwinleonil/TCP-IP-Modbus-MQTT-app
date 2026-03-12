"""Modbus RTU (serial) Server using pymodbus."""

import logging
import threading

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusDeviceContext,
    ModbusServerContext,
)
from pymodbus.server import StartSerialServer, ServerStop

logger = logging.getLogger("comm_app.modbus.rtu_server")


class ModbusRTUServer:
    """Modbus RTU server over a serial port with configurable holding registers."""

    def __init__(self):
        self._context: ModbusServerContext | None = None
        self._slave_context: ModbusDeviceContext | None = None
        self._thread: threading.Thread | None = None
        self._running = False

        # Callbacks
        self.on_started: callable = None
        self.on_stopped: callable = None
        self.on_error: callable = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start_server(
        self,
        port: str = "COM1",
        baudrate: int = 9600,
        parity: str = "N",
        stopbits: int = 1,
        slave_id: int = 1,
        register_count: int = 100,
    ) -> None:
        if self._running:
            return
        block = ModbusSequentialDataBlock(0, [0] * register_count)
        self._slave_context = ModbusDeviceContext(
            di=block, co=block, hr=block, ir=block, zero_mode=True
        )
        self._context = ModbusServerContext(
            slaves={slave_id: self._slave_context}, single=False
        )
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            kwargs={
                "port": port,
                "baudrate": baudrate,
                "parity": parity,
                "stopbits": stopbits,
            },
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Modbus RTU server starting on %s (baud=%d, parity=%s, stop=%d)",
            port, baudrate, parity, stopbits,
        )
        if self.on_started:
            self.on_started()

    def _run(self, port: str, baudrate: int, parity: str, stopbits: int) -> None:
        try:
            StartSerialServer(
                context=self._context,
                port=port,
                baudrate=baudrate,
                parity=parity,
                stopbits=stopbits,
                bytesize=8,
            )
        except Exception as e:
            logger.error("Modbus RTU server error: %s", e)
            if self.on_error:
                self.on_error(str(e))
        finally:
            self._running = False

    def set_register(self, address: int, value: int, slave_id: int = 1) -> None:
        if self._context:
            ctx = self._context[slave_id]
            ctx.setValues(3, address, [value])

    def get_register(self, address: int, slave_id: int = 1) -> int | None:
        if self._context:
            ctx = self._context[slave_id]
            values = ctx.getValues(3, address, count=1)
            return values[0] if values else None
        return None

    def get_registers(self, address: int, count: int, slave_id: int = 1) -> list[int]:
        if self._context:
            ctx = self._context[slave_id]
            return ctx.getValues(3, address, count=count)
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
        logger.info("Modbus RTU server stopped")
        if self.on_stopped:
            self.on_stopped()
