"""Application configuration with JSON persistence."""

import json
import os
from dataclasses import dataclass, field, asdict


@dataclass
class TCPServerConfig:
    host: str = "0.0.0.0"
    port: int = 5000


@dataclass
class TCPClientConfig:
    host: str = "127.0.0.1"
    port: int = 5000


@dataclass
class MQTTConfig:
    broker: str = "localhost"
    port: int = 1883
    client_id: str = "comm_app_client"


@dataclass
class ModbusTCPServerConfig:
    host: str = "0.0.0.0"
    port: int = 5020
    register_count: int = 100


@dataclass
class ModbusTCPClientConfig:
    host: str = "127.0.0.1"
    port: int = 5020


@dataclass
class ModbusRTUServerConfig:
    port: str = "COM1"
    baudrate: int = 9600
    parity: str = "N"
    stopbits: int = 1
    slave_id: int = 1
    register_count: int = 100


@dataclass
class ModbusRTUClientConfig:
    port: str = "COM1"
    baudrate: int = 9600
    parity: str = "N"
    stopbits: int = 1
    slave_id: int = 1


@dataclass
class MQTTBrokerConfig:
    enabled: bool = False
    port: int = 1883
    config_path: str = "config/mosquitto.conf"


@dataclass
class AppConfig:
    theme: str = "light"
    tcp_server: TCPServerConfig = field(default_factory=TCPServerConfig)
    tcp_client: TCPClientConfig = field(default_factory=TCPClientConfig)
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    modbus_tcp_server: ModbusTCPServerConfig = field(default_factory=ModbusTCPServerConfig)
    modbus_tcp_client: ModbusTCPClientConfig = field(default_factory=ModbusTCPClientConfig)
    modbus_rtu_server: ModbusRTUServerConfig = field(default_factory=ModbusRTUServerConfig)
    modbus_rtu_client: ModbusRTUClientConfig = field(default_factory=ModbusRTUClientConfig)
    mqtt_broker: MQTTBrokerConfig = field(default_factory=MQTTBrokerConfig)


_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config.json")


def _nested_from_dict(cls, data: dict):
    """Recursively build a dataclass from a dict."""
    field_types = {f.name: f.type for f in cls.__dataclass_fields__.values()}
    kwargs = {}
    for key, value in data.items():
        if key in field_types and isinstance(value, dict):
            # Resolve the type from the annotation string
            sub_cls = globals().get(field_types[key])
            if sub_cls is not None:
                kwargs[key] = _nested_from_dict(sub_cls, value)
            else:
                kwargs[key] = value
        else:
            kwargs[key] = value
    return cls(**kwargs)


def load_config(path: str | None = None) -> AppConfig:
    """Load configuration from JSON file or return defaults."""
    path = path or _CONFIG_FILE
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _nested_from_dict(AppConfig, data)
    return AppConfig()


def save_config(config: AppConfig, path: str | None = None) -> None:
    """Persist configuration to JSON file."""
    path = path or _CONFIG_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2)
