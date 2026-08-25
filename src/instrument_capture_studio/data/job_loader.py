from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from instrument_capture_studio.core.results import (
    MeasurementResult,
)
from instrument_capture_studio.data.metadata import (
    load_capture_metadata,
)
from instrument_capture_studio.data.npz import (
    load_spectrum_npz,
    load_waveform_npz,
)
from instrument_capture_studio.workflows.context import (
    CaptureContext,
)


@dataclass(frozen=True)
class LoadedCaptureJob:
    """从磁盘重新加载的一次 Capture Job。"""

    job_id: str
    captured_at: datetime
    context: CaptureContext
    metadata: dict[str, Any]


def _load_measurement(
    value: dict[str, Any] | None,
) -> MeasurementResult | None:
    if value is None:
        return None

    return MeasurementResult(
        measurement=value["measurement"],
        value=float(value["value"]),
        unit=value["unit"],
        metadata=dict(
            value.get(
                "metadata",
                {},
            )
        ),
    )


def load_capture_job(
    job_directory: Path,
) -> LoadedCaptureJob:
    """从标准 Job 目录恢复完整 CaptureContext。"""

    job_directory = Path(
        job_directory
    )

    metadata_path = (
        job_directory
        / "metadata.json"
    )

    metadata = load_capture_metadata(
        metadata_path
    )

    schema_version = metadata.get(
        "schema_version"
    )

    if schema_version != 1:
        raise ValueError(
            "unsupported capture metadata "
            f"schema_version: {schema_version}"
        )

    spectrum_info = metadata.get(
        "spectrum"
    )

    if spectrum_info is None:
        spectrum = None
    else:
        spectrum = load_spectrum_npz(
            job_directory
            / "spectrum.npz",
            metadata=spectrum_info.get(
                "metadata",
                {},
            ),
        )

    waveform_info = metadata.get(
        "waveform"
    )

    if waveform_info is None:
        waveform = None
    else:
        waveform = load_waveform_npz(
            job_directory
            / "waveform.npz",
            channel=waveform_info[
                "channel"
            ],
            sample_rate_hz=(
                waveform_info.get(
                    "sample_rate_hz"
                )
            ),
            metadata=waveform_info.get(
                "metadata",
                {},
            ),
        )

    measurements = metadata.get(
        "measurements",
        {},
    )

    context = CaptureContext(
        spectrum=spectrum,
        delay=_load_measurement(
            measurements.get(
                "delay"
            )
        ),
        cycle_count=_load_measurement(
            measurements.get(
                "cycle_count"
            )
        ),
        waveform=waveform,
        metadata=dict(
            metadata.get(
                "metadata",
                {},
            )
        ),
    )

    return LoadedCaptureJob(
        job_id=metadata["job_id"],
        captured_at=datetime.fromisoformat(
            metadata["captured_at"]
        ),
        context=context,
        metadata=metadata,
    )
