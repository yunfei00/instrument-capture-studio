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
            "Probe Keysight DSO-X 3034A through "
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
            "TCPIP0::192.168.1.10::inst0::INSTR"
        ),
    )

    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=10000,
    )

    parser.add_argument(
        "--backend",
        default=None,
        help=(
            "Optional PyVISA backend, for example @py."
        ),
    )

    parser.add_argument(
        "--delay",
        action="store_true",
        help="Run DELAY measurement.",
    )

    parser.add_argument(
        "--cycle-count",
        action="store_true",
        help="Run cycle/pulse count measurement.",
    )

    parser.add_argument(
        "--waveform",
        action="store_true",
        help="Acquire waveform.",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all Phase 2 acquisition checks.",
    )

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
    from instrument_drivers.keysight.dsox3000 import (
        KeysightDSOX3000Driver,
    )

    from instrument_capture_studio.adapters.dsox3034a import (
        DSOX3034AAdapter,
        DSOX3034AConfig,
    )

    transport = VisaTransport(
        TransportConfig(
            resource=args.resource,
            timeout_ms=args.timeout_ms,
        ),
        backend=args.backend,
    )

    driver = KeysightDSOX3000Driver(
        transport
    )

    adapter = DSOX3034AAdapter(
        address=args.resource,
        driver=driver,
        config=DSOX3034AConfig(
            delay_source1=args.delay_source1,
            delay_source2=args.delay_source2,
            delay_edge1=args.delay_edge1,
            delay_edge2=args.delay_edge2,
            cycle_count_source=args.cycle_source,
            waveform_channel=args.waveform_channel,
        ),
    )

    print("=== DSO-X 3034A Probe ===")
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

        run_delay = (
            args.all
            or args.delay
        )

        run_cycle_count = (
            args.all
            or args.cycle_count
        )

        run_waveform = (
            args.all
            or args.waveform
        )

        if not any(
            (
                run_delay,
                run_cycle_count,
                run_waveform,
            )
        ):
            print()
            print(
                "Connection-only probe complete."
            )

        if run_delay:
            print()
            print("[2] DELAY...")

            result = (
                adapter.acquire_delay()
            )

            print(
                "value:",
                result.value,
                result.unit,
            )

            print(
                "metadata:",
                result.metadata,
            )

        if run_cycle_count:
            print()
            print("[3] Cycle count...")

            result = (
                adapter.acquire_cycle_count()
            )

            print(
                "value:",
                result.value,
                result.unit,
            )

            print(
                "metadata:",
                result.metadata,
            )

        if run_waveform:
            print()
            print("[4] Waveform...")

            result = (
                adapter.acquire_waveform()
            )

            print(
                "channel:",
                result.channel,
            )

            print(
                "points:",
                result.points,
            )

            print(
                "sample_rate_hz:",
                result.sample_rate_hz,
            )

            if result.points:
                print(
                    "first_time_s:",
                    result.time_s[0],
                )

                print(
                    "first_voltage_v:",
                    result.voltage_v[0],
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
        print("[5] Disconnecting...")

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
            "NOTE: DSO-X front-panel/local-mode "
            "restoration still requires real-hardware "
            "qualification."
        )


if __name__ == "__main__":
    raise SystemExit(main())
