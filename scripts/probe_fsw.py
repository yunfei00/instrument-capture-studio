import argparse
import sys
from pathlib import Path


def add_platform_packages(platform_root: Path) -> None:
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
                f"platform package source not found: {src}"
            )

        sys.path.insert(
            0,
            str(src),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe Rohde & Schwarz FSW through "
            "Instrument Capture Studio."
        )
    )

    default_platform = (
        Path(__file__).resolve().parents[2]
        / "instrument-automation-platform"
    )

    parser.add_argument(
        "--platform-root",
        type=Path,
        default=default_platform,
        help=(
            "Path to instrument-automation-platform. "
            "Default: sibling repository."
        ),
    )

    parser.add_argument(
        "--resource",
        required=True,
        help=(
            "VISA resource, for example "
            "TCPIP0::192.168.1.20::inst0::INSTR"
        ),
    )

    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=15000,
    )

    parser.add_argument(
        "--backend",
        default=None,
        help="Optional PyVISA backend, for example @py.",
    )

    parser.add_argument(
        "--spectrum",
        action="store_true",
        help="Run one spectrum acquisition.",
    )

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
        help=(
            "Optional FSW trigger source. "
            "Leave unset to preserve current instrument setting."
        ),
    )

    parser.add_argument(
        "--channel",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--window",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--trace",
        type=int,
        default=1,
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

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
    from instrument_drivers.rohde_schwarz.fsw import (
        RohdeSchwarzFSWDriver,
    )

    from instrument_capture_studio.adapters.fsw import (
        FSWAdapter,
        FSWConfig,
    )

    transport = VisaTransport(
        TransportConfig(
            resource=args.resource,
            timeout_ms=args.timeout_ms,
        ),
        backend=args.backend,
    )

    driver = RohdeSchwarzFSWDriver(
        transport
    )

    adapter = FSWAdapter(
        address=args.resource,
        driver=driver,
        config=FSWConfig(
            center_frequency_hz=args.center_hz,
            span_hz=args.span_hz,
            rbw_hz=args.rbw_hz,
            vbw_hz=args.vbw_hz,
            trigger_source=args.trigger_source,
            channel=args.channel,
            window=args.window,
            trace=args.trace,
        ),
    )

    print("=== R&S FSW Probe ===")
    print("resource:", args.resource)

    try:
        print()
        print("[1] Connecting...")

        adapter.connect()

        status = adapter.get_status()

        print("connected:", adapter.is_connected())
        print("state:", status.state.value)
        print("model:", status.model)
        print("serial:", status.serial_number)
        print("firmware:", status.firmware_version)

        if not args.spectrum:
            print()
            print("Connection-only probe complete.")
            return 0

        print()
        print("[2] Spectrum acquisition...")

        result = adapter.acquire_spectrum()

        print("points:", result.points)

        if result.points:
            print(
                "start_hz:",
                result.frequencies_hz[0],
            )
            print(
                "stop_hz:",
                result.frequencies_hz[-1],
            )

            peak_index = max(
                range(result.points),
                key=result.amplitudes_dbm.__getitem__,
            )

            print(
                "peak_frequency_hz:",
                result.frequencies_hz[peak_index],
            )

            print(
                "peak_amplitude_dbm:",
                result.amplitudes_dbm[peak_index],
            )

        print(
            "metadata:",
            result.metadata,
        )

        return 0

    except Exception as exc:
        print()
        print(
            "PROBE FAILED:",
            type(exc).__name__,
            str(exc),
        )

        return 1

    finally:
        print()
        print("[3] Disconnecting...")

        try:
            adapter.disconnect()
            print("transport disconnected")
        except Exception as exc:
            print(
                "disconnect warning:",
                type(exc).__name__,
                str(exc),
            )

        print(
            "NOTE: FSW front-panel/local-mode restoration "
            "still requires real-hardware qualification."
        )


if __name__ == "__main__":
    raise SystemExit(main())
