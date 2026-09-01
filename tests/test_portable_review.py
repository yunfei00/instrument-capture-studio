import json
from pathlib import Path
import shutil

from instrument_capture_studio.data.manual_review import FORMAL_REVIEW_TRACES
from instrument_capture_studio.data.portable_review import (
    reject_portable_review_sample,
    save_portable_review_position,
    scan_portable_review_samples,
)


def _sample(root: Path, relative: str) -> Path:
    directory = root / relative
    directory.mkdir(parents=True)
    for filename in FORMAL_REVIEW_TRACES:
        (directory / filename).write_bytes(b"npz-placeholder")
    return directory


def test_portable_review_discovers_complete_samples_without_batch_metadata(tmp_path: Path):
    root = tmp_path / "copied-data"
    first = _sample(root, "700MHz/sample_0001")
    second = _sample(root, "705MHz/sample_0002")
    incomplete = root / "710MHz" / "sample_0003"
    incomplete.mkdir(parents=True)
    (incomplete / "spectrum_ext.npz").write_bytes(b"placeholder")

    scan = scan_portable_review_samples(root)

    assert [sample.directory for sample in scan.samples] == [first, second]
    assert [sample.frequency_hz for sample in scan.samples] == [700e6, 705e6]
    assert [sample.capture_index for sample in scan.samples] == [1, 2]
    assert scan.incomplete_directories == 1
    assert not (root / "batch.json").exists()


def test_portable_review_cursor_survives_root_move(tmp_path: Path):
    root = tmp_path / "original"
    _sample(root, "700MHz/sample_0001")
    _sample(root, "700MHz/sample_0002")
    scan = scan_portable_review_samples(root)
    save_portable_review_position(root, scan.samples[1], position=2, total=2)

    moved = tmp_path / "moved-copy"
    shutil.move(str(root), str(moved))
    moved_scan = scan_portable_review_samples(moved)

    assert moved_scan.resume_index == 1
    manifest = json.loads(
        (moved / ".review" / "review_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["last_sample"] == "700MHz/sample_0002"
    assert str(tmp_path) not in manifest["last_sample"]


def test_portable_review_delete_removes_only_selected_complete_sample(tmp_path: Path):
    root = tmp_path / "portable"
    first = _sample(root, "700MHz/sample_0001")
    second = _sample(root, "700MHz/sample_0002")
    scan = scan_portable_review_samples(root)

    result = reject_portable_review_sample(root, scan.samples[0])

    assert result.rejected_count == 1
    assert not first.exists()
    assert second.is_dir()
    refreshed = scan_portable_review_samples(root)
    assert [sample.directory for sample in refreshed.samples] == [second]
    assert refreshed.rejected_count == 1
    log_text = (root / ".review" / "rejected.jsonl").read_text(encoding="utf-8")
    assert "700MHz/sample_0001" in log_text
