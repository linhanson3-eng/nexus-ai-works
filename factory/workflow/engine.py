from __future__ import annotations

"""Workflow execution engine — DAG parallel execution with gate loops.

Kahn topological sort → parallel execution of independent nodes →
context passing → gate review with retry (max 3).
"""


import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from .models import WorkflowNode, WorkflowTemplate, NodeStatus, GateType
from .snapshot import RunSnapshot

logger = logging.getLogger(__name__)


@dataclass
class NodeResult:
    node_id: str
    agent_name: str
    status: NodeStatus = NodeStatus.PENDING
    output: str = ""
    error: str = ""
    retries: int = 0


@dataclass
class WorkflowResult:
    template_name: str
    task: str
    status: NodeStatus = NodeStatus.PENDING
    node_results: dict[str, NodeResult] = field(default_factory=dict)
    final_output: str = ""
    run_id: str = ""


# Callback for SSE streaming: (node_id, status, detail)
StatusCallback = Callable[[str, str, str], Awaitable[None]]


def _is_transient_error(error: str | None) -> bool:
    """Check if an error string indicates a transient (retryable) failure."""
    if not error:
        return False
    error_lower = error.lower()
    transient_keywords = ("429", "rate", "limit", "503", "timeout", "connection", "temporarily", "overloaded")
    return any(k in error_lower for k in transient_keywords)


