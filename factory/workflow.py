"""工作流模板库。

平台三大板块之一。所有工作流模板统一管理、可复用、可组合。
"""

from pathlib import Path
from typing import Any

import yaml

from config.schema import AgentSpec, WorkflowSpec


class WorkflowTemplate:
    """单个工作流模板。"""

    def __init__(self, name: str, description: str, stages: list[dict[str, Any]]):
        self.name = name
        self.description = description
        self.stages = stages

    def to_spec(self, **overrides: Any) -> WorkflowSpec:
        """将模板实例化为可执行的 WorkflowSpec。"""
        stages = [{**s, **overrides.get(s.get("id", ""), {})} for s in self.stages]
        return WorkflowSpec(name=self.name, stages=stages)


class WorkflowLibrary:
    """工作流模板库 — 平台的产出定义层。

    包含内置工作流模板，支持用户自定义模板。
    车间创建时从模板库中选择工作流。
    """

    BUILTIN: dict[str, WorkflowTemplate] = {}

    def __init__(self, templates_dir: Path | None = None):
        self._custom: dict[str, WorkflowTemplate] = {}
        self._dir = templates_dir
        self._load_builtin()
        if self._dir and self._dir.exists():
            self._load_custom()

    def _load_builtin(self) -> None:
        """注册内置工作流模板。"""
        self.BUILTIN["code-review"] = WorkflowTemplate(
            name="code-review",
            description="代码审查流水线：需求分析 → 代码生成 → 审查 → 合并",
            stages=[
                {
                    "id": "analyze",
                    "agent": "super",
                    "action": "分析需求，产出技术方案到制品仓库",
                    "output": "spec",
                },
                {
                    "id": "implement",
                    "agent": "super",
                    "action": "根据技术方案实现代码",
                    "output": "code",
                    "depends_on": ["analyze"],
                },
                {
                    "id": "review",
                    "agent": "reviewer",
                    "action": "审查代码，产出审查报告",
                    "output": "review_report",
                    "depends_on": ["implement"],
                    "gate": {
                        "type": "review",
                        "pass": "审查通过",
                        "fail": "回到 implement 阶段修改",
                    },
                },
            ],
        )
        self.BUILTIN["market-analysis"] = WorkflowTemplate(
            name="market-analysis",
            description="市场分析流水线：数据采集 → 分析 → 报告",
            stages=[
                {
                    "id": "collect",
                    "agent": "analyst",
                    "action": "搜索和采集相关市场数据",
                    "output": "raw_data",
                },
                {
                    "id": "analyze",
                    "agent": "analyst",
                    "action": "分析数据，产出分析报告",
                    "output": "report",
                    "depends_on": ["collect"],
                },
                {
                    "id": "review",
                    "agent": "reviewer",
                    "action": "审查报告质量和数据来源",
                    "output": "final_report",
                    "depends_on": ["analyze"],
                },
            ],
        )
        self.BUILTIN["content-creation"] = WorkflowTemplate(
            name="content-creation",
            description="内容创作流水线：选题 → 写作 → 编辑",
            stages=[
                {
                    "id": "plan",
                    "agent": "writer",
                    "action": "研究选题，确定大纲",
                    "output": "outline",
                },
                {
                    "id": "write",
                    "agent": "writer",
                    "action": "根据大纲写作初稿",
                    "output": "draft",
                    "depends_on": ["plan"],
                },
                {
                    "id": "edit",
                    "agent": "reviewer",
                    "action": "编辑和润色",
                    "output": "final",
                    "depends_on": ["write"],
                },
            ],
        )
        self.BUILTIN["legal-review"] = WorkflowTemplate(
            name="legal-review",
            description="法律审查流水线：文档分析 → 风险识别 → 审查报告",
            stages=[
                {
                    "id": "analyze",
                    "agent": "analyst",
                    "action": "分析合同或法律文档",
                    "output": "analysis",
                },
                {
                    "id": "identify_risks",
                    "agent": "super",
                    "action": "识别法律风险点",
                    "output": "risks",
                    "depends_on": ["analyze"],
                },
                {
                    "id": "report",
                    "agent": "writer",
                    "action": "撰写法律审查报告",
                    "output": "report",
                    "depends_on": ["identify_risks"],
                },
            ],
        )
        self.BUILTIN["simple"] = WorkflowTemplate(
            name="simple",
            description="单 Agent 直接执行，无多阶段流程",
            stages=[
                {
                    "id": "execute",
                    "agent": "super",
                    "action": "执行任务，产出结果",
                    "output": "result",
                },
            ],
        )

    def _load_custom(self) -> None:
        """加载用户自定义的工作流模板。"""
        assert self._dir is not None
        for f in self._dir.glob("*.yaml"):
            with open(f) as fh:
                data = yaml.safe_load(fh)
            self._custom[data["name"]] = WorkflowTemplate(
                name=data["name"],
                description=data.get("description", ""),
                stages=data.get("stages", []),
            )

    def list_all(self) -> list[dict[str, str]]:
        """列出所有可用模板。"""
        result = []
        for name, tmpl in {**self.BUILTIN, **self._custom}.items():
            source = "builtin" if name in self.BUILTIN else "custom"
            result.append(
                {"name": name, "description": tmpl.description, "source": source}
            )
        return result

    def get(self, name: str) -> WorkflowTemplate | None:
        """获取模板。先查自定义，再查内置。"""
        return self._custom.get(name) or self.BUILTIN.get(name)
