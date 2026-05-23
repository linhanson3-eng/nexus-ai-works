"""Tests for Memory V2 file-based store."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from factory.memory.v2_store import (
    MemoryEntry,
    MemoryV2Store,
    format_frontmatter,
    parse_frontmatter,
)


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def store(tmp_root):
    return MemoryV2Store(tmp_root / "memory")


# ── Frontmatter ──────────────────────────────────────────────────


class TestFrontmatter:
    def test_parse_basic(self):
        text = "---\nname: test\ndescription: Test desc\n---\n\nBody content\n"
        meta, body = parse_frontmatter(text)
        assert meta == {"name": "test", "description": "Test desc"}
        assert body.strip() == "Body content"

    def test_parse_no_frontmatter(self):
        text = "Just body content\n"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_parse_empty_frontmatter(self):
        text = "---\n---\n\nBody\n"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body.strip() == "Body"

    def test_format_basic(self):
        result = format_frontmatter(
            {"name": "test", "type": "profile"}, "Body content"
        )
        assert "---" in result
        assert "name: test" in result
        assert "type: profile" in result
        assert "Body content" in result


# ── Index ────────────────────────────────────────────────────────


class TestIndex:
    def test_read_empty(self, store):
        assert store.read_index() == []

    def test_write_and_read(self, store):
        entries = [
            MemoryEntry(
                name="user-profile",
                title="User Profile",
                path="profile/user.md",
                description="User stuff",
                type="profile",
            ),
            MemoryEntry(
                name="events-today",
                title="2026-05-21",
                path="events/2026-05-21.md",
                description="Today's events",
                type="event",
            ),
        ]
        store.write_index(entries)
        assert store.index_path.exists()

        loaded = store.read_index()
        assert len(loaded) == 2
        assert loaded[0].name == "user"  # derived from path stem
        assert loaded[1].type == "event"

    def test_add_to_index_new(self, store):
        entry = MemoryEntry(
            name="test", title="Test", path="test.md", description="d", type="profile"
        )
        store.add_to_index(entry)
        assert len(store.read_index()) == 1

    def test_add_to_index_replace(self, store):
        e1 = MemoryEntry(
            name="test", title="Old", path="test.md", description="d", type="profile"
        )
        store.add_to_index(e1)
        e2 = MemoryEntry(
            name="test", title="New", path="test.md", description="d", type="profile"
        )
        store.add_to_index(e2)
        entries = store.read_index()
        assert len(entries) == 1
        assert entries[0].title == "New"


# ── Profile ──────────────────────────────────────────────────────


class TestProfile:
    def test_write_and_read(self, store):
        store.write_profile("user", "# User Profile\n\n- Likes Python\n")
        meta, body = store.read_profile("user")
        assert meta["type"] == "profile"
        assert "Likes Python" in body

    def test_read_missing(self, store):
        meta, body = store.read_profile("user")
        assert meta == {}
        assert body == ""

    def test_overwrites(self, store):
        store.write_profile("user", "First version")
        store.write_profile("user", "Second version")
        _, body = store.read_profile("user")
        assert "Second version" in body
        assert "First version" not in body


# ── Events ───────────────────────────────────────────────────────


class TestEvents:
    def test_first_event_creates_file(self, store):
        store.append_event("Did something", date_str="2026-05-21")
        path = store.root / "events" / "2026-05-21.md"
        assert path.exists()
        content = path.read_text("utf-8")
        assert "Did something" in content

    def test_second_event_appends(self, store):
        store.append_event("First thing", date_str="2026-05-21")
        store.append_event("Second thing", date_str="2026-05-21")
        content = (store.root / "events" / "2026-05-21.md").read_text("utf-8")
        assert "First thing" in content
        assert "Second thing" in content

    def test_different_dates_different_files(self, store):
        store.append_event("Day 1", date_str="2026-05-20")
        store.append_event("Day 2", date_str="2026-05-21")
        assert (store.root / "events" / "2026-05-20.md").exists()
        assert (store.root / "events" / "2026-05-21.md").exists()


# ── Rules ────────────────────────────────────────────────────────


class TestRules:
    def test_first_rule(self, store):
        store.append_rule("Don't use emojis in code")
        path = store.root / "rules" / "feedback.md"
        assert path.exists()
        content = path.read_text("utf-8")
        assert "Don't use emojis in code" in content

    def test_multiple_rules(self, store):
        store.append_rule("Rule 1")
        store.append_rule("Rule 2")
        content = (store.root / "rules" / "feedback.md").read_text("utf-8")
        assert "Rule 1" in content
        assert "Rule 2" in content


# ── Context assembly ─────────────────────────────────────────────


class TestContext:
    def test_empty_context(self, store):
        assert store.get_context_for_prompt() == ""

    def test_context_from_index(self, store):
        store.add_to_index(
            MemoryEntry(
                name="test", title="Test", path="t.md", description="desc", type="profile"
            )
        )
        ctx = store.get_context_for_prompt()
        assert "Test" in ctx
        assert "desc" in ctx

    def test_full_context_includes_profiles(self, store):
        store.write_profile("user", "# User\n- Dev\n")
        store.write_profile("project", "# Project\n- Nexus\n")
        store.append_event("Made progress")
        store.append_rule("Be concise")

        ctx = store.get_full_context()
        assert "Dev" in ctx
        assert "Nexus" in ctx
        assert "Made progress" in ctx
        assert "Be concise" in ctx


# ── Entry ────────────────────────────────────────────────────────


class TestMemoryEntry:
    def test_to_index_line(self):
        entry = MemoryEntry(
            name="test",
            title="Test Entry",
            path="test/file.md",
            description="A test entry",
            type="profile",
        )
        line = entry.to_index_line()
        assert "[Test Entry]" in line
        assert "test/file.md" in line
        assert "A test entry" in line
