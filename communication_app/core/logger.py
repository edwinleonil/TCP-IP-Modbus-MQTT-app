"""Central logging module with Qt signal handler for UI integration."""

import logging
import os

from PySide6.QtCore import QObject, Signal


class LogSignalEmitter(QObject):
    """Emits log messages as Qt signals for the UI log panel."""
    log_message = Signal(str)


class QSignalHandler(logging.Handler):
    """Logging handler that emits records via a Qt signal."""

    def __init__(self, emitter: LogSignalEmitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self.emitter.log_message.emit(msg)


# Shared emitter instance
log_emitter = LogSignalEmitter()

_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "app.log")


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """Configure and return the application logger."""
    logger = logging.getLogger("comm_app")
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Qt signal handler (for UI)
    qt_handler = QSignalHandler(log_emitter)
    qt_handler.setLevel(logging.DEBUG)
    qt_handler.setFormatter(formatter)
    logger.addHandler(qt_handler)

    return logger
