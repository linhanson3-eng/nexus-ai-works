from __future__ import annotations
"""Skill loader and repo tests."""


import tempfile
from pathlib import Path

import pytest


SKILL_MD_CONTENT = """---
name: code-review
description: Comprehensive code review with security and quality checks
triggers:
  - review
  - code review
  - check code
version: "2.1.0"
tools:
  - gh
  - rg
models:
  - sonnet
  - opus
extra_field: custom_value
---

# Code Review Skill

This skill performs comprehensive code review.

## Usage

Trigger this skill when you need to review code changes.
"""

SKILL_MD_MINIMAL = """# Minimal Skill

No front matter here.
"""


class TestSkillFromFile:
    """Test Skill.from_file parsing."""

    def test_full_front_matter(self) -> None:
        from factory.skills.loader import Skill

        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / "code-review" / "Skill.md"
            skill_path.parent.mkdir()
            skill_path.write_text(SKILL_MD_CONTENT, encoding="utf-8")
            skill = Skill.from_file(skill_path)
            assert skill is not None
            assert skill.name == "code-review"
            assert skill.description == (
                "Comprehensive code review with security and quality checks"
            )
            assert skill.triggers == ("review", "code review", "check code")
            assert skill.version == "2.1.0"
            assert skill.tools == ("gh", "rg")
            assert skill.models == ("sonnet", "opus")
            assert skill.metadata == {"extra_field": "custom_value"}
            assert "Code Review Skill" in skill.body
            assert "## Usage" in skill.body

    def test_minimal_skill_no_front_matter(self) -> None:
        from factory.skills.loader import Skill

        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / "minimal.md"
            skill_path.write_text(SKILL_MD_MINIMAL, encoding="utf-8")
            skill = Skill.from_file(skill_path)
            assert skill is not None
            assert skill.name == "minimal"
            assert skill.description == ""
            assert skill.triggers == ()
            assert skill.body == SKILL_MD_MINIMAL

    def test_nonexistent_file(self) -> None:
        from factory.skills.loader import Skill

        skill = Skill.from_file(Path("/nonexistent/path/Skill.md"))
        assert skill is None

    def test_empty_front_matter(self) -> None:
        from factory.skills.loader import Skill

        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / "empty-front.md"
            skill_path.write_text("---\n---\n\nBody only.", encoding="utf-8")
            skill = Skill.from_file(skill_path)
            assert skill is not None
            assert skill.name == "empty-front"
            assert skill.body == "Body only."

    def test_invalid_yaml_front_matter(self) -> None:
        from factory.skills.loader import Skill

        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / "bad-yaml.md"
            skill_path.write_text("---\n: invalid yaml : :\n---\n\nBody.", encoding="utf-8")
            skill = Skill.from_file(skill_path)
            assert skill is not None
            assert skill.name == "bad-yaml"
            assert skill.body == "Body."


class TestSkillIndex:
    """Test progressive disclosure (index does not include body)."""

    def test_skill_index_no_body(self) -> None:
        from factory.skills.loader import SkillIndex

        idx = SkillIndex(
            name="test-skill",
            description="A test skill",
            triggers=("test",),
            version="1.2.3",
            path="/path/to/Skill.md",
        )
        assert idx.name == "test-skill"
        assert not hasattr(idx, "body")
        assert idx.triggers == ("test",)


