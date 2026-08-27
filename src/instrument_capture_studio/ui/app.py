"""Desktop application bootstrap."""

import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication, QLabel

from instrument_capture_studio.ui.release_window import MainWindow


_RELEASE_LABEL = "v0.9 · RC1"


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create the Qt application with stable product metadata."""
    QCoreApplication.setOrganizationName("Instrument Capture Studio")
    QCoreApplication.setApplicationName("Instrument Capture Studio")
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationDisplayName("Instrument Capture Studio")
    app.setStyle("Fusion")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
    return app


def create_main_window() -> MainWindow:
    """Create the real release-candidate window and apply release branding."""
    window = MainWindow()
    badge = window.findChild(QLabel, "alphaBadge")
    if badge is not None:
        badge.setText(_RELEASE_LABEL)
        badge.setMinimumWidth(130)
    window.statusBar().showMessage("就绪 · v0.9 RC1 · Phase 8D")
    return window


def main(argv: list[str] | None = None) -> int:
    app = create_application(argv)
    window = create_main_window()
    window.show()
    return app.exec()
