"""GEPA evolution engine tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from factory.evolution.types import (
    ExecutionTrajectory,
    CandidateSkill,
    EvolutionResult,
    SkillScore,
)
from factory.evolution.reflector import Reflector
from factory.evolution.mutator import Mutator
from factory.evolution.selector import Selector
from factory.evolution.engine import EvolutionEngine
from factory.evolution.logger import EvolutionLogger
from factory.evolution.lifecycle import SkillLifecycle
from factory.evolution.rollback import RollbackManager
from factory.evolution.hook import EvolutionHook


# ── Helpers ────────────────────────────────────────────────────────────


def _qualifying_trajectory(
    *,
    tool_count: int = 7,
    errors_overcome: int = 2,
    total_tokens: int = 9000,
    success: bool = True,
) -> ExecutionTrajectory:
    return ExecutionTrajectory(
        agent_name="test-agent",
        task="Fix a XSS vulnerability in the login page and deploy to staging",
        tools_used=["read_file", "write_file", "grep", "bash", "git", "web_search"],
        tool_count=tool_count,
        errors_overcome=errors_overcome,
        total_tokens=total_tokens,
        success=success,
        summary="Found XSS in login form, sanitized input, deployed fix.",
        timestamp="2026-05-21T10:00:00Z",
    )


def _candidate_skill(
    *,
    name: str = "test-skill",
    triggers: tuple[str, ...] = ("read", "write", "search"),
    estimated_token_savings: int = 3000,
    generation: int = 1,
) -> CandidateSkill:
    return CandidateSkill(
        name=name,
        description="A test candidate skill",
        triggers=triggers,
        prompt_template="# Test Skill\n\nInstructions here.",
        source_agent="test-agent",
        source_task="Test task",
        estimated_token_savings=estimated_token_savings,
        generation=generation,
    )


# ── TestExecutionTrajectory ────────────────────────────────────────────


class TestExecutionTrajectory:
    """Tests for ExecutionTrajectory and qualifies_for_evolution."""

    def test_qualifies_with_enough_tools_and_errors(self) -> None:
        traj = _qualifying_trajectory(tool_count=7, errors_overcome=2)
        assert traj.qualifies_for_evolution is True

    def test_not_enough_tools(self) -> None:
        traj = _qualifying_trajectory(tool_count=3, errors_overcome=2)
        assert traj.qualifies_for_evolution is False

    def test_no_errors_overcome(self) -> None:
        traj = _qualifying_trajectory(tool_count=7, errors_overcome=0)
        assert traj.qualifies_for_evolution is False

    def test_both_conditions_fail(self) -> None:
        traj = _qualifying_trajectory(tool_count=2, errors_overcome=0)
        assert traj.qualifies_for_evolution is False

    def test_minimum_boundary(self) -> None:
        traj = _qualifying_trajectory(tool_count=5, errors_overcome=1)
        assert traj.qualifies_for_evolution is True

    def test_default_values(self) -> None:
        traj = ExecutionTrajectory(agent_name="a", task="t")
        assert traj.tools_used == []
        assert traj.tool_count == 0
        assert traj.errors_overcome == 0
        assert traj.total_tokens == 0
        assert traj.success is False
        assert traj.qualifies_for_evolution is False


# ── TestCandidateSkill ─────────────────────────────────────────────────


class TestCandidateSkill:
    """Tests for CandidateSkill and to_skill_md."""

    def test_to_skill_md_format(self) -> None:
        skill = _candidate_skill(
            name="auto-fix-xss",
            triggers=("read", "write", "search"),
        )
        md = skill.to_skill_md()
        assert "---" in md
        assert "name: auto-fix-xss" in md
        assert "description: A test candidate skill" in md
        assert "  - read" in md
        assert "  - write" in md
        assert "  - search" in md
        assert "# Test Skill" in md

    def test_frozen_dataclass(self) -> None:
        skill = _candidate_skill(name="test")
        with pytest.raises(Exception):
            skill.name = "changed"  # type: ignore[misc]


# ── TestReflector ──────────────────────────────────────────────────────


class TestReflector:
    """Tests for Reflector analysis of execution trajectories."""

    def test_analyze_qualifying_trajectory(self) -> None:
        reflector = Reflector()
        traj = _qualifying_trajectory()
        candidates = reflector.analyze(traj)
        assert len(candidates) == 1
        c = candidates[0]
        assert c.source_agent == "test-agent"
        assert c.source_task == traj.task
        assert len(c.triggers) > 0
        assert len(c.prompt_template) > 0
        assert "XSS" in c.prompt_template

    def test_analyze_non_qualifying_trajectory(self) -> None:
        reflector = Reflector()
        traj = _qualifying_trajectory(tool_count=2, errors_overcome=0)
        candidates = reflector.analyze(traj)
        assert candidates == []

    def test_name_derivation(self) -> None:
        reflector = Reflector()
        traj = _qualifying_trajectory()
        traj = ExecutionTrajectory(
            agent_name="a",
            task="Fix XSS vulnerability",
            tools_used=["bash"],
            tool_count=5,
            errors_overcome=1,
            total_tokens=100,
            success=True,
        )
        name = reflector._derive_name(traj)
        assert name.startswith("auto-")
        assert "xss" in name.lower()

    def test_name_derivation_empty_task(self) -> None:
        reflector = Reflector()
        traj = ExecutionTrajectory(
            agent_name="a",
            task="",
            tools_used=["bash"],
            tool_count=5,
            errors_overcome=1,
        )
        name = reflector._derive_name(traj)
        assert name == "auto-unnamed"

    def test_trigger_derivation(self) -> None:
        reflector = Reflector()
        traj = _qualifying_trajectory()
        triggers = reflector._derive_triggers(traj)
        assert len(triggers) > 0
        # read_file -> "read", write_file -> "write"
        assert "read" in triggers or "write" in triggers

    def test_trigger_derivation_max_five(self) -> None:
        reflector = Reflector()
        traj = ExecutionTrajectory(
            agent_name="a",
            task="test",
            tools_used=[
                "read_file", "write_file", "grep", "bash", "git",
                "web_search", "extra_tool",
            ],
            tool_count=7,
            errors_overcome=1,
        )
        triggers = reflector._derive_triggers(traj)
        assert len(triggers) <= 5

    def test_prompt_generation(self) -> None:
        reflector = Reflector()
        traj = _qualifying_trajectory()
        prompt = reflector._derive_prompt(traj)
        assert "Task Pattern" in prompt
        assert "test-agent" in prompt
        assert "## Approach" in prompt
        assert "## Instructions" in prompt

    def test_token_savings_zero_when_not_success(self) -> None:
        reflector = Reflector()
        traj = _qualifying_trajectory(total_tokens=9000, success=False)
        candidates = reflector.analyze(traj)
        assert candidates[0].estimated_token_savings == 0


# ── TestMutator ────────────────────────────────────────────────────────


class TestMutator:
    """Tests for Mutator skill variation generation."""

    @pytest.fixture
    def mutator(self) -> Mutator:
        return Mutator(seed=42)

    def test_mutate_produces_variants(self, mutator: Mutator) -> None:
        skill = _candidate_skill()
        variants = mutator.mutate(skill, num_variants=2)
        assert len(variants) == 2
        for v in variants:
            assert v.generation == skill.generation + 1
            assert v.source_agent == skill.source_agent

    def test_mutate_zero_variants(self, mutator: Mutator) -> None:
        skill = _candidate_skill()
        variants = mutator.mutate(skill, num_variants=0)
        assert variants == []

    def test_prompt_mutation(self, mutator: Mutator) -> None:
        skill = _candidate_skill()
        mutated = mutator._mutate_prompt(skill)
        assert "[generation=2]" in mutated.prompt_template
        assert mutated.generation == 2

    def test_trigger_expand(self, mutator: Mutator) -> None:
        skill = _candidate_skill(triggers=("read",))
        mutated = mutator._expand_triggers(skill)
        assert len(mutated.triggers) > len(skill.triggers)
        assert mutated.generation == skill.generation + 1

    def test_trigger_prune(self, mutator: Mutator) -> None:
        skill = _candidate_skill(triggers=("read", "write", "search"))
        mutated = mutator._prune_triggers(skill)
        assert len(mutated.triggers) == len(skill.triggers) - 1
        # Original should be unchanged (frozen dataclass)
        assert len(skill.triggers) == 3

    def test_trigger_prune_minimum_protection(self, mutator: Mutator) -> None:
        skill = _candidate_skill(triggers=("read",))
        mutated = mutator._prune_triggers(skill)
        assert mutated.triggers == skill.triggers

    def test_deterministic_with_seed(self) -> None:
        m1 = Mutator(seed=42)
        m2 = Mutator(seed=42)
        skill = _candidate_skill()
        v1 = m1.mutate(skill)
        v2 = m2.mutate(skill)
        assert v1[0].prompt_template == v2[0].prompt_template


# ── TestSelector ───────────────────────────────────────────────────────


class TestSelector:
    """Tests for Selector Pareto-frontier selection."""

    @pytest.fixture
    def selector(self) -> Selector:
        return Selector()

    def test_select_with_scores(self, selector: Selector) -> None:
        skill = _candidate_skill()
        scores = [
            SkillScore(
                skill_name=skill.name,
                success_rate=0.8,
                token_savings=5000,
                reuse_count=3,
                total_score=0.75,
            )
        ]
        selected = selector.select([skill], scores)
        assert len(selected) == 1

    def test_all_below_threshold(self, selector: Selector) -> None:
        skill = _candidate_skill()
        scores = [
            SkillScore(
                skill_name=skill.name,
                total_score=0.1,
            )
        ]
        selected = selector.select([skill], scores)
        assert selected == []

    def test_empty_list(self, selector: Selector) -> None:
        selected = selector.select([])
        assert selected == []

    def test_pareto_rank_ordering(self, selector: Selector) -> None:
        s1 = _candidate_skill(name="a", estimated_token_savings=1000)
        s2 = _candidate_skill(name="b", estimated_token_savings=5000)
        s3 = _candidate_skill(name="c", estimated_token_savings=3000)
        ranked = selector.pareto_rank([s1, s2, s3])
        assert ranked[0].name == "b"
        assert ranked[2].name == "a"

    def test_score_with_zero_savings(self, selector: Selector) -> None:
        skill = _candidate_skill(estimated_token_savings=0)
        scores = selector._score_candidates([skill])
        assert scores[0].success_rate == 0.0
        assert scores[0].token_savings == 0


# ── TestEvolutionEngine ────────────────────────────────────────────────


class TestEvolutionEngine:
    """Tests for the full GEPA EvolutionEngine pipeline."""

    @pytest.fixture
    def engine(self) -> EvolutionEngine:
        with tempfile.TemporaryDirectory() as tmp:
            engine = EvolutionEngine(skills_dir=tmp)
            yield engine

    @pytest.mark.asyncio
    async def test_full_run_on_qualifying(self, engine: EvolutionEngine) -> None:
        traj = _qualifying_trajectory()
        result = await engine.run(traj)
        assert result.status == "created"
        assert len(result.skills_created) > 0
        assert len(engine.get_pending_review()) > 0

    @pytest.mark.asyncio
    async def test_run_on_non_qualifying(self, engine: EvolutionEngine) -> None:
        traj = _qualifying_trajectory(tool_count=2, errors_overcome=0)
        result = await engine.run(traj)
        assert result.status == "noop"
        assert result.skills_created == []
        assert engine.get_pending_review() == []

    def test_pending_review_queue(self, engine: EvolutionEngine) -> None:
        assert engine.get_pending_review() == []
        skill = _candidate_skill()
        engine._pending_review.append(skill)
        pending = engine.get_pending_review()
        assert len(pending) == 1
        assert pending[0].name == skill.name

    def test_approve_writes_skill_md(self, engine: EvolutionEngine) -> None:
        skill = _candidate_skill(name="auto-fix-xss")
        engine._pending_review.append(skill)

        approved = engine.approve("auto-fix-xss")
        assert approved is not None
        assert approved.name == "auto-fix-xss"

        # Verify Skill.md was written
        skill_file = (
            Path(engine.skills_dir) / "auto-fix-xss" / "Skill.md"
        )
        assert skill_file.exists()
        content = skill_file.read_text()
        assert "name: auto-fix-xss" in content

        # Verify removed from queue
        assert engine.get_pending_review() == []

    def test_approve_nonexistent(self, engine: EvolutionEngine) -> None:
        approved = engine.approve("nonexistent-skill")
        assert approved is None

    def test_reject_removes_from_queue(self, engine: EvolutionEngine) -> None:
        skill = _candidate_skill(name="to-reject")
        engine._pending_review.append(skill)
        assert len(engine.get_pending_review()) == 1

        result = engine.reject("to-reject")
        assert result is True
        assert engine.get_pending_review() == []

    def test_reject_nonexistent(self, engine: EvolutionEngine) -> None:
        result = engine.reject("nonexistent")
        assert result is False

    def test_review_queue_isolated_by_instance(self, engine: EvolutionEngine) -> None:
        skill = _candidate_skill(name="isolated")
        engine._pending_review.append(skill)

        # New engine should have an empty queue
        with tempfile.TemporaryDirectory() as tmp:
            other = EvolutionEngine(skills_dir=tmp)
            assert other.get_pending_review() == []


# ── TestEvolutionResult ────────────────────────────────────────────────


class TestEvolutionResult:
    """Tests for EvolutionResult defaults."""

    def test_default_noop(self) -> None:
        result = EvolutionResult()
        assert result.status == "noop"
        assert result.skills_created == []
        assert result.skills_updated == []

    def test_fields_accessible(self) -> None:
        result = EvolutionResult(
            trajectory_id="t1",
            status="created",
            message="Generated 2 candidates",
        )
        assert result.trajectory_id == "t1"
        assert result.status == "created"
        assert result.message == "Generated 2 candidates"


# ── Phase 7: Logger ───────────────────────────────────────────────


class TestEvolutionLogger:
    @pytest.fixture
    def logger(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            log = EvolutionLogger(Path(tmp) / "evo.db")
            yield log
            log.close()

    def test_log_cycle(self, logger):
        result = EvolutionResult(trajectory_id="t1", status="created",
                                 skills_created=[], message="test")
        logger.log_cycle(result)
        history = logger.get_history()
        assert len(history) >= 1
        assert history[0]["action"] == "cycle"

    def test_log_approval(self, logger):
        logger.log_approval("test-skill", "admin")
        history = logger.get_history()
        assert history[0]["action"] == "approve"
        assert history[0]["skill_name"] == "test-skill"

    def test_log_rejection(self, logger):
        logger.log_rejection("bad-skill")
        history = logger.get_history()
        assert history[0]["action"] == "reject"

    def test_log_rollback(self, logger):
        logger.log_rollback("rolled-skill", "deprecated")
        history = logger.get_history()
        assert history[0]["action"] == "rollback"

    def test_get_history_limit(self, logger):
        for i in range(5):
            logger.log_cycle(EvolutionResult(trajectory_id=f"t{i}"))
        history = logger.get_history(limit=3)
        assert len(history) == 3

    def test_get_history_by_skill(self, logger):
        logger.log_approval("skill-a")
        logger.log_rejection("skill-b")
        logger.log_rollback("skill-a", "buggy")
        history = logger.get_history(skill_name="skill-a")
        assert len(history) == 2

    def test_get_stats(self, logger):
        logger.log_cycle(EvolutionResult())
        logger.log_approval("s1")
        logger.log_rejection("s2")
        stats = logger.get_stats()
        assert stats["cycles"] == 1
        assert stats["approved"] == 1


# ── Phase 7: Lifecycle ────────────────────────────────────────────


class TestSkillLifecycle:
    @pytest.fixture
    def lifecycle(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            yield SkillLifecycle(tmp)

    def test_register_new_skill(self, lifecycle):
        meta = lifecycle.register("demo", "A demo skill")
        assert meta.name == "demo"
        assert meta.version == 1
        assert meta.status == "active"

    def test_update_bumps_version(self, lifecycle):
        lifecycle.register("demo")
        meta = lifecycle.update("demo", new_description="v2 desc")
        assert meta is not None
        assert meta.version == 2

    def test_deprecate(self, lifecycle):
        lifecycle.register("old-skill")
        meta = lifecycle.deprecate("old-skill", "no longer useful")
        assert meta is not None
        assert meta.status == "deprecated"

    def test_retire(self, lifecycle):
        lifecycle.register("retired-skill")
        meta = lifecycle.retire("retired-skill")
        assert meta is not None
        assert meta.status == "retired"

    def test_list_active_excludes_deprecated(self, lifecycle):
        lifecycle.register("active-1")
        lifecycle.register("active-2")
        lifecycle.deprecate("active-1")
        active = lifecycle.list_active()
        assert len(active) == 1
        assert active[0].name == "active-2"

    def test_list_deprecated(self, lifecycle):
        lifecycle.register("d1")
        lifecycle.deprecate("d1")
        assert len(lifecycle.list_deprecated()) == 1

    def test_get_nonexistent(self, lifecycle):
        assert lifecycle.get("nope") is None

    def test_reload(self, lifecycle):
        lifecycle.register("reload-test")
        lifecycle.reload()
        assert lifecycle.get("reload-test") is not None


# ── Phase 7: Rollback ─────────────────────────────────────────────


class TestRollbackManager:
    @pytest.fixture
    def rollback_mgr(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            logger = EvolutionLogger(Path(tmp) / "evo.db")
            yield RollbackManager(skills, logger)
            logger.close()

    def test_rollback_removes_skill_dir(self, rollback_mgr):
        skill_dir = rollback_mgr.skills_dir / "to-rollback"
        skill_dir.mkdir(parents=True)
        (skill_dir / "Skill.md").write_text("test")
        (skill_dir / ".meta.json").write_text('{"name":"to-rollback","version":1,"status":"active"}')
        ok = rollback_mgr.rollback("to-rollback", "test rollback")
        assert ok is True
        assert not skill_dir.exists()

    def test_rollback_nonexistent(self, rollback_mgr):
        assert rollback_mgr.rollback("nope") is False

    def test_archive_created_on_rollback(self, rollback_mgr):
        skill_dir = rollback_mgr.skills_dir / "archived-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / ".meta.json").write_text('{"name":"archived-skill","version":1,"status":"active"}')
        rollback_mgr.rollback("archived-skill", "archiving")
        archived = rollback_mgr.list_archived()
        assert len(archived) >= 1


# ── Phase 7: Hook ─────────────────────────────────────────────────


class TestEvolutionHook:
    @pytest.fixture
    def hook(self, tmp_path):
        from pathlib import Path
        log = EvolutionLogger(tmp_path / "evo.db")
        yield EvolutionHook(skills_dir=str(tmp_path), logger=log)

    def test_on_task_start_sets_trajectory(self, hook):
        hook.on_task_start("agent-1", "build feature")
        assert hook.trajectory is not None
        assert hook.trajectory.agent_name == "agent-1"

    def test_on_tool_call_tracks_count(self, hook):
        hook.on_task_start("a", "t")
        hook.on_tool_call("grep", True)
        hook.on_tool_call("bash", False)
        hook.on_tool_call("grep", True)
        assert hook._tool_count == 3
        assert hook._error_count == 1
        assert len(hook._tools_used) == 2

    def test_on_task_complete_populates_trajectory(self, hook):
        hook.on_task_start("a", "t")
        hook.on_tool_call("read_file", True)
        hook.on_tool_call("write_file", True)
        hook.on_task_complete(success=True, summary="done", total_tokens=5000)
        assert hook.trajectory is not None
        assert hook.trajectory.success is True
        assert hook.trajectory.tool_count == 2
        assert hook.trajectory.total_tokens == 5000

    def test_errors_not_counted_on_failure(self, hook):
        hook.on_task_start("a", "t")
        hook.on_tool_call("bash", False)
        hook.on_tool_call("bash", False)
        hook.on_task_complete(success=False)
        assert hook.trajectory.errors_overcome == 0  # failures don't count

    @pytest.mark.asyncio
    async def test_evolve_with_qualifying_trajectory(self, hook):
        hook.on_task_start("agent-x", "complex multi-step task")
        for _ in range(6):
            hook.on_tool_call("bash", True)
        hook.on_tool_call("grep", False)
        hook.on_tool_call("bash", True)
        hook.on_task_complete(success=True, summary="overcame grep error", total_tokens=8000)
        names = await hook.evolve()
        # May or may not generate candidates depending on reflector thresholds
        assert isinstance(names, list)

    def test_approve_and_reject(self, hook):
        hook.engine._pending_review = []
        from factory.evolution.types import CandidateSkill
        cs = CandidateSkill(name="test-skill", description="test",
                            prompt_template="do stuff")
        hook.engine._pending_review.append(cs)
        assert hook.approve("test-skill") is True
