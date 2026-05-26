from __future__ import annotations
"""Workflow engine tests."""


import pytest


from factory.workflow import (
    WorkflowNode,
    WorkflowTemplate,
    WorkflowRunner,
    WorkflowStore,
    NodeStatus,
)


class DummyWorkshop:
    def __init__(self):
        self.agents = {}
        self.workspace = None


@pytest.fixture
def workshop():
    return DummyWorkshop()


@pytest.fixture
def runner(workshop, tmp_path, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
    return WorkflowRunner(workshop)


# ── Models ────────────────────────────────────────────────────


class TestWorkflowNode:
    def test_minimal(self):
        n = WorkflowNode(id="a", label="Node A", agent_name="test")
        assert n.id == "a"
        assert n.depends_on == []

    def test_serialize_roundtrip(self):
        n = WorkflowNode(id="b", label="B", agent_name="dev", prompt="do it", depends_on=["a"], expected_output="code")
        d = n.to_dict()
        n2 = WorkflowNode.from_dict(d)
        assert n2.id == "b"
        assert n2.agent_name == "dev"
        assert n2.depends_on == ["a"]

    def test_gate_serialize(self):
        n = WorkflowNode(id="r", label="Review", agent_name="qa", gate={"type": "review"})
        d = n.to_dict()
        assert d["gate"] == {"type": "review"}
        n2 = WorkflowNode.from_dict(d)
        assert n2.gate == {"type": "review"}


class TestWorkflowTemplate:
    def test_roundtrip(self):
        nodes = [WorkflowNode(id="a"), WorkflowNode(id="b", depends_on=["a"])]
        t = WorkflowTemplate(name="test", description="desc", workspace="ws-1", nodes=nodes)
        d = t.to_dict()
        t2 = WorkflowTemplate.from_dict(d)
        assert t2.name == "test"
        assert len(t2.nodes) == 2


# ── DAG ───────────────────────────────────────────────────────


class TestDAG:
    def test_linear(self, runner):
        nodes = [WorkflowNode(id="a"), WorkflowNode(id="b"), WorkflowNode(id="c")]
        order = runner._resolve_order(nodes)
        assert set(order) == {"a", "b", "c"}
        assert len(order) == 3

    def test_diamond(self, runner):
        nodes = [
            WorkflowNode(id="x"),
            WorkflowNode(id="y", depends_on=["x"]),
            WorkflowNode(id="z", depends_on=["x"]),
            WorkflowNode(id="w", depends_on=["y", "z"]),
        ]
        order = runner._resolve_order(nodes)
        assert order[0] == "x"
        assert order[3] == "w"

    def test_parallel_ready(self, runner):
        nodes = [
            WorkflowNode(id="a"),
            WorkflowNode(id="b"),
            WorkflowNode(id="c", depends_on=["a", "b"]),
        ]
        order = runner._resolve_order(nodes)
        assert order[0] in ("a", "b")
        assert order[1] in ("a", "b")
        assert order[2] == "c"


# ── Execution ─────────────────────────────────────────────────


class TestExecution:
    @pytest.mark.asyncio
    async def test_single_node(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        tmpl = WorkflowTemplate(name="simple", nodes=[WorkflowNode(id="exec", label="Exec")])
        events: list = []
        async def cb(nid, status, detail):
            events.append((nid, status))

        runner = WorkflowRunner(workshop, on_status=cb)
        result = await runner.run(tmpl, "do it")
        assert result.status == NodeStatus.PASSED
        assert len(events) >= 2
        assert ("exec", "running") in events

    @pytest.mark.asyncio
    async def test_parallel_execution_order(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        """A and B have no dependencies, should execute. C depends on A and B."""
        completed_order: list[str] = []

        async def cb(nid, status, detail):
            if status == "passed":
                completed_order.append(nid)

        nodes = [
            WorkflowNode(id="a", label="A"),
            WorkflowNode(id="b", label="B"),
            WorkflowNode(id="c", label="C", depends_on=["a", "b"]),
        ]
        tmpl = WorkflowTemplate(name="parallel", nodes=nodes)
        runner = WorkflowRunner(workshop, on_status=cb)
        result = await runner.run(tmpl, "test")
        assert result.status == NodeStatus.PASSED
        # A and B finish before C starts
        assert completed_order.index("a") < completed_order.index("c")
        assert completed_order.index("b") < completed_order.index("c")

    @pytest.mark.asyncio
    async def test_mock_outputs(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        nodes = [
            WorkflowNode(id="a", label="A"),
            WorkflowNode(id="b", label="B", depends_on=["a"]),
        ]
        tmpl = WorkflowTemplate(name="mock", nodes=nodes)
        runner = WorkflowRunner(workshop, mock_outputs={
            "a": {"output": "result from a"},
            "b": {"output": "result from b"},
        })
        result = await runner.run(tmpl, "test")
        assert result.status == NodeStatus.PASSED
        assert result.node_results["a"].output == "result from a"

    @pytest.mark.asyncio
    async def test_mock_failure(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        nodes = [WorkflowNode(id="bad", label="Bad")]
        tmpl = WorkflowTemplate(name="fail", nodes=nodes)
        runner = WorkflowRunner(workshop, mock_outputs={
            "bad": {"status": "failed", "error": "boom"},
        })
        result = await runner.run(tmpl, "test")
        assert result.status == NodeStatus.FAILED
        assert result.node_results["bad"].error == "boom"

    @pytest.mark.asyncio
    async def test_context_passing(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        nodes = [
            WorkflowNode(id="up", label="Up"),
            WorkflowNode(id="down", label="Down", depends_on=["up"], prompt="use upstream"),
        ]
        tmpl = WorkflowTemplate(name="ctx", nodes=nodes)
        runner = WorkflowRunner(workshop, mock_outputs={
            "up": {"output": "upstream data"},
            "down": {"output": "processed"},
        })
        result = await runner.run(tmpl, "test")
        assert "upstream data" in runner._context.get("up", "")

    @pytest.mark.asyncio
    async def test_gate_fail_retries(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        nodes = [
            WorkflowNode(id="impl", label="Impl"),
            WorkflowNode(id="review", label="Review", depends_on=["impl"], gate={"type": "review"}),
        ]
        tmpl = WorkflowTemplate(name="gate", nodes=nodes)
        runner = WorkflowRunner(workshop, mock_outputs={
            "impl": {"output": "code"},
            "review": {"output": "审查不通过，需要修改"},
        })
        result = await runner.run(tmpl, "test")
        # Should have retried impl at least once
        assert result.node_results["impl"].retries >= 1


# ── Store ─────────────────────────────────────────────────────


class TestStore:
    def test_save_and_load(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        t = WorkflowTemplate(name="test-wf", description="Test", nodes=[WorkflowNode(id="a")])
        store.save(t)
        loaded = store.load("test-wf")
        assert loaded is not None
        assert loaded.name == "test-wf"
        assert len(loaded.nodes) == 1

    def test_list_all(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        store.save(WorkflowTemplate(name="wf1"))
        store.save(WorkflowTemplate(name="wf2"))
        items = store.list_all()
        assert len(items) == 2

    def test_delete(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        store.save(WorkflowTemplate(name="del-me"))
        assert store.delete("del-me") is True
        assert store.load("del-me") is None

    def test_delete_missing(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        assert store.delete("nope") is False


# ── Review Loop Node Type ─────────────────────────────────────


class TestReviewLoopNode:
    def test_node_type_supported(self):
        """review_loop node type is accepted by WorkflowNode."""
        node = WorkflowNode(id="review", node_type="review_loop", agent_name="review-loop")
        assert node.node_type == "review_loop"

    def test_workflow_template_with_review_loop(self, tmp_path):
        """Workflow template with review_loop node type loads correctly."""
        template = WorkflowTemplate(
            name="test-review",
            nodes=[WorkflowNode(
                id="review",
                node_type="review_loop",
                agent_name="review-loop",
                prompt='{"target": "src/test.py", "models": ["deepseek/deepseek-v4-pro", "siliconflow/kimi"]}',
            )],
        )
        store = WorkflowStore(tmp_path / "workflows")
        store.save(template)
        loaded = store.load("test-review")
        assert loaded is not None
        assert loaded.nodes[0].node_type == "review_loop"

    def test_review_loop_node_with_mock(self, workshop):
        """review_loop node with mock_outputs falls back to simulated execution."""
        from factory.workflow.engine import WorkflowRunner as WR
        template = WorkflowTemplate(
            name="rl-test",
            nodes=[WorkflowNode(
                id="rv", node_type="review_loop", agent_name="rv",
                prompt='{"target": "test.py", "models": ["a/x", "b/y"]}',
            )],
        )
        runner = WR(workshop, mock_outputs={"rv": {"status": "passed", "output": "verdict=PASS"}})
        import asyncio
        result = asyncio.run(runner.run(template, "review this"))
        assert result is not None
        assert result.status in (NodeStatus.PASSED, NodeStatus.FAILED)

    def test_delete_missing(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        assert store.delete("nope") is False

    def test_load_missing(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        assert store.load("nope") is None


# ── Code Node Type ────────────────────────────────────────────


class TestCodeNode:
    def test_code_node_type_roundtrip(self):
        """node_type='code' survives serialization roundtrip."""
        node = WorkflowNode(id="c1", node_type="code", agent_name="coder")
        d = node.to_dict()
        n2 = WorkflowNode.from_dict(d)
        assert n2.node_type == "code"
        assert n2.agent_name == "coder"

    def test_extract_code_targets(self, runner):
        """_extract_code_targets finds file paths in prompt and expected_output."""
        node = WorkflowNode(
            id="c1", node_type="code",
            prompt="Write src/sort.py with bubble sort",
            expected_output="tests/test_sort.py with test cases",
        )
        targets = runner._extract_code_targets(node)
        assert "src/sort.py" in targets
        assert "tests/test_sort.py" in targets

    def test_extract_code_targets_no_duplicates(self, runner):
        """Same file in prompt and expected_output should not duplicate."""
        node = WorkflowNode(
            id="c1", node_type="code",
            prompt="Edit src/app.ts to add login",
            expected_output="Updated src/app.ts",
        )
        targets = runner._extract_code_targets(node)
        assert targets.count("src/app.ts") == 1

    def test_code_node_prompt_formatting(self, runner):
        """Code node prompt contains code-specific formatting."""
        runner._context["up"] = "some upstream data"
        node = WorkflowNode(
            id="c1", node_type="code", agent_name="coder",
            prompt="Implement bubble_sort in sort.py",
            depends_on=["up"],
        )
        prompt = runner._build_prompt(node, "Write code")
        assert "写代码完成以下任务" in prompt
        assert "sort.py" in prompt
        assert "直接输出完整代码" in prompt
        assert "## 上游阶段产出" in prompt
        assert "upstream data" in prompt
        assert "## 当前阶段" not in prompt

    def test_code_node_execution_with_mock(self, workshop, tmp_path, monkeypatch):
        """Code node with mock output returns expected result."""
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        node = WorkflowNode(
            id="c1", node_type="code", agent_name="coder",
            prompt="Write sort.py",
        )
        tmpl = WorkflowTemplate(name="code-test", nodes=[node])
        runner = WorkflowRunner(workshop, mock_outputs={
            "c1": {"status": "passed", "output": "def bubble_sort(arr): ..."},
        })
        import asyncio
        result = asyncio.run(runner.run(tmpl, "write code"))
        assert result.status == NodeStatus.PASSED
        assert "bubble_sort" in result.node_results["c1"].output

    def test_code_node_passes_upstream_context(self, workshop, tmp_path, monkeypatch):
        """Downstream code node receives upstream output in prompt."""
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        nodes = [
            WorkflowNode(id="review", label="Review", agent_name="demo"),
            WorkflowNode(
                id="fix", node_type="code", agent_name="demo",
                prompt="Fix issues in sort.py",
                depends_on=["review"],
            ),
        ]
        tmpl = WorkflowTemplate(name="ctx-test", nodes=nodes)
        runner = WorkflowRunner(workshop, mock_outputs={
            "review": {"status": "passed", "output": "Line 3: missing type hint"},
            "fix": {"status": "passed", "output": "fixed code"},
        })
        import asyncio
        result = asyncio.run(runner.run(tmpl, "test"))
        assert result.status == NodeStatus.PASSED
        assert "missing type hint" in runner._context.get("review", "")

    def test_code_review_pipeline_roundtrip(self, tmp_path):
        """4-node pipeline template roundtrip: coder → reviewer → fix → confirm."""
        nodes = [
            WorkflowNode(id="coder", node_type="code", agent_name="demo", prompt="Write code", timeout_seconds=600),
            WorkflowNode(id="reviewer", agent_name="demo", prompt="Review", depends_on=["coder"], gate={"type": "review"}),
            WorkflowNode(id="fix", node_type="code", agent_name="demo", prompt="Fix", depends_on=["reviewer"], timeout_seconds=600),
            WorkflowNode(id="confirm", agent_name="demo", prompt="Confirm", depends_on=["fix"], gate={"type": "review"}),
        ]
        tmpl = WorkflowTemplate(name="code-review-pipeline", description="Full pipeline", workspace="demo", nodes=nodes, max_total_seconds=1800)
        store = WorkflowStore(tmp_path / "workflows")
        store.save(tmpl)
        loaded = store.load("code-review-pipeline")
        assert loaded is not None
        assert len(loaded.nodes) == 4
        assert loaded.max_total_seconds == 1800
        assert loaded.nodes[0].node_type == "code"
        assert loaded.nodes[2].node_type == "code"
        assert loaded.nodes[1].gate == {"type": "review"}
        assert loaded.nodes[3].gate == {"type": "review"}


class TestOpportunityDiscovery:
    """商机发现 · 蜂群扫描 — 4 scout 并行 → 交叉验证 → 简报 → gate review 闭环."""

    @staticmethod
    def _load_template():
        import yaml
        path = Path(__file__).resolve().parent.parent.parent / "config" / "workflows" / "opportunity-discovery.yaml"
        data = yaml.safe_load(path.read_text("utf-8"))
        return WorkflowTemplate.from_dict(data)

    def test_load_and_structure(self):
        """9 nodes: 4 scouts + cross_validator + synthesizer + reviewer + fix + confirm."""
        tmpl = self._load_template()
        assert tmpl.name == "opportunity-discovery"
        assert len(tmpl.nodes) == 9
        assert tmpl.max_total_seconds == 2400

    def test_parallel_scouts(self):
        """4 scout nodes have no dependencies → execute in parallel batch."""
        tmpl = self._load_template()
        scouts = [n for n in tmpl.nodes if n.id in ("market_intel", "demand_intel", "policy_intel", "tech_intel")]
        assert len(scouts) == 4
        for s in scouts:
            assert s.depends_on == []
            assert s.agent_name == "demo"

    def test_cross_validator_depends_on_all_scouts(self):
        """cross_validator waits for all 4 scouts."""
        tmpl = self._load_template()
        cv = next(n for n in tmpl.nodes if n.id == "cross_validator")
        assert set(cv.depends_on) == {"market_intel", "demand_intel", "policy_intel", "tech_intel"}

    def test_gate_review_loop(self):
        """reviewer and confirm have gate: review."""
        tmpl = self._load_template()
        reviewer = next(n for n in tmpl.nodes if n.id == "reviewer")
        confirm = next(n for n in tmpl.nodes if n.id == "confirm")
        assert reviewer.gate == {"type": "review"}
        assert confirm.gate == {"type": "review"}

    def test_dag_order(self):
        """Verify linear order after scouts: cv → synthesizer → reviewer → fix → confirm."""
        tmpl = self._load_template()
        runner = WorkflowRunner.__new__(WorkflowRunner)
        runner._node_map = {n.id: n for n in tmpl.nodes}
        order = runner._resolve_order(tmpl.nodes)
        # Scouts all come before cross_validator
        cv_idx = order.index("cross_validator")
        for sid in ("market_intel", "demand_intel", "policy_intel", "tech_intel"):
            assert order.index(sid) < cv_idx
        # After cross_validator: synthesizer → reviewer → fix → confirm
        assert order.index("cross_validator") < order.index("synthesizer") < order.index("reviewer") < order.index("fix") < order.index("confirm")

    def test_mock_execution(self, workshop, tmp_path, monkeypatch):
        """Full pipeline with mock outputs completes successfully."""
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        tmpl = self._load_template()
        mock = {
            nid: {"status": "passed", "output": f"Mock output from {nid}"}
            for nid in ("market_intel", "demand_intel", "policy_intel", "tech_intel",
                         "cross_validator", "synthesizer", "reviewer", "fix", "confirm")
        }
        runner = WorkflowRunner(workshop, mock_outputs=mock)
        import asyncio
        result = asyncio.run(runner.run(tmpl, "社区团购 SaaS 工具市场"))
        assert result.status == NodeStatus.PASSED
        assert len(result.node_results) >= 9

    def test_roundtrip(self, tmp_path):
        """Save → load roundtrip via WorkflowStore."""
        tmpl = self._load_template()
        store = WorkflowStore(tmp_path / "workflows")
        store.save(tmpl)
        loaded = store.load("opportunity-discovery")
        assert loaded is not None
        assert len(loaded.nodes) == 9
        assert loaded.max_total_seconds == 2400


class TestMarketResearch:
    """市场调研 · 深度研报 — Planner → 4 Researchers → Reviewer → Publisher → gate review 闭环."""

    @staticmethod
    def _load_template():
        import yaml
        path = Path(__file__).resolve().parent.parent.parent / "config" / "workflows" / "market-research.yaml"
        data = yaml.safe_load(path.read_text("utf-8"))
        return WorkflowTemplate.from_dict(data)

    def test_load_and_structure(self):
        """10 nodes: planner + 4 researchers + reviewer + publisher + qa_reviewer + fix + confirm."""
        tmpl = self._load_template()
        assert tmpl.name == "market-research"
        assert len(tmpl.nodes) == 10
        assert tmpl.max_total_seconds == 3600

    def test_planner_is_entry_point(self):
        """planner has no dependencies — entry point of the pipeline."""
        tmpl = self._load_template()
        planner = next(n for n in tmpl.nodes if n.id == "planner")
        assert planner.depends_on == []

    def test_researchers_depend_on_planner(self):
        """4 researchers all depend on planner → parallel batch after planner."""
        tmpl = self._load_template()
        for rid in ("researcher_market", "researcher_competition", "researcher_demand", "researcher_risk"):
            r = next(n for n in tmpl.nodes if n.id == rid)
            assert r.depends_on == ["planner"]

    def test_reviewer_depends_on_all_researchers(self):
        """reviewer waits for all 4 researchers."""
        tmpl = self._load_template()
        reviewer = next(n for n in tmpl.nodes if n.id == "reviewer")
        assert set(reviewer.depends_on) == {
            "researcher_market", "researcher_competition", "researcher_demand", "researcher_risk",
        }

    def test_gate_review_at_qa(self):
        """qa_reviewer and confirm have gate: review."""
        tmpl = self._load_template()
        qa = next(n for n in tmpl.nodes if n.id == "qa_reviewer")
        confirm = next(n for n in tmpl.nodes if n.id == "confirm")
        assert qa.gate == {"type": "review"}
        assert confirm.gate == {"type": "review"}

    def test_dag_order(self):
        """Verify DAG: planner → researchers (parallel) → reviewer → publisher → qa → fix → confirm."""
        tmpl = self._load_template()
        runner = WorkflowRunner.__new__(WorkflowRunner)
        runner._node_map = {n.id: n for n in tmpl.nodes}
        order = runner._resolve_order(tmpl.nodes)
        # planner before all researchers
        p_idx = order.index("planner")
        for rid in ("researcher_market", "researcher_competition", "researcher_demand", "researcher_risk"):
            assert order.index(rid) > p_idx
        # researchers before reviewer
        rv_idx = order.index("reviewer")
        for rid in ("researcher_market", "researcher_competition", "researcher_demand", "researcher_risk"):
            assert order.index(rid) < rv_idx
        # sequential tail: reviewer → publisher → qa_reviewer → fix → confirm
        assert order.index("reviewer") < order.index("publisher") < order.index("qa_reviewer") < order.index("fix") < order.index("confirm")

    def test_mock_execution(self, workshop, tmp_path, monkeypatch):
        """Full pipeline with mock outputs completes successfully."""
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        tmpl = self._load_template()
        mock = {
            nid: {"status": "passed", "output": f"Mock output from {nid}"}
            for nid in ("planner", "researcher_market", "researcher_competition",
                         "researcher_demand", "researcher_risk", "reviewer",
                         "publisher", "qa_reviewer", "fix", "confirm")
        }
        runner = WorkflowRunner(workshop, mock_outputs=mock)
        import asyncio
        result = asyncio.run(runner.run(tmpl, "社区团购 SaaS 工具市场"))
        assert result.status == NodeStatus.PASSED
        assert len(result.node_results) >= 9

    def test_roundtrip(self, tmp_path):
        """Save → load roundtrip via WorkflowStore."""
        tmpl = self._load_template()
        store = WorkflowStore(tmp_path / "workflows")
        store.save(tmpl)
        loaded = store.load("market-research")
        assert loaded is not None
        assert len(loaded.nodes) == 10
        assert loaded.max_total_seconds == 3600


from pathlib import Path
