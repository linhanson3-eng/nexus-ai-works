"""Workflow template persistence — YAML files in ~/.nexus/workflows/."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .models import WorkflowTemplate

logger = logging.getLogger(__name__)

DEFAULT_DIR = Path.home() / ".nexus" / "workflows"


class WorkflowStore:
    """CRUD for workflow templates persisted as YAML files."""

    def __init__(self, directory: str | Path | None = None):
        self._dir = Path(directory) if directory else DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, template: WorkflowTemplate) -> Path:
        path = self._dir / f"{template.name}.yaml"
        path.write_text(yaml.dump(template.to_dict(), allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def load(self, name: str) -> WorkflowTemplate | None:
        path = self._dir / f"{name}.yaml"
        if not path.exists():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return WorkflowTemplate.from_dict(data)

    def delete(self, name: str) -> bool:
        path = self._dir / f"{name}.yaml"
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_all(self) -> list[dict[str, str]]:
        result = []
        for f in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                result.append({
                    "name": data.get("name", f.stem),
                    "description": data.get("description", ""),
                    "workspace": data.get("workspace", ""),
                    "node_count": len(data.get("nodes", [])),
                })
            except Exception:
                logger.warning("Failed to parse workflow file: %s", f, exc_info=True)
                result.append({"name": f.stem, "description": "(parse error)", "workspace": "", "node_count": 0})
        return result
