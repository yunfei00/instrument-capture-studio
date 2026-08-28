"""Engineering dialog for qualifying the new paired acquisition sequence."""

from __future__ import annotations

import json

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from instrument_capture_studio.app.runtime import DSOXRuntimeSettings, FSWRuntimeSettings
from instrument_capture_studio.ui.recipe_debug_controller import RecipeDebugController


_STEP_ORDER = (
    "read_sweep_time",
    "configure_sync_scope",
    "arm_fsw_ext",
    "capture_sync_scope",
    "read_ext_spectrum",
    "configure_followup_scope",
    "capture_followup_scope",
    "capture_freerun_spectrum",
)

_STEP_TITLES = {
    "read_sweep_time": "1. 读取 FSW Sweep Time",
    "configure_sync_scope": "2. 配置示波器第一次时间窗口",
    "arm_fsw_ext": "3. FSW 设置 EXT 并 ARM",
    "capture_sync_scope": "4. 示波器第一次采集 / 触发 FSW",
    "read_ext_spectrum": "5. 读取 FSW EXT 频谱",
    "configure_followup_scope": "6. 配置示波器第二次时间窗口",
    "capture_followup_scope": "7. 示波器第二次独立采集",
    "capture_freerun_spectrum": "8. FSW Free Run 再采一次频谱",
}


