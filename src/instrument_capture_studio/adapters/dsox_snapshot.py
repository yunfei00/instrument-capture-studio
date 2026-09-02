"""Read the InfiniiVision Snapshot All measurement set after one waveform.

Keysight documents ``:MEASure:ALL`` as the front-panel-equivalent Snapshot All
command. The command itself is not a query, so the commercial application reads
the 31 scalar measurements shown by Snapshot All individually and stores their
raw/numeric results with the waveform.

Snapshot collection is auxiliary evidence. A missing/invalid individual
measurement is recorded instead of failing an otherwise valid waveform capture.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math


@dataclass(frozen=True)
class SnapshotMeasurementSpec:
    key: str
    label: str
    query_template: str
    unit: str


# InfiniiVision 3000 X-Series Snapshot All: 31 single-waveform measurements.
# The explicit channel source keeps the values tied to the waveform that was
# just acquired, even if the operator has other channels displayed.
SNAPSHOT_ALL_MEASUREMENTS: tuple[SnapshotMeasurementSpec, ...] = (
    SnapshotMeasurementSpec("peak_to_peak", "Pk-Pk", ":MEASure:VPP? {source}", "V"),
    SnapshotMeasurementSpec("maximum", "Max", ":MEASure:VMAX? {source}", "V"),
    SnapshotMeasurementSpec("minimum", "Min", ":MEASure:VMIN? {source}", "V"),
    SnapshotMeasurementSpec("amplitude", "Ampl", ":MEASure:VAMPlitude? {source}", "V"),
    SnapshotMeasurementSpec("top", "Top", ":MEASure:VTOP? {source}", "V"),
    SnapshotMeasurementSpec("base", "Base", ":MEASure:VBASe? {source}", "V"),
    SnapshotMeasurementSpec("overshoot", "Over", ":MEASure:OVERshoot? {source}", "%"),
    SnapshotMeasurementSpec("preshoot", "Pre", ":MEASure:PREShoot? {source}", "%"),
    SnapshotMeasurementSpec("average_cycle", "Avg - Cyc", ":MEASure:VAVerage? CYCLe,{source}", "V"),
    SnapshotMeasurementSpec("average_display", "Avg - FS", ":MEASure:VAVerage? DISPlay,{source}", "V"),
    SnapshotMeasurementSpec("dc_rms_cycle", "DC RMS - Cyc", ":MEASure:VRMS? CYCLe,DC,{source}", "V"),
    SnapshotMeasurementSpec("dc_rms_display", "DC RMS - FS", ":MEASure:VRMS? DISPlay,DC,{source}", "V"),
    SnapshotMeasurementSpec("ac_rms_cycle", "AC RMS - Cyc", ":MEASure:VRMS? CYCLe,AC,{source}", "V"),
    SnapshotMeasurementSpec("ac_rms_display", "AC RMS - FS", ":MEASure:VRMS? DISPlay,AC,{source}", "V"),
    SnapshotMeasurementSpec("period", "Period", ":MEASure:PERiod? {source}", "s"),
    SnapshotMeasurementSpec("frequency", "Freq", ":MEASure:FREQuency? {source}", "Hz"),
    SnapshotMeasurementSpec("positive_width", "+Width", ":MEASure:PWIDth? {source}", "s"),
    SnapshotMeasurementSpec("negative_width", "-Width", ":MEASure:NWIDth? {source}", "s"),
    SnapshotMeasurementSpec("burst_width", "Burst Width", ":MEASure:BWIDth? {source}", "s"),
    SnapshotMeasurementSpec("positive_duty", "+Duty", ":MEASure:DUTYcycle? {source}", "%"),
    SnapshotMeasurementSpec("negative_duty", "-Duty", ":MEASure:NDUTy? {source}", "%"),
    SnapshotMeasurementSpec("rise_time", "Rise", ":MEASure:RISetime? {source}", "s"),
    SnapshotMeasurementSpec("fall_time", "Fall", ":MEASure:FALLtime? {source}", "s"),
    SnapshotMeasurementSpec("x_at_min", "X@Min", ":MEASure:XMIN? {source}", "s"),
    SnapshotMeasurementSpec("x_at_max", "X@Max", ":MEASure:XMAX? {source}", "s"),
    SnapshotMeasurementSpec("positive_pulse_count", "+ Pulse Count", ":MEASure:PPULses? {source}", "count"),
    SnapshotMeasurementSpec("negative_pulse_count", "- Pulse Count", ":MEASure:NPULses? {source}", "count"),
    SnapshotMeasurementSpec("rising_edge_count", "Rise Edge", ":MEASure:PEDGes? {source}", "count"),
    SnapshotMeasurementSpec("falling_edge_count", "Fall Edge", ":MEASure:NEDGes? {source}", "count"),
    SnapshotMeasurementSpec("area_cycle", "Area - Cyc", ":MEASure:AREa? CYCLe,{source}", "V*s"),
    SnapshotMeasurementSpec("area_display", "Area - FS", ":MEASure:AREa? DISPlay,{source}", "V*s"),
)


def read_snapshot_all(driver, channel: int) -> dict[str, object]:
    """Read one lossless Snapshot All record for the selected analog channel.

    Invalid scope measurements commonly use an infinity sentinel around 9.9E+37.
    Those values are kept in ``raw`` but exposed as ``value=None``/``valid=False``.
    Driver/firmware errors are captured per measurement so this optional feature
    never discards the waveform that was already acquired successfully.
    """

    channel_number = int(channel)
    if channel_number not in {1, 2, 3, 4}:
        raise ValueError("Snapshot All channel must be between 1 and 4")

    source = f"CHANnel{channel_number}"
    snapshot: dict[str, object] = {
        "schema_version": 1,
        "kind": "keysight_infiniivision_snapshot_all",
        "source": source,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "install_command": ":MEASure:ALL",
        "measurement_count": len(SNAPSHOT_ALL_MEASUREMENTS),
        "measurements": {},
    }

    # Match the front-panel Snapshot All operation first. There is no query form
    # for :MEASure:ALL on this family, so scalar values are queried below.
    try:
        driver.write(f":MEASure:SOURce {source}")
        driver.write(":MEASure:ALL")
    except Exception as exc:  # auxiliary evidence must not fail acquisition
        snapshot["install_error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }

    results: dict[str, object] = {}
    successful = 0
    for spec in SNAPSHOT_ALL_MEASUREMENTS:
        command = spec.query_template.format(source=source)
        entry: dict[str, object] = {
            "label": spec.label,
            "command": command,
            "unit": spec.unit,
        }
        try:
            raw = str(driver.query(command)).strip()
            entry["raw"] = raw
            value, valid = _parse_measurement_value(raw)
            entry["value"] = value
            entry["valid"] = valid
            if valid:
                successful += 1
        except Exception as exc:  # firmware/signal dependent queries may fail
            entry["raw"] = None
            entry["value"] = None
            entry["valid"] = False
            entry["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        results[spec.key] = entry

    snapshot["measurements"] = results
    snapshot["successful_measurements"] = successful
    snapshot["failed_or_invalid_measurements"] = len(results) - successful
    return snapshot


def _parse_measurement_value(raw: str) -> tuple[float | None, bool]:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, False
    if not math.isfinite(value) or abs(value) >= 9.0e37:
        return None, False
    return value, True
