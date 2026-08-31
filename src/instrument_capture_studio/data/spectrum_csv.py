import csv
from pathlib import Path

from instrument_capture_studio.core.results import SpectrumResult


def write_spectrum_csv(path: Path, spectrum: SpectrumResult) -> None:
    """保存频谱 Trace 为两列 CSV。

    普通扫频保存 ``frequency_hz, amplitude_dbm``；FSW Zero Span 保存
    ``time_s, amplitude_dbm``，避免把同一个中心频率重复写成无意义横轴。
    """

    if spectrum.time_s is not None:
        if len(spectrum.time_s) != len(spectrum.amplitudes_dbm):
            raise ValueError("spectrum time and amplitude lengths must match")
        header = ("time_s", "amplitude_dbm")
        x_values = spectrum.time_s
    else:
        if len(spectrum.frequencies_hz) != len(spectrum.amplitudes_dbm):
            raise ValueError("spectrum frequency and amplitude lengths must match")
        header = ("frequency_hz", "amplitude_dbm")
        x_values = spectrum.frequencies_hz

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(zip(x_values, spectrum.amplitudes_dbm))
