import csv
from pathlib import Path

from instrument_capture_studio.core.results import (
    WaveformResult,
)


def write_waveform_csv(
    path: Path,
    waveform: WaveformResult,
) -> None:
    """保存示波器波形为标准两列 CSV。"""

    if (
        len(waveform.time_s)
        != len(waveform.voltage_v)
    ):
        raise ValueError(
            "waveform time and voltage "
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
        writer = csv.writer(file)

        writer.writerow(
            [
                "time_s",
                "voltage_v",
            ]
        )

        writer.writerows(
            zip(
                waveform.time_s,
                waveform.voltage_v,
            )
        )
