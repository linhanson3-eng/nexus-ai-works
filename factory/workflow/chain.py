from __future__ import annotations

"""Chain orchestration — sequentially runs workflow templates as steps in a pipeline.

Each step references a workflow template. Steps can be freely reordered,
enabled/disabled, and configured with independent input sources and approval gates.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import ChainStep, ChainTemplate, NodeStatus
from .engine import WorkflowRunner, WorkflowResult

logger = logging.getLogger(__name__)

CHAIN_DIR = Path.home() / ".nexus" / "chains"


# ── Callbacks ──────────────────────────────────────────────────────

@dataclass
class ChainCallbacks:
    """Callbacks invoked by ChainRunner at interaction points.

    All return a dict with at minimum {"action": "..."}:
      - manual_input callback: returns {"action": "continue", "input": "..."}
      - approval callback: returns {"action": "agree" | "modify" | "execute", "modified_output": "..."}
    """

    on_manual_input: Any = None    # async (step: ChainStep) -> dict
    on_approval: Any = None        # async (step: ChainStep, output: str) -> dict
    on_step_start: Any = None      # async (step: ChainStep) -> None
    on_step_complete: Any = None   # async (step: ChainStep, result: WorkflowResult) -> None


# ── Step Result ────────────────────────────────────────────────────

@dataclass
class ChainStepResult:
    step_id: str
    template: str
    status: NodeStatus = NodeStatus.PENDING
    output: str = ""
    error: str = ""


@dataclass
class ChainResult:
    chain_name: str
    status: NodeStatus = NodeStatus.PENDING
    step_results: dict[str, ChainStepResult] = field(default_factory=dict)
    final_output: str = ""


# ── Chain Runner ───────────────────────────────────────────────────

class ChainRunner:
    """Executes a ChainTemplate by running each step's workflow in sequence.

    Steps with input.from == "manual" pause for human input via callback.
    Steps with approval == True pause for human approval after completion.
    Disabled steps (enabled == False) are skipped.
    """

    def __init__(self, workshop: Any, store: Any = None, *, callbacks: ChainCallbacks | None = None, org: Any = None):
        self.workshop = workshop
        self._store = store
        self._org = org
        self._callbacks = callbacks or ChainCallbacks()
        self._step_outputs: dict[str, str] = {}

    async def run(self, chain: ChainTemplate, task: str) -> ChainResult:
        result = ChainResult(chain_name=chain.name, status=NodeStatus.RUNNING)
        enabled_steps = [s for s in chain.steps if s.enabled]

        for step in enabled_steps:
            result.step_results[step.id] = ChainStepResult(
                step_id=step.id, template=step.template,
                status=NodeStatus.RUNNING,
            )

            # ── Resolve input ────────────────────────────
            input_source = step.input.get("from", "manual")
            step_task = task

            if input_source == "manual":
                if self._callbacks.on_manual_input:
                    await self._callbacks.on_step_start(step) if self._callbacks.on_step_start else None
                    cb_result = await self._callbacks.on_manual_input(step)
                    if cb_result.get("action") == "skip":
                        result.step_results[step.id].status = NodeStatus.SKIPPED
                        continue
                    step_task = cb_result.get("input", task)
            elif input_source == "upstream":
                upstream_id = step.input.get("step", "")
                if upstream_id and upstream_id in self._step_outputs:
                    step_task = self._step_outputs[upstream_id][:4000]

            # ── Load template ─────────────────────────────
            tmpl = None
            if self._org is not None and hasattr(self._org, "workflow_store"):
                tmpl = self._org.workflow_store.load(step.template)
            if tmpl is None:
                from .store import WorkflowStore
                ws = WorkflowStore()
                tmpl = ws.load(step.template)

            if tmpl is None:
                result.step_results[step.id].status = NodeStatus.FAILED
                result.step_results[step.id].error = f"Template not found: {step.template}"
                result.status = NodeStatus.FAILED
                result.final_output = f"Template '{step.template}' not found for step '{step.id}'"
                return result

            # ── Run workflow ──────────────────────────────
            if self._callbacks.on_step_start:
                await self._callbacks.on_step_start(step)

            runner = WorkflowRunner(self.workshop, store=self._store, org=self._org)
            wf_result = await runner.run(tmpl, step_task)

            # ── Store output ──────────────────────────────
            step_output = wf_result.final_output or ""
            self._step_outputs[step.id] = step_output
            result.step_results[step.id].output = step_output
            result.step_results[step.id].status = wf_result.status

            if self._callbacks.on_step_complete:
                await self._callbacks.on_step_complete(step, wf_result)

            # ── Approval gate ─────────────────────────────
            if step.approval:
                if self._callbacks.on_approval:
                    cb_result = await self._callbacks.on_approval(step, step_output)
                    action = cb_result.get("action", "agree")
                    if action == "modify":
                        step_output = cb_result.get("modified_output", step_output)
                        self._step_outputs[step.id] = step_output
                        result.step_results[step.id].output = step_output
                    elif action == "execute":
                        pass  # human did something manually, continue

            if wf_result.status == NodeStatus.FAILED:
                result.status = NodeStatus.FAILED
                result.final_output = wf_result.final_output
                return result

        result.status = NodeStatus.PASSED
        if enabled_steps:
            result.final_output = result.step_results[enabled_steps[-1].id].output
        return result


# ── Chain Store ────────────────────────────────────────────────────

class ChainStore:
    """CRUD for chain templates persisted as YAML files in ~/.nexus/chains/."""

    def __init__(self, directory: str | Path | None = None):
        self._dir = Path(directory) if directory else CHAIN_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, chain: ChainTemplate) -> Path:
        path = self._dir / f"{chain.name}.yaml"
        path.write_text(yaml.dump(chain.to_dict(), allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def load(self, name: str) -> ChainTemplate | None:
        path = self._dir / f"{name}.yaml"
        if not path.exists():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return ChainTemplate.from_dict(data)

    def delete(self, name: str) -> bool:
        path = self._dir / f"{name}.yaml"
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_all(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for f in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                result.append({
                    "name": data.get("name", f.stem),
                    "description": data.get("description", ""),
                    "step_count": len(data.get("steps", [])),
                })
            except Exception:
                logger.warning("Failed to parse chain file: %s", f, exc_info=True)
                result.append({"name": f.stem, "description": "(parse error)", "step_count": 0})
        return result
