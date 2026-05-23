"""Tests for deep search tool."""

from __future__ import annotations


from factory.tools.deep_search import (
    _clean_html,
    _MODE_PROMPTS,
    create_deep_search_tool,
    deep_search_handler,
)


class TestHtmlCleaning:
    def test_strips_tags(self):
        result = _clean_html("<p>Hello <b>World</b></p>")
        assert "Hello" in result
        assert "World" in result

    def test_strips_scripts(self):
        result = _clean_html('<script>alert("xss")</script><p>content</p>')
        assert "alert" not in result
        assert "content" in result

    def test_normalizes_whitespace(self):
        result = _clean_html("<p>a</p>   \n\n\n   <p>b</p>")
        assert "a" in result
        assert "b" in result

    def test_empty(self):
        assert _clean_html("") == ""

    def test_truncates_large(self):
        huge = "<p>" + "x" * 10000 + "</p>"
        result = _clean_html(huge)
        assert len(result) <= 7000  # max 6000 * 2 before strip, roughly


class TestDeepSearchTool:
    def test_tool_creation(self):
        tool = create_deep_search_tool()
        assert tool.name == "deep_search"
        assert "query" in tool.parameters.get("required", [])
        assert tool.handler is deep_search_handler

    def test_tool_schema(self):
        tool = create_deep_search_tool()
        props = tool.parameters.get("properties", {})
        assert "query" in props
        assert "mode" in props
        assert "max_results" in props
        assert "deep_read" in props
        assert props["mode"]["enum"] == ["summary", "compare", "fact_check"]

    def test_tool_description(self):
        tool = create_deep_search_tool()
        assert "Deep web search" in tool.description


class TestModePrompts:
    def test_summary_mode_exists(self):
        assert "summary" in _MODE_PROMPTS
        assert "关键发现" in _MODE_PROMPTS["summary"]

    def test_compare_mode_exists(self):
        assert "compare" in _MODE_PROMPTS
        assert "来源一致性" in _MODE_PROMPTS["compare"]

    def test_fact_check_mode_exists(self):
        assert "fact_check" in _MODE_PROMPTS
        assert "可信度" in _MODE_PROMPTS["fact_check"]

    def test_all_modes_have_prompts(self):
        for mode in ("summary", "compare", "fact_check"):
            assert mode in _MODE_PROMPTS
            assert len(_MODE_PROMPTS[mode]) > 50
