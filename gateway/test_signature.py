from __future__ import annotations

"""Tests for HMAC request signing."""

from gateway.signature import get_or_create_secret, sign_request


class TestGetOrCreateSecret:
    def test_returns_string(self):
        secret = get_or_create_secret()
        assert isinstance(secret, str)
        assert len(secret) == 64  # token_hex(32) = 64 chars

    def test_idempotent(self):
        s1 = get_or_create_secret()
        s2 = get_or_create_secret()
        assert s1 == s2


class TestSignRequest:
    def test_produces_hex_digest(self):
        sig = sign_request("POST", "/api/test", '{"key":"val"}', "2026-01-01T00:00:00Z")
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA256 hex

    def test_different_inputs_produce_different_signatures(self):
        sig1 = sign_request("GET", "/api/a", "", "t1")
        sig2 = sign_request("POST", "/api/a", "", "t1")
        assert sig1 != sig2

    def test_same_inputs_produce_same_signature(self):
        sig1 = sign_request("POST", "/api/x", "hello", "ts")
        sig2 = sign_request("POST", "/api/x", "hello", "ts")
        assert sig1 == sig2

    def test_empty_body(self):
        sig = sign_request("GET", "/api/health", "", "now")
        assert len(sig) == 64
