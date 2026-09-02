import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from instrument_capture_studio.core.results import SpectrumResult, WaveformResult
from instrument_capture_studio.workflows.context import CaptureContext


def _spectrum_summary(spectrum: SpectrumResult | None) -> dict[str, Any] | None:
    if spectrum is None:
        return None

    frequencies = spectrum.frequencies_hz
    summary: dict[str, Any] = {
        "points": spectrum.points,
        "axis_kind": spectrum.axis_kind,
        "start_frequency_hz": frequencies[0] if frequencies else None,
        "stop_frequency_hz": frequencies[-1] if frequencies else None,
        "metadata": spectrum.metadata,
    }
    if spectrum.time_s is not None:
        summary["start_time_s"] = spectrum.time_s[0] if spectrum.time_s else None
        summary["stop_time_s"] = spectrum.time_s[-1] if spectrum.time_s else None
        summary["center_frequency_hz"] = spectrum.metadata.get(
            "center_frequency_hz"
        )
        summary["span_hz"] = spectrum.metadata.get("span_hz", 0.0)
        summary["sweep_time_s"] = spectrum.metadata.get("sweep_time_s")
    return summary


def _waveform_summary(waveform: WaveformResult | None) -> dict[str, Any] | None:
    if waveform is None:
        return None
    return {
        "channel": waveform.channel,
        "points": waveform.points,
        "sample_rate_hz": waveform.sample_rate_hz,
        "metadata": waveform.metadata,
    }


def _measurement_summary(value):
    if value is None:
        return None
    return {
        "measurement": value.measurement,
        "value": value.value,
        "unit": value.unit,
        "metadata": value.metadata,
    }


def _paired_acquisition_parameters(context: CaptureContext) -> dict[str, Any]:
    """Build the compact measurement-condition record requested for each Job."""

    instruments = context.metadata.get("instruments")
    spectrum_analyzer = (
        instruments.get("spectrum_analyzer")
        if isinstance(instruments, dict)
        else None
    )
    frontend = (
        spectrum_analyzer.get("frontend")
        if isinstance(spectrum_analyzer, dict)
        else None
    )
    timing_windows = context.metadata.get("timing_windows")

    return {
        "fsw": {
            "sweep_time_s": context.metadata.get("fsw_sweep_time_s"),
            "frontend": deepcopy(frontend) if isinstance(frontend, dict) else None,
        },
        "dsox": {
            "sync": deepcopy(timing_windows.get("sync"))
            if isinstance(timing_windows, dict)
            and isinstance(timing_windows.get("sync"), dict)
            else None,
            "followup": deepcopy(timing_windows.get("followup"))
            if isinstance(timing_windows, dict)
            and isinstance(timing_windows.get("followup"), dict)
            else None,
        },
    }


def build_capture_metadata(
    job_id: str,
    context: CaptureContext,
    *,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Convert CaptureContext to the final schema-v1 Job metadata."""

    timestamp = captured_at or datetime.now()
    recipe = str(context.metadata.get("recipe") or "legacy_debug")

    if recipe == "ext_imm_pair":
        spectra = {
            "ext": _spectrum_summary(context.spectrum_ext),
            "freerun": _spectrum_summary(context.spectrum_freerun),
        }
        oscilloscope = {
            "waveform_channel": context.metadata.get("waveform_channel"),
            "sync": _waveform_summary(context.waveform_sync),
            "followup": _waveform_summary(context.waveform_followup),
            "timing_windows": context.metadata.get("timing_windows"),
        }
    else:
        spectra = {
            "ext": _spectrum_summary(context.spectrum_ext),
            "imm": _spectrum_summary(context.spectrum_imm),
        }
        oscilloscope = {
            "waveform_channel": context.metadata.get("waveform_channel"),
            "delay": {
                "measurement": _measurement_summary(context.delay),
                "waveform": _waveform_summary(context.waveform_delay),
            },
            "cycle_count": {
                "measurement": _measurement_summary(context.cycle_count),
                "waveform": _waveform_summary(context.waveform_cycle),
            },
        }

    metadata: dict[str, Any] = {
        "schema_version": 1,
        "job_id": job_id,
        "captured_at": timestamp.isoformat(),
        "recipe": recipe,
        "capture_complete": context.capture_complete,
        "spectra": spectra,
        "oscilloscope": oscilloscope,
        "metadata": context.metadata,
    }

    if recipe == "ext_imm_pair":
        # Keep the values easy to find in metadata.json instead of requiring
        # downstream users to understand the internal context structure.
        metadata["acquisition_parameters"] = _paired_acquisition_parameters(context)

    if context.spectrum is not None:
        metadata["debug_spectrum"] = _spectrum_summary(context.spectrum)
    if context.waveform is not None:
        metadata["debug_waveform"] = _waveform_summary(context.waveform)
    if context.delay is not None and context.waveform_delay is None:
        metadata["debug_delay"] = _measurement_summary(context.delay)
    if context.cycle_count is not None and context.waveform_cycle is None:
        metadata["debug_cycle_count"] = _measurement_summary(context.cycle_count)

    return metadata


def write_capture_metadata(path: Path, metadata: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
        file.write("\n")


def load_capture_metadata(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)
