"""Bridge layer — the ONLY module allowed to import from factory.vendor.claw_code_agent.

All Nexus code goes through this bridge. To swap the agent engine,
only this file needs to change.
"""

from __future__ import annotations

import asyncio as _asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── claw-code-agent imports (vendor boundary) ──────────────────

from factory.vendor.claw_code_agent.agent_runtime import LocalCodingAgent
from factory.vendor.claw_code_agent.agent_types import (
    AgentPermissions as _ClawPermissions,
    AgentRunResult,
    AgentRuntimeConfig,
    BudgetConfig,
    ModelConfig,
)


# ── Nexus re-exports (thin wrappers) ───────────────────────────


@dataclass(frozen=True)
class EngineConfig:
    """Nexus engine configuration — maps to claw-code AgentRuntimeConfig."""

    cwd: Path = field(default_factory=Path.cwd)
    max_turns: int = 30
    command_timeout_seconds: float = 120.0
    max_output_chars: int = 16000
    allow_file_write: bool = True
    allow_shell_commands: bool = True
    allow_destructive_shell: bool = False

    # Streaming
    stream_model_responses: bool = True

    # Context management
    auto_compact_tokens: int = 80000
    auto_snip_tokens: int = 30000
    compact_preserve_messages: int = 6

    # Budget
    budget: BudgetConfig | None = None

    # Prompt
    system_prompt: str = ""
    disable_claude_md: bool = True

    # Session
    session_directory: str = ""
    scratchpad_root: str = ""

    def to_claw_runtime_config(self) -> AgentRuntimeConfig:
        perm = _ClawPermissions(
            allow_file_write=self.allow_file_write,
            allow_shell_commands=self.allow_shell_commands,
            allow_destructive_shell_commands=self.allow_destructive_shell,
        )
        budget = self.budget or BudgetConfig()
        return AgentRuntimeConfig(
            cwd=self.cwd,
            max_turns=self.max_turns,
            command_timeout_seconds=self.command_timeout_seconds,
            max_output_chars=self.max_output_chars,
            stream_model_responses=self.stream_model_responses,
            permissions=perm,
            auto_compact_threshold_tokens=self.auto_compact_tokens,
            auto_snip_threshold_tokens=self.auto_snip_tokens,
            compact_preserve_messages=self.compact_preserve_messages,
            budget_config=budget,
            disable_claude_md_discovery=self.disable_claude_md,
            session_directory=(
                Path(self.session_directory) if self.session_directory else self.cwd / ".sessions"
            ),
            scratchpad_root=(
                Path(self.scratchpad_root) if self.scratchpad_root else self.cwd / ".scratch"
            ),
        )


@dataclass(frozen=True)
class NexusPermissions:
    """Nexus permission model — maps from config/schema.py AgentPermissions."""

    allow_file_write: bool = False
    allow_shell_commands: bool = False
    allow_destructive_shell: bool = False


def _normalize_base_url(url: str) -> str:
    """Ensure base_url ends with /v1 for OpenAI-compatible APIs."""
    if not url:
        return url
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return url


def create_model_config(
    model: str,
    base_url: str = "",
    api_key: str = "",
    temperature: float = 0.0,
    timeout_seconds: float = 120.0,
    *,
    registry: Any = None,
) -> ModelConfig:
    """Create a ModelConfig from Nexus settings.

    If a ProviderRegistry is passed, the model string is resolved
    through it: ``"anthropic/claude-sonnet-4-6"`` → provider base_url
    and actual model name ``"claude-sonnet-4-6"``.
    """
    actual_model = model
    if registry is not None:
        provider, resolved = registry.resolve(model)
        if provider is not None:
            actual_model = resolved
            base_url = provider.base_url or base_url
            api_key = provider.api_key or api_key

    base_url = _normalize_base_url(base_url)

    if not base_url:
        raise ValueError(
            f"No base_url configured for model '{model}'. "
            f"Please add a provider in Settings > LLM Key."
        )

    return ModelConfig(
        model=actual_model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
    )


def create_agent(
    model_config: ModelConfig,
    engine_config: EngineConfig,
    *,
    append_system_prompt: str | None = None,
) -> LocalCodingAgent:
    """Create a LocalCodingAgent instance from Nexus configs.

    If engine_config.system_prompt is set, it completely overrides the
    vendor system prompt (Claude Code minimal style). Otherwise the
    vendor default is used.
    """
    runtime_config = engine_config.to_claw_runtime_config()
    return LocalCodingAgent(
        model_config=model_config,
        runtime_config=runtime_config,
        override_system_prompt=engine_config.system_prompt or None,
        append_system_prompt=append_system_prompt,
    )


class AgentLoopEngine:
    """Thin wrapper around LocalCodingAgent for Nexus execution flow.

    Provides: run, resume, tool registry management, and
    session persistence — all through the bridge.
    """

    def __init__(
        self,
        agent: LocalCodingAgent,
        *,
        engine_config: EngineConfig | None = None,
    ):
        self._agent = agent
        self._config = engine_config
        self._last_session_id: str = ""

    @property
    def agent(self) -> LocalCodingAgent:
        if self._agent is None:
            raise RuntimeError("Engine has been invalidated. Create a new engine.")
        return self._agent

    @property
    def tool_registry(self) -> dict[str, Any]:
        if self._agent is None:
            raise RuntimeError("Engine has been invalidated. Create a new engine.")
        return self._agent.tool_registry

    @property
    def last_session_id(self) -> str:
        return self._last_session_id

    def register_tool(self, name: str, tool: Any) -> None:
        self._agent.tool_registry[name] = tool

    def register_tools(self, tools: dict[str, Any]) -> None:
        self._agent.tool_registry.update(tools)

    async def run(self, prompt: str | list[dict]) -> AgentRunResult:
        """Execute a fresh agent run (synchronous agent, run in thread)."""
        if self._agent is None:
            raise RuntimeError("Engine has been invalidated. Create a new engine.")
        result = await _asyncio.to_thread(self._agent.run, prompt)
        if result.session_id:
            self._last_session_id = result.session_id
        return result

    async def resume(
        self,
        prompt: str | list[dict],
        session_id: str | None = None,
    ) -> AgentRunResult:
        """Resume from a previous session."""
        from factory.vendor.claw_code_agent.session_store import (
            load_agent_session,
        )

        if self._agent is None:
            raise RuntimeError("Engine has been invalidated. Create a new engine.")

        sid = session_id or self._last_session_id
        if not sid:
            return await self.run(prompt)

        stored = load_agent_session(sid, directory=self._agent.runtime_config.session_directory)
        if stored is None:
            return await self.run(prompt)

        result = await _asyncio.to_thread(self._agent.resume, prompt, stored)
        if result.session_id:
            self._last_session_id = result.session_id
        return result

    def invalidate(self) -> None:
        """Clear cached agent state (for model/config hot-reload)."""
        self._agent = None
        self._last_session_id = ""
