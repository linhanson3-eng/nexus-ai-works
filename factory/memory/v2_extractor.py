"""Memory V2 事实提取器 — LLM 驱动的语义记忆抽取。

从对话中自动提取结构化事实，更新用户画像、项目背景、事件记录和反馈规则。

设计原则:
- 配置驱动：提取提示词从模板文件读取，可自由修改
- 轻量级：仅在被调用时运行，不在每次 Agent 执行后自动触发
- 合并优先：用户画像和项目背景采用合并更新，而非简单追加
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any

from factory.memory.v2_store import MemoryV2Store

# ── Default extraction prompt ────────────────────────────────────────

DEFAULT_EXTRACT_PROMPT = """你是一个记忆管理助手。从以下对话内容中提取关键事实，用于更新长期记忆。

请按以下分类输出 JSON：

{
  "user_facts": ["关于用户角色、偏好、知识的事实"],
  "project_facts": ["关于项目目标、进展、决策的事实"],
  "event_summary": "本次对话的摘要（1-2句话）",
  "feedback_rules": ["用户给出的反馈或纠正（如有）"]
}

规则：
- 只提取明确的信息，不要推测
- 事实应该是不依赖对话上下文也能理解的独立陈述
- 如果某类没有内容，返回空数组/空字符串
- 用户偏好/习惯 → user_facts
- 项目相关决策/进展 → project_facts
- 用户纠正了你的行为 → feedback_rules

对话内容：
---
$conversation
---
"""


@dataclass
class ExtractedFacts:
    """LLM 提取的结构化事实。"""

    user_facts: list[str] = field(default_factory=list)
    project_facts: list[str] = field(default_factory=list)
    event_summary: str = ""
    feedback_rules: list[str] = field(default_factory=list)


class MemoryV2Extractor:
    """LLM 驱动的事实提取器。

    用法:
        extractor = MemoryV2Extractor(store, llm_callable)
        facts = await extractor.extract(conversation_text)
        await extractor.apply(facts)
    """

    def __init__(
        self,
        store: MemoryV2Store | None = None,
        llm_callable: Any | None = None,
        *,
        prompt_template: str = "",
    ):
        self.store = store or MemoryV2Store()
        self._llm = llm_callable
        self.prompt_template = prompt_template or DEFAULT_EXTRACT_PROMPT

    async def extract(self, conversation_text: str) -> ExtractedFacts:
        """Run LLM extraction on conversation text."""
        if not conversation_text.strip():
            return ExtractedFacts()

        prompt = Template(self.prompt_template).substitute(conversation=conversation_text)

        if self._llm is not None:
            return await self._extract_with_llm(prompt)
        return self._extract_heuristic(conversation_text)

    async def _extract_with_llm(self, prompt: str) -> ExtractedFacts:
        """Use the provided LLM callable for extraction."""
        import json

        try:
            result = await self._llm(prompt)
            if isinstance(result, str):
                result = _parse_json_block(result)
            if isinstance(result, dict):
                return ExtractedFacts(
                    user_facts=result.get("user_facts", []),
                    project_facts=result.get("project_facts", []),
                    event_summary=result.get("event_summary", ""),
                    feedback_rules=result.get("feedback_rules", []),
                )
        except Exception:
            pass
        return ExtractedFacts()

    def _extract_heuristic(self, text: str) -> ExtractedFacts:
        """Fallback heuristic when no LLM is available.

        Returns an empty result with a timestamp-based event summary
        only — heuristic extraction would be too noisy for profiles.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        return ExtractedFacts(
            event_summary=f"对话发生于 {now} UTC，{len(text)} 字符",
        )

    # ── Apply extracted facts ────────────────────────────────────

    async def apply(self, facts: ExtractedFacts, date_str: str = "") -> None:
        """Apply extracted facts to the memory store."""
        self.store.ensure_dirs()

        # User profile — merge with existing
        if facts.user_facts:
            self._merge_user_profile(facts.user_facts)

        # Project profile — merge with existing
        if facts.project_facts:
            self._merge_project_profile(facts.project_facts)

        # Event summary — append
        if facts.event_summary:
            self.store.append_event(facts.event_summary, date_str=date_str)

        # Feedback rules — append each
        for rule in facts.feedback_rules:
            if rule.strip():
                self.store.append_rule(rule.strip())

    def _merge_user_profile(self, new_facts: list[str]) -> None:
        """Merge new facts into existing user profile."""
        meta, existing = self.store.read_profile("user")

        facts_block = "\n".join(f"- {f}" for f in new_facts)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if existing.strip():
            content = f"{existing.strip()}\n\n## 更新 ({now})\n\n{facts_block}\n"
        else:
            content = f"# 用户画像\n\n{facts_block}\n"

        self.store.write_profile("user", content, "User role, preferences, and knowledge")

    def _merge_project_profile(self, new_facts: list[str]) -> None:
        """Merge new facts into existing project profile."""
        meta, existing = self.store.read_profile("project")

        facts_block = "\n".join(f"- {f}" for f in new_facts)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if existing.strip():
            content = f"{existing.strip()}\n\n## 更新 ({now})\n\n{facts_block}\n"
        else:
            content = f"# 项目背景\n\n{facts_block}\n"

        self.store.write_profile(
            "project", content, "Project background, goals, and decisions"
        )


# ── Helpers ───────────────────────────────────────────────────────────

def _parse_json_block(text: str) -> dict | None:
    """Extract JSON object from text that may have markdown fences."""
    import json
    import re

    # Try to find a JSON block in markdown
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Try the whole text as JSON
    text_stripped = text.strip()
    if text_stripped.startswith("{"):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass

    return None
