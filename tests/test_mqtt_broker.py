"""Tests for MQTT broker manager."""

import os
import unittest
from unittest.mock import patch, MagicMock

from communication_app.mqtt.mqtt_broker_manager import (
    MQTTBrokerManager,
    BrokerStatus,
    find_mosquitto,
    install_guidance,
)


class TestFindMosquitto(unittest.TestCase):
    @patch("shutil.which", return_value="/usr/sbin/mosquitto")
    def test_found_on_path(self, mock_which):
        assert find_mosquitto() == "/usr/sbin/mosquitto"

    @patch("shutil.which", return_value=None)
    @patch("os.path.isfile", return_value=False)
    def test_not_found(self, mock_isfile, mock_which):
        assert find_mosquitto() is None


class TestInstallGuidance(unittest.TestCase):
    @patch("os.name", "nt")
    def test_windows_guidance(self):
        text = install_guidance()
        assert "winget" in text or "Download" in text

    @patch("os.name", "posix")
    def test_linux_guidance(self):
        text = install_guidance()
        assert "apt" in text


class TestBrokerManagerStatus(unittest.TestCase):
    def test_initial_status(self):
        mgr = MQTTBrokerManager()
        assert mgr.status == BrokerStatus.STOPPED
        assert mgr.is_running is False

    def test_set_executable(self):
        mgr = MQTTBrokerManager()
        mgr.executable_path = "/custom/path"
        assert mgr.executable_path == "/custom/path"

    @patch(
        "communication_app.mqtt.mqtt_broker_manager.find_mosquitto",
        return_value=None,
    )
    def test_start_without_exe_errors(self, _):
        mgr = MQTTBrokerManager()
        mgr._exe_path = None
        errors = []
        mgr.on_error = lambda e: errors.append(e)
        mgr.start()
        assert mgr.status == BrokerStatus.ERROR
        assert len(errors) == 1

    def test_stop_when_not_running(self):
        mgr = MQTTBrokerManager()
        mgr.stop()  # should not raise
        assert mgr.status == BrokerStatus.STOPPED


class TestBrokerStatusEnum(unittest.TestCase):
    def test_values(self):
        assert BrokerStatus.STOPPED.value == "Stopped"
        assert BrokerStatus.RUNNING.value == "Running"
        assert BrokerStatus.STARTING.value == "Starting"
        assert BrokerStatus.ERROR.value == "Error"


if __name__ == "__main__":
    unittest.main()