class RecipeDebugDialog(QDialog):
    """Keep one pair of VISA sessions alive while advancing the recipe manually."""

    def __init__(
        self,
        fsw_settings: FSWRuntimeSettings,
        dsox_settings: DSOXRuntimeSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._fsw_settings = fsw_settings
        self._dsox_settings = dsox_settings
        self._controller = RecipeDebugController(self)
        self._state = "idle"
        self._busy = False
        self._close_after_reset = False

        self.setWindowTitle("工程调试 · 新采集流程单步验证")
        self.resize(980, 760)
        self.setMinimumSize(860, 650)
        self._build_ui()
        self._wire_signals()
        self._update_controls()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        notice = QLabel(
            "此窗口只做真机单步资格验证，不会改写当前正式 Workflow 或保存正式样本。"
            "FSW 的中心频率 / Span / RBW / VBW / Sweep Time 由测试人员预先在仪表上配置；"
            "调试流程只读取 Sweep Time，并切换 EXT / Free Run Trigger。"
        )
        notice.setWordWrap(True)
        root.addWidget(notice)

        summary_group = QGroupBox("调试参数")
        summary = QFormLayout(summary_group)
        summary.addRow("FSW VISA", QLabel(self._fsw_settings.resource))
        summary.addRow("DSO-X VISA", QLabel(self._dsox_settings.resource))
        summary.addRow("Waveform Channel", QLabel(f"CH{self._dsox_settings.waveform_channel}"))

        self.followup_position_ms_edit = QLineEdit("484")
        self.followup_position_ms_edit.setObjectName("debugFollowupPositionMsEdit")
        self.followup_scale_ns_edit = QLineEdit("20")
        self.followup_scale_ns_edit.setObjectName("debugFollowupScaleNsEdit")
        summary.addRow("第二次 Horizontal Position (ms)", self.followup_position_ms_edit)
        summary.addRow("第二次 Horizontal Scale (ns/div)", self.followup_scale_ns_edit)

        self.sweep_value_label = QLabel("未读取")
        self.auto_position_label = QLabel("未计算")
        self.auto_scale_label = QLabel("未计算")
        summary.addRow("FSW Sweep Time", self.sweep_value_label)
        summary.addRow("第一次 Position = Sweep/2", self.auto_position_label)
        summary.addRow("第一次 Scale = Sweep/10", self.auto_scale_label)
        root.addWidget(summary_group)

        action_group = QGroupBox("单步执行")
        grid = QGridLayout(action_group)
        self.start_button = QPushButton("建立调试会话")
        self.reset_button = QPushButton("复位调试状态")
        grid.addWidget(self.start_button, 0, 0, 1, 2)
        grid.addWidget(self.reset_button, 0, 2, 1, 2)

        self.step_buttons: dict[str, QPushButton] = {}
        for index, step_name in enumerate(_STEP_ORDER):
            button = QPushButton(_STEP_TITLES[step_name])
            button.setObjectName(f"debugStep{index + 1}Button")
            self.step_buttons[step_name] = button
            row = 1 + index // 2
            col = (index % 2) * 2
            grid.addWidget(button, row, col, 1, 2)
        root.addWidget(action_group)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("当前状态："))
        self.state_label = QLabel("IDLE")
        self.state_label.setObjectName("debugStateLabel")
        status_row.addWidget(self.state_label)
        status_row.addStretch(1)
        root.addLayout(status_row)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("每一步的 SCPI、回读值、PASS / FAIL 会显示在这里。")
        root.addWidget(self.log_edit, 1)

    def _wire_signals(self) -> None:
        self.start_button.clicked.connect(self._start_session)
        self.reset_button.clicked.connect(self._reset_session)
        for step_name, button in self.step_buttons.items():
            button.clicked.connect(
                lambda _checked=False, name=step_name: self._run_step(name)
            )

        self._controller.log.connect(self._append_log)
        self._controller.session_started.connect(self._on_session_started)
        self._controller.step_finished.connect(self._on_step_finished)
        self._controller.step_failed.connect(self._on_step_failed)
        self._controller.session_reset.connect(self._on_session_reset)

    def _start_session(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._append_log("\n=== 建立新的单步调试会话 ===")
        self._update_controls()
        self._controller.start_session(self._fsw_settings, self._dsox_settings)

    def _reset_session(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._append_log("\n=== 请求复位调试会话 ===")
        self._update_controls()
        self._controller.reset_session()

    def _run_step(self, step_name: str) -> None:
        if self._busy:
            return
        parameters: dict[str, float] = {}
        if step_name == "configure_followup_scope":
            try:
                position_ms = float(self.followup_position_ms_edit.text().strip())
                scale_ns = float(self.followup_scale_ns_edit.text().strip())
            except ValueError:
                QMessageBox.warning(self, "参数错误", "第二次 Position / Scale 必须是数字。")
                return
            if position_ms < 0 or scale_ns <= 0:
                QMessageBox.warning(
                    self,
                    "参数错误",
                    "Horizontal Position 必须 >= 0，Horizontal Scale 必须 > 0。",
                )
                return
            parameters = {
                "position_s": position_ms * 1e-3,
                "scale_s_per_div": scale_ns * 1e-9,
            }

        self._busy = True
        self._append_log(f"\n>>> {_STEP_TITLES[step_name]}")
        self._update_controls()
        self._controller.run_step(step_name, parameters)

    def _on_session_started(self, payload: dict) -> None:
        self._busy = False
        self._state = str(payload.get("state", "connected"))
        self._append_payload(payload)
        self._update_controls()

    def _on_step_finished(self, step_name: str, payload: dict) -> None:
        self._busy = False
        self._state = str(payload.get("state", self._state))
        if step_name == "read_sweep_time":
            sweep_s = float(payload["sweep_time_s"])
            position_s = float(payload["sync_position_s"])
            scale_s = float(payload["sync_scale_s_per_div"])
            self.sweep_value_label.setText(f"{sweep_s:g} s  ({sweep_s * 1e3:g} ms)")
            self.auto_position_label.setText(
                f"{position_s:g} s  ({position_s * 1e3:g} ms)"
            )
            self.auto_scale_label.setText(
                f"{scale_s:g} s/div  ({scale_s * 1e3:g} ms/div)"
            )
        self._append_payload(payload)
        if self._state == "fsw_armed":
            self._append_log("[提示] FSW 当前正在等待 EXT Trigger；下一步执行示波器第一次采集。")
        if self._state == "complete":
            self._append_log("\n=== 8 个单步全部完成：新硬件时序已跑通，可开始核对数据/屏幕 ===")
        self._update_controls()

    def _on_step_failed(self, step_name: str, error_type: str, message: str) -> None:
        self._busy = False
        self._append_log(f"[FAIL] {step_name}: {error_type}: {message}")
        self._append_log("[提示] 当前调试会话状态不自动跳步；建议先点击“复位调试状态”再重试。")
        self._update_controls(force_reset_only=True)

    def _on_session_reset(self, payload: dict) -> None:
        self._busy = False
        self._state = "idle"
        self._append_payload(payload)
        self._update_controls()
        if self._close_after_reset:
            self._close_after_reset = False
            QTimer.singleShot(0, self.close)

    def _append_payload(self, payload: dict) -> None:
        scpi = payload.get("scpi")
        if isinstance(scpi, list):
            for command in scpi:
                self._append_log(f"SCPI  {command}")
        elif scpi:
            self._append_log(f"SCPI  {scpi}")
        clean_payload = {key: value for key, value in payload.items() if key != "scpi"}
        self._append_log(json.dumps(clean_payload, ensure_ascii=False, indent=2, default=str))

    def _append_log(self, message: str) -> None:
        self.log_edit.appendPlainText(str(message))

    def _update_controls(self, *, force_reset_only: bool = False) -> None:
        self.state_label.setText(self._state.upper())
        self.start_button.setEnabled(not self._busy and self._state == "idle")
        self.reset_button.setEnabled(not self._busy and self._state != "idle")

        enabled_step = None
        state_to_step = {
            "connected": "read_sweep_time",
            "sweep_time_read": "configure_sync_scope",
            "sync_scope_configured": "arm_fsw_ext",
            "fsw_armed": "capture_sync_scope",
            "sync_scope_captured": "read_ext_spectrum",
            "ext_spectrum_read": "configure_followup_scope",
            "followup_scope_configured": "capture_followup_scope",
            "followup_scope_captured": "capture_freerun_spectrum",
        }
        if not force_reset_only:
            enabled_step = state_to_step.get(self._state)
        for name, button in self.step_buttons.items():
            button.setEnabled(not self._busy and name == enabled_step)

        followup_editable = (
            not self._busy
            and self._state in {"connected", "sweep_time_read", "sync_scope_configured", "fsw_armed", "sync_scope_captured", "ext_spectrum_read"}
        )
        self.followup_position_ms_edit.setEnabled(followup_editable)
        self.followup_scale_ns_edit.setEnabled(followup_editable)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._state != "idle" and not self._close_after_reset:
            self._close_after_reset = True
            self._append_log("\n关闭请求：先安全复位 FSW/DSO-X 调试状态，再关闭窗口。")
            self._busy = False
            self._reset_session()
            event.ignore()
            return
        self._controller.shutdown()
        event.accept()
