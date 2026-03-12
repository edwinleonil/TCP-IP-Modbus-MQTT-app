# TCP-IP-Modbus-MQTT-app

A cross-platform **PySide6 desktop application** for managing and monitoring industrial communication protocols: **TCP/IP**, **MQTT**, and **Modbus** (TCP + RTU).

## Features

- **TCP/IP** – multi-client server and client with live message exchange
- **MQTT** – broker connection, topic subscribe/publish, real-time message viewer
- **Modbus TCP** – server with editable holding registers, client with read/write controls
- **Modbus RTU** – serial (RS-485) server and client with auto-detected COM ports
- **Dark / Light theme** toggle (persisted in config)
- System-wide log panel + file logging (`app.log`)
- Threaded workers with Qt signals for responsive UI

## Architecture

```
┌─────────────────────────────────────────────┐
│                  UI Layer                    │
│  MainWindow ─ TCPPanel ─ MQTTPanel ─ Modbus │
├─────────────────────────────────────────────┤
│             Threading Layer                  │
│  QThread workers  ←  Qt Signals/Slots       │
├─────────────────────────────────────────────┤
│           Communication Layer                │
│  TCPServer/Client  MQTT  ModbusTCP  RTU     │
├─────────────────────────────────────────────┤
│               Core Layer                     │
│  Config (JSON)  Logger  MessageFormat        │
└─────────────────────────────────────────────┘
```

## Project Structure

```
communication_app/
├── main.py                     # Entry point
├── core/
│   ├── config.py               # JSON-based configuration
│   ├── logger.py               # Central logging + Qt signal handler
│   └── message_format.py       # CommMessage dataclass
├── ui/
│   ├── main_window.py          # QMainWindow with tabs + log dock
│   ├── tcp_panel.py            # TCP server/client UI
│   ├── mqtt_panel.py           # MQTT UI
│   └── modbus_panel.py         # Modbus TCP + RTU UI
├── tcp/
│   ├── tcp_server.py           # Socket-based TCP server
│   └── tcp_client.py           # Socket-based TCP client
├── mqtt/
│   └── mqtt_client.py          # paho-mqtt wrapper
├── modbus/
│   ├── modbus_server.py        # Modbus TCP server (pymodbus)
│   ├── modbus_client.py        # Modbus TCP client (pymodbus)
│   ├── modbus_rtu_server.py    # Modbus RTU server (serial)
│   └── modbus_rtu_client.py    # Modbus RTU client (serial)
├── threads/
│   └── worker_threads.py       # QThread workers for all protocols
└── resources/
    └── dark_theme.qss          # Dark mode stylesheet
tests/
├── test_config.py
├── test_message_format.py
├── test_tcp.py
├── test_mqtt.py
└── test_modbus.py
```

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```bash
uv sync
```

To include dev dependencies (pytest):

```bash
uv sync --extra dev
```

### Dependencies

- PySide6
- paho-mqtt
- pymodbus
- pyserial

## Usage

```bash
uv run communication-app
```

Or directly:

```bash
uv run python communication_app/main.py
```

The main window opens with three tabs (TCP/IP, MQTT, Modbus) and a system log dock at the bottom.

## Running Tests

```bash
uv run pytest tests/
```

> **Note:** MQTT tests require a broker on `localhost:1883` (e.g. Mosquitto). They are auto-skipped if no broker is found.

## Platform Support

- Windows
- Linux
- Raspberry Pi OS
