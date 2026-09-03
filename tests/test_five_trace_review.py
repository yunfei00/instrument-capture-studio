from instrument_capture_studio.data.manual_review import FORMAL_REVIEW_TRACES
from instrument_capture_studio.ui.five_trace_review import VIDEO_REVIEW_LAYOUT


def test_video_review_uses_requested_two_row_layout():
    assert VIDEO_REVIEW_LAYOUT == (
        ("spectrum_freerun.npz", "FSW Free Run", 0, 0, 3),
        ("spectrum_video.npz", "FSW VIDEO", 0, 3, 3),
        ("spectrum_ext.npz", "FSW EXT", 1, 0, 2),
        ("waveform_sync.npz", "DSO-X 第一次同步波形", 1, 2, 2),
        ("waveform_followup.npz", "DSO-X 第二次波形", 1, 4, 2),
    )


def test_video_review_keeps_old_four_trace_portable_sample_contract():
    assert "spectrum_video.npz" not in FORMAL_REVIEW_TRACES
    assert set(FORMAL_REVIEW_TRACES) == {
        "spectrum_ext.npz",
        "waveform_sync.npz",
        "waveform_followup.npz",
        "spectrum_freerun.npz",
    }