class WorkflowRunner:
    """Executes a WorkflowTemplate with parallel node scheduling.

    - Independent nodes run in parallel via asyncio.gather
    - Nodes with dependencies wait for upstream completion
    - Review gates trigger retry loops on failure (max 3 retries)
    - SSE status callbacks fire on every node state transition
    """

    MAX_RETRIES: int = 3

    def __init__(
        self,
        workshop: Any,
        store: Any = None,
        *,
        on_status: StatusCallback | None = None,
        mock_outputs: dict[str, dict[str, str]] | None = None,
        run_id: str = "",
    ):
        self.workshop = workshop
        self.store = store
        self._on_status = on_status
        self._mock_outputs = mock_outputs or {}
        self._context: dict[str, str] = {}
        self._node_map: dict[str, WorkflowNode] = {}
        self._run_id = run_id or RunSnapshot.new_run_id()
        self._snapshot = RunSnapshot()

    async def run(self, template: WorkflowTemplate, task: str) -> WorkflowResult:
        """Execute all nodes in dependency order, parallel where possible."""
        self._node_map = {n.id: n for n in template.nodes}
        result = WorkflowResult(template_name=template.name, task=task, status=NodeStatus.RUNNING)
        result.run_id = self._run_id

        for node in template.nodes:
            result.node_results[node.id] = NodeResult(node_id=node.id, agent_name=node.agent_name)

        order = self._resolve_order(template.nodes)
        total_timeout = getattr(template, 'max_total_seconds', 0) or 0

        try:
            if total_timeout > 0:
                return await asyncio.wait_for(
                    self._run_impl(template, task, result, order),
                    timeout=total_timeout,
                )
            return await self._run_impl(template, task, result, order)
        except asyncio.TimeoutError:
            result.status = NodeStatus.FAILED
            result.final_output = f"Workflow timeout after {total_timeout}s"
            self._save_checkpoint(template, task, result)
            return result

    async def _run_impl(self, template: WorkflowTemplate, task: str, result: WorkflowResult, order: list[str]) -> WorkflowResult:
        completed: set[str] = set()
        idx = 0

        while idx < len(order):
            # Collect all ready nodes (all deps completed) starting from idx
            batch: list[str] = []
            for nid in order[idx:]:
                node = self._node_map.get(nid)
                if node and all(d in completed for d in node.depends_on):
                    batch.append(nid)

            if not batch:
                # Shouldn't happen in valid DAG, but safety
                idx += 1
                continue

            # Execute batch in parallel
            tasks = [self._execute_node(nid, task) for nid in batch]
            node_results = await asyncio.gather(*tasks)

            for nr in node_results:
                # Preserve retries from previous attempt
                prev = result.node_results.get(nr.node_id)
                if prev and prev.retries > 0:
                    nr.retries = prev.retries
                result.node_results[nr.node_id] = nr
                completed.add(nr.node_id)

                if nr.status == NodeStatus.FAILED:
                    result.status = NodeStatus.FAILED
                    result.final_output = nr.error or f"Node '{nr.node_id}' failed"
                    self._save_checkpoint(template, task, result)
                    return result

            # After batch completes, check gates on all completed nodes
            for nid in batch:
                node = self._node_map.get(nid)
                nr = result.node_results[nid]
                if node and node.gate and nr.status == NodeStatus.PASSED:
                    retry_idx = self._handle_gate(node, nr, order)
                    current_idx = order.index(nid)
                    if retry_idx != current_idx:
                        target_id = order[retry_idx]
                        target_result = result.node_results[target_id]
                        target_result.retries += 1
                        if target_result.retries > self.MAX_RETRIES:
                            result.status = NodeStatus.FAILED
                            result.final_output = f"Gate retry limit exceeded for '{target_id}'"
                            self._save_checkpoint(template, task, result)
                            return result
                        completed.discard(target_id)
                        idx = retry_idx
                        break  # restart batch collection
            else:
                max_batch_idx = max(order.index(nid) for nid in batch)
                idx = max_batch_idx + 1

            # Store outputs in context for downstream nodes
            for nid in batch:
                nr = result.node_results[nid]
                self._context[nid] = nr.output

            # Save checkpoint after batch
            self._save_checkpoint(template, task, result)

        # Collect final output
        if order:
            final_id = order[-1]
            result.final_output = result.node_results[final_id].output

        result.status = NodeStatus.PASSED
        # Clean up snapshot on success
        self._snapshot.delete(self._run_id)
        return result

    async def _execute_node(self, node_id: str, task: str) -> NodeResult:
        node = self._node_map[node_id]
        timeout = getattr(node, 'timeout_seconds', 300) or 300
        await self._notify(node_id, "running", "")

        try:
            return await asyncio.wait_for(
                self._execute_node_impl(node_id, task),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            await self._notify(node_id, "failed", f"Timeout after {timeout}s")
            return NodeResult(
                node_id=node_id, agent_name=node.agent_name,
                status=NodeStatus.FAILED, error=f"Timeout after {timeout}s",
            )

    async def _execute_node_impl(self, node_id: str, task: str) -> NodeResult:
        node = self._node_map[node_id]
        node_type = getattr(node, 'node_type', 'agent') or 'agent'

        # Condition node: agent evaluates condition, output used for routing
        # Transform node: agent runs code/transformation
        # Both fall through to the same agent execution path for now

        # Mock for testing
        if node_id in self._mock_outputs:
            mock = self._mock_outputs[node_id]
            status = NodeStatus.FAILED if mock.get("status") == "failed" else NodeStatus.PASSED
            await self._notify(node_id, status.value, mock.get("output", ""))
            return NodeResult(
                node_id=node_id, agent_name=node.agent_name,
                status=status, output=mock.get("output", ""),
                error=mock.get("error", ""),
            )

        # Build prompt with upstream context
        prompt = self._build_prompt(node, task)

        try:
            agent = None
            if hasattr(self.workshop, "agents") and self.workshop.agents:
                agent = self.workshop.agents.get(node.agent_name)
                if agent is None:
                    agent = next(iter(self.workshop.agents.values()))

            if agent is not None:
                return await self._run_with_agent(node_id, node.agent_name, agent, prompt)
            return await self._run_simulated(node, task)
        except Exception as exc:
            await self._notify(node_id, "failed", str(exc))
            return NodeResult(node_id=node_id, agent_name=node.agent_name, status=NodeStatus.FAILED, error=str(exc))

    async def _run_with_agent(self, node_id: str, agent_name: str, agent: Any, prompt: str) -> NodeResult:
        from factory.memory.store import MemoryStore

        store = self.store if self.store is not None else MemoryStore(":memory:")

        # Use injected runner factory or default to NexusAgentRunner
        runner_factory = getattr(self, "_runner_factory", None)
        if runner_factory is None:
            from factory.runner import NexusAgentRunner
            runner_factory = NexusAgentRunner

        max_retries = 2
        for attempt in range(max_retries + 1):
            runner = runner_factory(agent, self.workshop, store)
            agent_result = await runner.run(prompt)

            if agent_result.error is None:
                await self._notify(node_id, "passed", agent_result.content[:200])
                return NodeResult(node_id=node_id, agent_name=agent_name, status=NodeStatus.PASSED, output=agent_result.content)

            error_kind = getattr(agent_result, "error_kind", None)
            error_str = agent_result.error or ""
            if error_kind and error_kind.value:
                error_str = f"[{error_kind.value}] {error_str}"

            if attempt < max_retries and _is_transient_error(error_str):
                await asyncio.sleep(2 ** attempt)
                continue

            await self._notify(node_id, "failed", error_str)
            return NodeResult(node_id=node_id, agent_name=agent_name, status=NodeStatus.FAILED, error=error_str)

        # Unreachable — kept for type completeness
        await self._notify(node_id, "failed", "Max retries exceeded")
        return NodeResult(node_id=node_id, agent_name=agent_name, status=NodeStatus.FAILED, error="Max retries exceeded")

    async def _run_simulated(self, node: WorkflowNode, task: str) -> NodeResult:
        content = f"[simulated] Node: {node.id}\nAgent: {node.agent_name}\nTask: {task}"
        upstream_ids = node.depends_on
        if upstream_ids:
            content += "\n## Upstream outputs\n"
            for uid in upstream_ids:
                ctx_val = self._context.get(uid, "")
                if ctx_val:
                    content += f"- {uid}: {ctx_val[:200]}\n"
        await self._notify(node.id, "passed", content[:200])
        return NodeResult(node_id=node.id, agent_name=node.agent_name, status=NodeStatus.PASSED, output=content)

    # ── DAG resolution ──────────────────────────────────────────

    def _resolve_order(self, nodes: list[WorkflowNode]) -> list[str]:
        node_ids = {n.id for n in nodes}
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
        adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}

        for n in nodes:
            for dep in n.depends_on:
                if dep in node_ids:
                    adjacency[dep].append(n.id)
                    in_degree[n.id] += 1

        queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
        result: list[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        remaining = node_ids - set(result)
        if remaining:
            result.extend(sorted(remaining))
        return result

    # ── Gate ─────────────────────────────────────────────────────

    def _handle_gate(self, node: WorkflowNode, result: NodeResult, order: list[str]) -> int:
        """Return the index in order to retry, or current index if passed."""
        gate = node.gate or {}
        if gate.get("type") != GateType.REVIEW.value:
            return order.index(node.id)

        # Simple heuristic: if output contains failure signals, retry upstream
        output_lower = result.output.lower()
        fail_signals = ["不通过", "fail", "需要修改", "reject", "问题", "error"]
        if any(s in output_lower for s in fail_signals):
            target_id = node.depends_on[-1] if node.depends_on else node.id
            try:
                return order.index(target_id)
            except ValueError:
                pass
        return order.index(node.id)

    # ── Helpers ──────────────────────────────────────────────────

    def _save_checkpoint(self, template: WorkflowTemplate, task: str, result: WorkflowResult) -> None:
        """Save current execution state to snapshot for potential resume."""
        self._snapshot.save(
            run_id=self._run_id,
            template=template,
            task=task,
            node_states={nid: nr.status.value for nid, nr in result.node_results.items()},
            node_outputs={nid: nr.output for nid, nr in result.node_results.items()},
            node_errors={nid: nr.error for nid, nr in result.node_results.items()},
            retries={nid: nr.retries for nid, nr in result.node_results.items()},
            final_output=result.final_output,
        )

    def _build_prompt(self, node: WorkflowNode, task: str) -> str:
        node_type = getattr(node, 'node_type', 'agent') or 'agent'
        if node_type == 'condition':
            parts: list[str] = [f"判断以下条件是否成立，只回答「通过」或「不通过」：\n{node.prompt}"]
        elif node_type == 'transform':
            parts: list[str] = [f"执行以下代码或数据转换：\n{node.prompt}"]
        else:
            parts: list[str] = [f"任务：{task}"]
        if node.depends_on:
            parts.append("\n## 上游阶段产出\n")
            for dep_id in node.depends_on:
                if dep_id in self._context:
                    parts.append(f"### {dep_id}\n{self._context[dep_id][:2000]}\n")
        parts.append(f"\n## 当前阶段\n{node.prompt or node.expected_output}")
        return "\n".join(parts)

    async def _notify(self, node_id: str, status: str, detail: str) -> None:
        if self._on_status:
            try:
                await self._on_status(node_id, status, detail)
            except Exception:
                logger.exception("Status callback failed for node %s: %s", node_id, status)

    # ── Resume ────────────────────────────────────────────────────

    @staticmethod
    async def resume_from(run_id: str, org, workshop=None) -> WorkflowResult | None:
        """Resume a previously interrupted workflow run.

        Args:
            run_id: The run ID to resume.
            org: OrgEngine instance (for workflow_store access).
            workshop: Optional workshop override.

        Returns:
            WorkflowResult if resumed successfully, None if snapshot not found.
        """
        snap = RunSnapshot()
        data = snap.load(run_id)
        if data is None:
            return None

        tmpl = org.workflow_store.load(data["template_name"])
        if tmpl is None:
            return None

        # Build mock_outputs for completed nodes so they return instantly
        mock_outputs: dict[str, dict[str, str]] = {}
        for nid, status_str in data["node_states"].items():
            if status_str == NodeStatus.PASSED.value:
                mock_outputs[nid] = {
                    "status": "passed",
                    "output": data["node_outputs"].get(nid, ""),
                    "error": "",
                }

        runner = WorkflowRunner(
            workshop or (org.workshops[0] if org.workshops else None),
            mock_outputs=mock_outputs,
            run_id=run_id,
        )

        # Execute — completed nodes will be mocked (instant return)
        # PENDING nodes will execute normally
        result = await runner.run(tmpl, data["task"])

        # If complete, clean up
        if result.status == NodeStatus.PASSED:
            snap.delete(run_id)

        return result
