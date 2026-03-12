"""Modbus TCP Client using pymodbus."""

import logging

from pymodbus.client import ModbusTcpClient

logger = logging.getLogger("comm_app.modbus.tcp_client")


class ModbusTCPClient:
    """Modbus TCP client for reading/writing holding registers."""

    def __init__(self):
        self._client: ModbusTcpClient | None = None
        self._connected = False

        # Callbacks
        self.on_connected: callable = None
        self.on_disconnected: callable = None
        self.on_error: callable = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self, host: str, port: int = 5020, timeout: float = 5.0) -> None:
        if self._connected:
            return
        self._client = ModbusTcpClient(host, port=port, timeout=timeout)
        if self._client.connect():
            self._connected = True
            logger.info("Modbus TCP client connected to %s:%d", host, port)
            if self.on_connected:
                self.on_connected()
        else:
            logger.error("Modbus TCP connect failed to %s:%d", host, port)
            if self.on_error:
                self.on_error(f"Modbus TCP connect failed to {host}:{port}")
            self._client = None

    def read_holding_registers(
        self, address: int, count: int = 1, slave: int = 1
    ) -> list[int] | None:
        if not self._connected or not self._client:
            return None
        try:
            result = self._client.read_holding_registers(
                address, count=count, slave=slave
            )
            if result.isError():
                logger.error("Modbus read error: %s", result)
                if self.on_error:
                    self.on_error(f"Modbus read error: {result}")
                return None
            return list(result.registers)
        except Exception as e:
            logger.error("Modbus read exception: %s", e)
            if self.on_error:
                self.on_error(str(e))
            return None

    def write_register(
        self, address: int, value: int, slave: int = 1
    ) -> bool:
        if not self._connected or not self._client:
            return False
        try:
            result = self._client.write_register(address, value, slave=slave)
            if result.isError():
                logger.error("Modbus write error: %s", result)
                if self.on_error:
                    self.on_error(f"Modbus write error: {result}")
                return False
            return True
        except Exception as e:
            logger.error("Modbus write exception: %s", e)
            if self.on_error:
                self.on_error(str(e))
            return False

    def disconnect(self) -> None:
        if not self._client:
            return
        self._connected = False
        self._client.close()
        self._client = None
        logger.info("Modbus TCP client disconnected")
        if self.on_disconnected:
            self.on_disconnected()
