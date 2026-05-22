"""Feature flag system — separates free/open-source features from paid/subscription features."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureFlag:
    key: str
    description: str
    free: bool


FEATURES: tuple[FeatureFlag, ...] = (
    FeatureFlag("workspace.create", "创建工作区", True),
    FeatureFlag("workspace.run_workflow", "运行工作流", True),
    FeatureFlag("workspace.agent_manage", "管理 Agent", True),
    FeatureFlag("kanban.use", "使用看板", True),
    FeatureFlag("memory.basic", "基础记忆 (30天)", True),
    FeatureFlag("mcp.builtin", "内置 MCP 工具", True),
    FeatureFlag("skill.basic", "基础技能管理", True),
    FeatureFlag("evolution.basic", "基础自进化", True),
    FeatureFlag("workflow.builtin", "内置工作流模板", True),
    FeatureFlag("library.local", "本地模板库", True),
    FeatureFlag("marketplace.browse", "浏览方案市场", True),
    # --- Paid features ---
    FeatureFlag("workspace.unlimited", "无限工作区数量", False),
    FeatureFlag("workspace.export", "导出工作区为 .nexus 包", False),
    FeatureFlag("memory.extended", "扩展记忆 (365天+ 无限容量)", False),
    FeatureFlag("evolution.advanced", "高级自进化 (自定义 Mutator)", False),
    FeatureFlag("mcp.custom", "自定义 MCP 服务端", False),
    FeatureFlag("marketplace.install", "安装付费方案", False),
    FeatureFlag("library.cloud", "云端模板库同步", False),
    FeatureFlag("chain.create", "创建协作链", False),
    FeatureFlag("agent.subagent_spawn", "Agent 创建子 Agent", False),
)

_FREE_FEATURES: frozenset[str] = frozenset(f.key for f in FEATURES if f.free)
_PAID_FEATURES: frozenset[str] = frozenset(f.key for f in FEATURES if not f.free)


def is_feature_allowed(feature_key: str, is_vip: bool = False) -> bool:
    """Check if a feature is allowed for the given subscription tier."""
    if feature_key in _FREE_FEATURES:
        return True
    if is_vip and feature_key in _PAID_FEATURES:
        return True
    return False


def get_all_features() -> tuple[FeatureFlag, ...]:
    return FEATURES


def get_paid_features() -> tuple[FeatureFlag, ...]:
    return tuple(f for f in FEATURES if not f.free)
