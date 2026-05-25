from __future__ import annotations

import asyncio
import time
import pytest
from gateway.mcp.auth import MCPTokenManager


class TestMCPTokenManager:
    @pytest.fixture
    def mgr(self):
        return MCPTokenManager(secret="test-secret-key-for-mcp", kid="k1")

    def test_issue_and_verify_jwt_token(self, mgr):
        token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
        parts = token.split(".")
        assert len(parts) == 3

        payload = mgr.verify(token)
        assert payload is not None
        assert payload["session_id"] == "sess-abc"
        assert payload["workshop_name"] == "demo"
        assert payload["iss"] == "ai-factory"

    def test_expired_token_returns_none(self):
        mgr = MCPTokenManager(secret="test-secret", ttl_seconds=-1)
        token = mgr.issue(user_id="user-1", session_id="sess-expired", workshop_name="demo")
        assert mgr.verify(token) is None

    def test_tampered_token_returns_none(self, mgr):
        token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
        tampered = token[:-5] + "xxxxx"
        assert mgr.verify(tampered) is None

    def test_max_uses_default_1(self):
        mgr = MCPTokenManager(secret="test-secret", max_uses=1)
        token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
        assert mgr.verify(token) is not None
        assert mgr.verify(token) is None

    def test_max_uses_custom(self):
        mgr = MCPTokenManager(secret="test-secret", max_uses=3)
        token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
        for _ in range(3):
            assert mgr.verify(token) is not None
        assert mgr.verify(token) is None

    def test_revoke_token(self, mgr):
        token = mgr.issue(user_id="user-1", session_id="sess-xyz", workshop_name="demo")
        payload = mgr.verify(token)
        assert payload is not None
        jti = payload["jti"]
        mgr.revoke(jti)
        assert mgr.verify(token) is None

    def test_use_counts_cleanup(self):
        mgr = MCPTokenManager(secret="test-secret", ttl_seconds=0, max_uses=5)
        for i in range(10):
            token = mgr.issue(user_id="u1", session_id=f"sess-{i}", workshop_name="demo")
            mgr.verify(token)
        mgr._cleanup_stale()
        assert len(mgr._use_counts) == 0

    def test_aud_and_sub_claims(self, mgr):
        token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
        payload = mgr.verify(token)
        assert payload["aud"] == "ai-factory"
        assert payload["sub"] == "user-1"

    def test_empty_secret_raises(self):
        with pytest.raises(RuntimeError, match="non-empty secret"):
            MCPTokenManager(secret="")


class TestMCPRateLimiter:

    def test_token_bucket_consumes_burst(self):
        from gateway.mcp.server import TokenBucket

        bucket = TokenBucket(rate=100.0, burst=5)
        for _ in range(5):
            assert asyncio.run(bucket.consume()) is True
        assert asyncio.run(bucket.consume()) is False

    async def test_concurrent_consumes_no_race(self):
        from gateway.mcp.server import TokenBucket

        bucket = TokenBucket(rate=1000.0, burst=200)
        results = []

        async def consumer():
            for _ in range(100):
                results.append(await bucket.consume())

        await asyncio.gather(consumer(), consumer())
        consumed = sum(1 for r in results if r)
        assert consumed == 200  # 2 * 100, burst=200


class TestMCPTools:

    def test_tool_definitions_all_have_required_fields(self):
        from gateway.mcp.tools import TOOL_DEFINITIONS

        for tool in TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert isinstance(tool["inputSchema"]["required"], list)

    def test_execute_task_modes_are_valid(self):
        from gateway.mcp.tools import TOOL_DEFINITIONS

        for tool in TOOL_DEFINITIONS:
            if tool["name"] == "nexus_execute_task":
                modes = tool["inputSchema"]["properties"]["mode"]["enum"]
                assert "continue" in modes
                assert "fork" in modes
                assert "spawn" in modes
                assert "btw" in modes

    def test_all_tools_count(self):
        from gateway.mcp.tools import TOOL_DEFINITIONS

        assert len(TOOL_DEFINITIONS) == 9
