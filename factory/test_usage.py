"""Tests for usage tracking."""
import os
import secrets
import pytest
from factory.usage import record, get_user_stats, UsageEvent, DB_PATH


@pytest.fixture(autouse=True)
def clean_db():
    """Remove usage DB before each test for isolation."""
    db_path = DB_PATH.expanduser()
    if db_path.exists():
        db_path.unlink()
    yield
    if db_path.exists():
        db_path.unlink()


def _uid():
    return secrets.token_hex(8)


class TestUsageEvent:
    def test_event_constants_defined(self):
        assert UsageEvent.WORKFLOW_RUN == "workflow.run"
        assert UsageEvent.AGENT_CALL == "agent.call"
        assert UsageEvent.TOKEN_CONSUMED == "token.consumed"
        assert UsageEvent.WORKSPACE_CREATED == "workspace.created"


class TestUsageRecord:
    def test_record_does_not_raise(self):
        record(_uid(), UsageEvent.WORKFLOW_RUN, "simple", 1)

    def test_record_and_query(self):
        user_id = _uid()
        record(user_id, UsageEvent.AGENT_CALL, "claude-sonnet-4-6", 5)
        record(user_id, UsageEvent.TOKEN_CONSUMED, "", 15000)

        stats = get_user_stats(user_id, days=30)
        assert stats[UsageEvent.AGENT_CALL] == 5
        assert stats[UsageEvent.TOKEN_CONSUMED] == 15000

    def test_get_user_stats_empty(self):
        stats = get_user_stats(_uid(), days=30)
        assert stats == {}

    def test_record_multiple_events(self):
        user_id = _uid()
        for _ in range(3):
            record(user_id, UsageEvent.WORKFLOW_RUN, "simple", 1)

        stats = get_user_stats(user_id, days=30)
        assert stats[UsageEvent.WORKFLOW_RUN] == 3
