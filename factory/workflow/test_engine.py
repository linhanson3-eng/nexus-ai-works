"""Workflow execution engine tests.

Tests are written against the WorkflowRunner API. All execution paths
are exercised via mock_outputs (no real LLM calls).
"""

from __future__ import annotations

import pytest

from factory.workflow import WorkflowTemplate, WorkflowLibrary
from factory.workflow.engine import WorkflowRunner, StageResult, WorkflowResult


class DummyWorkshop:
    """Minimal workshop stub for testing workflow execution."""

    def __init__(self):
        self.agents = {}
        self.workspace = None


@pytest.fixture
def workshop():
    return DummyWorkshop()


@pytest.fixture
def runner(workshop):
    return WorkflowRunner(workshop)


@pytest.fixture
def lib():
    return WorkflowLibrary()


class TestDAGResolution:
    def test_simple_linear(self, runner):
        stages: list[dict] = [
            {"id": "a", "agent": "super", "action": "a"},
            {"id": "b", "agent": "super", "action": "b"},
            {"id": "c", "agent": "super", "action": "c"},
        ]
        order = runner._resolve_order(stages)
        assert len(order) == 3
        assert set(order) == {"a", "b", "c"}

    def test_with_dependencies(self, runner):
        stages: list[dict] = [
            {"id": "a", "agent": "super", "action": "a"},
            {"id": "b", "agent": "super", "action": "b", "depends_on": ["a"]},
            {"id": "c", "agent": "super", "action": "c", "depends_on": ["b"]},
        ]
        order = runner._resolve_order(stages)
        assert order.index("a") < order.index("b") < order.index("c")

    def test_diamond_dag(self, runner):
        stages: list[dict] = [
            {"id": "x", "agent": "super", "action": "x"},
            {"id": "y", "agent": "super", "action": "y", "depends_on": ["x"]},
            {"id": "z", "agent": "super", "action": "z", "depends_on": ["x"]},
            {"id": "w", "agent": "super", "action": "w", "depends_on": ["y", "z"]},
        ]
        order = runner._resolve_order(stages)
        assert order.index("x") == 0
        assert order.index("w") == 3

    def test_single_stage(self, runner):
        order = runner._resolve_order([{"id": "only", "agent": "super", "action": "x"}])
        assert order == ["only"]

    def test_cycle_handled_gracefully(self, runner):
        stages: list[dict] = [
            {"id": "a", "agent": "super", "action": "a", "depends_on": ["c"]},
            {"id": "b", "agent": "super", "action": "b", "depends_on": ["a"]},
            {"id": "c", "agent": "super", "action": "c", "depends_on": ["b"]},
        ]
        order = runner._resolve_order(stages)
        assert len(order) == 3
        assert set(order) == {"a", "b", "c"}


class TestStageExecution:
    @pytest.mark.asyncio
    async def test_stage_passes(self, runner):
        stage = {"id": "test", "agent": "super", "action": "run test"}
        sr = await runner._execute_stage(stage, "task: test")
        assert isinstance(sr, StageResult)
        assert sr.status == "passed"
        assert sr.stage_id == "test"

    @pytest.mark.asyncio
    async def test_stage_with_mock_output(self, workshop):
        runner = WorkflowRunner(workshop, mock_outputs={
            "s1": {"status": "passed", "output": "mock result"},
        })
        stage = {"id": "s1", "agent": "super", "action": "x"}
        sr = await runner._execute_stage(stage, "task")
        assert sr.status == "passed"
        assert sr.output == "mock result"

    @pytest.mark.asyncio
    async def test_stage_with_mock_failure(self, workshop):
        runner = WorkflowRunner(workshop, mock_outputs={
            "bad": {"status": "failed", "error": "something broke"},
        })
        stage = {"id": "bad", "agent": "super", "action": "x"}
        sr = await runner._execute_stage(stage, "task")
        assert sr.status == "failed"
        assert sr.error == "something broke"

    @pytest.mark.asyncio
    async def test_context_passed_between_stages(self, runner):
        runner._context["up"] = "upstream output"
        prompt = runner._build_prompt(
            {"id": "down", "agent": "super", "action": "x", "depends_on": ["up"]},
            "test task",
        )
        assert "upstream output" in prompt

    @pytest.mark.asyncio
    async def test_prompt_includes_task(self, runner):
        prompt = runner._build_prompt(
            {"id": "analyze", "agent": "analyst", "action": "analyze"},
            "Review the code",
        )
        assert "Review the code" in prompt


