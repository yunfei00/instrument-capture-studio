"""PySide6 main window for Instrument Capture Studio."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from instrument_capture_studio.app.runtime import (
    DSOXRuntimeSettings,
    FSWRuntimeSettings,
)
from instrument_capture_studio.ui.controller import HardwareController


class MainWindow(QMainWindow):
    """Commercial desktop UI for one DSO-X + FSW capture station."""

    def __init__(self) -> None:
        super().__init__()
        self._capture_busy = False
        self._controller = HardwareController(self)

        self.setWindowTitle("Instrument Capture Studio")
        self.resize(1280, 820)
        self.setMinimumSize(1050, 700)

        self._build_ui()
        self._apply_style()
        self._wire_actions()
        self._refresh_data_tree()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        root.addWidget(self._build_header())

        content_splitter = QSplitter(Qt.Orientation.Vertical)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.addWidget(self._build_control_area())
        content_splitter.addWidget(self._build_bottom_area())
        content_splitter.setStretchFactor(0, 4)
        content_splitter.setStretchFactor(1, 3)

        root.addWidget(content_splitter, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪 · Phase 6 Alpha")

    def _build_header(self) -> QWidget:
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)

        title_box = QVBoxLayout()
        title = QLabel("Instrument Capture Studio")
        title.setObjectName("pageTitle")
        subtitle = QLabel("DSO-X 3034A + R&S FSW 联合采集")
        subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        badge = QLabel("PHASE 6 · ALPHA")
        badge.setObjectName("alphaBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setMinimumWidth(130)

        layout.addLayout(title_box)
        layout.addStretch(1)
        layout.addWidget(badge)
        return frame

    def _build_control_area(self) -> QWidget:
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        layout.addWidget(self._build_fsw_group(), 0, 0)
        layout.addWidget(self._build_dsox_group(), 0, 1)
        layout.addWidget(self._build_capture_group(), 1, 0, 1, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        return container

    def _build_fsw_group(self) -> QGroupBox:
        group = QGroupBox("频谱仪 · R&S FSW")
        grid = QGridLayout(group)

        self.fsw_resource_edit = QLineEdit()
        self.fsw_resource_edit.setObjectName("fswResourceEdit")
        self.fsw_resource_edit.setPlaceholderText(
            "例如 TCPIP0::192.168.1.10::inst0::INSTR"
        )
        self.fsw_status_label = self._status_label("未测试")
        self.fsw_connect_button = QPushButton("测试连接")
        self.fsw_connect_button.setObjectName("fswConnectButton")

        grid.addWidget(QLabel("VISA 地址"), 0, 0)
        grid.addWidget(self.fsw_resource_edit, 0, 1, 1, 3)
        grid.addWidget(QLabel("状态"), 1, 0)
        grid.addWidget(self.fsw_status_label, 1, 1)
        grid.addWidget(self.fsw_connect_button, 1, 2, 1, 2)

        params = QWidget()
        form = QFormLayout(params)
        form.setContentsMargins(0, 6, 0, 0)

        self.center_hz_edit = self._number_edit("600000000")
        self.span_hz_edit = self._number_edit("200000000")
        self.rbw_hz_edit = self._number_edit("1000000")
        self.vbw_hz_edit = self._number_edit("1000000")
        self.trigger_source_combo = QComboBox()
        self.trigger_source_combo.addItems(["IMM", "EXT"])
        self.fsw_timeout_edit = self._number_edit("30")

        form.addRow("中心频率 (Hz)", self.center_hz_edit)
        form.addRow("Span (Hz)", self.span_hz_edit)
        form.addRow("RBW (Hz)", self.rbw_hz_edit)
        form.addRow("VBW (Hz)", self.vbw_hz_edit)
        form.addRow("Trigger", self.trigger_source_combo)
        form.addRow("Step Timeout (s)", self.fsw_timeout_edit)
        grid.addWidget(params, 2, 0, 1, 4)
        return group

    def _build_dsox_group(self) -> QGroupBox:
        group = QGroupBox("示波器 · Keysight DSO-X 3034A")
        grid = QGridLayout(group)

        self.dsox_resource_edit = QLineEdit()
        self.dsox_resource_edit.setObjectName("dsoxResourceEdit")
        self.dsox_resource_edit.setPlaceholderText(
            "例如 TCPIP0::192.168.1.20::inst0::INSTR"
        )
        self.dsox_status_label = self._status_label("未测试")
        self.dsox_connect_button = QPushButton("测试连接")
        self.dsox_connect_button.setObjectName("dsoxConnectButton")

        grid.addWidget(QLabel("VISA 地址"), 0, 0)
        grid.addWidget(self.dsox_resource_edit, 0, 1, 1, 3)
        grid.addWidget(QLabel("状态"), 1, 0)
        grid.addWidget(self.dsox_status_label, 1, 1)
        grid.addWidget(self.dsox_connect_button, 1, 2, 1, 2)

        params = QWidget()
        form = QFormLayout(params)
        form.setContentsMargins(0, 6, 0, 0)

        self.delay_source1_edit = QLineEdit("CHANnel1")
        self.delay_source2_edit = QLineEdit("CHANnel2")
        self.delay_edge1_combo = QComboBox()
        self.delay_edge1_combo.addItems(["+1", "-1"])
        self.delay_edge2_combo = QComboBox()
        self.delay_edge2_combo.addItems(["+1", "-1"])
        self.cycle_source_edit = QLineEdit("CHANnel1")
        self.waveform_channel_spin = QSpinBox()
        self.waveform_channel_spin.setRange(1, 4)
        self.waveform_channel_spin.setValue(1)

        form.addRow("DELAY Source 1", self.delay_source1_edit)
        form.addRow("DELAY Source 2", self.delay_source2_edit)
        form.addRow("DELAY Edge 1", self.delay_edge1_combo)
        form.addRow("DELAY Edge 2", self.delay_edge2_combo)
        form.addRow("Cycle Count Source", self.cycle_source_edit)
        form.addRow("Waveform Channel", self.waveform_channel_spin)
        grid.addWidget(params, 2, 0, 1, 4)
        return group

    def _build_capture_group(self) -> QGroupBox:
        group = QGroupBox("联合采集")
        layout = QGridLayout(group)

        self.output_root_edit = QLineEdit(
            str(Path.home() / "InstrumentCaptureStudio" / "data")
        )
        self.output_root_edit.setObjectName("outputRootEdit")
        self.output_browse_button = QPushButton("浏览…")
        self.output_browse_button.setObjectName("outputBrowseButton")

        self.job_state_label = self._status_label("IDLE")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("等待采集")

        self.start_button = QPushButton("开始采集")
        self.start_button.setObjectName("startCaptureButton")
        self.start_button.setProperty("primary", True)
        self.stop_button = QPushButton("停止采集")
        self.stop_button.setObjectName("stopCaptureButton")
        self.stop_button.setEnabled(False)

        layout.addWidget(QLabel("数据目录"), 0, 0)
        layout.addWidget(self.output_root_edit, 0, 1, 1, 4)
        layout.addWidget(self.output_browse_button, 0, 5)
        layout.addWidget(QLabel("Job 状态"), 1, 0)
        layout.addWidget(self.job_state_label, 1, 1)
        layout.addWidget(self.progress_bar, 1, 2, 1, 2)
        layout.addWidget(self.start_button, 1, 4)
        layout.addWidget(self.stop_button, 1, 5)

        note = QLabel(
            "连接测试在后台打开仪表并读取身份后自动断开；正式采集由 Capture Job 管理连接生命周期。"
        )
        note.setObjectName("alphaNote")
        note.setWordWrap(True)
        layout.addWidget(note, 2, 0, 1, 6)
        return group

    def _build_bottom_area(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3000)
        self.log_view.setPlaceholderText("连接、采集、超时、取消和错误信息将在这里显示。")
        log_layout.addWidget(self.log_view)

        data_group = QGroupBox("数据浏览")
        data_layout = QVBoxLayout(data_group)
        toolbar = QHBoxLayout()
        self.refresh_data_button = QPushButton("刷新")
        self.open_data_button = QPushButton("选择数据目录…")
        toolbar.addWidget(self.refresh_data_button)
        toolbar.addWidget(self.open_data_button)
        toolbar.addStretch(1)
        self.data_tree = QTreeWidget()
        self.data_tree.setObjectName("dataTree")
        self.data_tree.setHeaderLabels(["文件", "类型 / 大小"])
        self.data_tree.setAlternatingRowColors(True)
        data_layout.addLayout(toolbar)
        data_layout.addWidget(self.data_tree)

        splitter.addWidget(log_group)
        splitter.addWidget(data_group)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        return splitter

    def _wire_actions(self) -> None:
        self.output_browse_button.clicked.connect(self._choose_output_root)
        self.open_data_button.clicked.connect(self._choose_output_root)
        self.refresh_data_button.clicked.connect(self._refresh_data_tree)
        self.fsw_connect_button.clicked.connect(self._test_fsw_connection)
        self.dsox_connect_button.clicked.connect(self._test_dsox_connection)
        self.start_button.clicked.connect(self._start_capture)
        self.stop_button.clicked.connect(self._stop_capture)

        self._controller.log.connect(self._append_log)
        self._controller.instrument_tested.connect(self._on_instrument_tested)
        self._controller.instrument_test_failed.connect(
            self._on_instrument_test_failed
        )
        self._controller.capture_started.connect(self._on_capture_started)
        self._controller.capture_finished.connect(self._on_capture_finished)
        self._controller.capture_failed.connect(self._on_capture_failed)

    def _test_fsw_connection(self) -> None:
        try:
            settings = self._build_fsw_settings()
        except ValueError as exc:
            self._show_input_error(str(exc))
            return

        self.fsw_status_label.setText("测试中")
        self.fsw_connect_button.setEnabled(False)
        self._controller.test_fsw(settings)

    def _test_dsox_connection(self) -> None:
        try:
            settings = self._build_dsox_settings()
        except ValueError as exc:
            self._show_input_error(str(exc))
            return

        self.dsox_status_label.setText("测试中")
        self.dsox_connect_button.setEnabled(False)
        self._controller.test_dsox(settings)

    def _start_capture(self) -> None:
        try:
            fsw_settings = self._build_fsw_settings()
            dsox_settings = self._build_dsox_settings()
        except ValueError as exc:
            self._show_input_error(str(exc))
            return

        output_root = self.output_root_edit.text().strip()
        if not output_root:
            self._show_input_error("数据目录不能为空")
            return

        self._set_capture_busy(True)
        self.job_state_label.setText("STARTING")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("正在启动采集…")
        self._controller.start_capture(fsw_settings, dsox_settings, output_root)

    def _stop_capture(self) -> None:
        if not self._capture_busy:
            return
        self.job_state_label.setText("CANCELING")
        self.progress_bar.setFormat("正在安全停止…")
        self.stop_button.setEnabled(False)
        self._controller.cancel_capture()

    def _on_instrument_tested(self, key: str, payload: dict) -> None:
        label, button = self._instrument_widgets(key)
        label.setText("可用")
        label.setToolTip(
            "\n".join(
                filter(
                    None,
                    [
                        payload.get("model"),
                        payload.get("serial_number"),
                        payload.get("firmware_version"),
                        payload.get("address"),
                    ],
                )
            )
        )
        button.setEnabled(not self._capture_busy)

    def _on_instrument_test_failed(
        self,
        key: str,
        error_type: str,
        message: str,
    ) -> None:
        label, button = self._instrument_widgets(key)
        label.setText("失败")
        label.setToolTip(f"{error_type}: {message}")
        button.setEnabled(not self._capture_busy)

    def _on_capture_started(self, job_id: str) -> None:
        self.job_state_label.setText("RUNNING")
        self.progress_bar.setFormat(f"采集中 · {job_id}")
        self._append_log(f"Job ID：{job_id}")
        self.statusBar().showMessage(f"正在采集 · {job_id}")

    def _on_capture_finished(self, result) -> None:
        self._set_capture_busy(False)
        state = result.state.value.upper()
        self.job_state_label.setText(state)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if state == "SUCCEEDED" else 0)
        self.progress_bar.setFormat(state)

        for step in result.steps:
            line = f"{step.name}: {step.state.value}"
            if step.error:
                line += f" · {step.error}"
            self._append_log(line)

        if result.output_files:
            self._append_log("输出文件：")
            for path in result.output_files:
                self._append_log(f"  {path}")

        self._refresh_data_tree()
        self.statusBar().showMessage(f"采集结束 · {state}", 8000)

    def _on_capture_failed(self, error_type: str, message: str) -> None:
        self._set_capture_busy(False)
        self.job_state_label.setText("FAILED")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("FAILED")
        self._append_log(f"FAILED · {error_type}: {message}")
        self._refresh_data_tree()
        self.statusBar().showMessage("采集失败", 8000)

    def _build_fsw_settings(self) -> FSWRuntimeSettings:
        return FSWRuntimeSettings(
            resource=self.fsw_resource_edit.text().strip(),
            center_frequency_hz=self._optional_float(self.center_hz_edit, "中心频率"),
            span_hz=self._optional_float(self.span_hz_edit, "Span"),
            rbw_hz=self._optional_float(self.rbw_hz_edit, "RBW"),
            vbw_hz=self._optional_float(self.vbw_hz_edit, "VBW"),
            trigger_source=self.trigger_source_combo.currentText(),
            step_timeout_s=self._required_float(self.fsw_timeout_edit, "FSW Step Timeout"),
        )

    def _build_dsox_settings(self) -> DSOXRuntimeSettings:
        return DSOXRuntimeSettings(
            resource=self.dsox_resource_edit.text().strip(),
            delay_source1=self.delay_source1_edit.text().strip(),
            delay_source2=self.delay_source2_edit.text().strip(),
            delay_edge1=self.delay_edge1_combo.currentText(),
            delay_edge2=self.delay_edge2_combo.currentText(),
            cycle_count_source=self.cycle_source_edit.text().strip(),
            waveform_channel=self.waveform_channel_spin.value(),
        )

    def _set_capture_busy(self, busy: bool) -> None:
        self._capture_busy = busy
        self.start_button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)
        self.fsw_connect_button.setEnabled(not busy)
        self.dsox_connect_button.setEnabled(not busy)
        self.output_browse_button.setEnabled(not busy)

    def _instrument_widgets(self, key: str):
        if key == "fsw":
            return self.fsw_status_label, self.fsw_connect_button
        return self.dsox_status_label, self.dsox_connect_button

    def _choose_output_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择采集数据目录",
            self.output_root_edit.text(),
        )
        if not selected:
            return
        self.output_root_edit.setText(selected)
        self._append_log(f"数据目录：{selected}")
        self._refresh_data_tree()

    def _refresh_data_tree(self) -> None:
        self.data_tree.clear()
        root = Path(self.output_root_edit.text()).expanduser()

        if not root.exists():
            self.data_tree.addTopLevelItem(QTreeWidgetItem(["暂无数据", str(root)]))
            return

        entries = sorted(
            root.rglob("*"),
            key=lambda path: (not path.is_dir(), str(path).lower()),
        )
        for path in entries[:500]:
            try:
                relative = path.relative_to(root)
            except ValueError:
                relative = path
            if path.is_dir():
                kind = "目录"
            else:
                kind = (
                    f"{path.suffix.lstrip('.').upper() or 'FILE'} · "
                    f"{path.stat().st_size} B"
                )
            self.data_tree.addTopLevelItem(QTreeWidgetItem([str(relative), kind]))

    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _show_input_error(self, message: str) -> None:
        QMessageBox.warning(self, "参数错误", message)

    @staticmethod
    def _optional_float(edit: QLineEdit, name: str) -> float | None:
        text = edit.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{name} 必须是数字") from exc

    @staticmethod
    def _required_float(edit: QLineEdit, name: str) -> float:
        text = edit.text().strip()
        if not text:
            raise ValueError(f"{name} 不能为空")
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{name} 必须是数字") from exc

    @staticmethod
    def _number_edit(value: str) -> QLineEdit:
        edit = QLineEdit(value)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        return edit

    @staticmethod
    def _status_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("statusPill")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        label.setMinimumWidth(90)
        return label

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._capture_busy:
            self._controller.cancel_capture()
            QMessageBox.information(
                self,
                "正在停止采集",
                "已发送停止请求。请等待 Job 结束后再关闭程序。",
            )
            event.ignore()
            return

        self._controller.shutdown()
        event.accept()

    def _apply_style(self) -> None:
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)

        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f6f8;
                color: #17202a;
            }
            QLabel#pageTitle {
                font-size: 24px;
                font-weight: 700;
                color: #101828;
            }
            QLabel#pageSubtitle {
                color: #667085;
                font-size: 12px;
            }
            QLabel#alphaBadge {
                background: #e8f1ff;
                color: #175cd3;
                border: 1px solid #b2ccff;
                border-radius: 12px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QGroupBox {
                background: white;
                border: 1px solid #dfe3e8;
                border-radius: 10px;
                margin-top: 12px;
                padding: 14px 10px 10px 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #344054;
            }
            QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTreeWidget {
                background: white;
                border: 1px solid #cfd6df;
                border-radius: 6px;
                padding: 6px;
                selection-background-color: #2f6fed;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
            QPlainTextEdit:focus, QTreeWidget:focus {
                border: 1px solid #2f6fed;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cfd6df;
                border-radius: 6px;
                padding: 7px 14px;
                min-height: 18px;
            }
            QPushButton:hover:enabled {
                background: #f8fafc;
                border-color: #98a2b3;
            }
            QPushButton[primary="true"] {
                background: #2f6fed;
                color: white;
                border-color: #2f6fed;
                font-weight: 600;
            }
            QPushButton[primary="true"]:hover:enabled {
                background: #245ccc;
            }
            QPushButton:disabled {
                color: #98a2b3;
                background: #f2f4f7;
            }
            QLabel#statusPill {
                background: #f2f4f7;
                color: #475467;
                border-radius: 10px;
                padding: 4px 10px;
                font-weight: 600;
            }
            QLabel#alphaNote {
                color: #7a5d00;
                background: #fff8db;
                border: 1px solid #f5df91;
                border-radius: 6px;
                padding: 7px;
            }
            QProgressBar {
                background: #eef2f6;
                border: 1px solid #dfe3e8;
                border-radius: 6px;
                text-align: center;
                min-height: 24px;
            }
            QProgressBar::chunk {
                background: #2f6fed;
                border-radius: 5px;
            }
            """
        )
