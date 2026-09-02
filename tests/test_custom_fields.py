import json
from pathlib import Path

import pytest

from instrument_capture_studio.data.batch_manifest import write_batch_manifest
from instrument_capture_studio.data.custom_fields import (
    ensure_sample_info,
    normalize_user_fields,
    read_sample_user_fields,
    update_batch_user_fields,
    update_directory_user_fields,
    write_sample_user_fields,
)


FORMAL = (
    "spectrum_ext.npz",
    "waveform_sync.npz",
    "waveform_followup.npz",
    "spectrum_freerun.npz",
)


def _paired_sample(directory: Path) -> None:
    directory.mkdir(parents=True)
    for name in FORMAL:
        (directory / name).write_bytes(b"npz-placeholder")


def test_normalize_user_fields_preserves_order_and_rejects_duplicates():
    fields = normalize_user_fields(
        [
            {"name": " 项目名称 ", "value": " P1 "},
            {"name": "手机型号", "value": "ABC"},
            {"name": "", "value": ""},
        ]
    )
    assert fields == (
        {"name": "项目名称", "value": "P1"},
        {"name": "手机型号", "value": "ABC"},
    )

    with pytest.raises(ValueError, match="名称重复"):
        normalize_user_fields(
            [
                {"name": "项目名称", "value": "A"},
                {"name": "项目名称", "value": "B"},
            ]
        )


def test_sample_info_is_portable_and_editable_without_npz_rewrite(tmp_path: Path):
    sample = tmp_path / "700MHz" / "sample_0001"
    _paired_sample(sample)
    before = {name: (sample / name).read_bytes() for name in FORMAL}

    path = ensure_sample_info(
        sample,
        job_id="sample_0001",
        frequency_hz=700e6,
        user_fields=[
            {"name": "项目名称", "value": "Power2"},
            {"name": "Android版本", "value": "16"},
        ],
    )
    assert path == sample / "sample_info.json"
    assert read_sample_user_fields(sample)[0]["value"] == "Power2"

    write_sample_user_fields(
        sample,
        [{"name": "项目名称", "value": "Power2-new"}],
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["revision"] == 2
    assert payload["user_fields"] == [
        {"name": "项目名称", "value": "Power2-new"}
    ]
    assert {name: (sample / name).read_bytes() for name in FORMAL} == before


def test_directory_update_creates_sample_info_for_copied_dataset(tmp_path: Path):
    first = tmp_path / "700MHz" / "sample_0001"
    second = tmp_path / "705MHz" / "sample_0002"
    _paired_sample(first)
    _paired_sample(second)

    updated = update_directory_user_fields(
        tmp_path,
        [
            {"name": "测试场景", "value": "游戏"},
            {"name": "手机型号", "value": "ABC-AN00"},
        ],
    )

    assert updated == 2
    assert read_sample_user_fields(first)[0]["value"] == "游戏"
    assert read_sample_user_fields(second)[1]["value"] == "ABC-AN00"


def test_batch_update_changes_manifest_and_existing_samples(tmp_path: Path):
    batch = tmp_path / "batches" / "batch-fields"
    job_id = "batch-fields-f001-n0001"
    sample = batch / "f001_700MHz" / job_id
    _paired_sample(sample)
    manifest_path = batch / "batch.json"
    write_batch_manifest(
        manifest_path,
        {
            "schema_version": 1,
            "batch_id": "batch-fields",
            "state": "succeeded",
            "jobs": [
                {
                    "job_id": job_id,
                    "state": "succeeded",
                    "frequency_hz": 700e6,
                    "frequency_index": 1,
                    "capture_index": 1,
                }
            ],
        },
    )

    count = update_batch_user_fields(
        manifest_path,
        [{"name": "项目名称", "value": "Project-A"}],
    )

    assert count == 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["user_fields"] == [
        {"name": "项目名称", "value": "Project-A"}
    ]
    assert read_sample_user_fields(sample) == (
        {"name": "项目名称", "value": "Project-A"},
    )


def test_batch_update_refuses_running_or_paused_batch(tmp_path: Path):
    for state in ("running", "paused"):
        manifest_path = tmp_path / state / "batch.json"
        write_batch_manifest(
            manifest_path,
            {
                "schema_version": 1,
                "batch_id": f"batch-{state}",
                "state": state,
                "user_fields": [{"name": "项目名称", "value": "Original"}],
                "jobs": [],
            },
        )

        with pytest.raises(RuntimeError, match="不允许修改项目记录"):
            update_batch_user_fields(
                manifest_path,
                [{"name": "项目名称", "value": "Changed"}],
            )

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert payload["user_fields"] == [
            {"name": "项目名称", "value": "Original"}
        ]
