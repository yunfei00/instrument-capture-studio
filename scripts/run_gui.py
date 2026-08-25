#!/usr/bin/env python3
"""Launch the Instrument Capture Studio desktop UI."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from instrument_capture_studio.ui.app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
