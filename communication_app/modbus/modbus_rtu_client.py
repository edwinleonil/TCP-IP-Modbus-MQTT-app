"""Modbus RTU (serial) Client using pymodbus."""

import logging

from pymodbus.client import ModbusSerialClient

logger = logging.getLogger("comm_app.modbus.rtu_client")


class ModbusRTUClient:
    """Modbus RTU client for reading/writing holding registers over serial."""

    def __init__(self):
        self._client: ModbusSerialClient | None = None
        self._connected = False

        # Callbacks
        self.on_connected: callable = None
        self.on_disconnected: callable = None
        self.on_error: callable = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(
        self,
        port: str = "COM1",
        baudrate: int = 9600,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 3.0,
    ) -> None:
        if self._connected:
            return
        self._client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            stopbits=stopbits,
            bytesize=8,
            timeout=timeout,
        )
        if self._client.connect():
            self._connected = True
            logger.info(
                "Modbus RTU client connected to %s (baud=%d)", port, baudrate
            )
            if self.on_connected:
                self.on_connected()
        else:
            logger.error("Modbus RTU connect failed on %s", port)
            if self.on_error:
                self.on_error(f"Modbus RTU connect failed on {port}")
            self._client = None

    def read_holding_registers(
        self, address: int, count: int = 1, slave: int = 1
    ) -> list[int] | None:
        if not self._connected or not self._client:
            return None
        try:
            result = self._client.read_holding_registers(
                address, count=count, device_id=slave
            )
            if result.isError():
                logger.error("Modbus RTU read error: %s", result)
                if self.on_error:
                    self.on_error(f"Modbus RTU read error: {result}")
                return None
            return list(result.registers)
        except Exception as e:
            logger.error("Modbus RTU read exception: %s", e)
            if self.on_error:
                self.on_error(str(e))
            return None

    def write_register(
        self, address: int, value: int, slave: int = 1
    ) -> bool:
        if not self._connected or not self._client:
            return False
        try:
            result = self._client.write_register(address, value, device_id=slave)
            if result.isError():
                logger.error("Modbus RTU write error: %s", result)
                if self.on_error:
                    self.on_error(f"Modbus RTU write error: {result}")
                return False
            return True
        except Exception as e:
            logger.error("Modbus RTU write exception: %s", e)
            if self.on_error:
                self.on_error(str(e))
            return False

    def disconnect(self) -> None:
        if not self._client:
            return
        self._connected = False
        self._client.close()
        self._client = None
        logger.info("Modbus RTU client disconnected")
        if self.on_disconnected:
            self.on_disconnected()
