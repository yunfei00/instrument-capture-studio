"""Phase 8 release preflight checks.

Examples:
    python scripts/phase8_preflight.py --self-check
    python scripts/phase8_preflight.py --data-root D:\\capture-data
    python scripts/phase8_preflight.py --batch D:\\capture-data\\batches\\2026-08-26\\batch-xxx\\batch.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from instrument_capture_studio.data.acceptance import validate_batch_artifacts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Instrument Capture Studio Phase 8 preflight")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="check Python/runtime imports used by the release build",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        help="capture data root; validates the most recent Batch",
    )
    parser.add_argument(
        "--batch",
        type=Path,
        help="explicit batch.json to validate",
    )
    return parser


def _self_check() -> bool:
    print(f"Python: {sys.version.split()[0]}")
    if sys.version_info < (3, 10):
        print("FAIL: Python >= 3.10 is required")
        return False

    try:
        import numpy
        import PySide6
        import instrument_capture_studio
        from instrument_capture_studio.ui.product_window import MainWindow  # noqa: F401
    except Exception as exc:
        print(f"FAIL: runtime import error: {type(exc).__name__}: {exc}")
        return False

    print(f"NumPy: {numpy.__version__}")
    print(f"PySide6: {PySide6.__version__}")
    print("PASS: release runtime imports")
    return True


def _latest_batch(data_root: Path) -> Path | None:
    candidates = sorted(
        data_root.expanduser().resolve().glob("batches/*/*/batch.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _validate_batch(path: Path) -> bool:
    report = validate_batch_artifacts(path)
    print(f"Batch: {report.batch_id}")
    print(f"State: {report.state}")
    print(
        "Captures: "
        f"{report.completed_captures}/{report.total_captures} "
        f"(successful jobs: {report.successful_jobs})"
    )
    print(f"Failed attempts: {report.failed_jobs}")
    print(f"Recovery events: {report.recovery_events}")

    for warning in report.warnings:
        print(f"WARN: {warning}")

    if report.missing_files:
        print(f"Missing standard files: {len(report.missing_files)}")
        for item in report.missing_files[:20]:
            print(f"  - {item}")
        if len(report.missing_files) > 20:
            print(f"  ... and {len(report.missing_files) - 20} more")

    if report.passed:
        print("PASS: Batch artifact acceptance")
        return True

    print("FAIL: Batch artifact acceptance")
    return False


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    ok = True

    if args.self_check:
        ok = _self_check() and ok

    batch_path = args.batch
    if batch_path is None and args.data_root is not None:
        batch_path = _latest_batch(args.data_root)
        if batch_path is None:
            print(f"FAIL: no batch.json found under {args.data_root}")
            ok = False

    if batch_path is not None:
        try:
            ok = _validate_batch(batch_path) and ok
        except Exception as exc:
            print(f"FAIL: {type(exc).__name__}: {exc}")
            ok = False

    if not args.self_check and batch_path is None and args.data_root is None:
        _parser().print_help()
        return 2

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
