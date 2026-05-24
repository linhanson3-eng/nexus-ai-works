from __future__ import annotations
"""Tests for safe env-var parsing (factory/env.py)."""


import os

import pytest

from factory.env import env_int, env_bool, env_str, env_path


class TestEnvInt:
    def test_default(self):
        assert env_int("NX_NOEXIST", 42) == 42

    def test_valid(self, monkeypatch):
        monkeypatch.setenv("NX_TIMEOUT", "300")
        assert env_int("NX_TIMEOUT", 600) == 300

    def test_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("NX_TIMEOUT", "abc")
        assert env_int("NX_TIMEOUT", 600) == 600

    def test_below_min(self, monkeypatch):
        monkeypatch.setenv("NX_TIMEOUT", "3")
        assert env_int("NX_TIMEOUT", 600, min=10) == 10

    def test_above_max(self, monkeypatch):
        monkeypatch.setenv("NX_TIMEOUT", "99999")
        assert env_int("NX_TIMEOUT", 600, max=3600) == 3600

    def test_empty_string_uses_default(self):
        assert env_int("NX_NOEXIST", 600) == 600


class TestEnvBool:
    def test_truthy(self, monkeypatch):
        for v in ("1", "true", "yes", "on", "True", "YES"):
            monkeypatch.setenv("NX_FLAG", v)
            assert env_bool("NX_FLAG") is True

    def test_falsy(self, monkeypatch):
        for v in ("0", "false", "no", "off"):
            monkeypatch.setenv("NX_FLAG", v)
            assert env_bool("NX_FLAG") is False

    def test_empty_uses_default(self, monkeypatch):
        monkeypatch.setenv("NX_FLAG", "")
        assert env_bool("NX_FLAG", default=True) is True
        assert env_bool("NX_FLAG", default=False) is False

    def test_default(self):
        assert env_bool("NX_NOEXIST", default=True) is True
        assert env_bool("NX_NOEXIST", default=False) is False

    def test_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("NX_FLAG", "maybe")
        assert env_bool("NX_FLAG", default=False) is False


class TestEnvStr:
    def test_default(self):
        assert env_str("NX_NOEXIST", "fallback") == "fallback"

    def test_valid_choice(self, monkeypatch):
        monkeypatch.setenv("NX_ENV", "development")
        assert env_str("NX_ENV", "production", choices=("development", "production")) == "development"

    def test_invalid_choice(self, monkeypatch):
        monkeypatch.setenv("NX_ENV", "hacked")
        assert env_str("NX_ENV", "production", choices=("development", "production")) == "production"


class TestEnvPath:
    def test_default(self):
        p = env_path("NX_NOEXIST", "~/.nexus/test.db")
        assert p.name == "test.db"
        assert str(p).startswith(str(os.path.expanduser("~")))

    def test_custom(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NX_PATH", str(tmp_path / "custom.db"))
        p = env_path("NX_PATH", "~/.nexus/default.db")
        assert p.name == "custom.db"
