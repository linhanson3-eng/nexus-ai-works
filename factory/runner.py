from __future__ import annotations

"""Nexus AgentRunner — claw-code-agent integration + memory + TokenJuice.

Connects:
1. claw-code-agent LocalCodingAgent executes agent tasks
2. ToolInterceptor intercepts tool calls → TokenJuice compression → Memory Tree
3. Session persistence + resume across requests
4. Interactive questioning via AskUserRuntime bridge
5. Post-execution: Bucket-Seal cascade, Obsidian vault write
"""


import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from factory.engine.bridge import (
    AgentLoopEngine,
    EngineConfig,
    create_agent,
    create_model_config,
)
from factory.engine.providers import ProviderRegistry
from factory.engine.tools import build_tool_registry, resolve_tools
from factory.memory import MemoryStore, SourceTree, VaultWriter
from factory.memory.tree import BucketSeal
from factory.tokenjuice import compact_tool_output, load_rules
from factory.kanban.sync import KanbanSync, TaskEvent
from factory.security.guard import check_shell_command, detect_secrets, sanitize_path

logger = logging.getLogger(__name__)

# Agent engine cache: avoids 16+ runtime filesystem scans per request
_ENGINE_CACHE: dict[tuple, tuple] = {}


class ErrorKind(str, Enum):
    """Structured error classification for agent task failures."""

    NONE = ""
    TOOL_FAILURE = "tool_failure"
    API_ERROR = "api_error"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TaskResult:
    """Result of one agent execution."""

    content: str
    tools_used: list[str] = field(default_factory=list)
    error: str | None = None
    error_kind: ErrorKind = ErrorKind.NONE
    error_context: dict[str, str] = field(default_factory=dict)
    chunks_written: int = 0
    summaries_generated: int = 0
    session_id: str = ""
    turns: int = 0
    cost_usd: float = 0.0
    model: str = ""
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
        settings_store: Any = None,
        org: Any = None,
    ):
        self.spec = agent_spec
        self.workshop = workshop
        self.store = store
        self.vault = VaultWriter(vault_path)
        self._org = org
        self.kanban_sync = kanban_sync

        # Reuse shared SettingsStore when available (avoid disk read + decrypt per request)
        if settings_store is not None:
            self._settings = settings_store
        else:
            from factory.settings.store import SettingsStore
            self._settings = SettingsStore()

        # Memory tree init
        self.source_tree = SourceTree(
            store, f"src-{agent_spec.name}", f"agent:{agent_spec.name}"
        )

        # TokenJuice rules
        self.tj_rules = load_rules()

    # ── Runtime overrides (set by API layer) ─────────────────

    def set_model_override(self, model: str) -> None:
        """Override the model for the next run."""
        self._model_override = model

    def set_reasoning_effort(self, effort: str) -> None:
        """Set reasoning effort: low, medium, high, xhigh."""
        self._reasoning_effort = effort
    def _build_budget(self):
        """Build BudgetConfig with reasoning token limit based on effort."""
        from factory.engine.bridge import BudgetConfig
        effort = getattr(self, "_reasoning_effort", "")
        mapping = {"low": 1024, "medium": 4096, "high": 8192, "xhigh": 16384}
        max_reasoning = mapping.get(effort)
        return BudgetConfig(max_reasoning_tokens=max_reasoning) if max_reasoning else None

    def _resolve_model(self) -> str:
        """Return the model string for this agent, falling back to the first available provider model."""
        # 0. Runtime model override (from API request)
        override = getattr(self, "_model_override", "")
        if override:
            return override
        # 1. Spec model
        spec_model = getattr(self.spec, "model", "") or ""
        if hasattr(spec_model, "value"):
            spec_model = spec_model.value
        if spec_model:
            return spec_model

        # 1.5. User-configured default model preference (Settings → Preferences)
        try:
            prefs = self._settings._data.get("preferences", {})
            default_model = prefs.get("default_model", "")
            if default_model:
                return default_model
        except (json.JSONDecodeError, OSError):
            pass

        # 2. First model from provider with an API key, then any provider
        try:
            providers = self._settings.list_providers()
            # Prefer providers with API keys configured
            keyed: list[tuple[str, dict]] = []
            unkeyed: list[tuple[str, dict]] = []
            for name, cfg in providers.items():
                models = cfg.get("models", [])
                if not models:
                    continue
                if cfg.get("api_key", ""):
                    keyed.append((name, cfg))
                else:
                    unkeyed.append((name, cfg))
            for name, cfg in keyed + unkeyed:
                provider_type = cfg.get("provider_type", name)
                return f"{provider_type}/{cfg['models'][0]}"
        except (ImportError, json.JSONDecodeError, OSError):
            pass

        return ""

    def _get_engine(self) -> AgentLoopEngine:
        """Get or create a cached engine to avoid 16 runtime scans per request."""
        model = self._resolve_model()
        self._resolved_model = model

        workspace_path = str(getattr(self.workshop, "workspace", "."))
        permissions = getattr(self.spec, "permissions", None)

        allow_write = getattr(permissions, "filesystem", None)
        allow_write = (
            len(getattr(allow_write, "write", ["workspace"])) > 0
            if allow_write else True
        )
        allow_shell = getattr(permissions, "shell", None)
        allow_shell = getattr(allow_shell, "exec", True) if allow_shell else True

        registry = ProviderRegistry.from_store(self._settings)
        model_config = create_model_config(
            model=model,
            registry=registry,
        )

        cache_key = (workspace_path, model)
        if cache_key not in _ENGINE_CACHE:
            engine_config = EngineConfig(
                cwd=Path(workspace_path).expanduser().resolve(),
                max_turns=30,
                allow_file_write=allow_write,
                allow_shell_commands=allow_shell,
                system_prompt="你是Nexus全能助手，简短直接回答问题。",
                budget=self._build_budget(),
            )

            # Generate search manifest once (not every request)
            manifest_path = engine_config.cwd / ".claw-search.json"
            if not manifest_path.exists():
                self._settings.write_search_manifest(engine_config.cwd)

            # Register nexus platform tools directly (no HTTP MCP — vendor only supports stdio)

            agent = create_agent(model_config=model_config, engine_config=engine_config)
            engine = AgentLoopEngine(agent, engine_config=engine_config)
            _ENGINE_CACHE[cache_key] = (engine,)

        return _ENGINE_CACHE[cache_key][0]

    # ── Main execution ──────────────────────────────────────────

    async def run(self, task: str, *, progress_queue=None, session_id: str = "") -> TaskResult:
        """Execute a task through the claw-code-agent loop.

        Args:
            task: The task description.
            progress_queue: Optional asyncio.Queue for real-time event streaming.
            session_id: If provided, resume from existing session (multi-turn).
        """
        self._progress_queue = progress_queue
        task_id = f"task-{self.source_tree.tree_id}"
        request_id = getattr(self, "_request_id", "") or ""
        model = self._resolve_model()
        ws = getattr(self.workshop, "name", "") if self.workshop else ""
        logger.info(
            "Agent run start — agent=%s workshop=%s model=%s task=[%s] rid=%s resume=%s",
            self.spec.name, ws, model, task[:120], request_id[:8], bool(session_id),
        )

        # Notify kanban (fire-and-forget, don't block agent start)
        if self.kanban_sync:
            asyncio.create_task(self.kanban_sync.on_task_event(TaskEvent(
                agent_name=self.spec.name,
                task_id=task_id,
                event_type="task_started",
                title=task[:200],
                detail=task,
            )))

        # Build prompt — skip custom context when resuming (session has full history)
        engine = self._get_engine()

        if session_id:
            # Resume: session already has system prompt + full conversation history
            prompt = task
        else:
            # Fresh run: build prompt with system_prompt + guide + context
            system_prompt = getattr(self.spec, "system_prompt", "") or ""
            guide_content = ""
            guide_file = getattr(self.spec, "guide_file", "")
            if guide_file:
                ws_dir = Path(getattr(self.workshop, "workspace", ".") or ".")
                guide_path = ws_dir / guide_file
                if guide_path.exists():
                    guide_content = await asyncio.to_thread(
                        guide_path.read_text, "utf-8"
                    )
            prompt = f"任务：{task}"
            if guide_content:
                prompt = f"## 引导指令\n\n{guide_content}\n\n---\n\n{prompt}"
            if system_prompt:
                prompt = f"{system_prompt}\n\n{prompt}"

        # Execute via claw-code-agent
        from factory.env import env_int
        AGENT_TOTAL_TIMEOUT = env_int("AGENT_TOTAL_TIMEOUT", 600, min=10, max=7200)
        try:
            result = await asyncio.wait_for(
                self._run_agent_loop(engine, prompt, session_id),
                timeout=AGENT_TOTAL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return TaskResult(
                content="",
                error=f"Agent execution timed out after {AGENT_TOTAL_TIMEOUT}s",
                error_kind=ErrorKind.TIMEOUT,
                error_context={"timeout_seconds": str(AGENT_TOTAL_TIMEOUT)},
                model=getattr(self, "_resolved_model", ""),
            )
        except ImportError:
            simulated = await self._run_simulated(task, context)
            return TaskResult(
                content=simulated.content,
                tools_used=simulated.tools_used,
                error=simulated.error,
                model=getattr(self, "_resolved_model", ""),
            )

        # 4. Bucket-Seal cascade compression (non-critical — must not crash the run)
        try:
            bucket_seal = BucketSeal(self.store)
            dummy = _make_dummy_summariser()
            sealed = await bucket_seal.seal_one_level(self.source_tree.tree_id, 0, dummy)
            if sealed:
                self.vault.write_summary(sealed)
                for level in range(1, 3):
                    more = await bucket_seal.seal_one_level(self.source_tree.tree_id, level, dummy)
                    if more:
                        self.vault.write_summary(more)
        except Exception:
            logger.exception("Bucket-Seal cascade failed for run")

        # 5. Write INDEX
        self.vault.write_index(self.store)

        # Notify kanban
        if self.kanban_sync:
            await self.kanban_sync.on_task_event(TaskEvent(
                agent_name=self.spec.name,
                task_id=task_id,
                event_type="task_completed" if not result.error else "task_failed",
                title=task[:200],
                detail=result.error or result.content,
                output_full=result.content if not result.error else "",
                turns=result.turns,
                cost_usd=result.cost_usd,
                tools_used=result.tools_used,
                model=getattr(result, 'model', ''),
            ))

        logger.info(
            "Agent run end — agent=%s turns=%d cost=%.4f tools=%d error=%s rid=%s",
            self.spec.name, result.turns, result.cost_usd,
            len(result.tools_used), result.error_kind.value or "none",
            getattr(self, "_request_id", "")[:8],
        )
        return result

    async def _run_agent_loop(
        self,
        engine: AgentLoopEngine,
        prompt: str,
        session_id: str = "",
    ) -> TaskResult:
        """Execute through claw-code-agent's LocalCodingAgent.

        If session_id is provided, resumes from persisted session (multi-turn).
        Otherwise starts a fresh run.
        """
        from factory.engine.bridge import default_tool_registry

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

        # Register nexus platform tools (spawn/fork/list/read/write)
        from factory.engine.nexus_tools import register_nexus_tools
        register_nexus_tools(
            engine,
            org=self._org,
            kanban_store=self.kanban_sync.store if self.kanban_sync else None,
            session_manager=None,
            settings_store=self._settings,
        )

        # ── Unified skill system (claude-code-agent compatible) ──
        # Bundled skills → Marketplace plugins → Project skills → Slash commands
        from factory.skills.marketplace import SkillMarketplace
        from factory.skills.loader import SkillLoader
        from factory.engine.bridge import ToolExecutionResult

        marketplace = SkillMarketplace(workspace=engine._config.cwd if engine._config else None)
        marketplace.discover()

        _original_execute_skill = engine.agent._execute_skill

        def _skill_executor(arguments: dict[str, object]) -> Any:
            result = _original_execute_skill(arguments)
            if result.ok or result.metadata.get("action") != "skill_not_found":
                return result

            skill_name = str(arguments.get("skill", "")).strip().lstrip("/")
            if not skill_name:
                return result

            # Check marketplace (Claude Code plugins ecosystem)
            mp_skill = marketplace.get(skill_name)
            if mp_skill is not None:
                body = mp_skill.get_body()
                return ToolExecutionResult(
                    name="Skill",
                    ok=True,
                    content=body,
                    metadata={
                        "action": "skill",
                        "skill_name": skill_name,
                        "source": "marketplace",
                        "should_query": True,
                    },
                )

            # Check project-level skills (skills/ directory)
            loader = SkillLoader("skills")
            skill = loader.load_skill(skill_name)
            if skill is not None:
                return ToolExecutionResult(
                    name="Skill",
                    ok=True,
                    content=skill.body,
                    metadata={
                        "action": "skill",
                        "skill_name": skill_name,
                        "source": "project",
                        "should_query": True,
                    },
                )

            return result

        engine.agent._execute_skill = _skill_executor

        # Build unified skill listing for system prompt
        skill_prompt_parts: list[str] = []
        mp_prompt = marketplace.format_for_prompt()
        if mp_prompt:
            skill_prompt_parts.append(mp_prompt)

        ws_name = getattr(self.workshop, "name", "") if self.workshop else ""
        if ws_name:
            try:
                from factory.skills.repo import SkillRepo

                repo = SkillRepo()
                installed = repo.list_installed(ws_name)
                if installed:
                    lines = ["## 已安装技能 (Workspace)", ""]
                    for s in installed:
                        lines.append(f"- **{s.name}**: {s.description}")
                    skill_prompt_parts.append("\n".join(lines))
            except (ImportError, OSError):
                pass

        skill_prompt = "\n\n".join(skill_prompt_parts)
        if skill_prompt and engine.agent.append_system_prompt:
            engine.agent.append_system_prompt = (
                engine.agent.append_system_prompt + "\n\n" + skill_prompt
            )
        elif skill_prompt:
            engine.agent.append_system_prompt = skill_prompt

        # Execute — resume if session_id provided, otherwise fresh run
        if session_id:
            result = await engine.resume(prompt, session_id)
        else:
            result = await engine.run(prompt)

        # Extract tool calls for tracking
        tool_events = _extract_tool_events(result.transcript) if hasattr(result, 'transcript') else []
        tool_names = list(set(e["tool"] for e in tool_events)) if tool_events else getattr(result, "tool_calls", []) or []

        # Record to memory
        for evt in tool_events:
            self.record_tool_call(evt["tool"], evt.get("output", ""), result.session_id or "session")

        error_kind = ErrorKind.NONE
        error_context_info: dict[str, str] = {}
        if result.stop_reason and result.stop_reason not in ("end_turn", "stop", "max_tokens"):
            error_kind = _classify_error(result.stop_reason, result.final_output or "")
            error_context_info = {
                "stop_reason": result.stop_reason,
                "tools_called": ", ".join(tool_names) if tool_names else "none",
                "turns_used": str(result.turns),
            }

        return TaskResult(
            content=result.final_output or "",
            tools_used=tool_names,
            error=result.stop_reason if result.stop_reason and result.stop_reason not in ("end_turn", "stop", "max_tokens") else None,
            error_kind=error_kind,
            error_context=error_context_info,
            session_id=result.session_id or "",
            turns=result.turns,
            cost_usd=result.total_cost_usd or 0.0,
            model=getattr(self, "_resolved_model", ""),
            events=result.events if hasattr(result, 'events') else (),
        )

    async def _run_simulated(self, task: str, context: str) -> TaskResult:
        """Fallback when claw-code-agent is unavailable (tests only)."""
        content = f"[simulated] Task: {task}\nContext: {context[:200]}"
        return TaskResult(content=content, tools_used=[], error_kind=ErrorKind.NONE, error_context={})

    # ── Memory recording ────────────────────────────────────────

    def record_chat(self, role: str, content: str, session_id: str) -> None:
        # Detect secrets in content before storing
        result = detect_secrets(content)
        if result.found:
            logger.warning("Secret detected in %s message (session=%s): %s", role, session_id[:8], result.secrets)
        chunk = self.source_tree.append_chat(role, content, session_id)
        self.vault.write_chunk(chunk)

        # Push real-time event to SSE queue
        q = getattr(self, "_progress_queue", None)
        if q is not None and role == "assistant":
            import asyncio as _aio
            try:
                loop = _aio.get_running_loop()
                loop.call_soon_threadsafe(
                    q.put_nowait,
                    ("content_delta", {"text": content[:300]}),
                )
            except RuntimeError:
                pass  # no running event loop

    def record_tool_call(self, tool_name: str, output: str, session_id: str) -> None:
        # Note: this runs in a worker thread (via asyncio.to_thread), so
        # synchronous compression does NOT block the event loop.
        result = detect_secrets(output)
        if result.found:
            logger.warning("Secret detected in tool output '%s' (session=%s): %s", tool_name, session_id[:8], result.secrets)
        compressed = compact_tool_output(tool_name, stdout=output, rules=self.tj_rules)
        content = compressed.inline_text if not compressed.passthrough else output
        chunk = self.source_tree.append_tool_output(tool_name, content, session_id)
        self.vault.write_chunk(chunk)

        # Push real-time event to SSE queue
        q = getattr(self, "_progress_queue", None)
        if q is not None:
            import asyncio as _aio
            try:
                loop = _aio.get_running_loop()
                loop.call_soon_threadsafe(
                    q.put_nowait,
                    ("tool_result", {"tool": tool_name, "content": content[:500]}),
                )
            except RuntimeError:
                pass  # no running event loop


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

def _build_context(task: str, memories: list[dict], recent: list[dict] | None = None) -> str:
    parts = []
    if recent:
        parts.append("## 最近的对话记录\n")
        for m in recent:
            role = "用户" if m.get("owner", "").startswith("user") else "助手"
            parts.append(f"- [{role}]: {m.get('content', '')[:300]}")
        parts.append("")
    if memories:
        parts.append("## 相关历史记录\n")
        for m in memories[:3]:
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


def _classify_error(stop_reason: str, output: str) -> ErrorKind:
    """Classify error stop reason into structured ErrorKind."""
    reason_lower = (stop_reason + " " + output[:500]).lower()
    if any(k in reason_lower for k in ("tool_error", "tool_call", "tool_use_failed", "tool_execution")):
        return ErrorKind.TOOL_FAILURE
    if any(k in reason_lower for k in ("429", "rate", "limit", "quota", "billing", "budget", "max_token")):
        return ErrorKind.BUDGET_EXCEEDED
    if any(k in reason_lower for k in ("timeout", "timed out", "deadline")):
        return ErrorKind.TIMEOUT
    if any(k in reason_lower for k in ("401", "403", "unauthorized", "forbidden", "permission")):
        return ErrorKind.PERMISSION_DENIED
    if any(k in reason_lower for k in ("api_error", "server_error", "500", "502", "503", "connect", "refused")):
        return ErrorKind.API_ERROR
    return ErrorKind.UNKNOWN


def _make_dummy_summariser():
    async def summarise(contents: list[str], tree_id: str) -> str:
        return "\n\n".join(c[:300] for c in contents[:5])
    return summarise
