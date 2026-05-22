"""Nexus Agent Engine — claw-code-agent integration layer.

This is the ONLY package allowed to import from factory.vendor.claw_code_agent.
All other modules go through the bridge (bridge.py).
"""

from factory.engine.bridge import (
    AgentLoopEngine,
    BudgetConfig,
    EngineConfig,
    ModelConfig,
    NexusPermissions,
    create_agent,
    create_model_config,
)
from factory.engine.tools import build_tool_registry, resolve_tools
from factory.engine.pool import AgentPool, get_pool
from factory.engine.providers import Provider, ProviderRegistry

__all__ = [
    "AgentLoopEngine",
    "AgentPool",
    "BudgetConfig",
    "EngineConfig",
    "ModelConfig",
    "NexusPermissions",
    "Provider",
    "ProviderRegistry",
    "build_tool_registry",
    "create_agent",
    "create_model_config",
    "get_pool",
    "resolve_tools",
]
