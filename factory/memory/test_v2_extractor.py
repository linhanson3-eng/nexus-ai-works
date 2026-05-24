from __future__ import annotations
"""Tests for Memory V2 fact extractor."""


import tempfile
from pathlib import Path

import pytest

from factory.memory.v2_extractor import (
    DEFAULT_EXTRACT_PROMPT,
    ExtractedFacts,
    MemoryV2Extractor,
    MemoryV2Store,
    _parse_json_block,
)


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def store(tmp_root):
    return MemoryV2Store(tmp_root / "memory")


@pytest.fixture
def extractor(store):
    return MemoryV2Extractor(store)


# ── JSON parsing ─────────────────────────────────────────────────


class TestJsonParsing:
    def test_parse_json_fenced(self):
        text = '```json\n{"key": "value"}\n```'
        result = _parse_json_block(text)
        assert result == {"key": "value"}

    def test_parse_json_plain(self):
        text = '{"key": "value"}'
        result = _parse_json_block(text)
        assert result == {"key": "value"}

    def test_parse_json_in_text(self):
        text = 'Some text\n```json\n{"a": 1}\n```\nMore text'
        result = _parse_json_block(text)
        assert result == {"a": 1}

    def test_parse_invalid_returns_none(self):
        assert _parse_json_block("not json") is None
        assert _parse_json_block("") is None


# ── Heuristic extraction ─────────────────────────────────────────


class TestHeuristicExtraction:
    @pytest.mark.asyncio
    async def test_empty_conversation(self, extractor):
        facts = await extractor.extract("")
        assert facts.user_facts == []
        assert facts.project_facts == []
        assert facts.feedback_rules == []

    @pytest.mark.asyncio
    async def test_produces_event_summary(self, extractor):
        facts = await extractor.extract("Some conversation about coding")
        assert facts.event_summary != ""

    @pytest.mark.asyncio
    async def test_no_false_positives(self, extractor):
        """Heuristic should not produce facts (only LLM can)."""
        facts = await extractor.extract("The user is a developer")
        assert facts.user_facts == []
        assert facts.project_facts == []
        assert facts.feedback_rules == []


# ── LLM extraction ───────────────────────────────────────────────


class TestLLMExtraction:
    @pytest.mark.asyncio
    async def test_extract_with_mock_llm(self, store):
        async def mock_llm(prompt: str) -> str:
            return """```json
{
  "user_facts": ["User is a Python developer"],
  "project_facts": ["Project uses FastAPI"],
  "event_summary": "Discussed architecture.",
  "feedback_rules": ["Be concise"]
}
```"""

        extractor = MemoryV2Extractor(store, llm_callable=mock_llm)
        facts = await extractor.extract("We built an API with FastAPI")
        assert "User is a Python developer" in facts.user_facts
        assert "Project uses FastAPI" in facts.project_facts
        assert "Discussed architecture" in facts.event_summary
        assert "Be concise" in facts.feedback_rules

    @pytest.mark.asyncio
    async def test_extract_with_dict_llm(self, store):
        async def mock_llm(prompt: str) -> dict:
            return {
                "user_facts": ["Likes clean code"],
                "project_facts": [],
                "event_summary": "Talked about code quality.",
                "feedback_rules": [],
            }

        extractor = MemoryV2Extractor(store, llm_callable=mock_llm)
        facts = await extractor.extract("Write clean code please")
        assert "Likes clean code" in facts.user_facts


# ── Apply ────────────────────────────────────────────────────────


class TestApply:
    @pytest.mark.asyncio
    async def test_apply_writes_profiles(self, store, extractor):
        facts = ExtractedFacts(
            user_facts=["Prefers Python"],
            project_facts=["Nexus is the project name"],
            event_summary="Initial setup",
            feedback_rules=["No emojis"],
        )
        await extractor.apply(facts, date_str="2026-05-21")

        # Profiles written
        _, user_body = store.read_profile("user")
        assert "Prefers Python" in user_body

        _, project_body = store.read_profile("project")
        assert "Nexus is the project name" in project_body

        # Event appended
        event_content = (store.root / "events" / "2026-05-21.md").read_text("utf-8")
        assert "Initial setup" in event_content

        # Rule appended
        rules_content = (store.root / "rules" / "feedback.md").read_text("utf-8")
        assert "No emojis" in rules_content

    @pytest.mark.asyncio
    async def test_apply_merges_user_profile(self, store, extractor):
        store.write_profile("user", "# User\n\n- Existing fact\n")
        facts = ExtractedFacts(user_facts=["New fact"])
        await extractor.apply(facts, date_str="2026-05-21")

        _, body = store.read_profile("user")
        assert "Existing fact" in body
        assert "New fact" in body

    @pytest.mark.asyncio
    async def test_apply_empty_facts_noop(self, store, extractor):
        facts = ExtractedFacts()
        await extractor.apply(facts)
        # Should not create any files
        assert not (store.root / "profile" / "user.md").exists()


# ── Prompt template ──────────────────────────────────────────────


class TestPromptTemplate:
    def test_default_template_contains_placeholder(self):
        assert "$conversation" in DEFAULT_EXTRACT_PROMPT

    def test_custom_template(self, store):
        extractor = MemoryV2Extractor(store, prompt_template="Extract: $conversation")
        assert extractor.prompt_template == "Extract: $conversation"
