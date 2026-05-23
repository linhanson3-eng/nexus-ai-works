"""Cross-workshop chain execution — sequential pipeline across workshops.

A Chain defines an ordered list of (workshop, workflow) steps.
ChainRunner executes them sequentially, feeding each step's products
as context into the next step.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

import yaml

from factory.env import env_int

logger = logging.getLogger(__name__)

CHAIN_TOTAL_TIMEOUT = env_int("CHAIN_TOTAL_TIMEOUT", 1800, min=10, max=86400)  # 30 min default


# ── Models ─────────────────────────────────────────────────────


@dataclass
class ChainStep:
    """One step in a cross-workshop chain."""

    workshop: str
    workflow: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"workshop": self.workshop}
        if self.workflow:
            d["workflow"] = self.workflow
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ChainStep:
        return cls(
            workshop=data["workshop"],
            workflow=data.get("workflow", ""),
            description=data.get("description", ""),
        )


@dataclass
class Chain:
    """An ordered pipeline of cross-workshop steps."""

    name: str
    description: str = ""
    steps: list[ChainStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Chain:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            steps=[ChainStep.from_dict(s) for s in data.get("steps", [])],
        )


# ── Storage ────────────────────────────────────────────────────


class ChainStore:
    """YAML-based persistence for chains."""

    def __init__(self, base_dir: str = "~/.nexus/chains") -> None:
        self._dir = Path(base_dir).expanduser()
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, chain: Chain) -> Path:
        path = self._dir / f"{chain.name}.yaml"
        path.write_text(yaml.dump(chain.to_dict(), allow_unicode=True, sort_keys=False), "utf-8")
        return path

    def load(self, name: str) -> Chain | None:
        path = self._dir / f"{name}.yaml"
        if not path.exists():
            return None
        data = yaml.safe_load(path.read_text("utf-8"))
        return Chain.from_dict(data)

    def delete(self, name: str) -> bool:
        path = self._dir / f"{name}.yaml"
        if path.exists():
            path.unlink()
            return True
        return False

    def list_all(self) -> list[dict[str, Any]]:
        if not self._dir.exists():
            return []
        result: list[dict[str, Any]] = []
        for p in sorted(self._dir.glob("*.yaml")):
            data = yaml.safe_load(p.read_text("utf-8"))
            result.append({
                "name": data["name"],
                "description": data.get("description", ""),
                "step_count": len(data.get("steps", [])),
                "steps": [s["workshop"] for s in data.get("steps", [])],
            })
        return result


# ── Runner ─────────────────────────────────────────────────────

StatusCallback = Callable[[str, str, str], Awaitable[None]]


@dataclass
class ChainResult:
    chain_name: str
    status: str = "pending"
    step_results: list[dict[str, Any]] = field(default_factory=list)
    final_output: str = ""


class ChainRunner:
    """Execute a Chain sequentially, passing products between steps."""

    def __init__(
        self,
        org: Any,
        kanban_store: Any = None,
        *,
        on_status: StatusCallback | None = None,
    ):
        self.org = org
        self.kanban_store = kanban_store
        self._on_status = on_status

    async def run(self, chain: Chain, task: str) -> ChainResult:
        try:
            return await asyncio.wait_for(
                self._run_impl(chain, task),
                timeout=CHAIN_TOTAL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return ChainResult(
                chain_name=chain.name,
                status="failed",
                final_output=f"Chain timeout after {CHAIN_TOTAL_TIMEOUT}s",
            )

    async def _run_impl(self, chain: Chain, task: str) -> ChainResult:
        from factory.workshop.manager import WorkshopManager
        from factory.workflow.engine import WorkflowRunner, WorkflowResult

        mgr = WorkshopManager(self.org, self.kanban_store)
        result = ChainResult(chain_name=chain.name, status="running")
        upstream_products: str = ""

        for i, step in enumerate(chain.steps):
            ws = mgr.get(step.workshop)
            if ws is None:
                await self._notify("error", step.workshop,
                                   f"Workspace '{step.workshop}' not found")
                result.status = "failed"
                result.final_output = f"Workspace not found: {step.workshop}"
                return result

            # Build enriched task with upstream context
            enriched_task = task
            if upstream_products and i > 0:
                enriched_task = (
                    f"{task}\n\n"
                    f"## 上游工作区产出 (来自 {' → '.join(s.workshop for s in chain.steps[:i])})\n\n"
                    f"{upstream_products[:4000]}"
                )

            await self._notify("step_started", step.workshop,
                               f"Step {i+1}/{len(chain.steps)}: {step.workshop}")

            # Run workflow
            if step.workflow:
                tmpl = self.org.workflow_store.load(step.workflow) if self.org.workflow_store else None
                if tmpl is None:
                    await self._notify("step_error", step.workshop,
                                       f"Workflow '{step.workflow}' not found")
                    result.status = "failed"
                    result.final_output = f"Workflow not found: {step.workflow}"
                    return result

                # Run workflow with SSE passthrough
                wf_runner = WorkflowRunner(ws, store=self.org.workflow_store,
                                           on_status=self._on_status)
                wf_result: WorkflowResult = await wf_runner.run(tmpl, enriched_task)
                step_output = wf_result.final_output
                wf_status = wf_result.status.value
            else:
                # No workflow specified — run first agent directly
                from factory.runner import NexusAgentRunner
                from factory.memory import MemoryStore

                if not ws.spec.agents:
                    step_output = f"[simulated] No agents in workspace '{step.workshop}'"
                    wf_status = "passed"
                else:
                    agent_spec = ws.spec.agents[0]
                    store = MemoryStore(":memory:")
                    runner = NexusAgentRunner(agent_spec, ws, store)
                    agent_result = await runner.run(enriched_task)
                    step_output = agent_result.content
                    wf_status = "failed" if agent_result.error else "passed"

            await self._notify("step_completed", step.workshop,
                               f"Done: {step.workshop} ({wf_status})")

            result.step_results.append({
                "workshop": step.workshop,
                "workflow": step.workflow,
                "status": wf_status,
                "output": step_output[:1000],
            })

            if wf_status == "failed":
                result.status = "failed"
                result.final_output = step_output
                return result

            # Collect products for downstream
            try:
                bridge_products = self._collect_products(step.workshop)
                if bridge_products:
                    upstream_products = bridge_products
                elif step_output:
                    upstream_products = step_output
            except Exception as exc:
                logger.warning("Bridge product collection failed for step %s: %s", step_name, exc)
                upstream_products = step_output

        result.status = "passed"
        result.final_output = result.step_results[-1]["output"] if result.step_results else ""
        await self._notify("chain_completed", chain.name, "All steps completed")
        return result

    def _collect_products(self, workshop_name: str) -> str:
        """Collect product files from a workshop for downstream context."""
        from factory.workshop.bridge import WorkshopBridge

        bridge = WorkshopBridge(self.org.warehouse)
        products = bridge.list_peer_products(workshop_name)
        if not products:
            return ""

        parts: list[str] = []
        for filename in products[:10]:
            try:
                content = bridge.read_peer_product(workshop_name, filename)
                if len(content) > 2000:
                    content = content[:2000] + "\n...(truncated)"
                parts.append(f"### {filename}\n{content}")
            except Exception as exc:
                logger.debug("Skipping unreadable product %s/%s: %s", workshop_name, filename, exc)
                continue

        return "\n\n".join(parts) if parts else ""

    async def _notify(self, event: str, target: str, detail: str) -> None:
        if self._on_status:
            try:
                await self._on_status(event, target, detail)
            except Exception:
                logger.exception("Status callback failed for target %s event %s", target, event)
