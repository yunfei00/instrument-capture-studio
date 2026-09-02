"""Optional FSW VIDEO-triggered fifth spectrum layered on the v1.2 workspace."""

from dataclasses import replace

from PySide6.QtWidgets import QCheckBox, QGridLayout, QLabel, QLineEdit

from instrument_capture_studio.app.capture_recipe import CaptureRecipe
from instrument_capture_studio.ui.snapshot_window import MainWindow as SnapshotWindow


class MainWindow(SnapshotWindow):
    """Workspace with an optional VIDEO-triggered FSW Single spectrum."""

    def __init__(self) -> None:
        super().__init__()
        self._install_video_trigger_control()
        # These controls are created after the inherited preference restore.
        self._preferences.restore(self)
        self.video_trigger_checkbox.toggled.connect(self._save_preferences)
        self.video_trigger_checkbox.toggled.connect(self._sync_video_trigger_control)
        self.video_trigger_checkbox.toggled.connect(self._update_recipe_summary)
        self.video_trigger_level_edit.editingFinished.connect(self._save_preferences)
        self.video_trigger_level_edit.editingFinished.connect(
            self._update_recipe_summary
        )
        self.recipe_combo.currentTextChanged.connect(self._sync_video_trigger_control)
        self._sync_video_trigger_control()
        self._update_recipe_summary()
        self.statusBar().showMessage(
            "就绪 · v1.3 开发版 · Snapshot All · VIDEO 触发频谱可选"
        )

    def _install_video_trigger_control(self) -> None:
        card = self.commercial_task_parameter_card
        grid = card.layout() if card is not None else None
        if not isinstance(grid, QGridLayout):
            raise RuntimeError("task parameter card must use QGridLayout")

        row = grid.rowCount()
        self.video_trigger_checkbox = QCheckBox(
            "原有四路完成后追加一次 VIDEO Trigger Single 频谱",
            card,
        )
        self.video_trigger_checkbox.setObjectName("videoTriggerCheckbox")
        self.video_trigger_checkbox.setChecked(False)
        self.video_trigger_checkbox.setToolTip(
            "默认关闭。开启后不改变原有 EXT / 两次 DSO-X / Free Run 顺序，"
            "只在最后追加一次 FSW VIDEO Trigger 单次采集。"
        )

        self.video_trigger_level_edit = QLineEdit("45.9", card)
        self.video_trigger_level_edit.setObjectName("videoTriggerLevelEdit")
        self.video_trigger_level_edit.setMaximumWidth(120)
        self.video_trigger_level_edit.setToolTip(
            "VIDEO Trigger Level，单位 %，有效范围 0 到 100。调试值默认为 45.9%。"
        )

        level_box = QLabel("%", card)
        offset_note = QLabel(
            "Trigger Offset 自动 = -Sweep Time / 2 · Sweep Time 在 VIDEO 采集前重新读取",
            card,
        )
        offset_note.setObjectName("videoTriggerOffsetNote")
        offset_note.setWordWrap(True)

        grid.addWidget(QLabel("VIDEO 触发频谱", card), row, 0)
        grid.addWidget(self.video_trigger_checkbox, row, 1, 1, 2)
        grid.addWidget(offset_note, row, 3)

        grid.addWidget(QLabel("Video Trigger Level", card), row + 1, 0)
        grid.addWidget(self.video_trigger_level_edit, row + 1, 1)
        grid.addWidget(level_box, row + 1, 2)
        self.video_trigger_level_label = level_box

    def _build_fsw_settings(self):
        settings = super()._build_fsw_settings()
        enabled = (
            self._selected_recipe() is CaptureRecipe.EXT_IMM_PAIR
            and self.video_trigger_checkbox.isChecked()
        )
        level_pct = 45.9
        if enabled:
            level_pct = self._required_float(
                self.video_trigger_level_edit,
                "Video Trigger Level",
            )
            if not 0.0 <= level_pct <= 100.0:
                raise ValueError("Video Trigger Level 必须在 0 到 100% 之间")
        return replace(
            settings,
            video_trigger_enabled=enabled,
            video_trigger_level_pct=level_pct,
        )

    def _sync_recipe_controls(self, *_args) -> None:
        super()._sync_recipe_controls(*_args)
        self._sync_video_trigger_control()

    def _sync_video_trigger_control(self, *_args) -> None:
        if not hasattr(self, "video_trigger_checkbox"):
            return
        paired = self._selected_recipe() is CaptureRecipe.EXT_IMM_PAIR
        enabled = paired and not self._capture_busy
        self.video_trigger_checkbox.setEnabled(enabled)
        level_enabled = enabled and self.video_trigger_checkbox.isChecked()
        self.video_trigger_level_edit.setEnabled(level_enabled)
        self.video_trigger_level_label.setEnabled(level_enabled)

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        self._sync_video_trigger_control()

    def _update_recipe_summary(self, *_args) -> None:
        super()._update_recipe_summary(*_args)
        if not hasattr(self, "video_trigger_checkbox"):
            return
        if self._selected_recipe() is not CaptureRecipe.EXT_IMM_PAIR:
            return
        if self.video_trigger_checkbox.isChecked():
            level = self.video_trigger_level_edit.text().strip() or "45.9"
            suffix = (
                f" VIDEO 频谱：开启，Level={level}%，"
                "Offset=-Sweep Time/2，原有四路完成后追加 Single。"
            )
        else:
            suffix = " VIDEO 频谱：关闭，原有四路采集完全不变。"
        self.recipe_summary_label.setText(self.recipe_summary_label.text() + suffix)
