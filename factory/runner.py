"""工厂 AgentRunner — nanobot AgentRunner 接入 + 记忆 + TokenJuice。

连接点：
1. nanobot AgentRunner 执行 Agent 任务
2. AgentHook 拦截每次 tool call → TokenJuice 压缩 → Memory Tree 写入
3. 会话结束后写入 Obsidian vault
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.memory import MemoryStore, SourceTree, SourceKind, VaultWriter
from factory.memory.tree import BucketSeal
from factory.tokenjuice import compact_tool_output, load_rules
from factory.kanban.sync import KanbanSync, TaskEvent


@dataclass
class TaskResult:
    """一次 Agent 执行的结果。"""

    content: str
    tools_used: list[str] = field(default_factory=list)
    error: str | None = None
    chunks_written: int = 0
    summaries_generated: int = 0


class FactoryAgentRunner:
    """工厂 Agent 执行器。

    将 AgentSpec → nanobot AgentRunner → 记忆写入完整链路。
    """

    def __init__(
        self,
        agent_spec: Any,
        workshop: Any,
        store: MemoryStore,
        *,
        vault_path: str = "~/.factory/vault",
        kanban_sync: KanbanSync | None = None,
    ):
        self.spec = agent_spec
        self.workshop = workshop
        self.store = store
        self.vault = VaultWriter(vault_path)
        self.kanban_sync = kanban_sync

        # 初始化记忆树
        self.source_tree = SourceTree(
            store, f"src-{agent_spec.name}", f"agent:{agent_spec.name}"
        )

        # 加载 TokenJuice 规则
        self.tj_rules = load_rules()

    async def run(self, task: str) -> TaskResult:
        """执行单个任务。"""
        task_id = f"task-{self.source_tree.tree_id}"

        # 通知看板：任务开始
        if self.kanban_sync:
            await self.kanban_sync.on_task_event(TaskEvent(
                agent_name=self.spec.name,
                task_id=task_id,
                event_type="task_started",
                title=task[:200],
            ))

        # 1. 从 Source Tree 组装上下文
        relevant_memories = self.source_tree.query(task, limit=5)
        context = _build_context(task, relevant_memories)

        # 2. 确定模型
        model = getattr(self.spec, "model", "anthropic/claude-sonnet-4-6")
        if hasattr(self.spec, "model") and hasattr(self.spec.model, "value"):
            model = self.spec.model.value

        # 3. 构建 system prompt
        system_prompt = getattr(self.spec, "system_prompt", "")
        workspace_path = str(getattr(self.workshop, "workspace", "."))

        # 4. 创建 nanobot AgentRunner 并执行
        try:
            result = await self._run_nanobot(
                task=task,
                context=context,
                model=model,
                system_prompt=system_prompt,
                workspace_path=workspace_path,
            )
        except ImportError:
            return await self._run_simulated(task, context)

        # 5. Bucket-Seal 级联压缩
        bucket_seal = BucketSeal(self.store)
        dummy = _make_dummy_summariser()
        sealed = await bucket_seal.seal_one_level(self.source_tree.tree_id, 0, dummy)
        if sealed:
            self.vault.write_summary(sealed)
            for level in range(1, 3):
                more = await bucket_seal.seal_one_level(self.source_tree.tree_id, level, dummy)
                if more:
                    self.vault.write_summary(more)

        # 6. 写 INDEX
        self.vault.write_index(self.store)

        # 通知看板：任务完成/失败
        if self.kanban_sync:
            await self.kanban_sync.on_task_event(TaskEvent(
                agent_name=self.spec.name,
                task_id=task_id,
                event_type="task_completed" if not result.error else "task_failed",
                title=task[:200],
                detail=result.error or result.content[:200],
            ))

        return result

    async def _run_nanobot(
        self,
        task: str,
        context: str,
        model: str,
        system_prompt: str,
        workspace_path: str,
    ) -> TaskResult:
        """通过 nanobot AgentRunner 执行。"""
        from nanobot.agent.runner import AgentRunner, AgentRunSpec, AgentRunResult
        from nanobot.agent.hook import AgentHook, AgentHookContext
        from nanobot.agent.tools.registry import ToolRegistry
        from nanobot.config.loader import load_config
        from nanobot.llm.provider import make_provider

        # 加载 nanobot 配置
        config = load_config()
        provider = make_provider(config, model=model)

        # 创建 tool registry（权限过滤）
        tools = ToolRegistry()
        # FIXME: 根据 spec.tools 过滤加载工具
        # 当前加载全部内置工具

        # 创建记忆钩子
        hook = _MemoryHook(self)

        spec = AgentRunSpec(
            initial_messages=[
                {"role": "system", "content": system_prompt} if system_prompt else None,
                {"role": "user", "content": f"{context}\n\n---\n\n任务：{task}"},
            ],
            tools=tools,
            model=model,
            max_iterations=30,
            max_tool_result_chars=10_000,
            workspace=Path(workspace_path),
            hook=hook,
        )
        # 过滤 None
        spec.initial_messages = [m for m in spec.initial_messages if m is not None]

        runner = AgentRunner(provider)
        nanobot_result: AgentRunResult = await runner.run(spec)

        return TaskResult(
            content=nanobot_result.final_content or "",
            tools_used=nanobot_result.tools_used,
            error=nanobot_result.error,
        )

    async def _run_simulated(self, task: str, context: str) -> TaskResult:
        """nanobot 不可用时的模拟执行（仅用于测试）。"""
        content = f"[simulated] Task: {task}\nContext: {context[:200]}"
        return TaskResult(content=content, tools_used=[])

    def record_chat(self, role: str, content: str, session_id: str) -> None:
        chunk = self.source_tree.append_chat(role, content, session_id)
        self.vault.write_chunk(chunk)

    def record_tool_call(self, tool_name: str, output: str, session_id: str) -> None:
        compressed = compact_tool_output(tool_name, stdout=output, rules=self.tj_rules)
        content = compressed.inline_text if not compressed.passthrough else output
        chunk = self.source_tree.append_tool_output(tool_name, content, session_id)
        self.vault.write_chunk(chunk)


class _MemoryHook:
    """nanobot AgentHook — 拦截 tool call 写入记忆。"""

    def __init__(self, runner: FactoryAgentRunner):
        self.runner = runner
        self._session_id = "session-" + str(id(self))[-8:]

    async def on_tool_start(self, ctx: Any) -> None:
        pass

    async def on_tool_end(self, ctx: Any) -> None:
        if hasattr(ctx, "tool_name") and hasattr(ctx, "result"):
            output = str(ctx.result) if ctx.result else ""
            self.runner.record_tool_call(ctx.tool_name, output, self._session_id)


def _build_context(task: str, memories: list[dict]) -> str:
    parts = []
    if memories:
        parts.append("## 相关历史记录\n")
        for m in memories[:5]:
            parts.append(f"- {m.get('content', '')[:200]}")
        parts.append("")
    return "\n".join(parts)


def _make_dummy_summariser():
    async def summarise(contents: list[str], tree_id: str) -> str:
        return "\n\n".join(c[:300] for c in contents[:5])

    return summarise
