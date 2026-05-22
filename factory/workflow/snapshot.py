"""工作流执行快照 — 持久化运行状态，支持断点续跑。

Storage: ~/.nexus/runs/{run_id}.json
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import NodeStatus, WorkflowTemplate

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path("~/.nexus/runs").expanduser()


class RunSnapshot:
    """单个工作流运行的完整状态快照。"""

    def __init__(self, base_dir: str | Path = SNAPSHOT_DIR) -> None:
        self._dir = Path(base_dir)

    def _path(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.json"

    def save(
        self,
        run_id: str,
        template: WorkflowTemplate,
        task: str,
        node_states: dict[str, str],   # node_id → status value string
        node_outputs: dict[str, str],   # node_id → output text
        node_errors: dict[str, str],    # node_id → error text
        retries: dict[str, int],        # node_id → retry count
        final_output: str = "",
    ) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        data = {
            "run_id": run_id,
            "template_name": template.name,
            "task": task,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "node_states": node_states,
            "node_outputs": node_outputs,
            "node_errors": node_errors,
            "retries": retries,
            "final_output": final_output,
        }
        target = self._path(run_id)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        os.replace(tmp, target)  # atomic rename

    def load(self, run_id: str) -> dict | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def list_incomplete(self) -> list[dict]:
        """Return all incomplete runs (have PENDING/RUNNING/FAILED nodes)."""
        if not self._dir.exists():
            return []
        result = []
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt snapshot file: %s", f)
                continue
            states = data.get("node_states", {})
            has_incomplete = any(
                s in (NodeStatus.PENDING.value, NodeStatus.RUNNING.value, NodeStatus.FAILED.value)
                for s in states.values()
            )
            if has_incomplete:
                result.append(data)
        return result

    def delete(self, run_id: str) -> None:
        path = self._path(run_id)
        path.unlink(missing_ok=True)

    @staticmethod
    def new_run_id() -> str:
        return f"run-{uuid.uuid4().hex[:8]}"
