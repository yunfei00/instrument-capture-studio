"""Desktop widgets and dialogs for inspecting saved capture artifacts."""

import json
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

from instrument_capture_studio.data.trace_preview import TracePreview, load_trace_preview


class TraceChartWidget(QWidget):
    """Reusable chart used by both inline browsing and the large dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._path: Path | None = None

        self.summary_label = QLabel("选择 NPZ 曲线后在这里预览")
        self.summary_label.setObjectName("tracePreviewSummary")
        self.summary_label.setWordWrap(True)

        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setMinimumHeight(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.chart_view, 1)

        self.clear()

    @property
    def path(self) -> Path | None:
        return self._path

    def clear(self, message: str = "选择 NPZ 曲线后在这里预览") -> None:
        self._path = None
        self.summary_label.setText(message)
        chart = QChart()
        chart.setTitle("数据预览")
        chart.legend().hide()
        self.chart_view.setChart(chart)

    def load_path(self, path: Path) -> TracePreview:
        path = Path(path)
        preview = load_trace_preview(path)
        self._path = path
        self.chart_view.setChart(_build_chart(preview, path))

        summary = [preview.title, f"{len(preview.x)} preview points"]
        summary.extend(preview.details)
        self.summary_label.setText("   ·   ".join(summary))
        return preview


class TraceViewerDialog(QDialog):
    """Plot one saved spectrum or waveform NPZ file."""

    def __init__(self, path: Path, parent=None) -> None:
        super().__init__(parent)
        path = Path(path)
        self.setWindowTitle(f"曲线查看 · {path.parent.name}")
        self.resize(980, 620)

        viewer = TraceChartWidget(self)
        preview = viewer.load_path(path)
        self.setWindowTitle(f"{preview.title} · {path.parent.name}")

        layout = QVBoxLayout(self)
        layout.addWidget(viewer)


class JsonViewerDialog(QDialog):
    """Readable viewer for batch.json, job.json, and metadata.json."""

    def __init__(self, path: Path, parent=None) -> None:
        super().__init__(parent)
        path = Path(path)
        self.setWindowTitle(path.name)
        self.resize(900, 650)

        value = json.loads(path.read_text(encoding="utf-8"))
        text = json.dumps(value, ensure_ascii=False, indent=2)

        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(text)

        layout = QVBoxLayout(self)
        layout.addWidget(editor)


def _build_chart(preview: TracePreview, path: Path) -> QChart:
    series = QLineSeries()
    series.replace(
        [
            QPointF(float(x), float(y))
            for x, y in zip(preview.x, preview.y, strict=True)
        ]
    )

    chart = QChart()
    chart.addSeries(series)
    chart.legend().hide()
    chart.setTitle(f"{preview.title} · {path.name}")

    axis_x = QValueAxis()
    axis_x.setTitleText(preview.x_label)
    axis_y = QValueAxis()
    axis_y.setTitleText(preview.y_label)
    _set_axis_range(axis_x, preview.x)
    _set_axis_range(axis_y, preview.y)

    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_x)
    series.attachAxis(axis_y)
    return chart


def _set_axis_range(axis: QValueAxis, values) -> None:
    minimum = float(values.min())
    maximum = float(values.max())
    if minimum == maximum:
        padding = 1.0 if minimum == 0 else abs(minimum) * 0.05
        minimum -= padding
        maximum += padding
    axis.setRange(minimum, maximum)
