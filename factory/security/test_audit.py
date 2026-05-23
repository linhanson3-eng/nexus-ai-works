"""Tests for audit trail system."""
import secrets

import pytest
from factory.security.audit import record, query, get_recent_events, purge_old, AuditEvent


@pytest.fixture(autouse=True)
def clean_audit_db(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    monkeypatch.setenv("AUDIT_DB_PATH", str(db_path))
    if db_path.exists():
        db_path.unlink()
    yield
    if db_path.exists():
        db_path.unlink()


class TestAuditRecord:
    def test_record_does_not_raise(self):
        record(AuditEvent.AUTH_LOGIN, "user.login", actor="test_user")

    def test_record_and_query(self):
        uid = secrets.token_hex(8)
        record(AuditEvent.AUTH_LOGIN, "user.login", actor=uid, detail="from 127.0.0.1")

        results = query(actor=uid)
        assert len(results) == 1
        assert results[0]["event_type"] == AuditEvent.AUTH_LOGIN
        assert results[0]["action"] == "user.login"

    def test_query_by_event_type(self):
        record(AuditEvent.CONFIG_CHANGE, "settings.updated", actor="admin")
        record(AuditEvent.AUTH_FAILED, "login.failed", actor="attacker", detail="bad password")

        config_events = query(event_type=AuditEvent.CONFIG_CHANGE)
        assert len(config_events) == 1
        assert config_events[0]["action"] == "settings.updated"

        auth_fails = query(event_type=AuditEvent.AUTH_FAILED)
        assert len(auth_fails) == 1

    def test_query_empty(self):
        results = query(actor="nonexistent_user")
        assert results == []

    def test_get_recent_events(self):
        for i in range(5):
            record(AuditEvent.WORKFLOW_EXECUTE, f"wf.run.{i}", actor="agent")
        events = get_recent_events(limit=3)
        assert len(events) == 3

    def test_purge_old(self):
        record(AuditEvent.DATA_DELETE, "card.deleted", actor="user")
        deleted = purge_old(days=365)
        assert deleted >= 0

    def test_all_event_types(self):
        for attr in dir(AuditEvent):
            if attr.isupper():
                event_type = getattr(AuditEvent, attr)
                record(event_type, f"test.{event_type}", actor="tester")
        all_events = get_recent_events(limit=50)
        assert len(all_events) > 0
