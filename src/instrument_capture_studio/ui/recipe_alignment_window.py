"""Recipe realignment window used while the new hardware sequence is qualified."""

from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton

from instrument_capture_studio.ui.recipe_debug_dialog import RecipeDebugDialog
from instrument_capture_studio.ui.release_window import MainWindow as ReleaseWindow


class MainWindow(ReleaseWindow):
    """Keep all RC hardening while exposing the staged hardware debugger."""

    def __init__(self) -> None:
        self._recipe_debug_dialog: RecipeDebugDialog | None = None
        super().__init__()
        self._install_recipe_debug_action()
        self.statusBar().showMessage("就绪 · Recipe Realignment · 单步真机验证")

    def _install_recipe_debug_action(self) -> None:
        group = self.start_button.parentWidget()
        layout = group.layout()
        if not isinstance(layout, QGridLayout):
            raise RuntimeError("capture group must use QGridLayout")

        self.recipe_debug_button = QPushButton("工程调试 / 单步采集", group)
        self.recipe_debug_button.setObjectName("recipeDebugButton")
        note = QLabel(
            "新正式流程尚未合入一键采集；先按 8 个硬件步骤逐条确认 SCPI 与屏幕结果。",
            group,
        )
        note.setObjectName("alphaNote")
        note.setWordWrap(True)
        layout.addWidget(QLabel("新流程验证"), 9, 0)
        layout.addWidget(self.recipe_debug_button, 9, 1, 1, 2)
        layout.addWidget(note, 9, 3, 1, 3)
        self.recipe_debug_button.clicked.connect(self._open_recipe_debugger)

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "recipe_debug_button"):
            self.recipe_debug_button.setEnabled(not busy and self._recipe_debug_dialog is None)

    def _open_recipe_debugger(self) -> None:
        if self._capture_busy or self._recipe_debug_dialog is not None:
            return
        try:
            fsw_settings = self._build_fsw_settings()
            dsox_settings = self._build_dsox_settings()
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "调试参数错误",
                f"请先确认两台仪表 VISA 地址及基础参数有效。\n\n{type(exc).__name__}: {exc}",
            )
            return

        dialog = RecipeDebugDialog(fsw_settings, dsox_settings, self)
        self._recipe_debug_dialog = dialog
        self.recipe_debug_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.fsw_connect_button.setEnabled(False)
        self.dsox_connect_button.setEnabled(False)
        dialog.finished.connect(self._on_recipe_debugger_closed)
        dialog.show()

    def _on_recipe_debugger_closed(self, _result: int) -> None:
        dialog = self._recipe_debug_dialog
        self._recipe_debug_dialog = None
        if dialog is not None:
            dialog.deleteLater()
        self._sync_recipe_controls()
        if hasattr(self, "recipe_debug_button"):
            self.recipe_debug_button.setEnabled(not self._capture_busy)
