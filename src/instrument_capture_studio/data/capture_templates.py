"""Named capture configuration templates stored outside the source tree."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


_INVALID_NAME_CHARS = set('<>:"/\\|?*')


@dataclass(frozen=True)
class CaptureTemplate:
    name: str
    saved_at: str
    values: dict[str, object]


class CaptureTemplateStore:
    """Persist named experiment/capture configurations as JSON files."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def list_names(self) -> tuple[str, ...]:
        if not self._root.exists():
            return ()

        names: list[str] = []
        for path in sorted(self._root.glob("*.json"), key=lambda item: item.name.lower()):
            try:
                record = self._load_path(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            names.append(record.name)
        return tuple(names)

    def save(self, name: str, values: dict[str, object]) -> CaptureTemplate:
        normalized = self._validate_name(name)
        self._root.mkdir(parents=True, exist_ok=True)
        record = CaptureTemplate(
            name=normalized,
            saved_at=datetime.now(timezone.utc).isoformat(),
            values=dict(values),
        )
        payload = {
            "schema_version": 1,
            "name": record.name,
            "saved_at": record.saved_at,
            "values": record.values,
        }
        path = self._path_for(normalized)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
        return record

    def load(self, name: str) -> CaptureTemplate:
        normalized = self._validate_name(name)
        path = self._path_for(normalized)
        if not path.exists():
            raise FileNotFoundError(f"capture template not found: {normalized}")
        return self._load_path(path)

    def delete(self, name: str) -> None:
        normalized = self._validate_name(name)
        path = self._path_for(normalized)
        if path.exists():
            path.unlink()

    def _load_path(self, path: Path) -> CaptureTemplate:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("capture template must contain a JSON object")
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported capture template schema")

        name = self._validate_name(str(payload.get("name") or ""))
        values = payload.get("values")
        if not isinstance(values, dict):
            raise ValueError("capture template values must be an object")

        return CaptureTemplate(
            name=name,
            saved_at=str(payload.get("saved_at") or ""),
            values=dict(values),
        )

    def _path_for(self, name: str) -> Path:
        return self._root / f"{name}.json"

    @staticmethod
    def _validate_name(name: str) -> str:
        normalized = str(name).strip()
        if not normalized:
            raise ValueError("模板名称不能为空")
        if normalized in {".", ".."}:
            raise ValueError("模板名称无效")
        if any(char in _INVALID_NAME_CHARS for char in normalized):
            raise ValueError("模板名称不能包含 <>:\"/\\|?*")
        return normalized


def default_template_directory() -> Path:
    return Path.home() / "InstrumentCaptureStudio" / "config" / "templates"
