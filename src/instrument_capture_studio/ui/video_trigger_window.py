"""Optional FSW VIDEO-triggered fifth spectrum layered on the v1.2 workspace."""

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTreeWidgetItem,
)

from instrument_capture_studio.app.capture_recipe import CaptureRecipe
from instrument_capture_studio.data.manual_review import FORMAL_REVIEW_TRACES
from instrument_capture_studio.data.portable_review import scan_portable_review_samples
from instrument_capture_studio.ui.five_trace_review import (
    FiveTraceDirectoryReviewDialog,
    FiveTraceManualReviewDialog,
)
from instrument_capture_studio.ui.product_window import _file_description
from instrument_capture_studio.ui.snapshot_window import MainWindow as SnapshotWindow


_VIDEO_JOB_FILES = (
    "spectrum_video.npz",
    "spectrum_video.csv",
)


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
        self._update_review_tooltips()
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

    @staticmethod
    def _append_job_files(node: QTreeWidgetItem, directory: Path) -> None:
        """Expose the v1.3 VIDEO artifacts alongside the existing formal files."""
        SnapshotWindow._append_job_files(node, directory)
        for filename in _VIDEO_JOB_FILES:
            path = Path(directory) / filename
            if not path.exists():
                continue
            child = QTreeWidgetItem([filename, _file_description(path)])
            child.setData(0, Qt.ItemDataRole.UserRole, str(path))
            node.addChild(child)

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

    def _update_review_tooltips(self) -> None:
        if hasattr(self, "manual_review_button"):
            self.manual_review_button.setToolTip(
                "五图人工筛选：上排 Free Run + VIDEO；下排 EXT + 两次 DSO-X。"
                "Del 规则与原来完全一致，删除整个当前样本目录。"
            )
        if hasattr(self, "directory_review_button"):
            self.directory_review_button.setToolTip(
                "目录人工筛选同样使用五图布局。旧四图数据仍可筛选；"
                "存在 spectrum_video.npz 时作为第五图显示。"
            )

    def _open_manual_review(self) -> None:
        manifest_path, frequency_index, job_id = self._selected_review_context()
        if manifest_path is None:
            return
        dialog = FiveTraceManualReviewDialog(
            manifest_path,
            frequency_index=frequency_index,
            start_job_id=job_id,
            parent=self,
        )
        dialog.showFullScreen()
        dialog.exec()
        self._refresh_data_tree()

    def _open_directory_review(self) -> None:
        start = Path(self.output_root_edit.text()).expanduser()
        if not start.is_dir():
            start = Path.home()
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择需要人工筛选的数据根目录",
            str(start),
        )
        if not selected:
            return

        root = Path(selected).expanduser().resolve()
        try:
            scan = scan_portable_review_samples(root)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "目录人工筛选",
                f"无法扫描所选目录：\n{type(exc).__name__}: {exc}",
            )
            return
        if not scan.samples:
            QMessageBox.information(
                self,
                "目录人工筛选",
                "没有发现完整样本。\n\n兼容规则仍以原有四个核心 NPZ 判断完整样本：\n"
                + "\n".join(FORMAL_REVIEW_TRACES)
                + "\n\n如果存在 spectrum_video.npz，会自动作为第五张图显示。",
            )
            return

        dialog = FiveTraceDirectoryReviewDialog(root, scan=scan, parent=self)
        dialog.showFullScreen()
        dialog.exec()
        self._refresh_data_tree()
