"""Manage an Eclipse Mosquitto broker as a subprocess."""

import enum
import logging
import os
import shutil
import subprocess
import threading

logger = logging.getLogger("comm_app.mqtt.broker")

_COMMON_WIN_PATHS = [
    r"C:\Program Files\mosquitto\mosquitto.exe",
    r"C:\Program Files (x86)\mosquitto\mosquitto.exe",
]

_COMMON_UNIX_PATHS = [
    "/usr/sbin/mosquitto",
    "/usr/local/sbin/mosquitto",
    "/usr/bin/mosquitto",
    "/usr/local/bin/mosquitto",
    "/opt/homebrew/sbin/mosquitto",
]


class BrokerStatus(enum.Enum):
    STOPPED = "Stopped"
    STARTING = "Starting"
    RUNNING = "Running"
    ERROR = "Error"


def find_mosquitto() -> str | None:
    """Auto-detect the Mosquitto executable on the system."""
    path = shutil.which("mosquitto")
    if path:
        return path

    candidates = _COMMON_WIN_PATHS if os.name == "nt" else _COMMON_UNIX_PATHS
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def install_guidance() -> str:
    """Return platform-specific install instructions for Mosquitto."""
    if os.name == "nt":
        return (
            "Mosquitto is not installed or not found on PATH.\n\n"
            "Install options:\n"
            "  1. Download the installer from https://mosquitto.org/download/\n"
            "  2. Or use: winget install EclipseFoundation.Mosquitto\n\n"
            "After installing, restart the application."
        )
    return (
        "Mosquitto is not installed or not found on PATH.\n\n"
        "Install options:\n"
        "  • Ubuntu/Debian: sudo apt install mosquitto\n"
        "  • Fedora: sudo dnf install mosquitto\n"
        "  • macOS: brew install mosquitto\n\n"
        "After installing, restart the application."
    )


class MQTTBrokerManager:
    """Launch, monitor, and stop an Eclipse Mosquitto broker subprocess."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._status = BrokerStatus.STOPPED
        self._exe_path: str | None = find_mosquitto()
        self._log_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Callbacks
        self.on_status_changed: callable = None
        self.on_log_message: callable = None
        self.on_error: callable = None

    @property
    def status(self) -> BrokerStatus:
        return self._status

    @property
    def executable_path(self) -> str | None:
        return self._exe_path

    @executable_path.setter
    def executable_path(self, path: str) -> None:
        self._exe_path = path

    @property
    def is_running(self) -> bool:
        return (
            self._status == BrokerStatus.RUNNING
            and self._process is not None
            and self._process.poll() is None
        )

    def _set_status(self, status: BrokerStatus) -> None:
        self._status = status
        if self.on_status_changed:
            self.on_status_changed(status)

    def start(self, port: int = 1883, config_path: str | None = None) -> None:
        """Start the Mosquitto broker."""
        if self.is_running:
            return

        if not self._exe_path:
            self._set_status(BrokerStatus.ERROR)
            if self.on_error:
                self.on_error(install_guidance())
            return

        self._set_status(BrokerStatus.STARTING)
        self._stop_event.clear()

        cmd = [self._exe_path, "-v"]
        if config_path and os.path.isfile(config_path):
            cmd += ["-c", config_path]
        else:
            cmd += ["-p", str(port)]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            self._set_status(BrokerStatus.ERROR)
            if self.on_error:
                self.on_error(f"Executable not found: {self._exe_path}")
            return
        except OSError as exc:
            self._set_status(BrokerStatus.ERROR)
            if self.on_error:
                self.on_error(str(exc))
            return

        self._log_thread = threading.Thread(
            target=self._read_output, daemon=True
        )
        self._log_thread.start()

    def stop(self) -> None:
        """Stop the broker subprocess gracefully."""
        if self._process is None:
            return
        self._stop_event.set()
        try:
            self._process.terminate()
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=3)
        finally:
            self._process = None
            self._set_status(BrokerStatus.STOPPED)

    def restart(self, port: int = 1883, config_path: str | None = None) -> None:
        """Stop then start the broker."""
        self.stop()
        self.start(port, config_path)

    # ---------------------------------------------------------------- Internal
    def _read_output(self) -> None:
        """Read broker stdout/stderr in a background thread, emitting logs."""
        proc = self._process
        if proc is None or proc.stdout is None:
            return

        first_line = True
        try:
            for line in proc.stdout:
                if self._stop_event.is_set():
                    break
                text = line.rstrip("\n")
                if first_line:
                    self._set_status(BrokerStatus.RUNNING)
                    first_line = False
                if self.on_log_message:
                    self.on_log_message(text)
        except ValueError:
            pass  # stream closed

        # Process ended
        if not self._stop_event.is_set():
            code = proc.poll()
            if code and code != 0:
                self._set_status(BrokerStatus.ERROR)
                if self.on_error:
                    self.on_error(f"Broker exited with code {code}")
            else:
                self._set_status(BrokerStatus.STOPPED)
