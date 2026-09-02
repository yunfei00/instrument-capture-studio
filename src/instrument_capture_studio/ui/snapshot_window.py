"""Optional DSO-X Snapshot All control layered on the v1.2 workspace."""

from dataclasses import replace

from PySide6.QtWidgets import QCheckBox, QGridLayout, QLabel

from instrument_capture_studio.app.capture_recipe import CaptureRecipe
from instrument_capture_studio.ui.custom_fields_window import MainWindow as CustomFieldsWindow


class MainWindow(CustomFieldsWindow):
    """v1.2 workspace with optional post-waveform Snapshot All collection."""

    def __init__(self) -> None:
        super().__init__()
        self._install_snapshot_all_control()
        # The checkbox is created after the inherited preference restore.
        self._preferences.restore(self)
        self.snapshot_all_checkbox.toggled.connect(self._save_preferences)
        self.snapshot_all_checkbox.toggled.connect(self._update_recipe_summary)
        self.recipe_combo.currentTextChanged.connect(self._sync_snapshot_all_control)
        self._sync_snapshot_all_control()
        self._update_recipe_summary()
        self.statusBar().showMessage("就绪 · v1.2.0 · 项目记录 · Snapshot All 可选")

    def _install_snapshot_all_control(self) -> None:
        card = self.commercial_task_parameter_card
        grid = card.layout() if card is not None else None
        if not isinstance(grid, QGridLayout):
            raise RuntimeError("task parameter card must use QGridLayout")

        row = grid.rowCount()
        self.snapshot_all_checkbox = QCheckBox(
            "每次示波器波形后读取 Snapshot All（31 项）",
            card,
        )
        self.snapshot_all_checkbox.setObjectName("snapshotAllCheckbox")
        self.snapshot_all_checkbox.setChecked(False)
        self.snapshot_all_checkbox.setToolTip(
            "开启后，每次 DSO-X Single 波形读取完成后，立即读取 Snapshot All 的 31 项测量值。"
            "结果写入该波形 metadata，并内嵌到 NPZ。会增加采集耗时；单项测量无效不会使波形采集失败。"
        )
        note = QLabel("默认关闭 · 开启后同步波形和第二次波形都会各读取一次", card)
        note.setObjectName("snapshotAllNote")
        note.setWordWrap(True)

        grid.addWidget(QLabel("示波器快照", card), row, 0)
        grid.addWidget(self.snapshot_all_checkbox, row, 1, 1, 2)
        grid.addWidget(note, row, 3)

    def _build_dsox_settings(self):
        settings = super()._build_dsox_settings()
        return replace(
            settings,
            snapshot_all_enabled=self.snapshot_all_checkbox.isChecked(),
        )

    def _sync_recipe_controls(self, *_args) -> None:
        super()._sync_recipe_controls(*_args)
        self._sync_snapshot_all_control()

    def _sync_snapshot_all_control(self, *_args) -> None:
        if not hasattr(self, "snapshot_all_checkbox"):
            return
        requires_dsox = self._selected_recipe() in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.DSOX_ONLY,
        }
        self.snapshot_all_checkbox.setEnabled(requires_dsox and not self._capture_busy)

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        self._sync_snapshot_all_control()

    def _update_recipe_summary(self, *_args) -> None:
        super()._update_recipe_summary(*_args)
        if not hasattr(self, "snapshot_all_checkbox"):
            return
        if self._selected_recipe() not in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.DSOX_ONLY,
        }:
            return
        suffix = (
            " Snapshot All：开启，每次示波器波形后额外读取 31 项测量值。"
            if self.snapshot_all_checkbox.isChecked()
            else " Snapshot All：关闭。"
        )
        self.recipe_summary_label.setText(self.recipe_summary_label.text() + suffix)
