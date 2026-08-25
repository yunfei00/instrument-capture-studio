#!/usr/bin/env python3
"""Launch the Instrument Capture Studio desktop UI."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def add_platform_packages_if_available() -> None:
    """Support source runs with a sibling or nested platform checkout."""

    candidates = (
        REPO_ROOT.parent / "instrument-automation-platform",
        REPO_ROOT / "instrument-automation-platform",
    )

    platform_root = next(
        (candidate for candidate in candidates if candidate.exists()),
        None,
    )
    if platform_root is None:
        return

    for package in (
        "instrument_core",
        "instrument_scpi",
        "instrument_drivers",
    ):
        src = platform_root / "packages" / package / "src"
        if src.exists() and str(src) not in sys.path:
            sys.path.insert(0, str(src))


add_platform_packages_if_available()

from instrument_capture_studio.ui.app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
