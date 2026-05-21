"""Selector -- Pareto-frontier skill selection."""

from __future__ import annotations

from factory.evolution.types import CandidateSkill, SkillScore


class Selector:
    """Pareto-frontier selection for candidate skills.

    Evaluates skills across 3 dimensions: success rate, token savings, reuse count.
    """

    def __init__(self, success_weight: float = 0.4, token_weight: float = 0.3,
                 reuse_weight: float = 0.3, min_score: float = 0.3):
        self.success_weight = success_weight
        self.token_weight = token_weight
        self.reuse_weight = reuse_weight
        self.min_score = min_score

    def select(self, candidates: list[CandidateSkill],
               scores: list[SkillScore] | None = None) -> list[CandidateSkill]:
        if not candidates:
            return []
        if scores is None:
            scores = self._score_candidates(candidates)
        selected = []
        for candidate, score in zip(candidates, scores):
            if score.total_score >= self.min_score:
                selected.append(candidate)
        return selected

    def _score_candidates(self, candidates: list[CandidateSkill]) -> list[SkillScore]:
        scores = []
        for c in candidates:
            est_success = min(1.0, c.estimated_token_savings / 10000)
            norm_savings = min(1.0, c.estimated_token_savings / 5000)
            reuse = min(1.0, c.generation / 3)
            total = (
                self.success_weight * est_success +
                self.token_weight * norm_savings +
                self.reuse_weight * reuse
            )
            scores.append(SkillScore(
                skill_name=c.name,
                success_rate=round(est_success, 3),
                token_savings=c.estimated_token_savings,
                reuse_count=c.generation,
                total_score=round(total, 3),
            ))
        return scores

    def pareto_rank(self, candidates: list[CandidateSkill]) -> list[CandidateSkill]:
        scores = self._score_candidates(candidates)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1].total_score, reverse=True)
        return [c for c, _ in ranked]
