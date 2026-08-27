"""Generate lightweight offline HTML reports for formal Recipe batches."""

import csv
from dataclasses import dataclass
from html import escape
from pathlib import Path

import numpy as np

from instrument_capture_studio.data.batch_manifest import load_batch_manifest
from instrument_capture_studio.data.timing import (
    BatchTimingSummary,
    TimingMetric,
    summarize_batch_timings,
)
from instrument_capture_studio.data.trace_preview import TracePreview, load_trace_preview


@dataclass(frozen=True)
class BatchReportResult:
    report_html: Path
    jobs_csv: Path
    timing_csv: Path
    asset_count: int


_TRACE_COLUMNS = (
    ("spectrum_ext.npz", "spectrum-ext", "查看 EXT 频谱"),
    ("spectrum_imm.npz", "spectrum-imm", "查看 IMM 频谱"),
    ("waveform_delay.npz", "waveform-delay", "查看 DELAY 波形"),
    ("waveform_cycle.npz", "waveform-cycle", "查看 CYCLE 波形"),
)

_TIMING_LABELS = {
    "frequency_config": "FSW 频率配置",
    "job_total": "完整 Job",
    "fsw_ext_arm": "FSW EXT ARM",
    "dsox_delay_group": "DSO-X DELAY 组",
    "fsw_ext_read": "FSW EXT wait/read",
    "dsox_cycle_group": "DSO-X CYCLE 组",
    "fsw_imm": "FSW IMM",
    "save_result": "保存结果",
}


def export_batch_report(
    manifest_path: Path,
    output_directory: Path | None = None,
) -> BatchReportResult:
    """Create an HTML summary plus representative formal Recipe traces.

    One representative successful Job is plotted for each frequency point. A
    paired training Job can contribute four traces: EXT spectrum, IMM spectrum,
    DELAY waveform and CYCLE_COUNT waveform. The full Job list stays in jobs.csv
    and persisted node timings are summarized as avg/P95/max in timing.csv.
    """

    manifest_path = Path(manifest_path)
    manifest = load_batch_manifest(manifest_path)
    destination = Path(output_directory or manifest_path.parent / "report")
    assets = destination / "assets"
    destination.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)

    jobs = manifest.get("jobs")
    jobs = jobs if isinstance(jobs, list) else []
    plan = manifest.get("plan")
    plan = plan if isinstance(plan, dict) else {}

    jobs_csv = destination / "jobs.csv"
    _write_jobs_csv(jobs_csv, jobs)

    timing_summary = summarize_batch_timings(manifest_path)
    timing_csv = destination / "timing.csv"
    _write_timing_csv(timing_csv, timing_summary)

    representatives = _representative_jobs_by_frequency(jobs)
    frequency_rows: list[str] = []
    asset_count = 0

    frequencies = plan.get("frequencies_hz")
    if not isinstance(frequencies, list):
        frequencies = sorted(representatives)

    for index, raw_frequency in enumerate(frequencies, start=1):
        try:
            frequency_hz = float(raw_frequency)
        except (TypeError, ValueError):
            continue
        record = representatives.get(frequency_hz)
        successful_count = _successful_count(jobs, frequency_hz)
        representative_job = "—"
        cells = {key: "—" for _filename, key, _label in _TRACE_COLUMNS}

        if record is not None:
            representative_job = escape(str(record.get("job_id") or ""))
            for filename, key, label in _TRACE_COLUMNS:
                trace_path = _find_output_file(record, filename)
                if trace_path is None or not trace_path.exists():
                    continue
                preview = load_trace_preview(trace_path)
                asset_name = f"f{index:03d}-{key}.svg"
                (assets / asset_name).write_text(
                    render_trace_svg(preview),
                    encoding="utf-8",
                )
                cells[key] = f'<a href="assets/{asset_name}">{label}</a>'
                asset_count += 1

        frequency_rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{frequency_hz / 1e6:g}</td>"
            f"<td>{successful_count}</td>"
            f"<td>{representative_job}</td>"
            f"<td>{cells['spectrum-ext']}</td>"
            f"<td>{cells['spectrum-imm']}</td>"
            f"<td>{cells['waveform-delay']}</td>"
            f"<td>{cells['waveform-cycle']}</td>"
            "</tr>"
        )

    report_html = destination / "report.html"
    report_html.write_text(
        _build_html(
            manifest=manifest,
            plan=plan,
            frequency_rows="\n".join(frequency_rows),
            jobs_csv_name=jobs_csv.name,
            timing_csv_name=timing_csv.name,
            timing_summary=timing_summary,
        ),
        encoding="utf-8",
    )

    return BatchReportResult(
        report_html=report_html,
        jobs_csv=jobs_csv,
        timing_csv=timing_csv,
        asset_count=asset_count,
    )


