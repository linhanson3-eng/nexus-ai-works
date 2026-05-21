"""Reflector — analyzes execution trajectories to extract reusable patterns."""

from __future__ import annotations

import re

from factory.evolution.types import ExecutionTrajectory, CandidateSkill


class Reflector:
    """Analyze execution traces and generate candidate skills."""

    def __init__(self, min_tool_calls: int = 5, min_errors: int = 1):
        self.min_tool_calls = min_tool_calls
        self.min_errors = min_errors

    def analyze(self, trajectory: ExecutionTrajectory) -> list[CandidateSkill]:
        if not trajectory.qualifies_for_evolution:
            return []
        name = self._derive_name(trajectory)
        triggers = self._derive_triggers(trajectory)
        prompt = self._derive_prompt(trajectory)
        savings = trajectory.total_tokens // 3 if trajectory.success else 0
        return [CandidateSkill(
            name=name,
            description=f"Auto-generated from {trajectory.agent_name}: {trajectory.task[:100]}",
            triggers=tuple(triggers),
            prompt_template=prompt,
            source_agent=trajectory.agent_name,
            source_task=trajectory.task,
            estimated_token_savings=savings,
        )]

    def _derive_name(self, trajectory: ExecutionTrajectory) -> str:
        task = trajectory.task.strip()
        words = re.findall(r"[\w一-鿿]+", task)
        name = "-".join(words[:4]).lower() if words else "unnamed"
        return f"auto-{name}"

    def _derive_triggers(self, trajectory: ExecutionTrajectory) -> list[str]:
        tool_keywords = {
            "read_file": ["read", "file"],
            "write_file": ["write", "create"],
            "grep": ["search", "find"],
            "bash": ["run", "execute"],
            "git": ["commit", "branch"],
            "web_search": ["search", "research"],
        }
        triggers: list[str] = []
        for tool in trajectory.tools_used:
            kw = tool_keywords.get(tool, [tool])
            triggers.extend(kw[:1])
        return triggers[:5]

    def _derive_prompt(self, trajectory: ExecutionTrajectory) -> str:
        parts = [
            f"# Task Pattern: {trajectory.task[:200]}",
            "",
            "## Approach",
            f"Based on {trajectory.agent_name}'s execution using "
            f"{len(trajectory.tools_used)} tools "
            f"and overcoming {trajectory.errors_overcome} errors.",
            "",
            "## Summary",
            trajectory.summary[:500],
            "",
            "## Instructions",
            "Follow a similar approach for tasks of this type. "
            f"Focus on: {', '.join(trajectory.tools_used[:5])}.",
        ]
        return "\n".join(parts)
