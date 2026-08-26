"""Desktop dialogs for inspecting saved capture artifacts."""

import json
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QDialog, QPlainTextEdit, QVBoxLayout
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

from instrument_capture_studio.data.trace_preview import load_trace_preview


class TraceViewerDialog(QDialog):
    """Plot one saved spectrum.npz or waveform.npz file."""

    def __init__(self, path: Path, parent=None) -> None:
        super().__init__(parent)
        path = Path(path)
        preview = load_trace_preview(path)

        self.setWindowTitle(f"{preview.title} · {path.parent.name}")
        self.resize(980, 620)

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

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        layout = QVBoxLayout(self)
        layout.addWidget(chart_view)


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


def _set_axis_range(axis: QValueAxis, values) -> None:
    minimum = float(values.min())
    maximum = float(values.max())
    if minimum == maximum:
        padding = 1.0 if minimum == 0 else abs(minimum) * 0.05
        minimum -= padding
        maximum += padding
    axis.setRange(minimum, maximum)
