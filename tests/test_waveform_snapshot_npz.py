from pathlib import Path

import numpy as np

from instrument_capture_studio.core.results import WaveformResult
from instrument_capture_studio.data.npz import load_waveform_npz, write_waveform_npz


def test_waveform_npz_roundtrips_snapshot_all_metadata(tmp_path: Path):
    path = tmp_path / "waveform_sync.npz"
    waveform = WaveformResult(
        channel="CH1",
        time_s=[0.0, 1e-9, 2e-9],
        voltage_v=[0.1, 0.2, 0.3],
        sample_rate_hz=1e9,
        metadata={
            "sample_kind": "sync",
            "snapshot_all": {
                "measurement_count": 31,
                "source": "CHANnel1",
                "measurements": {
                    "frequency": {
                        "label": "Freq",
                        "unit": "Hz",
                        "value": 123.0,
                        "valid": True,
                    }
                },
            },
        },
    )

    write_waveform_npz(path, waveform)

    with np.load(path, allow_pickle=False) as data:
        assert "time_s" in data.files
        assert "voltage_v" in data.files
        assert "metadata_json" in data.files

    loaded = load_waveform_npz(path, channel="CH1", sample_rate_hz=1e9)
    assert loaded.time_s == waveform.time_s
    assert loaded.voltage_v == waveform.voltage_v
    assert loaded.metadata["sample_kind"] == "sync"
    assert loaded.metadata["snapshot_all"]["measurement_count"] == 31
    assert (
        loaded.metadata["snapshot_all"]["measurements"]["frequency"]["value"]
        == 123.0
    )


def test_waveform_npz_without_metadata_remains_backward_compatible(tmp_path: Path):
    path = tmp_path / "legacy_waveform.npz"
    np.savez_compressed(
        path,
        time_s=np.asarray([0.0, 1.0]),
        voltage_v=np.asarray([2.0, 3.0]),
    )

    loaded = load_waveform_npz(path, channel="CH2")

    assert loaded.metadata == {}
    assert loaded.time_s == [0.0, 1.0]
    assert loaded.voltage_v == [2.0, 3.0]
