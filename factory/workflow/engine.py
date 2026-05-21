"""Workflow execution engine — DAG-based multi-stage workflow runner.

Executes workflow stages in dependency order. Supports gate-based loops
(review pass/fail -> retry previous stage up to MAX_RETRIES).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from . import WorkflowTemplate


@dataclass
class StageResult:
    """Result of executing one workflow stage."""

    stage_id: str
    agent_name: str
    status: str = "pending"  # pending | running | passed | failed | skipped
    output: str = ""
    error: str = ""
    retries: int = 0


@dataclass
class WorkflowResult:
    """Result of executing an entire workflow."""

    template_name: str
    task: str
    status: str = "pending"  # pending | running | passed | failed
    stage_results: dict[str, StageResult] = field(default_factory=dict)
    final_output: str = ""


# ---------------------------------------------------------------------------
# Gate signal keywords — matched against stage output to determine pass/fail
# ---------------------------------------------------------------------------
_PASS_SIGNALS: tuple[str, ...] = (
    "pass", "passed", "通过", "approved", "lgtm", "没有问题",
)
_FAIL_SIGNALS: tuple[str, ...] = (
    "fail", "failed", "不通过", "未通过", "退回", "rejected",
    "需要修改", "有问题", "不符合",
)


class WorkflowRunner:
    """Executes a workflow template against a workshop.

    DAG execution:
    1. Topological sort of stages based on depends_on
    2. Execute stages in order, feeding upstream context downstream
    3. For each stage, call the workshop's agent to perform the action
    4. Handle gates: review pass -> continue, review fail -> retry prior
       stage (max 3 retries)
    5. Collect stage outputs into context for downstream stages
    """

    MAX_RETRIES: int = 3

    def __init__(
        self,
        workshop: Any,
        store: Any = None,
        *,
        mock_outputs: dict[str, dict[str, str]] | None = None,
    ) -> None:
        """Create a workflow runner.

        Args:
            workshop: A Workshop object with an ``agents`` dict and
                      ``workspace`` attribute.
            store: Optional memory/data store.
            mock_outputs: Optional dict mapping stage_id -> mock
                          StageResult fields.  When provided the
                          runner skips real agent execution and
                          returns the pre-configured mock result
                          instead.  Intended for testing.
        """
        self.workshop = workshop
        self.store = store
        self._mock_outputs: dict[str, dict[str, str]] = mock_outputs or {}
        self._context: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self, template: WorkflowTemplate, task: str
    ) -> WorkflowResult:
        """Execute a workflow template top to bottom.

        Returns a ``WorkflowResult`` whose ``status`` is ``"passed"``
        when every stage completes and all gates pass, or ``"failed"``
        otherwise.
        """
        result = WorkflowResult(
            template_name=template.name,
            task=task,
            status="running",
        )

        # Prime StageResult entries so callers can inspect partial results
        for stage in template.stages:
            result.stage_results[stage["id"]] = StageResult(
                stage_id=stage["id"],
                agent_name=stage.get("agent", ""),
            )

        order = self._resolve_order(template.stages)

        idx = 0
        while idx < len(order):
            stage_id = order[idx]
            stage = self._find_stage(template.stages, stage_id)
            if stage is None:
                idx += 1
                continue

            stage_result = await self._execute_stage(stage, task)
            result.stage_results[stage_id] = stage_result

            if stage_result.status == "failed":
                result.status = "failed"
                result.final_output = stage_result.error or "Stage failed"
                return result

            # Store output for downstream stages
            self._context[stage_id] = stage_result.output

            # Gate handling (review pass/fail -> retry loop)
            if "gate" in stage:
                next_idx = self._handle_gate(
                    stage, stage_result, order, idx
                )
                if next_idx != idx:
                    # Gate triggered a jump — track retries on the
                    # target stage
                    target_id = order[next_idx]
                    target_sr = result.stage_results[target_id]
                    target_sr.retries += 1
                    if target_sr.retries > self.MAX_RETRIES:
                        result.status = "failed"
                        result.final_output = (
                            f"Gate '{stage['gate']['type']}' failed "
                            f"after {self.MAX_RETRIES} retries for "
                            f"stage '{target_id}'"
                        )
                        return result
                    idx = next_idx
                    continue

            idx += 1

        # Collect final output from the last executed stage
        if order:
            final_id = order[-1]
            final_sr = result.stage_results.get(final_id)
            if final_sr is not None:
                result.final_output = final_sr.output

        result.status = "passed"
        return result

    # ------------------------------------------------------------------
    # DAG resolution
    # ------------------------------------------------------------------

    def _resolve_order(
        self, stages: list[dict[str, Any]]
    ) -> list[str]:
        """Topological sort — returns stage IDs in execution order.

        Uses Kahn's algorithm (BFS with in-degree tracking).  If the
        graph contains a cycle the remaining unvisited nodes are
        appended in alphabetical order so the caller always gets a
        complete list.
        """
        stage_ids = {s["id"] for s in stages}
        in_degree: dict[str, int] = {sid: 0 for sid in stage_ids}
        adjacency: dict[str, list[str]] = {sid: [] for sid in stage_ids}

        for s in stages:
            sid = s["id"]
            for dep in s.get("depends_on", []):
                if dep in stage_ids:
                    adjacency[dep].append(sid)
                    in_degree[sid] += 1

        queue: deque[str] = deque(
            sid for sid, deg in in_degree.items() if deg == 0
        )
        result: list[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Handle cycles gracefully — append remaining nodes sorted
        remaining = stage_ids - set(result)
        if remaining:
            result.extend(sorted(remaining))

        return result

    # ------------------------------------------------------------------
    # Stage execution
    # ------------------------------------------------------------------

    async def _execute_stage(
        self, stage: dict[str, Any], task: str
    ) -> StageResult:
        """Execute one stage via agent (or mock for testing)."""
        stage_id: str = stage["id"]
        agent_name: str = stage.get("agent", "")

        # Testing hook — return pre-configured mock result
        if stage_id in self._mock_outputs:
            mock = self._mock_outputs[stage_id]
            return StageResult(
                stage_id=stage_id,
                agent_name=agent_name,
                status=mock.get("status", "passed"),
                output=mock.get("output", ""),
                error=mock.get("error", ""),
                retries=int(mock.get("retries", 0)),
            )

        prompt = self._build_prompt(stage, task)

        try:
            agent = (
                self.workshop.agents.get(agent_name)
                if hasattr(self.workshop, "agents")
                else None
            )
            if agent is not None:
                return await self._run_with_agent(
                    stage_id, agent_name, agent, prompt
                )
            return await self._run_simulated(stage, task)
        except Exception as exc:
            return StageResult(
                stage_id=stage_id,
                agent_name=agent_name,
                status="failed",
                error=str(exc),
            )

    async def _run_with_agent(
        self,
        stage_id: str,
        agent_name: str,
        agent: Any,
        prompt: str,
    ) -> StageResult:
        """Execute a stage through a real agent runner."""
        from factory.memory.store import MemoryStore
        from factory.runner import FactoryAgentRunner

        store = self.store if self.store is not None else MemoryStore(":memory:")
        runner = FactoryAgentRunner(agent, self.workshop, store)
        agent_result = await runner.run(prompt)

        if agent_result.error:
            return StageResult(
                stage_id=stage_id,
                agent_name=agent_name,
                status="failed",
                error=agent_result.error or "Unknown error",
            )
        return StageResult(
            stage_id=stage_id,
            agent_name=agent_name,
            status="passed",
            output=agent_result.content,
        )

    async def _run_simulated(
        self, stage: dict[str, Any], task: str
    ) -> StageResult:
        """Simulated execution when no agent is available.

        Produces a deterministic output so tests and dry-runs are
        predictable.
        """
        stage_id: str = stage["id"]
        agent_name: str = stage.get("agent", "")
        action: str = stage.get("action", "")
        output_type: str = stage.get("output", "")

        content = (
            f"[simulated] Stage: {stage_id}\n"
            f"Agent: {agent_name}\n"
            f"Action: {action}\n"
            f"Task: {task}\n"
            f"Output-type: {output_type}\n"
        )
        # Include upstream context so downstream stages see a realistic
        # accumulation pattern
        upstream_ids = stage.get("depends_on", [])
        if upstream_ids:
            content += "\n## 上游阶段产出\n"
            for uid in upstream_ids:
                ctx_val = self._context.get(uid, "")
                if ctx_val:
                    content += f"- {uid}: {ctx_val[:120]}\n"

        return StageResult(
            stage_id=stage_id,
            agent_name=agent_name,
            status="passed",
            output=content,
        )

    # ------------------------------------------------------------------
    # Gate logic
    # ------------------------------------------------------------------

    def _handle_gate(
        self,
        stage: dict[str, Any],
        result: StageResult,
        order: list[str],
        current_idx: int,
    ) -> int:
        """Evaluate a review gate.

        Returns the index of the next stage to execute:

        * ``current_idx`` — gate passed; caller should advance to the
          next stage normally.
        * ``< current_idx`` — gate failed; caller should jump back to
          retry the indicated stage.
        """
        gate: dict[str, str] = stage.get("gate", {})
        gate_type: str = gate.get("type", "")

        if gate_type != "review":
            return current_idx

        passed = self._is_review_passed(result.output, gate)

        if passed:
            return current_idx  # continue forward

        # Determine which stage to retry — default to the last
        # dependency listed in depends_on
        depends_on: list[str] = stage.get("depends_on", [])
        if depends_on:
            target_id = depends_on[-1]
            try:
                return order.index(target_id)
            except ValueError:
                pass

        return current_idx  # safe default: no retry target found

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_review_passed(output: str, gate: dict[str, str]) -> bool:
        """Determine whether a review gate passed.

        Inspects *output* for known pass/fail signal keywords.
        When no signals are found the gate defaults to *passed* so
        workflows are not blocked by ambiguous output.
        """
        _ = gate  # reserved for future gate-parameter tuning
        output_lower = output.lower()

        # Explicit failure signals take priority
        for kw in _FAIL_SIGNALS:
            if kw in output_lower:
                return False

        for kw in _PASS_SIGNALS:
            if kw in output_lower:
                return True

        return True  # default: pass

    def _build_prompt(self, stage: dict[str, Any], task: str) -> str:
        """Assemble context from upstream stages for this stage."""
        parts: list[str] = [f"任务：{task}"]

        upstream = stage.get("depends_on", [])
        if upstream:
            parts.append("\n## 上游阶段产出\n")
            for dep_id in upstream:
                if dep_id in self._context:
                    parts.append(
                        f"### {dep_id}\n{self._context[dep_id]}\n"
                    )

        parts.append(f"\n## 当前阶段\n{stage.get('action', '')}")

        return "\n".join(parts)

    @staticmethod
    def _find_stage(
        stages: list[dict[str, Any]], stage_id: str
    ) -> dict[str, Any] | None:
        """Find a stage dict by its ID."""
        for s in stages:
            if s["id"] == stage_id:
                return s
        return None
