from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class JobDataLayout:
    """Standard filesystem layout for one Capture Job."""

    root: Path
    job_id: str
    capture_date: date
    use_date_directory: bool = True

    @classmethod
    def build(
        cls,
        root: Path,
        job_id: str,
        *,
        capture_date: date | None = None,
        use_date_directory: bool = True,
    ) -> "JobDataLayout":
        normalized_job_id = job_id.strip()
        if not normalized_job_id:
            raise ValueError("job_id must not be empty")
        if "/" in normalized_job_id or "\\" in normalized_job_id:
            raise ValueError("job_id must not contain path separators")
        return cls(
            root=Path(root),
            job_id=normalized_job_id,
            capture_date=capture_date or date.today(),
            use_date_directory=bool(use_date_directory),
        )

    @property
    def date_directory(self) -> Path:
        if not self.use_date_directory:
            return self.root
        return self.root / self.capture_date.isoformat()

    @property
    def job_directory(self) -> Path:
        return self.date_directory / self.job_id

    @property
    def metadata_path(self) -> Path:
        return self.job_directory / "metadata.json"

    @property
    def job_manifest_path(self) -> Path:
        return self.job_directory / "job.json"

    # Internal legacy/debug names.
    @property
    def spectrum_csv_path(self) -> Path:
        return self.job_directory / "spectrum.csv"

    @property
    def spectrum_npz_path(self) -> Path:
        return self.job_directory / "spectrum.npz"

    @property
    def waveform_csv_path(self) -> Path:
        return self.job_directory / "waveform.csv"

    @property
    def waveform_npz_path(self) -> Path:
        return self.job_directory / "waveform.npz"

    # Final paired recipe artifacts.
    @property
    def spectrum_ext_csv_path(self) -> Path:
        return self.job_directory / "spectrum_ext.csv"

    @property
    def spectrum_ext_npz_path(self) -> Path:
        return self.job_directory / "spectrum_ext.npz"

    @property
    def waveform_sync_csv_path(self) -> Path:
        return self.job_directory / "waveform_sync.csv"

    @property
    def waveform_sync_npz_path(self) -> Path:
        return self.job_directory / "waveform_sync.npz"

    @property
    def waveform_followup_csv_path(self) -> Path:
        return self.job_directory / "waveform_followup.csv"

    @property
    def waveform_followup_npz_path(self) -> Path:
        return self.job_directory / "waveform_followup.npz"

    @property
    def spectrum_freerun_csv_path(self) -> Path:
        return self.job_directory / "spectrum_freerun.csv"

    @property
    def spectrum_freerun_npz_path(self) -> Path:
        return self.job_directory / "spectrum_freerun.npz"

    # Standalone recipes retained in v1.
    @property
    def spectrum_imm_csv_path(self) -> Path:
        return self.job_directory / "spectrum_imm.csv"

    @property
    def spectrum_imm_npz_path(self) -> Path:
        return self.job_directory / "spectrum_imm.npz"

    @property
    def waveform_delay_csv_path(self) -> Path:
        return self.job_directory / "waveform_delay.csv"

    @property
    def waveform_delay_npz_path(self) -> Path:
        return self.job_directory / "waveform_delay.npz"

    @property
    def waveform_cycle_csv_path(self) -> Path:
        return self.job_directory / "waveform_cycle.csv"

    @property
    def waveform_cycle_npz_path(self) -> Path:
        return self.job_directory / "waveform_cycle.npz"

    def create_directories(self) -> None:
        self.job_directory.mkdir(parents=True, exist_ok=True)
