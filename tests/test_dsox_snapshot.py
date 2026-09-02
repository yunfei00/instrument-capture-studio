import pytest

from instrument_capture_studio.adapters.dsox_snapshot import (
    SNAPSHOT_ALL_MEASUREMENTS,
    read_snapshot_all,
)


class FakeSnapshotDriver:
    def __init__(self):
        self.writes = []
        self.queries = []

    def write(self, command: str) -> None:
        self.writes.append(command)

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command.startswith(":MEASure:XMIN?"):
            return "9.9E+37"
        if command.startswith(":MEASure:NEDGes?"):
            raise RuntimeError("measurement unavailable")
        return "1.25"


def test_snapshot_all_reads_31_values_after_installing_front_panel_snapshot():
    driver = FakeSnapshotDriver()

    snapshot = read_snapshot_all(driver, 2)

    assert len(SNAPSHOT_ALL_MEASUREMENTS) == 31
    assert driver.writes == [
        ":MEASure:SOURce CHANnel2",
        ":MEASure:ALL",
    ]
    assert len(driver.queries) == 31
    assert all("CHANnel2" in command for command in driver.queries)
    assert snapshot["kind"] == "keysight_infiniivision_snapshot_all"
    assert snapshot["source"] == "CHANnel2"
    assert snapshot["measurement_count"] == 31

    measurements = snapshot["measurements"]
    assert len(measurements) == 31
    assert measurements["peak_to_peak"]["value"] == pytest.approx(1.25)
    assert measurements["peak_to_peak"]["valid"] is True

    # DSO-X invalid-measurement sentinel is kept as raw evidence, not a value.
    assert measurements["x_at_min"]["raw"] == "9.9E+37"
    assert measurements["x_at_min"]["value"] is None
    assert measurements["x_at_min"]["valid"] is False

    # One unsupported/signal-dependent metric never fails the captured waveform.
    assert measurements["falling_edge_count"]["value"] is None
    assert measurements["falling_edge_count"]["valid"] is False
    assert measurements["falling_edge_count"]["error"]["type"] == "RuntimeError"
    assert snapshot["successful_measurements"] == 29
    assert snapshot["failed_or_invalid_measurements"] == 2


def test_snapshot_all_rejects_invalid_analog_channel():
    with pytest.raises(ValueError, match="between 1 and 4"):
        read_snapshot_all(FakeSnapshotDriver(), 5)
