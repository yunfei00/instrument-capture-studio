from datetime import date

import pytest

from instrument_capture_studio.data.layout import (
    JobDataLayout,
)


def test_job_layout_builds_expected_paths(
    tmp_path,
):
    layout = JobDataLayout.build(
        tmp_path,
        "job-001",
        capture_date=date(
            2026,
            8,
            25,
        ),
    )

    expected_root = (
        tmp_path
        / "2026-08-25"
        / "job-001"
    )

    assert (
        layout.job_directory
        == expected_root
    )

    assert (
        layout.metadata_path
        == expected_root
        / "metadata.json"
    )

    assert (
        layout.spectrum_csv_path
        == expected_root
        / "spectrum.csv"
    )

    assert (
        layout.spectrum_npz_path
        == expected_root
        / "spectrum.npz"
    )

    assert (
        layout.waveform_csv_path
        == expected_root
        / "waveform.csv"
    )

    assert (
        layout.waveform_npz_path
        == expected_root
        / "waveform.npz"
    )


def test_job_layout_creates_directory(
    tmp_path,
):
    layout = JobDataLayout.build(
        tmp_path,
        "job-create",
        capture_date=date(
            2026,
            8,
            25,
        ),
    )

    assert (
        layout.job_directory.exists()
        is False
    )

    layout.create_directories()

    assert (
        layout.job_directory.is_dir()
        is True
    )


@pytest.mark.parametrize(
    "job_id",
    [
        "",
        "   ",
        "../job",
        "folder/job",
        r"folder\job",
    ],
)
def test_job_layout_rejects_invalid_job_id(
    tmp_path,
    job_id,
):
    with pytest.raises(
        ValueError,
    ):
        JobDataLayout.build(
            tmp_path,
            job_id,
        )
