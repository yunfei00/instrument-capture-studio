"""Desktop application bootstrap."""

import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication

from instrument_capture_studio.ui.main_window import MainWindow


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create the Qt application with stable product metadata."""

    QCoreApplication.setOrganizationName("Instrument Capture Studio")
    QCoreApplication.setApplicationName("Instrument Capture Studio")

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationDisplayName("Instrument Capture Studio")
    app.setStyle("Fusion")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
    return app


def main(argv: list[str] | None = None) -> int:
    app = create_application(argv)
    window = MainWindow()
    window.show()
    return app.exec()
