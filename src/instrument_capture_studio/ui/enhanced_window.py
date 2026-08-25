"""Phase 6 enhancements layered on top of the stable main window."""

from instrument_capture_studio.ui.main_window import MainWindow as BaseMainWindow


_STEP_LABELS = {
    "fsw_spectrum": "FSW Spectrum",
    "dsox_delay": "DSO-X DELAY",
    "dsox_cycle_count": "DSO-X CYCLE_COUNT",
    "dsox_waveform": "DSO-X Waveform",
    "save_result": "Save Result",
}


class MainWindow(BaseMainWindow):
    """Stable Phase 6 window with real Capture Step progress."""

    def __init__(self) -> None:
        super().__init__()
        self._controller.capture_progress.connect(self._on_capture_progress)
        self.statusBar().showMessage("就绪 · Phase 6")

    def _on_capture_progress(
        self,
        step_name: str,
        state: str,
        completed_steps: int,
        step_count: int,
    ) -> None:
        if step_count <= 0:
            return

        percent = int(round(completed_steps * 100 / step_count))
        percent = max(0, min(100, percent))
        label = _STEP_LABELS.get(step_name, step_name)

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)

        if state == "running":
            self.progress_bar.setFormat(f"{percent}% · {label}")
            self._append_log(f"▶ {label}")
        elif state == "succeeded":
            self.progress_bar.setFormat(f"{percent}% · {label} 完成")
            self._append_log(f"✓ {label}")
        else:
            self.progress_bar.setFormat(f"{percent}% · {label} {state}")
