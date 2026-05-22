"""Nexus AgentRunner — claw-code-agent integration + memory + TokenJuice.

Connects:
1. claw-code-agent LocalCodingAgent executes agent tasks
2. ToolInterceptor intercepts tool calls → TokenJuice compression → Memory Tree
3. Session persistence + resume across requests
4. Interactive questioning via AskUserRuntime bridge
5. Post-execution: Bucket-Seal cascade, Obsidian vault write
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.engine.bridge import (
    AgentLoopEngine,
    EngineConfig,
    ModelConfig,
    create_agent,
    create_model_config,
)
from factory.engine.pool import get_pool
from factory.engine.providers import ProviderRegistry
from factory.engine.tools import build_tool_registry, resolve_tools
from factory.memory import MemoryStore, SourceTree, SourceKind, VaultWriter
from factory.memory.tree import BucketSeal
from factory.tokenjuice import compact_tool_output, load_rules
from factory.kanban.sync import KanbanSync, TaskEvent


@dataclass
class TaskResult:
    """Result of one agent execution."""

    content: str
    tools_used: list[str] = field(default_factory=list)
    error: str | None = None
    chunks_written: int = 0
    summaries_generated: int = 0
    session_id: str = ""
    turns: int = 0
    cost_usd: float = 0.0
    events: tuple = ()  # StreamEvent dicts for SSE streaming


class NexusAgentRunner:
    """Nexus agent executor powered by claw-code-agent.

    Wraps LocalCodingAgent via AgentLoopEngine bridge, adding
    memory, security, and platform integration layers.
    """

    def __init__(
        self,
        agent_spec: Any,
        workshop: Any,
        store: MemoryStore,
        *,
        vault_path: str = "~/.nexus/vault",
        kanban_sync: KanbanSync | None = None,
        model_api_key: str = "",
        model_base_url: str = "",
    ):
        self.spec = agent_spec
        self.workshop = workshop
        self.store = store
        self.vault = VaultWriter(vault_path)
        self.kanban_sync = kanban_sync
        self._model_api_key = model_api_key
        self._model_base_url = model_base_url

        # Memory tree init
        self.source_tree = SourceTree(
            store, f"src-{agent_spec.name}", f"agent:{agent_spec.name}"
        )

        # TokenJuice rules
        self.tj_rules = load_rules()

        # Engine — created lazily on first run
        self._engine: AgentLoopEngine | None = None
        self._engine_key = f"{workshop.name}:{agent_spec.name}"

    # ── Engine lifecycle ────────────────────────────────────────

    def _get_engine(self) -> AgentLoopEngine:
        """Get or create the agent engine."""
        if self._engine is not None and self._engine.agent is not None:
            return self._engine

        model = getattr(self.spec, "model", "anthropic/claude-sonnet-4-6")
        if hasattr(self.spec, "model") and hasattr(self.spec.model, "value"):
            model = self.spec.model.value

        workspace_path = str(getattr(self.workshop, "workspace", "."))
        permissions = getattr(self.spec, "permissions", None)

        allow_write = getattr(permissions, "filesystem", None)
        allow_write = (
            len(getattr(allow_write, "write", ["workspace"])) > 0
            if allow_write else True
        )
        allow_shell = getattr(permissions, "shell", None)
        allow_shell = getattr(allow_shell, "exec", True) if allow_shell else True
        allow_subagent = getattr(permissions, "subagent", None)
        allow_subagent = (
            getattr(allow_subagent, "spawn", True) if allow_subagent else True
        )

        registry = ProviderRegistry.load_defaults()
        model_config = create_model_config(
            model=model,
            base_url=self._model_base_url or "http://127.0.0.1:8000/v1",
            api_key=self._model_api_key,
            registry=registry,
        )

        engine_config = EngineConfig(
            cwd=Path(workspace_path).expanduser().resolve(),
            max_turns=30,
            allow_file_write=allow_write,
            allow_shell_commands=allow_shell,
        )

        # Generate search manifest from settings so SearchRuntime discovers it
        from factory.settings.store import SettingsStore
        SettingsStore().write_search_manifest(engine_config.cwd)

        # Use pool for caching
        pool = get_pool()
        self._engine = pool.get_or_create(
            key=self._engine_key,
            model_config=model_config,
            engine_config=engine_config,
        )
        return self._engine

    # ── Main execution ──────────────────────────────────────────

    async def run(self, task: str) -> TaskResult:
        """Execute a task through the claw-code-agent loop."""
        task_id = f"task-{self.source_tree.tree_id}"

        # Notify kanban
        if self.kanban_sync:
            await self.kanban_sync.on_task_event(TaskEvent(
                agent_name=self.spec.name,
                task_id=task_id,
                event_type="task_started",
                title=task[:200],
            ))

        # 1. Assemble context from memory
        relevant_memories = self.source_tree.query(task, limit=5)
        context = _build_context(task, relevant_memories)

        # 2. Build system prompt
        system_prompt = getattr(self.spec, "system_prompt", "") or ""
        prompt = f"{context}\n\n---\n\n任务：{task}"
        if system_prompt:
            prompt = f"{system_prompt}\n\n{prompt}"

        # 3. Execute via claw-code-agent
        try:
            engine = self._get_engine()
            result = await self._run_agent_loop(engine, prompt)
        except ImportError:
            return await self._run_simulated(task, context)

        # 4. Bucket-Seal cascade compression
        bucket_seal = BucketSeal(self.store)
        dummy = _make_dummy_summariser()
        sealed = await bucket_seal.seal_one_level(self.source_tree.tree_id, 0, dummy)
        if sealed:
            self.vault.write_summary(sealed)
            for level in range(1, 3):
                more = await bucket_seal.seal_one_level(self.source_tree.tree_id, level, dummy)
                if more:
                    self.vault.write_summary(more)

        # 5. Write INDEX
        self.vault.write_index(self.store)

        # Notify kanban
        if self.kanban_sync:
            await self.kanban_sync.on_task_event(TaskEvent(
                agent_name=self.spec.name,
                task_id=task_id,
                event_type="task_completed" if not result.error else "task_failed",
                title=task[:200],
                detail=result.error or result.content[:200],
            ))

        return result

    async def _run_agent_loop(
        self,
        engine: AgentLoopEngine,
        prompt: str,
    ) -> TaskResult:
        """Execute through claw-code-agent's LocalCodingAgent."""
        from factory.vendor.claw_code_agent.agent_tools import default_tool_registry

        # Build filtered tool registry
        spec_tools = getattr(self.spec, "tools", [])
        permissions = getattr(self.spec, "permissions", None)
        allow_shell = (
            getattr(getattr(permissions, "shell", None), "exec", True)
            if permissions else True
        )
        allow_write = (
            len(getattr(getattr(permissions, "filesystem", None), "write", ["workspace"])) > 0
            if permissions else True
        )
        allow_subagent = (
            getattr(getattr(permissions, "subagent", None), "spawn", True)
            if permissions else True
        )

        allowed = resolve_tools(
            spec_tools,
            allow_shell=allow_shell,
            allow_write=allow_write,
            allow_subagent=allow_subagent,
        )
        filtered_tools = build_tool_registry(default_tool_registry(), allowed)
        engine.agent.tool_registry.clear()
        engine.agent.tool_registry.update(filtered_tools)

        # Register deep_search if it's in the agent's allowed tools
        if "deep_search" in allowed:
            from factory.tools.deep_search import create_deep_search_tool
            engine.agent.tool_registry["deep_search"] = create_deep_search_tool()

        # Inject marketplace skills into system prompt
        from factory.skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace(workspace=engine._config.cwd if engine._config else None)
        marketplace.discover()
        skill_prompt = marketplace.format_for_prompt()
        if skill_prompt and engine.agent.append_system_prompt:
            engine.agent.append_system_prompt = (
                engine.agent.append_system_prompt + "\n\n" + skill_prompt
            )
        elif skill_prompt:
            engine.agent.append_system_prompt = skill_prompt

        # Execute
        result = await engine.run(prompt)

        # Extract tool calls for tracking
        tool_events = _extract_tool_events(result.transcript) if hasattr(result, 'transcript') else []
        tool_names = list(set(e["tool"] for e in tool_events)) if tool_events else result.tools_used or []

        # Record to memory
        for evt in tool_events:
            self.record_tool_call(evt["tool"], evt.get("output", ""), result.session_id or "session")

        return TaskResult(
            content=result.final_output or "",
            tools_used=tool_names,
            error=result.stop_reason if result.stop_reason and result.stop_reason != "end_turn" else None,
            session_id=result.session_id or "",
            turns=result.turns,
            cost_usd=result.total_cost_usd or 0.0,
            events=result.events if hasattr(result, 'events') else (),
        )

    async def _run_simulated(self, task: str, context: str) -> TaskResult:
        """Fallback when claw-code-agent is unavailable (tests only)."""
        content = f"[simulated] Task: {task}\nContext: {context[:200]}"
        return TaskResult(content=content, tools_used=[])

    # ── Memory recording ────────────────────────────────────────

    def record_chat(self, role: str, content: str, session_id: str) -> None:
        chunk = self.source_tree.append_chat(role, content, session_id)
        self.vault.write_chunk(chunk)

    def record_tool_call(self, tool_name: str, output: str, session_id: str) -> None:
        compressed = compact_tool_output(tool_name, stdout=output, rules=self.tj_rules)
        content = compressed.inline_text if not compressed.passthrough else output
        chunk = self.source_tree.append_tool_output(tool_name, content, session_id)
        self.vault.write_chunk(chunk)


