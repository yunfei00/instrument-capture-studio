import csv

import pytest

from instrument_capture_studio.core.results import (
    WaveformResult,
)
from instrument_capture_studio.data.waveform_csv import (
    write_waveform_csv,
)


def test_write_waveform_csv(
    tmp_path,
):
    path = (
        tmp_path
        / "waveform.csv"
    )

    waveform = WaveformResult(
        channel="CH1",
        time_s=[
            0.0,
            1e-6,
            2e-6,
        ],
        voltage_v=[
            0.1,
            0.2,
            -0.1,
        ],
        sample_rate_hz=1e6,
    )

    write_waveform_csv(
        path,
        waveform,
    )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(
            csv.reader(file)
        )

    assert rows == [
        [
            "time_s",
            "voltage_v",
        ],
        [
            "0.0",
            "0.1",
        ],
        [
            "1e-06",
            "0.2",
        ],
        [
            "2e-06",
            "-0.1",
        ],
    ]


def test_write_waveform_csv_rejects_mismatched_lengths(
    tmp_path,
):
    waveform = WaveformResult(
        channel="CH1",
        time_s=[
            0.0,
            1e-6,
        ],
        voltage_v=[
            0.1,
        ],
    )

    with pytest.raises(
        ValueError,
        match="lengths must match",
    ):
        write_waveform_csv(
            tmp_path
            / "waveform.csv",
            waveform,
        )