class TestProgressiveDisclosure:
    """Test SkillLoader list_skills, load_skill, reload."""

    @pytest.fixture
    def skills_dir(self) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            # Create directory-per-skill layout
            skill_dir = Path(tmp) / "code-review"
            skill_dir.mkdir()
            (skill_dir / "Skill.md").write_text(SKILL_MD_CONTENT, encoding="utf-8")

            # Create a minimal skill
            minimal_dir = Path(tmp) / "greeting"
            minimal_dir.mkdir()
            (minimal_dir / "Skill.md").write_text(
                "---\nname: greeting\ndescription: Say hello\ntriggers:\n  - hello\n  - hi\n---\n\nHello!",
                encoding="utf-8",
            )

            # Create a flat .md file
            flat_file = Path(tmp) / "flat-skill.md"
            flat_file.write_text(
                "---\nname: flat-skill\ndescription: Flat layout example\n---\n\nFlat content.",
                encoding="utf-8",
            )

            yield tmp

    def test_list_all_skills(self, skills_dir: str) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader(skills_dir)
        skills = loader.list_skills()
        assert len(skills) == 3
        names = {s.name for s in skills}
        assert names == {"code-review", "greeting", "flat-skill"}

    def test_list_with_query(self, skills_dir: str) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader(skills_dir)
        results = loader.list_skills("review")
        assert len(results) == 1
        assert results[0].name == "code-review"

    def test_list_by_trigger(self, skills_dir: str) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader(skills_dir)
        results = loader.list_skills("hello")
        assert len(results) == 1
        assert results[0].name == "greeting"

    def test_load_skill_full_content(self, skills_dir: str) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader(skills_dir)
        skill = loader.load_skill("code-review")
        assert skill is not None
        assert skill.name == "code-review"
        assert "Code Review Skill" in skill.body
        assert skill.tools == ("gh", "rg")

    def test_load_nonexistent_skill(self, skills_dir: str) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader(skills_dir)
        assert loader.load_skill("nonexistent") is None

    def test_load_skill_caching(self, skills_dir: str) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader(skills_dir)
        first = loader.load_skill("code-review")
        second = loader.load_skill("code-review")
        assert first is second

    def test_reload(self, skills_dir: str) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader(skills_dir)
        assert len(loader.list_skills()) == 3
        loader.reload()
        assert len(loader.list_skills()) == 3

    def test_find_by_trigger(self, skills_dir: str) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader(skills_dir)
        matched = loader.find_by_trigger("please do a code review for me")
        assert len(matched) == 1
        assert matched[0].name == "code-review"

    def test_find_by_trigger_no_match(self, skills_dir: str) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader(skills_dir)
        matched = loader.find_by_trigger("generate a report")
        assert matched == []

    def test_empty_dir(self) -> None:
        from factory.skills.loader import SkillLoader

        with tempfile.TemporaryDirectory() as tmp:
            loader = SkillLoader(tmp)
            assert loader.list_skills() == []

    def test_nonexistent_dir(self) -> None:
        from factory.skills.loader import SkillLoader

        loader = SkillLoader("/nonexistent/skills/dir")
        assert loader.list_skills() == []


class TestSkillRepo:
    """Test SkillRepo install, uninstall, enable/disable, list."""

    @pytest.fixture
    def repo(self) -> "SkillRepo":
        from factory.skills.repo import SkillRepo

        with tempfile.TemporaryDirectory() as tmp:
            # Create a skills dir with one skill file
            skills_dir = Path(tmp) / "skills" / "code-review"
            skills_dir.mkdir(parents=True)
            (skills_dir / "Skill.md").write_text(SKILL_MD_CONTENT, encoding="utf-8")

            repo = SkillRepo(
                db_path=Path(tmp) / "test.db",
                skills_dir=Path(tmp) / "skills",
            )
            yield repo

    def test_install_and_is_installed(self, repo: "SkillRepo") -> None:
        repo.install("code-review")
        assert repo.is_installed("code-review") is True

    def test_not_installed_by_default(self, repo: "SkillRepo") -> None:
        assert repo.is_installed("code-review") is False

    def test_uninstall(self, repo: "SkillRepo") -> None:
        repo.install("code-review")
        assert repo.is_installed("code-review") is True
        repo.uninstall("code-review")
        assert repo.is_installed("code-review") is False

    def test_disable_and_enable(self, repo: "SkillRepo") -> None:
        repo.install("code-review")
        assert repo.is_installed("code-review") is True
        repo.disable("code-review")
        assert repo.is_installed("code-review") is False
        repo.enable("code-review")
        assert repo.is_installed("code-review") is True

    def test_list_installed(self, repo: "SkillRepo") -> None:
        repo.install("code-review")
        installed = repo.list_installed()
        assert len(installed) == 1
        assert installed[0].name == "code-review"

    def test_list_empty_when_none_installed(self, repo: "SkillRepo") -> None:
        installed = repo.list_installed()
        assert installed == []

    def test_workshop_isolation(self, repo: "SkillRepo") -> None:
        repo.install("code-review", workshop_name="workshop-a")
        assert repo.is_installed("code-review", workshop_name="workshop-a") is True
        assert repo.is_installed("code-review", workshop_name="workshop-b") is False

    def test_double_install_idempotent(self, repo: "SkillRepo") -> None:
        repo.install("code-review")
        repo.install("code-review")
        installed = repo.list_installed()
        assert len(installed) == 1