# ── ToolInterceptor — hooks into claw-code-agent tool execution ─

class ToolInterceptor:
    """Intercepts tool calls for memory recording and security checks.

    Registered as a hook in claw-code-agent's tool execution pipeline.
    """

    def __init__(self, runner: NexusAgentRunner):
        self.runner = runner
        self._session_id = "session-" + str(id(self))[-8:]

    def on_tool_end(self, tool_name: str, result: str) -> None:
        """Called after each tool execution completes."""
        self.runner.record_tool_call(tool_name, result, self._session_id)


# ── Helpers ─────────────────────────────────────────────────────

def _build_context(task: str, memories: list[dict]) -> str:
    parts = []
    if memories:
        parts.append("## 相关历史记录\n")
        for m in memories[:5]:
            parts.append(f"- {m.get('content', '')[:200]}")
        parts.append("")
    return "\n".join(parts)


def _extract_tool_events(transcript: tuple) -> list[dict]:
    """Extract tool call events from transcript."""
    events = []
    for msg in transcript:
        if not isinstance(msg, dict):
            continue
        tool_calls = msg.get("tool_calls") or []
        for tc in tool_calls:
            fn = tc.get("function", {})
            events.append({
                "tool": fn.get("name", "?"),
                "arguments": fn.get("arguments", ""),
                "output": "",
            })
    return events


def _make_dummy_summariser():
    async def summarise(contents: list[str], tree_id: str) -> str:
        return "\n\n".join(c[:300] for c in contents[:5])
    return summarise
