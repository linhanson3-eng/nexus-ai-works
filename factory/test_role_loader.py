from __future__ import annotations
"""Tests for role config loader."""


import tempfile
from pathlib import Path

import pytest
import yaml

from config.schema import AgentPermissions, AgentSpec, BudgetSpec
from factory.role_loader import RoleLoader, _merge_prompt


@pytest.fixture
def roles_dir():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        (base / "test_role.yaml").write_text(
            yaml.dump({
                "name": "test_role",
                "description": "A test role",
                "append_prompt": "You are a test agent.",
                "model": {"default": "anthropic/claude-haiku-4-5", "budget_work": "anthropic/claude-haiku-4-5"},
                "budget": {
                    "max_total_tokens": 100000,
                    "max_total_cost_usd": 1.0,
                    "max_tool_calls": 10,
                    "max_model_calls": 5,
                    "max_session_turns": 5,
                },
                "permissions": {
                    "shell_exec": False,
                    "file_write": True,
                    "subagent_spawn": False,
                },
            }),
            encoding="utf-8",
        )
        yield base


@pytest.fixture
def loader(roles_dir):
    return RoleLoader(roles_dir)


class TestRoleLoader:
    def test_get_existing_role(self, loader):
        role = loader.get("test_role")
        assert role is not None
        assert role.name == "test_role"
        assert "You are a test agent" in role.append_prompt
        assert role.model.default == "anthropic/claude-haiku-4-5"
        assert role.permissions.file_write is True
        assert role.permissions.shell_exec is False

    def test_get_missing_role(self, loader):
        assert loader.get("nonexistent") is None

    def test_list_all(self, loader):
        names = loader.list_all()
        assert "test_role" in names

    def test_cache_hit(self, loader):
        role1 = loader.get("test_role")
        role2 = loader.get("test_role")
        assert role1 is role2


class TestApplyRole:
    def test_apply_role_adds_prompt(self, loader):
        spec = AgentSpec(
            name="test_agent",
            template="test",
            role="test_role",
            system_prompt="Be concise.",
        )
        result = loader.apply_role(spec)
        assert "You are a test agent" in result.system_prompt
        assert "Be concise." in result.system_prompt

    def test_apply_role_no_role_field(self, loader):
        spec = AgentSpec(name="test", system_prompt="Just prompt")
        result = loader.apply_role(spec)
        assert result.system_prompt == "Just prompt"

    def test_apply_role_unknown_role(self, loader):
        spec = AgentSpec(name="test", role="nonexistent")
        result = loader.apply_role(spec)
        assert result == spec

    def test_template_overrides_role_model(self, loader):
        spec = AgentSpec(
            name="test", role="test_role",
            model="anthropic/claude-opus-4-7",
        )
        result = loader.apply_role(spec)
        assert result.model == "anthropic/claude-opus-4-7"

    def test_template_overrides_role_budget(self, loader):
        custom_budget = BudgetSpec(max_total_tokens=999)
        spec = AgentSpec(
            name="test", role="test_role", budget=custom_budget,
        )
        result = loader.apply_role(spec)
        assert result.budget.max_total_tokens == 999

    def test_apply_role_converts_permissions(self, loader):
        spec = AgentSpec(
            name="test", role="test_role",
            permissions=AgentPermissions(),
        )
        result = loader.apply_role(spec)
        # Role should provide permissions since template has defaults
        assert result.permissions.shell.exec is False
        assert len(result.permissions.filesystem.write) > 0


class TestMergePrompt:
    def test_both_provided(self):
        result = _merge_prompt("Role prompt", "Template prompt")
        assert "Role prompt" in result
        assert "Template prompt" in result

    def test_only_role(self):
        result = _merge_prompt("Role prompt", "")
        assert result.strip() == "Role prompt"

    def test_only_template(self):
        result = _merge_prompt("", "Template prompt")
        assert result.strip() == "Template prompt"

    def test_both_empty(self):
        assert _merge_prompt("", "") == ""


class TestRealRoleFiles:
    """Verify role loading from config/roles/ directory."""

    def test_role_loading_from_dir(self):
        """RoleLoader loads from config/roles/ without errors."""
        loader = RoleLoader()
        names = loader.list_all()
        assert isinstance(names, list)
