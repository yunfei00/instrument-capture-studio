import csv
from pathlib import Path

from instrument_capture_studio.core.results import (
    SpectrumResult,
)


def write_spectrum_csv(
    path: Path,
    spectrum: SpectrumResult,
) -> None:
    """保存频谱 Trace 为标准两列 CSV。"""

    if (
        len(spectrum.frequencies_hz)
        != len(spectrum.amplitudes_dbm)
    ):
        raise ValueError(
            "spectrum frequency and amplitude "
            "lengths must match"
        )

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.writer(
            file
        )

        writer.writerow(
            [
                "frequency_hz",
                "amplitude_dbm",
            ]
        )

        writer.writerows(
            zip(
                spectrum.frequencies_hz,
                spectrum.amplitudes_dbm,
            )
        )
