"""Phase 8 release preflight checks.

Examples:
    python scripts/phase8_preflight.py --self-check
    python scripts/phase8_preflight.py --data-root D:\\capture-data
    python scripts/phase8_preflight.py --data-root D:\\capture-data\\2026-08-27
    python scripts/phase8_preflight.py --batch D:\\capture-data\\batches\\2026-08-27\\batch-xxx\\batch.json
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from instrument_capture_studio.data.acceptance import validate_batch_artifacts


_DATE_DIRECTORY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
        help=(
            "capture output root, a YYYY-MM-DD job directory, or a Batch directory; "
            "the newest batch.json is detected automatically"
        ),
    )
    parser.add_argument(
        "--batch",
        type=Path,
        help="explicit batch.json or Batch directory to validate",
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
        from instrument_capture_studio.ui.app import (
            create_application,
            create_main_window,
        )
        from instrument_capture_studio.ui.final_window import MainWindow  # noqa: F401
    except Exception as exc:
        print(f"FAIL: runtime import error: {type(exc).__name__}: {exc}")
        return False

    _ = instrument_capture_studio, create_application, create_main_window
    print(f"NumPy: {numpy.__version__}")
    print(f"PySide6: {PySide6.__version__}")
    print("PASS: release runtime imports")
    return True


def _candidate_search_roots(data_root: Path) -> tuple[Path, ...]:
    """Return safe nearby roots for the common capture-directory layouts.

    A user often points the tool at ``<root>/YYYY-MM-DD`` because that is where
    the Job directories are visible. Batch manifests are deliberately stored in
    the sibling ``<root>/batches/...`` tree, so include the parent automatically.
    """

    root = data_root.expanduser().resolve()
    candidates: list[Path] = [root]

    if root.is_file():
        candidates.append(root.parent)

    if root.is_dir() and _DATE_DIRECTORY.match(root.name):
        candidates.append(root.parent)

    if root.is_dir() and (root / "job.json").is_file():
        candidates.extend([root.parent, root.parent.parent])

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return tuple(unique)


def _find_batches(data_root: Path) -> tuple[Path, ...]:
    root = data_root.expanduser().resolve()

    if root.is_file():
        if root.name == "batch.json":
            return (root,)
        return ()

    found: dict[Path, float] = {}
    for search_root in _candidate_search_roots(root):
        direct = search_root / "batch.json"
        if direct.is_file():
            found[direct] = direct.stat().st_mtime

        batches_root = search_root / "batches"
        if batches_root.is_dir():
            for path in batches_root.glob("*/*/batch.json"):
                if path.is_file():
                    found[path.resolve()] = path.stat().st_mtime

        # Also support copied/reorganized acceptance data. The official layout
        # is preferred above, but recursive discovery makes the tool useful when
        # a Batch directory was copied by itself to another location.
        for path in search_root.rglob("batch.json"):
            if path.is_file():
                found[path.resolve()] = path.stat().st_mtime

    return tuple(
        path
        for path, _mtime in sorted(
            found.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )


def _count_job_manifests(data_root: Path) -> int:
    root = data_root.expanduser().resolve()
    if root.is_file():
        root = root.parent
    if not root.exists():
        return 0
    try:
        return sum(1 for path in root.rglob("job.json") if path.is_file())
    except OSError:
        return 0


def _latest_batch(data_root: Path) -> Path | None:
    batches = _find_batches(data_root)
    return batches[0] if batches else None


def _normalize_batch_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_dir():
        candidate = path / "batch.json"
        if candidate.is_file():
            return candidate
    return path


def _validate_batch(path: Path) -> bool:
    report = validate_batch_artifacts(path)
    print(f"Batch manifest: {Path(path).resolve()}")
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

    batch_path = _normalize_batch_path(args.batch) if args.batch is not None else None
    if batch_path is None and args.data_root is not None:
        batch_path = _latest_batch(args.data_root)
        if batch_path is None:
            job_count = _count_job_manifests(args.data_root)
            print(f"FAIL: no batch.json found near {args.data_root}")
            if job_count:
                print(f"INFO: found {job_count} job.json file(s) under the supplied path")
                print(
                    "INFO: this looks like a Job/date directory. "
                    "For Batch acceptance you can pass the same YYYY-MM-DD directory after "
                    "updating this script; it will also inspect the sibling batches directory."
                )
                print(
                    "INFO: if the acquisition mode was '单次采集', no batch.json is expected. "
                    "Use a frequency-sweep/fixed-frequency-continuous Batch for Phase 8 H."
                )
            else:
                print("INFO: no job.json was found either; check that --data-root points at saved capture data")
            ok = False

    if batch_path is not None:
        if not batch_path.is_file():
            print(f"FAIL: batch manifest does not exist: {batch_path}")
            ok = False
        else:
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
