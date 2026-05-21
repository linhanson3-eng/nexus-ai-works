"""GEPA Evolution Engine — orchestrates the full evolution cycle."""

from __future__ import annotations

from pathlib import Path

from factory.evolution.types import (
    ExecutionTrajectory,
    CandidateSkill,
    EvolutionResult,
)
from factory.evolution.reflector import Reflector
from factory.evolution.mutator import Mutator
from factory.evolution.selector import Selector


class EvolutionEngine:
    """GEPA self-evolution engine.

    Pipeline: Reflect -> Mutate -> Select -> Review (human gate)

    Triggered after agent tasks that qualify (5+ tool calls, errors overcome).
    All outputs go through the review stage before being committed as skills.
    """

    def __init__(self, skills_dir: str = "skills"):
        self.reflector = Reflector()
        self.mutator = Mutator()
        self.selector = Selector()
        self.skills_dir = skills_dir
        self._pending_review: list[CandidateSkill] = []

    async def run(self, trajectory: ExecutionTrajectory) -> EvolutionResult:
        """Run one evolution cycle on a trajectory."""
        result = EvolutionResult()

        # 1. Reflect: analyze trajectory -> candidates
        candidates = self.reflector.analyze(trajectory)
        if not candidates:
            result.status = "noop"
            result.message = (
                f"Trajectory did not qualify "
                f"(tools={trajectory.tool_count}, "
                f"errors={trajectory.errors_overcome})"
            )
            return result

        # 2. Mutate: generate variants
        all_candidates: list[CandidateSkill] = []
        for c in candidates:
            all_candidates.append(c)
            variants = self.mutator.mutate(c, num_variants=1)
            all_candidates.extend(variants)

        # 3. Select: Pareto frontier
        selected = self.selector.select(all_candidates)

        # 4. Queue for review (safety gate — human must approve)
        self._pending_review.extend(selected)

        result.skills_created = selected
        result.status = "created" if selected else "noop"
        result.message = (
            f"Generated {len(candidates)} candidates, "
            f"{len(selected)} passed selection. "
            f"Awaiting review."
        )
        return result

    def get_pending_review(self) -> list[CandidateSkill]:
        """Get skills awaiting human review before being committed."""
        return list(self._pending_review)

    def approve(self, skill_name: str) -> CandidateSkill | None:
        """Approve a skill and remove it from the review queue."""
        for i, s in enumerate(self._pending_review):
            if s.name == skill_name:
                # Write to skills directory
                skill_dir = Path(self.skills_dir) / s.name
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "Skill.md").write_text(
                    s.to_skill_md(), encoding="utf-8"
                )
                approved = self._pending_review.pop(i)
                return approved
        return None

    def reject(self, skill_name: str) -> bool:
        """Reject a skill and remove it from the review queue."""
        for i, s in enumerate(self._pending_review):
            if s.name == skill_name:
                self._pending_review.pop(i)
                return True
        return False
