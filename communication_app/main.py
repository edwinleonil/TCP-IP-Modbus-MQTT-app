"""Communication App – entry point."""

import sys

from PySide6.QtWidgets import QApplication

from communication_app.core.config import load_config
from communication_app.core.logger import setup_logging
from communication_app.ui.main_window import MainWindow


def main() -> None:
    config = load_config()
    setup_logging()

    app = QApplication(sys.argv)
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
