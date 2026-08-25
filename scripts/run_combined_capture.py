import argparse
import sys
from pathlib import Path
from uuid import uuid4


REPO_ROOT = (
    Path(__file__).resolve().parents[1]
)

sys.path.insert(
    0,
    str(REPO_ROOT / "src"),
)


def add_platform_packages(
    platform_root: Path,
) -> None:
    packages = (
        "instrument_core",
        "instrument_scpi",
        "instrument_drivers",
    )

    for package in packages:
        src = (
            platform_root
            / "packages"
            / package
            / "src"
        )

        if not src.exists():
            raise RuntimeError(
                "platform package source "
                f"not found: {src}"
            )

        sys.path.insert(
            0,
            str(src),
        )


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Run one DSO-X 3034A + FSW "
            "combined capture job."
        )
    )

    default_platform = (
        REPO_ROOT.parent
        / "instrument-automation-platform"
    )

    parser.add_argument(
        "--platform-root",
        type=Path,
        default=default_platform,
    )

    parser.add_argument(
        "--fsw-resource",
        required=True,
    )

    parser.add_argument(
        "--dsox-resource",
        required=True,
    )

    parser.add_argument(
        "--backend",
        default=None,
    )

    parser.add_argument(
        "--fsw-transport-timeout-ms",
        type=int,
        default=15000,
    )

    parser.add_argument(
        "--dsox-transport-timeout-ms",
        type=int,
        default=10000,
    )

    parser.add_argument(
        "--fsw-step-timeout-s",
        type=float,
        default=30.0,
        help=(
            "Overall FSW spectrum step timeout. "
            "Default: 30 seconds."
        ),
    )

    parser.add_argument(
        "--job-id",
        default=None,
    )

    # FSW
    parser.add_argument(
        "--center-hz",
        type=float,
        default=None,
    )

    parser.add_argument(
        "--span-hz",
        type=float,
        default=None,
    )

    parser.add_argument(
        "--rbw-hz",
        type=float,
        default=None,
    )

    parser.add_argument(
        "--vbw-hz",
        type=float,
        default=None,
    )

    parser.add_argument(
        "--trigger-source",
        default=None,
    )

    # DSO-X
    parser.add_argument(
        "--delay-source1",
        default="CHANnel1",
    )

    parser.add_argument(
        "--delay-source2",
        default="CHANnel2",
    )

    parser.add_argument(
        "--delay-edge1",
        default="+1",
    )

    parser.add_argument(
        "--delay-edge2",
        default="+1",
    )

    parser.add_argument(
        "--cycle-source",
        default="CHANnel1",
    )

    parser.add_argument(
        "--waveform-channel",
        type=int,
        default=1,
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    platform_root = (
        args.platform_root
        .expanduser()
        .resolve()
    )

    add_platform_packages(
        platform_root
    )

    from instrument_core.transport import (
        TransportConfig,
        VisaTransport,
    )

    from instrument_drivers.keysight.dsox3000 import (
        KeysightDSOX3000Driver,
    )

    from instrument_drivers.rohde_schwarz.fsw import (
        RohdeSchwarzFSWDriver,
    )

    from instrument_capture_studio.adapters.dsox3034a import (
        DSOX3034AAdapter,
        DSOX3034AConfig,
    )

    from instrument_capture_studio.adapters.fsw import (
        FSWAdapter,
        FSWConfig,
    )

    from instrument_capture_studio.app.combined_capture import (
        run_combined_capture,
    )

    from instrument_capture_studio.core.models import (
        JobState,
    )

    job_id = (
        args.job_id
        or f"capture-{uuid4().hex[:12]}"
    )

    fsw_transport = VisaTransport(
        TransportConfig(
            resource=args.fsw_resource,
            timeout_ms=(
                args.fsw_transport_timeout_ms
            ),
        ),
        backend=args.backend,
    )

    dsox_transport = VisaTransport(
        TransportConfig(
            resource=args.dsox_resource,
            timeout_ms=(
                args.dsox_transport_timeout_ms
            ),
        ),
        backend=args.backend,
    )

    fsw = FSWAdapter(
        address=args.fsw_resource,
        driver=RohdeSchwarzFSWDriver(
            fsw_transport
        ),
        config=FSWConfig(
            center_frequency_hz=(
                args.center_hz
            ),
            span_hz=args.span_hz,
            rbw_hz=args.rbw_hz,
            vbw_hz=args.vbw_hz,
            trigger_source=(
                args.trigger_source
            ),
        ),
    )

    dsox = DSOX3034AAdapter(
        address=args.dsox_resource,
        driver=KeysightDSOX3000Driver(
            dsox_transport
        ),
        config=DSOX3034AConfig(
            delay_source1=(
                args.delay_source1
            ),
            delay_source2=(
                args.delay_source2
            ),
            delay_edge1=args.delay_edge1,
            delay_edge2=args.delay_edge2,
            cycle_count_source=(
                args.cycle_source
            ),
            waveform_channel=(
                args.waveform_channel
            ),
        ),
    )

    print(
        "=== Instrument Capture Studio ==="
    )
    print("job_id:", job_id)
    print(
        "FSW:",
        args.fsw_resource,
    )
    print(
        "DSO-X:",
        args.dsox_resource,
    )

    try:
        result = run_combined_capture(
            fsw,
            dsox,
            job_id=job_id,
            fsw_timeout_s=(
                args.fsw_step_timeout_s
            ),
        )

    except Exception as exc:
        print()
        print(
            "CAPTURE FAILED:",
            type(exc).__name__,
            str(exc),
        )

        return 1

    print()
    print("=== JOB RESULT ===")
    print(
        "state:",
        result.state.value,
    )

    for step in result.steps:
        print(
            f"{step.name}: "
            f"{step.state.value}"
        )

        if step.error:
            print(
                "  error:",
                step.error,
            )

    print(
        "capture_complete:",
        result.metadata.get(
            "capture_complete"
        ),
    )

    print(
        "result_saved:",
        result.metadata.get(
            "result_saved"
        ),
    )

    print(
        "output_files:",
        result.output_files,
    )

    return (
        0
        if result.state
        == JobState.SUCCEEDED
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
