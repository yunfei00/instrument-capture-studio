"""Long-session capture controls layered on the delivery-ready workspace."""

from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil
from pathlib import Path
from time import monotonic

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
from instrument_capture_studio.data.time_estimate import estimate_capture_time
from instrument_capture_studio.ui.delivery_window import MainWindow as DeliveryWindow


class MainWindow(DeliveryWindow):
    """Delivery workspace with long-session planning and safe timed pauses."""

    def __init__(self) -> None:
        self._batch_total_captures = 0
        self._batch_completed_captures = 0
        self._batch_active_accumulated_s = 0.0
        self._batch_segment_started: float | None = None
        self._batch_wall_started: datetime | None = None
        self._auto_pause_deadline: float | None = None
        self._auto_pause_requested = False
        self._history_cache_root: str | None = None
        self._history_seconds_per_capture: float | None = None
        self._history_samples = 0
        self._history_batches = 0
        super().__init__()
        self._install_long_session_controls()
        # These controls are created after the inherited preference restore.
        self._preferences.restore(self)
        self._wire_long_session_controls()
        self._long_session_timer = QTimer(self)
        self._long_session_timer.setInterval(1000)
        self._long_session_timer.timeout.connect(self._on_long_session_tick)
        self._long_session_timer.start()
        self._sync_long_session_controls()
        self._refresh_time_estimate()

    # ------------------------------------------------------------------
    # Installation and preferences
    # ------------------------------------------------------------------
    def _install_long_session_controls(self) -> None:
        card = self.commercial_task_parameter_card
        grid = card.layout() if card is not None else None
        if not isinstance(grid, QGridLayout):
            raise RuntimeError("task parameter card must use QGridLayout")

        row = grid.rowCount()
        self.auto_pause_checkbox = QCheckBox("启用", card)
        self.auto_pause_checkbox.setObjectName("autoPauseCheckBox")
        self.auto_pause_checkbox.setChecked(True)

        self.auto_pause_minutes_spin = QSpinBox(card)
        self.auto_pause_minutes_spin.setObjectName("autoPauseMinutesSpin")
        self.auto_pause_minutes_spin.setRange(1, 24 * 60)
        self.auto_pause_minutes_spin.setValue(55)
        self.auto_pause_minutes_spin.setSuffix(" 分钟")
        self.auto_pause_minutes_spin.setToolTip(
            "达到设定时间后不会中断当前仪表操作；当前完整逻辑样本保存完成后安全暂停。"
        )

        timer_controls = QWidget(card)
        timer_layout = QHBoxLayout(timer_controls)
        timer_layout.setContentsMargins(0, 0, 0, 0)
        timer_layout.setSpacing(10)
        timer_layout.addWidget(self.auto_pause_checkbox)
        timer_layout.addWidget(self.auto_pause_minutes_spin)
        timer_layout.addStretch(1)

        self.capture_time_estimate_label = QLabel(card)
        self.capture_time_estimate_label.setObjectName("longSessionEstimate")
        self.capture_time_estimate_label.setWordWrap(True)

        self.capture_runtime_label = QLabel("尚未开始批量采集", card)
        self.capture_runtime_label.setObjectName("longSessionRuntime")
        self.capture_runtime_label.setWordWrap(True)

        grid.addWidget(QLabel("自动暂停", card), row, 0)
        grid.addWidget(timer_controls, row, 1, 1, 3)
        grid.addWidget(QLabel("采集时间评估", card), row + 1, 0)
        grid.addWidget(self.capture_time_estimate_label, row + 1, 1, 1, 3)
        grid.addWidget(QLabel("运行时间", card), row + 2, 0)
        grid.addWidget(self.capture_runtime_label, row + 2, 1, 1, 3)

    def _wire_long_session_controls(self) -> None:
        self.auto_pause_checkbox.toggled.connect(self._save_preferences)
        self.auto_pause_checkbox.toggled.connect(self._sync_long_session_controls)
        self.auto_pause_checkbox.toggled.connect(self._refresh_time_estimate)
        self.auto_pause_minutes_spin.valueChanged.connect(self._save_preferences)
        self.auto_pause_minutes_spin.valueChanged.connect(self._refresh_time_estimate)
        self.output_root_edit.editingFinished.connect(self._invalidate_history_estimate)

    def _invalidate_history_estimate(self, *_args) -> None:
        self._history_cache_root = None
        self._history_seconds_per_capture = None
        self._history_samples = 0
        self._history_batches = 0
        self._refresh_time_estimate()

    # ------------------------------------------------------------------
    # Parent hooks
    # ------------------------------------------------------------------
    def _sync_recipe_controls(self, *_args) -> None:
        super()._sync_recipe_controls(*_args)
        if hasattr(self, "auto_pause_checkbox"):
            self._sync_long_session_controls()
            self._refresh_time_estimate()

    def _sync_sweep_mode(self, *_args) -> None:
        super()._sync_sweep_mode(*_args)
        if hasattr(self, "auto_pause_checkbox"):
            self._sync_long_session_controls()
            self._refresh_time_estimate()

    def _update_sweep_summary(self, *_args) -> None:
        super()._update_sweep_summary(*_args)
        if hasattr(self, "capture_time_estimate_label"):
            self._refresh_time_estimate()

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "auto_pause_checkbox"):
            self._sync_long_session_controls()

    def _on_batch_started(self, batch_id: str, total_captures: int) -> None:
        super()._on_batch_started(batch_id, total_captures)
        self._batch_total_captures = total_captures
        self._batch_completed_captures = 0
        self._batch_active_accumulated_s = 0.0
        self._batch_segment_started = monotonic()
        self._batch_wall_started = datetime.now()
        self._arm_auto_pause_cycle()
        self._refresh_runtime_status()

    def _on_batch_progress(self, progress) -> None:
        super()._on_batch_progress(progress)
        self._batch_total_captures = progress.total_captures
        self._batch_completed_captures = progress.completed_captures
        self._refresh_runtime_status()

    def _on_batch_pause_changed(
        self,
        paused: bool,
        batch_id: str,
        completed: int,
        total: int,
    ) -> None:
        now = monotonic()
        if paused:
            self._stop_active_segment(now)
            self._auto_pause_deadline = None
        super()._on_batch_pause_changed(paused, batch_id, completed, total)
        self._batch_completed_captures = completed
        self._batch_total_captures = total
        if not paused:
            self._batch_segment_started = monotonic()
            self._arm_auto_pause_cycle()
        self._refresh_runtime_status()

    def _on_batch_finished(self, result) -> None:
        self._stop_active_segment(monotonic())
        self._auto_pause_deadline = None
        self._auto_pause_requested = False
        self._batch_completed_captures = result.completed_captures
        self._batch_total_captures = result.total_captures
        active = self._batch_active_accumulated_s
        super()._on_batch_finished(result)
        self.capture_runtime_label.setText(
            f"本次 Batch 已结束 · 有效运行 {_format_duration(active)} · "
            f"完成 {result.completed_captures}/{result.total_captures}"
        )
        # The just-finished batch is useful history for the next estimate.
        self._history_cache_root = None
        self._refresh_time_estimate()

    # ------------------------------------------------------------------
    # Time estimation
    # ------------------------------------------------------------------
    def _current_batch_plan(self) -> FrequencySweepPlan | None:
        if self._selected_recipe() is not CaptureRecipe.EXT_IMM_PAIR:
            return None
        mode = self._selected_execution_mode()
        if mode is ExecutionMode.SINGLE:
            return None
        try:
            if mode is ExecutionMode.FREQUENCY_SWEEP:
                return self._build_sweep_plan()
            center_hz = self._required_float(self.center_hz_edit, "中心频率")
            span_hz = self._required_float(self.span_hz_edit, "Span")
            return FrequencySweepPlan(
                start_hz=center_hz,
                stop_hz=center_hz,
                step_hz=1.0,
                span_hz=span_hz,
                captures_per_frequency=self.repeat_capture_count_spin.value(),
            )
        except ValueError:
            return None

    def _historical_seconds(self) -> float | None:
        root_text = self.output_root_edit.text().strip()
        if not root_text:
            return None
        if self._history_cache_root == root_text:
            return self._history_seconds_per_capture

        self._history_cache_root = root_text
        self._history_seconds_per_capture = None
        self._history_samples = 0
        self._history_batches = 0
        estimate = estimate_capture_time(
            Path(root_text).expanduser(),
            total_captures=1,
        )
        if estimate is not None:
            self._history_seconds_per_capture = estimate.seconds_per_capture
            self._history_samples = estimate.samples
            self._history_batches = estimate.batches
        return self._history_seconds_per_capture

    def _refresh_time_estimate(self, *_args) -> None:
        if not hasattr(self, "capture_time_estimate_label"):
            return
        plan = self._current_batch_plan()
        if plan is None:
            self.capture_time_estimate_label.setText(
                "批量模式启用后显示预计总时长；单次采集不启用自动暂停。"
            )
            return

        per_capture = self._historical_seconds()
        cycle_minutes = self.auto_pause_minutes_spin.value()
        auto_pause = self.auto_pause_checkbox.isChecked()
        prefix = (
            f"{plan.frequency_count} 个频点 · "
            f"{plan.total_captures} 个完整逻辑样本"
        )
        if per_capture is None:
            suffix = "暂无历史成功样本，完成首个样本后将按实际速度动态估算。"
            if auto_pause:
                suffix += f" 当前设置每 {cycle_minutes} 分钟安全自动暂停。"
            self.capture_time_estimate_label.setText(f"{prefix} · {suffix}")
            return

        total_seconds = per_capture * plan.total_captures
        text = (
            f"{prefix} · 历史平均 {per_capture:.1f}s/样本 · "
            f"预计总时长 {_format_duration(total_seconds)}"
        )
        if auto_pause:
            cycles = max(1, ceil(total_seconds / (cycle_minutes * 60.0)))
            text += f" · 约 {cycles} 个 {cycle_minutes} 分钟运行周期"
        text += f" · 基于 {self._history_samples} 个成功样本"
        self.capture_time_estimate_label.setText(text)

    # ------------------------------------------------------------------
    # Safe automatic pause and live ETA
    # ------------------------------------------------------------------
    def _batch_mode_active(self) -> bool:
        if not getattr(self, "_capture_busy", False):
            return False
        if self._selected_recipe() is not CaptureRecipe.EXT_IMM_PAIR:
            return False
        return self._selected_execution_mode() is not ExecutionMode.SINGLE

    def _sync_long_session_controls(self, *_args) -> None:
        if not hasattr(self, "auto_pause_checkbox"):
            return
        batch_mode = (
            self._selected_recipe() is CaptureRecipe.EXT_IMM_PAIR
            and self._selected_execution_mode() is not ExecutionMode.SINGLE
        )
        editable = batch_mode and not self._capture_busy
        self.auto_pause_checkbox.setEnabled(editable)
        self.auto_pause_minutes_spin.setEnabled(
            editable and self.auto_pause_checkbox.isChecked()
        )

    def _arm_auto_pause_cycle(self) -> None:
        self._auto_pause_requested = False
        if not self._batch_mode_active() or not self.auto_pause_checkbox.isChecked():
            self._auto_pause_deadline = None
            return
        self._auto_pause_deadline = (
            monotonic() + self.auto_pause_minutes_spin.value() * 60.0
        )

    def _stop_active_segment(self, now: float) -> None:
        if self._batch_segment_started is not None:
            self._batch_active_accumulated_s += max(
                0.0,
                now - self._batch_segment_started,
            )
            self._batch_segment_started = None

    def _active_elapsed(self, now: float | None = None) -> float:
        value = self._batch_active_accumulated_s
        if self._batch_segment_started is not None:
            current = monotonic() if now is None else now
            value += max(0.0, current - self._batch_segment_started)
        return value

    def _on_long_session_tick(self) -> None:
        if not hasattr(self, "capture_runtime_label"):
            return
        self._refresh_runtime_status()
        if (
            not self._batch_mode_active()
            or self._batch_is_paused
            or self._auto_pause_deadline is None
            or self._auto_pause_requested
        ):
            return

        remaining = self._auto_pause_deadline - monotonic()
        if remaining > 0:
            return

        self._auto_pause_requested = True
        minutes = self.auto_pause_minutes_spin.value()
        self._append_log(
            f"自动暂停计时达到 {minutes} 分钟；等待当前完整逻辑样本结束后安全暂停。"
        )
        self.statusBar().showMessage(
            "自动暂停时间已到；当前完整逻辑样本保存完成后暂停。"
        )
        self._toggle_pause()

    def _refresh_runtime_status(self) -> None:
        if not hasattr(self, "capture_runtime_label"):
            return
        if not self._batch_mode_active():
            if not self._capture_busy:
                self.capture_runtime_label.setText("尚未开始批量采集")
            return

        active = self._active_elapsed()
        completed = max(0, self._batch_completed_captures)
        total = max(0, self._batch_total_captures)
        parts = [
            f"有效运行 {_format_duration(active)}",
            f"已完成 {completed}/{total}",
        ]

        if completed > 0 and total > completed:
            average_s = active / completed
            remaining_s = average_s * (total - completed)
            finish_at = datetime.now() + timedelta(seconds=remaining_s)
            parts.append(f"平均 {average_s:.1f}s/样本")
            parts.append(f"预计剩余 {_format_duration(remaining_s)}")
            parts.append(f"预计完成 {finish_at:%H:%M}")
        elif completed == 0:
            historical = self._historical_seconds()
            if historical is not None and total > 0:
                parts.append(f"历史平均 {historical:.1f}s/样本")
                parts.append(
                    f"预计剩余 {_format_duration(historical * total)}"
                )

        if self._batch_is_paused:
            parts.append("当前已暂停")
        elif self._auto_pause_requested:
            parts.append("自动暂停已请求，等待当前样本完成")
        elif self._auto_pause_deadline is not None:
            remaining_cycle = max(0.0, self._auto_pause_deadline - monotonic())
            parts.append(f"本轮剩余 {_format_duration(remaining_cycle)}")

        self.capture_runtime_label.setText(" · ".join(parts))


def _format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"
