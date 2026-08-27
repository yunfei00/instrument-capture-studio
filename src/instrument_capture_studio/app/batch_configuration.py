"""Frozen runtime configuration for resumable formal Batch capture.

A resumable Batch must continue with the exact instrument/runtime settings that
were used when the Batch was first started. The snapshot is stored separately
from ``batch.json`` so it can be written as soon as the GUI receives the Batch
identifier and never gets overwritten by later Batch checkpoint writes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.app.runtime import DSOXRuntimeSettings, FSWRuntimeSettings


_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BatchCaptureConfiguration:
    recipe: CaptureRecipe
    execution_mode: ExecutionMode
    fsw_settings: FSWRuntimeSettings
    dsox_settings: DSOXRuntimeSettings
    schema_version: int = _SCHEMA_VERSION

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "recipe": self.recipe.value,
            "execution_mode": self.execution_mode.value,
            "fsw_settings": asdict(self.fsw_settings),
            "dsox_settings": asdict(self.dsox_settings),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "BatchCaptureConfiguration":
        try:
            schema_version = int(payload["schema_version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("batch configuration is missing schema_version") from exc
        if schema_version != _SCHEMA_VERSION:
            raise ValueError(
                f"unsupported batch configuration schema: {schema_version}"
            )

        fsw_payload = payload.get("fsw_settings")
        dsox_payload = payload.get("dsox_settings")
        if not isinstance(fsw_payload, dict):
            raise ValueError("batch configuration is missing fsw_settings")
        if not isinstance(dsox_payload, dict):
            raise ValueError("batch configuration is missing dsox_settings")

        try:
            recipe = CaptureRecipe(str(payload["recipe"]))
            execution_mode = ExecutionMode(str(payload["execution_mode"]))
            fsw_settings = FSWRuntimeSettings(**fsw_payload)
            dsox_settings = DSOXRuntimeSettings(**dsox_payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid batch configuration: {exc}") from exc

        if recipe is not CaptureRecipe.EXT_IMM_PAIR:
            raise ValueError("only EXT+IMM paired Batch is resumable in Phase 8B")
        if execution_mode is ExecutionMode.SINGLE:
            raise ValueError("single capture is not a resumable Batch")

        return cls(
            recipe=recipe,
            execution_mode=execution_mode,
            fsw_settings=fsw_settings,
            dsox_settings=dsox_settings,
            schema_version=schema_version,
        )


def batch_configuration_path(output_root: Path, batch_id: str) -> Path:
    normalized = str(batch_id).strip()
    if not normalized:
        raise ValueError("batch_id must not be empty")
    if "/" in normalized or "\\" in normalized:
        raise ValueError("batch_id must not contain path separators")
    return Path(output_root) / "batch-configs" / f"{normalized}.json"


def output_root_from_manifest(manifest_path: Path) -> Path:
    """Return ``<root>`` from ``<root>/batches/date/id/batch.json``."""
    path = Path(manifest_path).expanduser().resolve()
    try:
        if path.name != "batch.json" or path.parent.parent.parent.name != "batches":
            raise ValueError
        return path.parents[3]
    except (IndexError, ValueError) as exc:
        raise ValueError(f"unsupported Batch manifest location: {path}") from exc


def configuration_path_for_manifest(manifest_path: Path) -> Path:
    path = Path(manifest_path).expanduser().resolve()
    batch_id = path.parent.name
    return batch_configuration_path(output_root_from_manifest(path), batch_id)


def write_batch_configuration(
    path: Path,
    configuration: BatchCaptureConfiguration,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(configuration.to_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_batch_configuration(path: Path) -> BatchCaptureConfiguration:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load batch configuration: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("batch configuration must contain a JSON object")
    return BatchCaptureConfiguration.from_payload(payload)


def load_configuration_for_manifest(manifest_path: Path) -> BatchCaptureConfiguration:
    path = configuration_path_for_manifest(manifest_path)
    if not path.is_file():
        raise ValueError(
            "Batch has no frozen capture configuration; delete this debug Batch "
            "or start a new formal Batch before testing resume"
        )
    return load_batch_configuration(path)
