from __future__ import annotations
"""Mutator -- generates variations of candidate skills."""


import random

from factory.evolution.types import CandidateSkill


class Mutator:
    """Generate variations of candidate skills via random mutation operations."""

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    def mutate(self, candidate: CandidateSkill, num_variants: int = 2) -> list[CandidateSkill]:
        variants: list[CandidateSkill] = []
        for _ in range(num_variants):
            variants.append(self._apply_random_mutation(candidate))
        return variants

    def _apply_random_mutation(self, candidate: CandidateSkill) -> CandidateSkill:
        op = self._rng.choice(["prompt_variant", "trigger_expand", "trigger_prune"])
        if op == "prompt_variant":
            return self._mutate_prompt(candidate)
        elif op == "trigger_expand":
            return self._expand_triggers(candidate)
        else:
            return self._prune_triggers(candidate)

    def _mutate_prompt(self, candidate: CandidateSkill) -> CandidateSkill:
        new_prompt = candidate.prompt_template + f"\n\n[generation={candidate.generation + 1}]"
        return CandidateSkill(
            name=candidate.name, description=candidate.description,
            triggers=candidate.triggers, prompt_template=new_prompt,
            source_agent=candidate.source_agent, source_task=candidate.source_task,
            estimated_token_savings=candidate.estimated_token_savings,
            generation=candidate.generation + 1,
        )

    def _expand_triggers(self, candidate: CandidateSkill) -> CandidateSkill:
        generic = ["automate", "optimize", "refactor", "analyze", "generate"]
        existing = set(candidate.triggers)
        available = [t for t in generic if t not in existing]
        if not available:
            return candidate
        new_trigger = self._rng.choice(available)
        return CandidateSkill(
            name=candidate.name, description=candidate.description,
            triggers=tuple(list(candidate.triggers) + [new_trigger]),
            prompt_template=candidate.prompt_template,
            source_agent=candidate.source_agent, source_task=candidate.source_task,
            estimated_token_savings=candidate.estimated_token_savings,
            generation=candidate.generation + 1,
        )

    def _prune_triggers(self, candidate: CandidateSkill) -> CandidateSkill:
        if len(candidate.triggers) <= 2:
            return candidate
        return CandidateSkill(
            name=candidate.name, description=candidate.description,
            triggers=candidate.triggers[:-1],
            prompt_template=candidate.prompt_template,
            source_agent=candidate.source_agent, source_task=candidate.source_task,
            estimated_token_savings=candidate.estimated_token_savings,
            generation=candidate.generation + 1,
        )
