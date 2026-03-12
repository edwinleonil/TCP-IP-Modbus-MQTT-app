"""Tests for application configuration load/save."""

import json
import os
import tempfile

from communication_app.core.config import AppConfig, load_config, save_config


def test_default_config():
    cfg = AppConfig()
    assert cfg.theme == "light"
    assert cfg.tcp_server.port == 5000
    assert cfg.mqtt.broker == "localhost"
    assert cfg.modbus_rtu_server.baudrate == 9600


def test_save_and_load(tmp_path):
    path = os.path.join(str(tmp_path), "config.json")
    cfg = AppConfig()
    cfg.theme = "dark"
    cfg.tcp_server.port = 9999
    save_config(cfg, path)

    loaded = load_config(path)
    assert loaded.theme == "dark"
    assert loaded.tcp_server.port == 9999


def test_load_missing_file_returns_defaults():
    cfg = load_config("/nonexistent/config.json")
    assert cfg.theme == "light"
