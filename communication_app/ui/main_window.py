"""Main application window with tabbed protocol panels and system log dock."""

import logging
import os

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QDockWidget,
    QPlainTextEdit,
    QMenuBar,
    QMenu,
    QApplication,
)
from PySide6.QtGui import QAction

from communication_app.core.config import AppConfig, save_config
from communication_app.core.logger import log_emitter
from communication_app.ui.tcp_panel import TCPPanel
from communication_app.ui.mqtt_panel import MQTTPanel
from communication_app.ui.modbus_panel import ModbusPanel

logger = logging.getLogger("comm_app.ui.main")

_RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "..", "resources")
_DARK_QSS = os.path.join(_RESOURCES_DIR, "dark_theme.qss")
_MAX_LOG_LINES = 10_000


class MainWindow(QMainWindow):
    """Main application window hosting protocol tabs and system log."""

    def __init__(self, config: AppConfig | None = None):
        super().__init__()
        self._config = config or AppConfig()
        self.setWindowTitle("Communication App – TCP / MQTT / Modbus")
        self.resize(1200, 800)

        self._setup_menu()
        self._setup_tabs()
        self._setup_log_dock()
        self._connect_log_signal()
        self._apply_theme(self._config.theme)

    # ------------------------------------------------------------ Menu
    def _setup_menu(self) -> None:
        menu_bar: QMenuBar = self.menuBar()

        # File
        file_menu: QMenu = menu_bar.addMenu("&File")
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Settings
        settings_menu: QMenu = menu_bar.addMenu("&Settings")

        theme_menu: QMenu = settings_menu.addMenu("Theme")
        self._light_action = QAction("Light", self)
        self._light_action.setCheckable(True)
        self._dark_action = QAction("Dark", self)
        self._dark_action.setCheckable(True)
        theme_menu.addAction(self._light_action)
        theme_menu.addAction(self._dark_action)
        self._light_action.triggered.connect(lambda: self._set_theme("light"))
        self._dark_action.triggered.connect(lambda: self._set_theme("dark"))

        # Help
        help_menu: QMenu = menu_bar.addMenu("&Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------ Tabs
    def _setup_tabs(self) -> None:
        self._tabs = QTabWidget()
        self._tcp_panel = TCPPanel()
        self._mqtt_panel = MQTTPanel()
        self._modbus_panel = ModbusPanel()
        self._tabs.addTab(self._tcp_panel, "TCP/IP")
        self._tabs.addTab(self._mqtt_panel, "MQTT")
        self._tabs.addTab(self._modbus_panel, "Modbus")
        self.setCentralWidget(self._tabs)

    # -------------------------------------------------------- Log Dock
    def _setup_log_dock(self) -> None:
        self._log_dock = QDockWidget("System Logs", self)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(_MAX_LOG_LINES)
        self._log_dock.setWidget(self._log_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, self._log_dock)

    def _connect_log_signal(self) -> None:
        log_emitter.log_message.connect(self._append_log)

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self._log_view.appendPlainText(message)

    # ----------------------------------------------------------- Theme
    def _apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if theme == "dark" and os.path.isfile(_DARK_QSS):
            with open(_DARK_QSS, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            self._dark_action.setChecked(True)
            self._light_action.setChecked(False)
        else:
            app.setStyleSheet("")
            self._light_action.setChecked(True)
            self._dark_action.setChecked(False)

    def _set_theme(self, theme: str) -> None:
        self._config.theme = theme
        self._apply_theme(theme)
        try:
            save_config(self._config)
        except Exception as e:
            logger.error("Failed to save config: %s", e)

    # ----------------------------------------------------------- About
    def _show_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.about(
            self,
            "About Communication App",
            "Communication App v1.0\n\n"
            "Desktop application for managing TCP/IP, MQTT, and Modbus protocols.\n\n"
            "Built with PySide6, paho-mqtt, and pymodbus.",
        )

    # -------------------------------------------------------- Shutdown
    def closeEvent(self, event) -> None:
        logger.info("Shutting down…")
        self._tcp_panel.shutdown()
        self._mqtt_panel.shutdown()
        self._modbus_panel.shutdown()
        try:
            save_config(self._config)
        except Exception:
            pass
        event.accept()
