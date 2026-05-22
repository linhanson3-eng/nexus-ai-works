"""EvolutionHook — integrate GEPA evolution into AgentRunner execution."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from factory.evolution.types import ExecutionTrajectory
from factory.evolution.engine import EvolutionEngine
from factory.evolution.logger import EvolutionLogger
from factory.evolution.lifecycle import SkillLifecycle


class EvolutionHook:
    """Hook that collects execution trajectories and triggers evolution.

    Attach to FactoryAgentRunner to automatically analyze task executions
    and generate candidate skills from qualifying trajectories.

    Usage:
        hook = EvolutionHook(skills_dir="skills")
        runner = FactoryAgentRunner(..., evolution_hook=hook)
        result = await runner.run(task)
        # hook.trajectory now contains the execution trace
        candidates = await hook.evolve()
    """

    def __init__(self, skills_dir: str = "skills",
                 min_tool_calls: int = 5, min_errors: int = 1):
        self.skills_dir = skills_dir
        self.min_tool_calls = min_tool_calls
        self.min_errors = min_errors
        self.engine = EvolutionEngine(skills_dir)
        self.logger = EvolutionLogger()
        self.lifecycle = SkillLifecycle(skills_dir)
        self.trajectory: ExecutionTrajectory | None = None
        self._tool_count = 0
        self._error_count = 0
        self._tools_used: list[str] = []

    def on_task_start(self, agent_name: str, task: str) -> None:
        self._tool_count = 0
        self._error_count = 0
        self._tools_used = []
        self.trajectory = ExecutionTrajectory(
            agent_name=agent_name,
            task=task,
            timestamp=self._utc_now(),
        )

    def on_tool_call(self, tool_name: str, success: bool) -> None:
        self._tool_count += 1
        if tool_name not in self._tools_used:
            self._tools_used.append(tool_name)
        if not success:
            self._error_count += 1

    def on_task_complete(self, success: bool, summary: str = "",
                         total_tokens: int = 0) -> None:
        if self.trajectory is None:
            return
        self.trajectory = replace(
            self.trajectory,
            tools_used=list(self._tools_used),
            tool_count=self._tool_count,
            errors_overcome=self._error_count if success else 0,
            success=success,
            summary=summary,
            total_tokens=total_tokens,
        )

    async def evolve(self) -> list[str]:
        """Run the evolution cycle if the trajectory qualifies."""
        if self.trajectory is None:
            return []
        result = await self.engine.run(self.trajectory)
        self.logger.log_cycle(result)
        names = [s.name for s in result.skills_created]
        for s in result.skills_created:
            self.lifecycle.register(s.name, s.description)
        return names

    def approve(self, skill_name: str, approved_by: str = "human") -> bool:
        skill = self.engine.approve(skill_name)
        if skill:
            self.logger.log_approval(skill_name, approved_by)
            self.lifecycle.update(skill_name, skill.description)
            return True
        return False

    def reject(self, skill_name: str, rejected_by: str = "human") -> bool:
        ok = self.engine.reject(skill_name)
        if ok:
            self.logger.log_rejection(skill_name, rejected_by)
        return ok

    def _utc_now(self) -> str:
        from datetime import timezone, datetime
        return datetime.now(timezone.utc).isoformat()
