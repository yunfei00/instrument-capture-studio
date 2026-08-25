import pytest

from instrument_capture_studio.ui.state import (
    CapturePanelState,
    CaptureUiState,
    ConnectionState,
    InstrumentPanelState,
)


def test_instrument_panel_defaults_to_disconnected():
    state = InstrumentPanelState()

    assert state.connection is ConnectionState.DISCONNECTED
    assert state.is_connected is False


def test_instrument_panel_reports_connected():
    state = InstrumentPanelState(
        connection=ConnectionState.CONNECTED,
        model="FSW-26",
        firmware="6.00",
    )

    assert state.is_connected is True
    assert state.model == "FSW-26"


def test_capture_panel_idle_can_start():
    state = CapturePanelState()

    assert state.state is CaptureUiState.IDLE
    assert state.can_start is True
    assert state.can_stop is False
    assert state.is_busy is False


def test_capture_panel_running_can_stop():
    state = CapturePanelState(
        state=CaptureUiState.RUNNING,
        progress_percent=40,
        job_id="job-123",
    )

    assert state.can_start is False
    assert state.can_stop is True
    assert state.is_busy is True


def test_capture_panel_rejects_invalid_progress():
    with pytest.raises(
        ValueError,
        match="progress_percent",
    ):
        CapturePanelState(
            progress_percent=101,
        )
