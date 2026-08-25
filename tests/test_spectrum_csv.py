import csv

import pytest

from instrument_capture_studio.core.results import (
    SpectrumResult,
)
from instrument_capture_studio.data.spectrum_csv import (
    write_spectrum_csv,
)


def test_write_spectrum_csv(
    tmp_path,
):
    path = (
        tmp_path
        / "spectrum.csv"
    )

    spectrum = SpectrumResult(
        frequencies_hz=[
            500e6,
            600e6,
            700e6,
        ],
        amplitudes_dbm=[
            -80.0,
            -40.5,
            -70.25,
        ],
    )

    write_spectrum_csv(
        path,
        spectrum,
    )

    assert path.is_file()

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
            "frequency_hz",
            "amplitude_dbm",
        ],
        [
            "500000000.0",
            "-80.0",
        ],
        [
            "600000000.0",
            "-40.5",
        ],
        [
            "700000000.0",
            "-70.25",
        ],
    ]


def test_write_spectrum_csv_rejects_mismatched_lengths(
    tmp_path,
):
    spectrum = SpectrumResult(
        frequencies_hz=[
            500e6,
            600e6,
        ],
        amplitudes_dbm=[
            -80.0,
        ],
    )

    with pytest.raises(
        ValueError,
        match="lengths must match",
    ):
        write_spectrum_csv(
            tmp_path
            / "spectrum.csv",
            spectrum,
        )
