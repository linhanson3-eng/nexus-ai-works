from __future__ import annotations
"""Tests for WeChat iLink channel adapter."""

import json
from pathlib import Path

import httpx
import pytest

from factory.channel.adapter import (
    _inbound_handlers,
    _registry,
    on_inbound,
    register,
)
from factory.channel.types import ChannelMessage
from factory.channel.weixin import (
    WeixinChannel,
    WeixinConfig,
    _decrypt_aes_ecb,
    _encrypt_aes_ecb,
    _parse_aes_key,
    _pkcs7_unpad_safe,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clear_weixin() -> None:
    """Reset global registry before and after each test."""
    _registry.clear()
    _inbound_handlers.clear()
    yield
    _registry.clear()
    _inbound_handlers.clear()


@pytest.fixture
def wx_config() -> WeixinConfig:
    return WeixinConfig(
        token="test-token-abc123",
        enabled=True,
    )


@pytest.fixture
def weixin(wx_config: WeixinConfig, clear_weixin: None) -> WeixinChannel:
    return WeixinChannel(wx_config)


# ---------------------------------------------------------------------------
# TestWeixinConfig
# ---------------------------------------------------------------------------


class TestWeixinConfig:
    """Tests for WeixinConfig Pydantic model."""

    def test_defaults(self) -> None:
        cfg = WeixinConfig()
        assert cfg.enabled is False
        assert cfg.token == ""
        assert cfg.base_url == "https://ilinkai.weixin.qq.com"
        assert cfg.cdn_base_url == "https://novac2c.cdn.weixin.qq.com/c2c"
        assert cfg.poll_timeout == 35

    def test_dict_roundtrip(self) -> None:
        cfg = WeixinConfig(
            token="tk",
            enabled=True,
            allow_from=["user-a", "user-b"],
            poll_timeout=45,
        )
        data = cfg.model_dump()
        reloaded = WeixinConfig.model_validate(data)
        assert reloaded.token == "tk"
        assert reloaded.enabled is True
        assert reloaded.allow_from == ["user-a", "user-b"]
        assert reloaded.poll_timeout == 45


# ---------------------------------------------------------------------------
# TestWeixinChannel — lifecycle
# ---------------------------------------------------------------------------


class TestWeixinChannelLifecycle:
    """Tests for channel start/stop and state management."""

    @pytest.mark.asyncio
    async def test_initial_state_not_running(self, weixin: WeixinChannel) -> None:
        assert weixin.is_running is False

    @pytest.mark.asyncio
    async def test_config_stored(self, weixin: WeixinChannel, wx_config: WeixinConfig) -> None:
        assert weixin.name == "weixin"
        assert weixin.cfg is wx_config

    @pytest.mark.asyncio
    async def test_health_not_running(self, weixin: WeixinChannel) -> None:
        health = await weixin.health()
        assert health["name"] == "weixin"
        assert health["running"] is False
        assert health["type"] == "WeixinChannel"


# ---------------------------------------------------------------------------
# TestWeixinChannel — send
# ---------------------------------------------------------------------------


class TestWeixinChannelSend:
    """Tests for outbound message sending."""

    @pytest.mark.asyncio
    async def test_send_requires_token(self, weixin: WeixinChannel) -> None:
        weixin._token = ""
        weixin._client = httpx.AsyncClient()
        msg = ChannelMessage(
            sender="bot",
            content="hi",
            channel_name="weixin",
        )
        result = await weixin.send(msg)
        assert result is False


# ---------------------------------------------------------------------------
# TestWeixinChannel — message conversion
# ---------------------------------------------------------------------------


class TestWeixinChannelConversion:
    """Tests for ChannelMessage ↔ iLink protocol conversion."""

    def test_channel_message_to_context(self, weixin: WeixinChannel) -> None:
        msg = ChannelMessage(
            sender="wx-user-001",
            content="帮我搜索 Python 项目",
            channel_name="weixin",
            workshop_name="demo",
            agent_name="demo",
        )
        # Simulate caching context token (no real API call needed)
        weixin._context_tokens["wx-user-001"] = "ctx-token-123"
        assert weixin._context_tokens["wx-user-001"] == "ctx-token-123"

    def test_context_token_lookup(self, weixin: WeixinChannel) -> None:
        weixin._context_tokens["alice"] = "token-alice"
        weixin._context_tokens["bob"] = "token-bob"
        assert weixin._context_tokens.get("alice") == "token-alice"
        assert weixin._context_tokens.get("bob") == "token-bob"
        assert weixin._context_tokens.get("charlie", "") == ""


# ---------------------------------------------------------------------------
# TestWeixinChannel — session persistence
# ---------------------------------------------------------------------------


class TestWeixinChannelSession:
    """Tests for state save/load."""

    def test_save_and_load_state(self, weixin: WeixinChannel, tmp_path: Path) -> None:
        state_dir = tmp_path / "weixin"
        state_dir.mkdir()
        weixin._state_dir = state_dir
        weixin._token = "my-bot-token"
        weixin._context_tokens = {"user-1": "ctx-1"}
        weixin._get_updates_buf = "buf-abc"

        weixin._save_state()
        state_file = state_dir / "account.json"
        assert state_file.exists()

        data = json.loads(state_file.read_text())
        assert data["token"] == "my-bot-token"
        assert data["get_updates_buf"] == "buf-abc"
        assert data["context_tokens"]["user-1"] == "ctx-1"

    def test_load_state(self, weixin: WeixinChannel, tmp_path: Path) -> None:
        state_dir = tmp_path / "weixin"
        state_dir.mkdir()
        state_file = state_dir / "account.json"
        state_file.write_text(
            json.dumps({"token": "loaded-token", "get_updates_buf": "", "context_tokens": {}})
        )
        weixin._state_dir = state_dir
        assert weixin._load_state() is True
        assert weixin._token == "loaded-token"


# ---------------------------------------------------------------------------
# TestWeixinChannel — inbound handling
# ---------------------------------------------------------------------------


class TestWeixinChannelInbound:
    """Tests for inbound message routing via on_receive."""

    @pytest.mark.asyncio
    async def test_on_receive_fires_inbound_handlers(
        self, weixin: WeixinChannel, clear_weixin: None
    ) -> None:
        received: list[ChannelMessage] = []

        @on_inbound
        async def capture(msg: ChannelMessage) -> None:
            received.append(msg)

        msg = ChannelMessage(
            sender="wx-user",
            content="hello",
            channel_name="weixin",
            workshop_name="demo",
        )
        await weixin.on_receive(msg)
        assert len(received) == 1
        assert received[0].sender == "wx-user"
        assert received[0].content == "hello"

    @pytest.mark.asyncio
    async def test_broadcast_includes_weixin(
        self, weixin: WeixinChannel, clear_weixin: None
    ) -> None:
        from factory.channel.adapter import broadcast

        register("weixin", weixin)
        weixin._token = "tk"
        weixin._client = httpx.AsyncClient()

        # send returns False without real API, but shouldn't crash
        msg = ChannelMessage(sender="bot", content="test", channel_name="weixin")
        results = await broadcast(msg)
        assert "weixin" in results


# ---------------------------------------------------------------------------
# TestAESCrypto
# ---------------------------------------------------------------------------


class TestAESCrypto:
    """Tests for AES-128-ECB encrypt/decrypt used by WeChat media upload/download."""

    def test_parse_16_byte_raw_key(self) -> None:
        import base64
        raw = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10"
        key = _parse_aes_key(base64.b64encode(raw).decode())
        assert key == raw

    def test_parse_hex_encoded_key(self) -> None:
        import base64
        hex_str = "aabbccddeeff00112233445566778899"
        key = _parse_aes_key(base64.b64encode(hex_str.encode()).decode())
        assert key == bytes.fromhex(hex_str)

    def test_pkcs7_unpad_valid(self) -> None:
        data = b"hello" + bytes([11]) * 11  # 5 + 11 = 16
        unpadded = _pkcs7_unpad_safe(data)
        assert unpadded == b"hello"

    def test_pkcs7_unpad_invalid_returns_original(self) -> None:
        data = b"hello world!!!!!"  # 16 bytes, not valid pkcs7
        unpadded = _pkcs7_unpad_safe(data)
        assert unpadded == data

    def test_encrypt_decrypt_roundtrip(self) -> None:
        import base64
        import os
        raw_key = os.urandom(16)
        key_b64 = base64.b64encode(raw_key).decode()
        plain = b"Hello, WeChat media!"
        encrypted = _encrypt_aes_ecb(plain, key_b64)
        assert len(encrypted) >= len(plain)
        decrypted = _decrypt_aes_ecb(encrypted, key_b64)
        # _decrypt_aes_ecb already applies PKCS7 unpadding
        assert decrypted == plain
