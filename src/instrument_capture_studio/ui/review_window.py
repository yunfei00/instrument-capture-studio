"""Full-screen, keyboard-first human screening for paired capture samples."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from instrument_capture_studio.data.batch_manifest import load_batch_manifest
from instrument_capture_studio.data.manual_review import (
    FORMAL_REVIEW_TRACES,
    list_review_samples,
    reject_review_sample,
)
from instrument_capture_studio.data.portable_review import (
    PortableReviewScan,
    reject_portable_review_sample,
    save_portable_review_position,
    scan_portable_review_samples,
)
from instrument_capture_studio.ui.large_data_window import (
    MainWindow as LargeDataWindow,
    _FREQUENCY_ROLE,
    _KIND_ROLE,
    _MANIFEST_ROLE,
)
from instrument_capture_studio.ui.trace_viewer import TraceChartWidget


_TRACE_NAMES = {
    "spectrum_ext.npz": "FSW EXT",
    "waveform_sync.npz": "DSO-X 第一次同步波形",
    "waveform_followup.npz": "DSO-X 第二次波形",
    "spectrum_freerun.npz": "FSW Free Run",
}


class ManualReviewDialog(QDialog):
    """Review one Batch/frequency with four traces per logical sample."""

    def __init__(
        self,
        manifest_path: Path,
        *,
        frequency_index: int | None = None,
        start_job_id: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.manifest_path = Path(manifest_path).expanduser().resolve()
        self.frequency_index = frequency_index
        self._samples = list(
            list_review_samples(
                self.manifest_path,
                frequency_index=frequency_index,
            )
        )
        self._index = 0
        self._rejected_count = self._manifest_rejected_count()
        self._can_delete = self._batch_allows_review_delete()

        if start_job_id:
            for index, sample in enumerate(self._samples):
                if sample.job_id == start_job_id:
                    self._index = index
                    break

        self.setWindowTitle("人工筛选 · Instrument Capture Studio")
        self.setModal(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._build_ui()
        self._install_keyboard_shortcuts()
        self._show_current_sample()

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 12)
        root.setSpacing(8)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)

        self.position_label = QLabel()
        self.position_label.setObjectName("reviewPositionLabel")
        self.position_label.setStyleSheet("font-size: 16px; font-weight: 700;")

        self.help_label = QLabel("←/↑ 上一组   →/↓ 下一组   Del 删除整组   F11 全屏切换   Esc 退出")
        self.help_label.setObjectName("reviewHelpLabel")
        self.help_label.setStyleSheet("color: #475467; font-size: 13px;")

        self.notice_label = QLabel()
        self.notice_label.setObjectName("reviewNoticeLabel")
        self.notice_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.notice_label.setStyleSheet("color: #b42318; font-weight: 600;")

        header_layout.addWidget(self.position_label, 1)
        header_layout.addWidget(self.help_label, 2)
        header_layout.addWidget(self.notice_label, 1)
        root.addWidget(header)

        chart_grid = QGridLayout()
        chart_grid.setContentsMargins(0, 0, 0, 0)
        chart_grid.setHorizontalSpacing(10)
        chart_grid.setVerticalSpacing(10)
        self._viewers: dict[str, TraceChartWidget] = {}

        for index, filename in enumerate(FORMAL_REVIEW_TRACES):
            panel = QWidget(self)
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(6, 4, 6, 6)
            panel_layout.setSpacing(4)
            title = QLabel(_TRACE_NAMES[filename])
            title.setStyleSheet("font-size: 14px; font-weight: 700;")
            viewer = TraceChartWidget(panel)
            viewer.chart_view.setMinimumHeight(230)
            viewer.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            viewer.chart_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            panel_layout.addWidget(title)
            panel_layout.addWidget(viewer, 1)
            self._viewers[filename] = viewer
            chart_grid.addWidget(panel, index // 2, index % 2)

        chart_grid.setRowStretch(0, 1)
        chart_grid.setRowStretch(1, 1)
        chart_grid.setColumnStretch(0, 1)
        chart_grid.setColumnStretch(1, 1)
        root.addLayout(chart_grid, 1)

        footer = QWidget(self)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        self.previous_button = QPushButton("← 上一组")
        self.next_button = QPushButton("下一组 →")
        self.delete_button = QPushButton("Del 删除当前样本")
        for button in (self.previous_button, self.next_button, self.delete_button):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_button.setObjectName("reviewDeleteButton")
        self.delete_button.setEnabled(self._can_delete)
        self.delete_button.setStyleSheet(
            "QPushButton#reviewDeleteButton { font-weight: 700; padding: 7px 16px; }"
        )
        footer_layout.addWidget(self.previous_button)
        footer_layout.addWidget(self.next_button)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.delete_button)
        root.addWidget(footer)

        self.previous_button.clicked.connect(self._show_previous)
        self.next_button.clicked.connect(self._show_next)
        self.delete_button.clicked.connect(self._delete_current_without_confirmation)

        if not self._can_delete:
            self.notice_label.setText("当前 Batch 仍在运行/暂停，已禁用删除")

    def _install_keyboard_shortcuts(self) -> None:
        """Use window shortcuts so chart/button focus never steals review keys."""
        self._review_shortcuts: list[QShortcut] = []

        def bind(key, callback) -> None:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self._review_shortcuts.append(shortcut)

        bind(Qt.Key.Key_Right, self._show_next)
        bind(Qt.Key.Key_Down, self._show_next)
        bind(Qt.Key.Key_Left, self._show_previous)
        bind(Qt.Key.Key_Up, self._show_previous)
        bind(Qt.Key.Key_Delete, self._delete_current_without_confirmation)
        bind(Qt.Key.Key_F11, self._toggle_full_screen)
        bind(Qt.Key.Key_Escape, self.accept)

    def _toggle_full_screen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _show_previous(self) -> None:
        if not self._samples:
            return
        self._index = max(0, self._index - 1)
        self._show_current_sample()

    def _show_next(self) -> None:
        if not self._samples:
            return
        self._index = min(len(self._samples) - 1, self._index + 1)
        self._show_current_sample()

    def _show_current_sample(self) -> None:
        if not self._samples:
            self.position_label.setText(
                f"{self.manifest_path.parent.name} · 没有待筛选的成功样本 · 已删除 {self._rejected_count}"
            )
            for filename, viewer in self._viewers.items():
                viewer.clear(f"{_TRACE_NAMES[filename]} · 无数据")
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return

        self._index = min(max(self._index, 0), len(self._samples) - 1)
        sample = self._samples[self._index]
        self.position_label.setText(
            f"{sample.frequency_hz / 1e6:g} MHz   ·   "
            f"{self._index + 1}/{len(self._samples)}   ·   "
            f"样本 n{sample.capture_index:04d}   ·   "
            f"已删除 {self._rejected_count}"
        )
        self.setWindowTitle(f"人工筛选 · {sample.job_id}")

        for filename, viewer in self._viewers.items():
            path = sample.directory / filename
            if not path.is_file():
                viewer.clear(f"{_TRACE_NAMES[filename]} · 文件缺失：{filename}")
                continue
            try:
                viewer.load_path(path)
            except Exception as exc:
                viewer.clear(
                    f"{_TRACE_NAMES[filename]} · 文件异常：{type(exc).__name__}: {exc}"
                )

        self.previous_button.setEnabled(self._index > 0)
        self.next_button.setEnabled(self._index < len(self._samples) - 1)
        self.delete_button.setEnabled(self._can_delete)
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _delete_current_without_confirmation(self) -> None:
        if not self._can_delete or not self._samples:
            return
        sample = self._samples[self._index]
        try:
            result = reject_review_sample(self.manifest_path, sample.job_id)
        except Exception as exc:
            self.notice_label.setText(f"删除失败：{type(exc).__name__}: {exc}")
            return

        self._rejected_count = result.rejected_count
        self._samples.pop(self._index)
        if self._samples:
            self._index = min(self._index, len(self._samples) - 1)
        else:
            self._index = 0
        self._show_current_sample()
        self.notice_label.setText(f"已删除：{sample.job_id}")

    def _batch_allows_review_delete(self) -> bool:
        manifest = load_batch_manifest(self.manifest_path)
        return str(manifest.get("state") or "").lower() not in {"running", "paused"}

    def _manifest_rejected_count(self) -> int:
        manifest = load_batch_manifest(self.manifest_path)
        summary = manifest.get("review_summary")
        if isinstance(summary, dict):
            try:
                return int(summary.get("rejected_count") or 0)
            except (TypeError, ValueError):
                pass
        jobs = manifest.get("jobs")
        if not isinstance(jobs, list):
            return 0
        return sum(
            1
            for raw in jobs
            if isinstance(raw, dict)
            and str(raw.get("review_status") or "").lower() == "rejected"
        )


class DirectoryReviewDialog(ManualReviewDialog):
    """Review copied/moved datasets using only the four final NPZ files."""

    def __init__(
        self,
        data_root: Path,
        *,
        scan: PortableReviewScan | None = None,
        parent=None,
    ) -> None:
        QDialog.__init__(self, parent)
        self.data_root = Path(data_root).expanduser().resolve()
        self._scan = scan or scan_portable_review_samples(self.data_root)
        self._samples = list(self._scan.samples)
        self._index = min(self._scan.resume_index, max(0, len(self._samples) - 1))
        self._rejected_count = self._scan.rejected_count
        self._can_delete = True
        self.setWindowTitle("目录人工筛选 · Instrument Capture Studio")
        self.setModal(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._build_ui()
        self._install_keyboard_shortcuts()
        if self._scan.incomplete_directories:
            self.notice_label.setText(
                f"已跳过 {self._scan.incomplete_directories} 个不完整样本目录"
            )
        self._show_current_sample()

    def _show_current_sample(self) -> None:
        if not self._samples:
            self.position_label.setText(
                f"{self.data_root.name} · 没有可筛选的完整四图样本 · 已删除 {self._rejected_count}"
            )
            for filename, viewer in self._viewers.items():
                viewer.clear(f"{_TRACE_NAMES[filename]} · 无数据")
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            save_portable_review_position(self.data_root, None, position=0, total=0)
            return

        self._index = min(max(self._index, 0), len(self._samples) - 1)
        sample = self._samples[self._index]
        frequency = (
            f"{sample.frequency_hz / 1e6:g} MHz"
            if sample.frequency_hz is not None
            else "频率未知"
        )
        capture = (
            f"样本 n{sample.capture_index:04d}"
            if sample.capture_index is not None
            else sample.directory.name
        )
        self.position_label.setText(
            f"{frequency}   ·   {self._index + 1}/{len(self._samples)}   ·   "
            f"{capture}   ·   已删除 {self._rejected_count}"
        )
        self.setWindowTitle(f"目录人工筛选 · {sample.relative_path}")

        for filename, viewer in self._viewers.items():
            path = sample.directory / filename
            if not path.is_file():
                viewer.clear(f"{_TRACE_NAMES[filename]} · 文件缺失：{filename}")
                continue
            try:
                viewer.load_path(path)
            except Exception as exc:
                viewer.clear(
                    f"{_TRACE_NAMES[filename]} · 文件异常：{type(exc).__name__}: {exc}"
                )

        self.previous_button.setEnabled(self._index > 0)
        self.next_button.setEnabled(self._index < len(self._samples) - 1)
        self.delete_button.setEnabled(True)
        save_portable_review_position(
            self.data_root,
            sample,
            position=self._index + 1,
            total=len(self._samples),
        )
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _delete_current_without_confirmation(self) -> None:
        if not self._samples:
            return
        sample = self._samples[self._index]
        try:
            result = reject_portable_review_sample(self.data_root, sample)
        except Exception as exc:
            self.notice_label.setText(f"删除失败：{type(exc).__name__}: {exc}")
            return

        self._rejected_count = result.rejected_count
        self._samples.pop(self._index)
        if self._samples:
            self._index = min(self._index, len(self._samples) - 1)
        else:
            self._index = 0
        self._show_current_sample()
        self.notice_label.setText(f"已删除：{sample.relative_path}")


class MainWindow(LargeDataWindow):
    """Main workspace with Batch-aware and portable directory screening."""

    def __init__(self) -> None:
        super().__init__()
        self._install_manual_review_action()

    def _install_manual_review_action(self) -> None:
        bar = self.findChild(QWidget, "largeDataFilterBar")
        layout = bar.layout() if bar is not None else None
        self.manual_review_button = QPushButton("人工筛选当前 Batch", bar or self)
        self.manual_review_button.setObjectName("manualReviewButton")
        self.manual_review_button.setToolTip(
            "按当前 Batch/频率全屏筛选四条正式曲线；Del 无确认删除整个样本目录。"
        )
        self.directory_review_button = QPushButton("选择目录人工筛选", bar or self)
        self.directory_review_button.setObjectName("directoryReviewButton")
        self.directory_review_button.setToolTip(
            "处理已经复制或重新整理的数据：只要求每个样本目录保留四个正式 NPZ，不依赖 Batch/Job/metadata。"
        )
        if layout is not None:
            layout.addWidget(self.manual_review_button)
            layout.addWidget(self.directory_review_button)
        self.manual_review_button.clicked.connect(self._open_manual_review)
        self.directory_review_button.clicked.connect(self._open_directory_review)
        self.data_tree.itemSelectionChanged.connect(self._refresh_manual_review_action)
        self._refresh_manual_review_action()

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "manual_review_button"):
            self._refresh_manual_review_action()

    def _refresh_manual_review_action(self) -> None:
        if not hasattr(self, "manual_review_button"):
            return
        manifest_path, _frequency_index, _job_id = self._selected_review_context()
        self.manual_review_button.setEnabled(
            not self._capture_busy and manifest_path is not None
        )
        if hasattr(self, "directory_review_button"):
            self.directory_review_button.setEnabled(not self._capture_busy)

    def _open_manual_review(self) -> None:
        manifest_path, frequency_index, job_id = self._selected_review_context()
        if manifest_path is None:
            return
        dialog = ManualReviewDialog(
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
                "没有发现完整样本。\n\n每个样本目录至少需要同时包含：\n"
                + "\n".join(FORMAL_REVIEW_TRACES),
            )
            return

        dialog = DirectoryReviewDialog(root, scan=scan, parent=self)
        dialog.showFullScreen()
        dialog.exec()
        self._refresh_data_tree()

    def _selected_review_context(
        self,
    ) -> tuple[Path | None, int | None, str | None]:
        item = self.data_tree.currentItem() if hasattr(self, "data_tree") else None
        if item is None:
            return None, None, None

        manifest_path: Path | None = None
        frequency_index: int | None = None
        job_id: str | None = None
        current = item
        while current is not None:
            kind = current.data(0, _KIND_ROLE)
            if kind == "batch" and manifest_path is None:
                raw_manifest = current.data(0, _MANIFEST_ROLE)
                if raw_manifest:
                    manifest_path = Path(str(raw_manifest))
            if kind == "frequency" and frequency_index is None:
                raw_frequency = current.data(0, _FREQUENCY_ROLE)
                try:
                    frequency_index = int(raw_frequency)
                except (TypeError, ValueError):
                    pass
            if kind in {"job", "recent_job"} and job_id is None:
                job_id = current.text(0).strip() or None
            current = current.parent()

        if manifest_path is None:
            raw_path = item.data(0, Qt.ItemDataRole.UserRole)
            if raw_path:
                manifest_path = _find_batch_manifest(Path(str(raw_path)))

        if manifest_path is None or not manifest_path.is_file():
            return None, None, None

        if frequency_index is None and job_id:
            manifest = load_batch_manifest(manifest_path)
            jobs = manifest.get("jobs")
            if isinstance(jobs, list):
                for raw in jobs:
                    if not isinstance(raw, dict):
                        continue
                    if str(raw.get("job_id") or "") != job_id:
                        continue
                    try:
                        frequency_index = int(raw.get("frequency_index"))
                    except (TypeError, ValueError):
                        pass
                    break

        return manifest_path, frequency_index, job_id


def _find_batch_manifest(path: Path) -> Path | None:
    path = path.expanduser()
    candidate = path.parent if path.is_file() else path
    for directory in (candidate, *candidate.parents):
        manifest = directory / "batch.json"
        if manifest.is_file():
            return manifest
    return None
