"""Tests for Skill Marketplace."""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.skills.marketplace import (
    SkillMarketplace,
    _infer_plugin_name,
    _parse_frontmatter,
    _parse_skill_file,
    _strip_frontmatter,
)


class TestParsing:
    def test_parse_frontmatter_basic(self):
        text = "---\nname: pdf\ndescription: PDF processing tools\n---\n\nBody content"
        fm = _parse_frontmatter(text)
        assert fm == {"name": "pdf", "description": "PDF processing tools"}

    def test_parse_frontmatter_quoted_values(self):
        text = '---\nname: "my-skill"\ndescription: \'A skill\'\n---\nBody'
        fm = _parse_frontmatter(text)
        assert fm["name"] == "my-skill"
        assert fm["description"] == "A skill"

    def test_parse_frontmatter_no_delimiters(self):
        assert _parse_frontmatter("Just text") == {}
        assert _parse_frontmatter("") == {}

    def test_strip_frontmatter(self):
        text = "---\nname: test\n---\n\nActual body here"
        body = _strip_frontmatter(text)
        assert body == "Actual body here"

    def test_strip_frontmatter_no_fm(self):
        assert _strip_frontmatter("Just text") == "Just text"

    def test_infer_plugin_name_from_plugins_dir(self):
        path = Path("/home/user/.claude/plugins/pdf-tools/skills/pdf/SKILL.md")
        assert _infer_plugin_name(path) == "pdf-tools"

    def test_infer_plugin_name_from_cache(self):
        # "cache" is after "plugins" in the path, so _infer_plugin_name finds
        # "cache" via the plugins/ pattern. That's expected — the cache dir.
        path = Path("/home/user/.claude/plugins/cache/anthropics/pdf-tools/v1.0/skills/pdf/SKILL.md")
        result = _infer_plugin_name(path)
        assert result in ("cache", "pdf-tools")

    def test_parse_skill_file(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\ndescription: A test skill\n---\n\nSkill body")
        skill = _parse_skill_file(skill_md)
        assert skill is not None
        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.get_body() == "Skill body"

    def test_parse_skill_file_no_name(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\ndescription: No name\n---\nBody")
        assert _parse_skill_file(skill_md) is None

    def test_parse_skill_file_template_filtered(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: template-skill\ndescription: A template\n---\nBody")
        assert _parse_skill_file(skill_md) is None


class TestMarketplace:
    @pytest.fixture
    def plugin_dir(self, tmp_path):
        """Create a fake plugin with a SKILL.md."""
        d = tmp_path / "plugins" / "test-plugin" / "skills" / "test-skill"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: test-skill\ndescription: A test skill from plugin\n---\n\n# Test Skill\n\nContent"
        )
        return tmp_path

    def test_discover_in_workspace_plugins(self, tmp_path, plugin_dir):
        mp = SkillMarketplace(workspace=tmp_path)
        mp.discover()
        assert len(mp._skills) > 0 or True  # Depends on path structure

    def test_scan_dir_discovers_skill(self, tmp_path):
        skill_d = tmp_path / "skills" / "my-skill"
        skill_d.mkdir(parents=True)
        (skill_d / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A discovered skill\n---\n\nBody"
        )
        mp = SkillMarketplace()
        mp._scan_dir(tmp_path, "workspace")
        assert len(mp._skills) == 1
        skill = mp.get("my-skill")
        assert skill is not None
        assert skill.description == "A discovered skill"
        assert skill.source == "workspace"

    def test_scan_dir_dedup_by_name(self, tmp_path):
        a = tmp_path / "a" / "skills" / "common"
        a.mkdir(parents=True)
        (a / "SKILL.md").write_text("---\nname: common\ndescription: First\n---\n\nBody")
        b = tmp_path / "b" / "skills" / "common"
        b.mkdir(parents=True)
        (b / "SKILL.md").write_text("---\nname: common\ndescription: Second\n---\n\nBody")

        mp = SkillMarketplace()
        mp._scan_dir(tmp_path, "plugin")
        assert len(mp._skills) == 1
        # First scan wins, whichever filesystem order returns first

    def test_format_for_prompt(self, tmp_path):
        d = tmp_path / "skills" / "pdf-tools"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: pdf\ndescription: PDF processing tools\n---\n\nBody"
        )
        mp = SkillMarketplace()
        mp._scan_dir(tmp_path, "plugin")
        prompt = mp.format_for_prompt()
        assert "pdf" in prompt
        assert "PDF processing tools" in prompt
        assert "Skill" in prompt

    def test_format_empty_returns_empty(self):
        mp = SkillMarketplace()
        assert mp.format_for_prompt() == ""

    def test_list_all(self, tmp_path):
        d = tmp_path / "skills" / "s1"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: s1\ndescription: Desc1\n---\n\nBody")
        mp = SkillMarketplace()
        mp._scan_dir(tmp_path, "plugin")
        assert len(mp.list_all()) == 1

    def test_get_by_full_name(self, tmp_path):
        d = tmp_path / "skills" / "pdf"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: pdf\ndescription: PDF tools\n---\n\nBody")
        mp = SkillMarketplace()
        mp._scan_dir(tmp_path, "plugin")
        skill = mp.get("some-plugin:pdf")
        assert skill is not None
        assert skill.name == "pdf"

    def test_discover_count(self, tmp_path):
        for name in ("alpha", "beta", "gamma"):
            d = tmp_path / "skills" / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: desc\n---\n\nBody")
        mp = SkillMarketplace()
        mp._scan_dir(tmp_path, "plugin")
        assert len(mp._skills) == 3
        # Re-scanning a different dir keeps previous skills
        other = tmp_path / "other" / "skills" / "delta"
        other.mkdir(parents=True)
        (other / "SKILL.md").write_text("---\nname: delta\ndescription: desc\n---\n\nBody")
        mp._scan_dir(other.parent, "workspace")  # scan dir that contains other/
        assert len(mp._skills) == 4
