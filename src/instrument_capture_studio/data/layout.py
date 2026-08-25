from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class JobDataLayout:
    """一次 Capture Job 的标准数据目录和文件命名。"""

    root: Path
    job_id: str
    capture_date: date

    @classmethod
    def build(
        cls,
        root: Path,
        job_id: str,
        *,
        capture_date: date | None = None,
    ) -> "JobDataLayout":
        normalized_job_id = job_id.strip()

        if not normalized_job_id:
            raise ValueError(
                "job_id must not be empty"
            )

        if (
            "/" in normalized_job_id
            or "\\" in normalized_job_id
        ):
            raise ValueError(
                "job_id must not contain path separators"
            )

        return cls(
            root=Path(root),
            job_id=normalized_job_id,
            capture_date=(
                capture_date
                or date.today()
            ),
        )

    @property
    def date_directory(
        self,
    ) -> Path:
        return (
            self.root
            / self.capture_date.isoformat()
        )

    @property
    def job_directory(
        self,
    ) -> Path:
        return (
            self.date_directory
            / self.job_id
        )

    @property
    def metadata_path(
        self,
    ) -> Path:
        return (
            self.job_directory
            / "metadata.json"
        )

    @property
    def job_manifest_path(
        self,
    ) -> Path:
        return (
            self.job_directory
            / "job.json"
        )

    @property
    def spectrum_csv_path(
        self,
    ) -> Path:
        return (
            self.job_directory
            / "spectrum.csv"
        )

    @property
    def spectrum_npz_path(
        self,
    ) -> Path:
        return (
            self.job_directory
            / "spectrum.npz"
        )

    @property
    def waveform_csv_path(
        self,
    ) -> Path:
        return (
            self.job_directory
            / "waveform.csv"
        )

    @property
    def waveform_npz_path(
        self,
    ) -> Path:
        return (
            self.job_directory
            / "waveform.npz"
        )

    def create_directories(
        self,
    ) -> None:
        self.job_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