def render_trace_svg(
    preview: TracePreview,
    *,
    width: int = 1000,
    height: int = 420,
) -> str:
    """Render a saved trace to dependency-free SVG."""

    if width < 200 or height < 160:
        raise ValueError("SVG dimensions are too small")

    x = np.asarray(preview.x, dtype=np.float64)
    y = np.asarray(preview.y, dtype=np.float64)
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if x.size == 0:
        raise ValueError("trace does not contain finite points")

    left = 72.0
    right = 24.0
    top = 46.0
    bottom = 58.0
    plot_width = width - left - right
    plot_height = height - top - bottom

    x_min, x_max = _expanded_range(float(x.min()), float(x.max()))
    y_min, y_max = _expanded_range(float(y.min()), float(y.max()))

    px = left + (x - x_min) / (x_max - x_min) * plot_width
    py = top + (y_max - y) / (y_max - y_min) * plot_height
    points = " ".join(f"{a:.2f},{b:.2f}" for a, b in zip(px, py, strict=True))

    title = escape(preview.title)
    x_label = escape(preview.x_label)
    y_label = escape(preview.y_label)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{width / 2:.1f}" y="26" text-anchor="middle" font-family="Segoe UI,Arial" font-size="18" font-weight="600">{title}</text>
<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#667085" stroke-width="1"/>
<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#667085" stroke-width="1"/>
<polyline fill="none" stroke="#2f6fed" stroke-width="1.5" points="{points}"/>
<text x="{left}" y="{top + plot_height + 20}" font-family="Segoe UI,Arial" font-size="12">{x_min:g}</text>
<text x="{left + plot_width}" y="{top + plot_height + 20}" text-anchor="end" font-family="Segoe UI,Arial" font-size="12">{x_max:g}</text>
<text x="{left - 8}" y="{top + 5}" text-anchor="end" font-family="Segoe UI,Arial" font-size="12">{y_max:g}</text>
<text x="{left - 8}" y="{top + plot_height}" text-anchor="end" font-family="Segoe UI,Arial" font-size="12">{y_min:g}</text>
<text x="{left + plot_width / 2:.1f}" y="{height - 14}" text-anchor="middle" font-family="Segoe UI,Arial" font-size="13">{x_label}</text>
<text x="18" y="{top + plot_height / 2:.1f}" transform="rotate(-90 18 {top + plot_height / 2:.1f})" text-anchor="middle" font-family="Segoe UI,Arial" font-size="13">{y_label}</text>
</svg>'''


def _expanded_range(minimum: float, maximum: float) -> tuple[float, float]:
    if minimum != maximum:
        return minimum, maximum
    padding = 1.0 if minimum == 0 else abs(minimum) * 0.05
    return minimum - padding, maximum + padding


def _representative_jobs_by_frequency(
    jobs: list[object],
) -> dict[float, dict[str, object]]:
    representatives: dict[float, dict[str, object]] = {}
    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("state") or "").lower() != "succeeded":
            continue
        try:
            frequency_hz = float(raw.get("frequency_hz"))
        except (TypeError, ValueError):
            continue
        representatives.setdefault(frequency_hz, raw)
    return representatives


def _successful_count(jobs: list[object], frequency_hz: float) -> int:
    count = 0
    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("state") or "").lower() != "succeeded":
            continue
        try:
            candidate = float(raw.get("frequency_hz"))
        except (TypeError, ValueError):
            continue
        if candidate == frequency_hz:
            count += 1
    return count


def _find_output_file(
    record: dict[str, object],
    filename: str,
) -> Path | None:
    outputs = record.get("output_files")
    if not isinstance(outputs, list):
        return None
    for raw in outputs:
        path = Path(str(raw))
        if path.name == filename:
            return path
    return None


def _write_jobs_csv(path: Path, jobs: list[object]) -> None:
    fields = (
        "job_id",
        "state",
        "frequency_hz",
        "frequency_index",
        "capture_index",
        "attempt",
        "resume_sequence",
        "frequency_config_duration_ms",
        "started_at",
        "finished_at",
        "error",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for raw in jobs:
            if not isinstance(raw, dict):
                continue
            writer.writerow({field: raw.get(field) for field in fields})


def _timing_rows(summary: BatchTimingSummary):
    if summary.job_total is not None:
        yield "job_total", summary.job_total
    if summary.frequency_config is not None:
        yield "frequency_config", summary.frequency_config
    for name, metric in summary.steps.items():
        yield name, metric


def _write_timing_csv(path: Path, summary: BatchTimingSummary) -> None:
    fields = ("node", "label", "samples", "average_ms", "p95_ms", "max_ms")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for name, metric in _timing_rows(summary):
            writer.writerow(
                {
                    "node": name,
                    "label": _TIMING_LABELS.get(name, name),
                    "samples": metric.samples,
                    "average_ms": metric.average_ms,
                    "p95_ms": metric.p95_ms,
                    "max_ms": metric.max_ms,
                }
            )


def _timing_table(summary: BatchTimingSummary) -> str:
    rows = []
    for name, metric in _timing_rows(summary):
        rows.append(
            "<tr>"
            f"<td>{escape(_TIMING_LABELS.get(name, name))}</td>"
            f"<td>{metric.samples}</td>"
            f"<td>{metric.average_ms:g}</td>"
            f"<td>{metric.p95_ms:g}</td>"
            f"<td>{metric.max_ms:g}</td>"
            "</tr>"
        )
    if not rows:
        return '<tr><td colspan="5">暂无可汇总的成功 Job 时间数据</td></tr>'
    return "\n".join(rows)


def _build_html(
    *,
    manifest: dict[str, object],
    plan: dict[str, object],
    frequency_rows: str,
    jobs_csv_name: str,
    timing_csv_name: str,
    timing_summary: BatchTimingSummary,
) -> str:
    batch_id = escape(str(manifest.get("batch_id") or ""))
    state = escape(str(manifest.get("state") or "unknown").upper())
    completed = int(manifest.get("completed_captures") or 0)
    failed = int(manifest.get("failed_jobs") or 0)
    total = int(plan.get("total_captures") or 0)
    recovery_events = manifest.get("recovery_events")
    recovery_count = len(recovery_events) if isinstance(recovery_events, list) else 0

    def plan_value(key: str, divisor: float = 1.0) -> str:
        try:
            return f"{float(plan.get(key)) / divisor:g}"
        except (TypeError, ValueError):
            return "—"

    timing_rows = _timing_table(timing_summary)

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Instrument Capture Studio · {batch_id}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:28px;color:#17202a;background:#f7f8fa}}
.card{{background:white;border:1px solid #dfe3e8;border-radius:10px;padding:18px;margin-bottom:18px}}
h1,h2{{margin-top:0}} table{{border-collapse:collapse;width:100%;background:white}}
th,td{{border:1px solid #e4e7ec;padding:8px 10px;text-align:left}} th{{background:#f2f4f7}}
.kpi{{display:inline-block;margin-right:28px;margin-bottom:8px}} .value{{font-size:24px;font-weight:700}}
a{{color:#175cd3;text-decoration:none}}
</style>
</head>
<body>
<div class="card">
<h1>Instrument Capture Studio Batch Report</h1>
<div><strong>Batch ID：</strong>{batch_id}</div>
<div><strong>状态：</strong>{state}</div>
<div><strong>开始：</strong>{escape(str(manifest.get('started_at') or '—'))}</div>
<div><strong>结束：</strong>{escape(str(manifest.get('finished_at') or '—'))}</div>
</div>
<div class="card">
<h2>采集概览</h2>
<div class="kpi"><div class="value">{completed}/{total}</div><div>完成 / 总数</div></div>
<div class="kpi"><div class="value">{failed}</div><div>失败 Job</div></div>
<div class="kpi"><div class="value">{recovery_count}</div><div>自动恢复事件</div></div>
<p>频率：{plan_value('start_hz', 1e6)}–{plan_value('stop_hz', 1e6)} MHz，步长 {plan_value('step_hz', 1e6)} MHz，Span {plan_value('span_hz', 1e6)} MHz，每频点 {escape(str(plan.get('captures_per_frequency') or '—'))} 次。</p>
<p>正式配对样本：FSW EXT + FSW IMM + DSO-X DELAY 波形 + DSO-X CYCLE_COUNT 波形。</p>
<p><a href="{escape(jobs_csv_name)}">完整 Job 明细 CSV</a> · <a href="{escape(timing_csv_name)}">节点耗时 CSV</a></p>
</div>
<div class="card">
<h2>节点耗时统计</h2>
<p>仅统计成功 Job，失败 / 超时任务保留在 Job 明细中，不参与正常性能分布。</p>
<table>
<thead><tr><th>节点</th><th>样本数</th><th>平均 (ms)</th><th>P95 (ms)</th><th>最大 (ms)</th></tr></thead>
<tbody>
{timing_rows}
</tbody>
</table>
</div>
<div class="card">
<h2>频点结果</h2>
<table>
<thead><tr><th>#</th><th>中心频率 (MHz)</th><th>成功次数</th><th>代表 Job</th><th>EXT</th><th>IMM</th><th>DELAY 波形</th><th>CYCLE 波形</th></tr></thead>
<tbody>
{frequency_rows}
</tbody>
</table>
</div>
</body>
</html>'''