class TestGateLogic:
    def test_review_pass_returns_current(self, runner):
        stage = {"id": "review", "agent": "reviewer", "gate": {"type": "review"}}
        sr = StageResult(stage_id="review", agent_name="reviewer", status="passed",
                         output="审查通过，没有问题")
        order = ["impl", "review", "done"]
        next_idx = runner._handle_gate(stage, sr, order, 1)
        assert next_idx == 1

    def test_review_fail_jumps_back(self, runner):
        stage = {"id": "review", "agent": "reviewer",
                 "depends_on": ["impl"],
                 "gate": {"type": "review"}}
        sr = StageResult(stage_id="review", agent_name="reviewer", status="passed",
                         output="审查不通过，需要修改")
        order = ["impl", "review", "done"]
        next_idx = runner._handle_gate(stage, sr, order, 1)
        assert next_idx == 0

    def test_non_review_gate_noop(self, runner):
        stage = {"id": "check", "agent": "super", "gate": {"type": "lint"}}
        sr = StageResult(stage_id="check", agent_name="super", status="passed",
                         output="fail")
        order = ["a", "check", "b"]
        next_idx = runner._handle_gate(stage, sr, order, 1)
        assert next_idx == 1


class TestFullWorkflow:
    @pytest.mark.asyncio
    async def test_code_review_with_mocks(self, workshop, lib):
        tmpl = lib.get("code-review")
        assert tmpl is not None
        runner = WorkflowRunner(workshop, mock_outputs={
            "analyze": {"output": "技术方案完成"},
            "implement": {"output": "代码实现完成"},
            "review": {"output": "通过，无问题"},
        })
        result = await runner.run(tmpl, "Review PR #42")
        assert result.status == "passed"
        assert len(result.stage_results) == 3

    @pytest.mark.asyncio
    async def test_simple_workflow(self, workshop, lib):
        tmpl = lib.get("simple")
        runner = WorkflowRunner(workshop, mock_outputs={
            "execute": {"output": "done"},
        })
        result = await runner.run(tmpl, "Do something")
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_workflow_result_structure(self, workshop, lib):
        tmpl = lib.get("simple")
        runner = WorkflowRunner(workshop, mock_outputs={
            "execute": {"output": "result text"},
        })
        result = await runner.run(tmpl, "test")
        assert result.template_name == "simple"
        assert result.task == "test"
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_all_builtin_workflows(self, workshop, lib):
        for wf_info in lib.list_all():
            tmpl = lib.get(wf_info["name"])
            assert tmpl is not None
            mock = {s["id"]: {"output": f"mock {s['id']}"} for s in tmpl.stages}
            for s in tmpl.stages:
                if s.get("gate", {}).get("type") == "review":
                    mock[s["id"]]["output"] = "通过"
            runner = WorkflowRunner(workshop, mock_outputs=mock)
            result = await runner.run(tmpl, f"test {wf_info['name']}")
            assert result.status == "passed", f"Workflow {wf_info['name']} failed"

    @pytest.mark.asyncio
    async def test_workflow_failure_propagates(self, workshop, lib):
        tmpl = lib.get("code-review")
        runner = WorkflowRunner(workshop, mock_outputs={
            "analyze": {"status": "failed", "error": "analysis failed"},
        })
        result = await runner.run(tmpl, "test")
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_gate_pass_with_positive_signal(self, workshop):
        tmpl = WorkflowTemplate(name="pass-test", description="", stages=[
            {"id": "impl", "agent": "super", "action": "implement"},
            {"id": "review", "agent": "reviewer", "action": "review",
             "depends_on": ["impl"], "gate": {"type": "review"}},
        ])
        runner = WorkflowRunner(workshop, mock_outputs={
            "impl": {"output": "code done"},
            "review": {"output": "审查通过，lgtm"},
        })
        result = await runner.run(tmpl, "test")
        assert result.status == "passed"
