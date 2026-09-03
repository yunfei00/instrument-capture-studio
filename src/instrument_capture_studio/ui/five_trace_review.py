"""Five-trace screening layout for the optional VIDEO spectrum workflow.

The v1.3 acquisition adds ``spectrum_video.npz`` after the original four-trace
capture.  Review keeps the old sample/delete contract intact: the original four
NPZ files still define a portable complete sample, while VIDEO is displayed when
present.  This preserves review compatibility for older data and for captures
where the optional VIDEO trace was disabled.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from instrument_capture_studio.ui import review_window as _review_window
from instrument_capture_studio.ui.review_window import (
    DirectoryReviewDialog,
    ManualReviewDialog,
)
from instrument_capture_studio.ui.trace_viewer import TraceChartWidget


VIDEO_REVIEW_LAYOUT = (
    ("spectrum_freerun.npz", "FSW Free Run", 0, 0, 3),
    ("spectrum_video.npz", "FSW VIDEO", 0, 3, 3),
    ("spectrum_ext.npz", "FSW EXT", 1, 0, 2),
    ("waveform_sync.npz", "DSO-X 第一次同步波形", 1, 2, 2),
    ("waveform_followup.npz", "DSO-X 第二次波形", 1, 4, 2),
)

# The inherited sample-refresh code uses review_window's title map for clear/error
# messages.  Registering the optional fifth trace here lets us reuse the proven
# navigation and delete behavior without changing the v1.2 four-trace contract.
_review_window._TRACE_NAMES.setdefault("spectrum_video.npz", "FSW VIDEO")


class _FiveTraceLayoutMixin:
    """Replace only the chart arrangement; navigation/delete semantics stay inherited."""

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

        self.help_label = QLabel(
            "←/↑ 上一组   →/↓ 下一组   Del 删除整组   F11 全屏切换   Esc 退出"
        )
        self.help_label.setObjectName("reviewHelpLabel")
        self.help_label.setStyleSheet("color: #475467; font-size: 13px;")

        self.notice_label = QLabel()
        self.notice_label.setObjectName("reviewNoticeLabel")
        self.notice_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.notice_label.setStyleSheet("color: #b42318; font-weight: 600;")

        header_layout.addWidget(self.position_label, 1)
        header_layout.addWidget(self.help_label, 2)
        header_layout.addWidget(self.notice_label, 1)
        root.addWidget(header)

        chart_grid = QGridLayout()
        chart_grid.setObjectName("fiveTraceReviewGrid")
        chart_grid.setContentsMargins(0, 0, 0, 0)
        chart_grid.setHorizontalSpacing(10)
        chart_grid.setVerticalSpacing(10)
        self._viewers: dict[str, TraceChartWidget] = {}

        for filename, title_text, row, column, column_span in VIDEO_REVIEW_LAYOUT:
            panel = QWidget(self)
            panel.setObjectName(f"reviewPanel_{filename.replace('.', '_')}")
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(6, 4, 6, 6)
            panel_layout.setSpacing(4)

            title = QLabel(title_text, panel)
            title.setStyleSheet("font-size: 14px; font-weight: 700;")
            viewer = TraceChartWidget(panel)
            viewer.chart_view.setMinimumHeight(205)
            viewer.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            viewer.chart_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            panel_layout.addWidget(title)
            panel_layout.addWidget(viewer, 1)
            self._viewers[filename] = viewer
            chart_grid.addWidget(panel, row, column, 1, column_span)

        chart_grid.setRowStretch(0, 1)
        chart_grid.setRowStretch(1, 1)
        for column in range(6):
            chart_grid.setColumnStretch(column, 1)
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


class FiveTraceManualReviewDialog(_FiveTraceLayoutMixin, ManualReviewDialog):
    """Batch-aware review with two spectrum charts above three remaining traces."""


class FiveTraceDirectoryReviewDialog(_FiveTraceLayoutMixin, DirectoryReviewDialog):
    """Portable review with the same five-chart presentation."""
