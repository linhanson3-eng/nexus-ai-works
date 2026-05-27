from __future__ import annotations

"""Personal WeChat channel using HTTP long-poll iLink API.

Protocol reverse-engineered from ``@tencent-weixin/openclaw-weixin`` v2.4.2.
Pure Python — no npm / Node.js dependency.

Usage:
    1. Configure in org.yaml channels: [{name: weixin, enabled: true}]
    2. Start gateway → QR code printed to console → scan with WeChat
    3. Token persisted to ~/.factory/weixin/account.json
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import random
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from factory.channel.adapter import ChannelAdapter
from factory.channel.types import ChannelMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"
ILINK_APP_ID = "bot"
WEIXIN_CHANNEL_VERSION = "2.4.2"

ITEM_TEXT = 1
ITEM_IMAGE = 2
ITEM_VOICE = 3
ITEM_FILE = 4
ITEM_VIDEO = 5

MESSAGE_TYPE_USER = 1
MESSAGE_TYPE_BOT = 2
MESSAGE_STATE_FINISH = 2

ERRCODE_SESSION_EXPIRED = -14

WEIXIN_MAX_MESSAGE_LEN = 4000
CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"

MAX_CONSECUTIVE_FAILURES = 3
BACKOFF_DELAY_S = 30
RETRY_DELAY_S = 2
MAX_QR_REFRESH_COUNT = 3
SESSION_PAUSE_DURATION_S = 60 * 60


def _build_client_version(version: str) -> int:
    """Encode semver as 0x00MMNNPP."""
    parts = version.split(".")
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    return ((major & 0xFF) << 16) | ((minor & 0xFF) << 8) | (patch & 0xFF)


ILINK_APP_CLIENT_VERSION = _build_client_version(WEIXIN_CHANNEL_VERSION)
BASE_INFO: dict[str, str] = {"channel_version": WEIXIN_CHANNEL_VERSION}

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class WeixinConfig(BaseModel):
    """Personal WeChat channel configuration."""

    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    base_url: str = ILINK_BASE_URL
    cdn_base_url: str = CDN_BASE_URL
    poll_timeout: int = 35
    state_dir: str = ""


# ---------------------------------------------------------------------------
# WeChat Channel Adapter
# ---------------------------------------------------------------------------


class WeixinChannel(ChannelAdapter):
    """Personal WeChat channel adapter using iLink HTTP long-poll.

    Connects to ilinkai.weixin.qq.com to send/receive personal WeChat messages.
    Authentication via QR code login → persistent bot token.
    """

    def __init__(self, config: WeixinConfig | None = None) -> None:
        cfg_dict = config.model_dump() if config else {}
        super().__init__(name="weixin", config=cfg_dict)
        self.cfg: WeixinConfig = config or WeixinConfig()

        self._client: httpx.AsyncClient | None = None
        self._token: str = self.cfg.token
        self._get_updates_buf: str = ""
        self._context_tokens: dict[str, str] = {}
        self._state_dir: Path | None = None
        self._poll_task: asyncio.Task | None = None
        self._session_pause_until: float = 0.0

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _get_state_dir(self) -> Path:
        if self._state_dir:
            return self._state_dir
        if self.cfg.state_dir:
            d = Path(self.cfg.state_dir).expanduser()
        else:
            d = Path.home() / ".factory" / "weixin"
        d.mkdir(parents=True, exist_ok=True)
        self._state_dir = d
        return d

    def _load_state(self) -> bool:
        state_file = self._get_state_dir() / "account.json"
        if not state_file.exists():
            return False
        try:
            data = json.loads(state_file.read_text())
            self._token = data.get("token", "")
            self._get_updates_buf = data.get("get_updates_buf", "")
            ctx = data.get("context_tokens", {})
            if isinstance(ctx, dict):
                self._context_tokens = {
                    str(k): str(v) for k, v in ctx.items() if str(k).strip()
                }
            return bool(self._token)
        except Exception:
            logger.exception("Failed to load Weixin account state")
            return False

    def _save_state(self) -> None:
        state_file = self._get_state_dir() / "account.json"
        try:
            data = {
                "token": self._token,
                "get_updates_buf": self._get_updates_buf,
                "context_tokens": self._context_tokens,
            }
            state_file.write_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            logger.exception("Failed to save Weixin state")

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _random_wechat_uin() -> str:
        uint32 = int.from_bytes(os.urandom(4), "big")
        return base64.b64encode(str(uint32).encode()).decode()

    def _make_headers(self, *, auth: bool = True) -> dict[str, str]:
        headers: dict[str, str] = {
            "X-WECHAT-UIN": self._random_wechat_uin(),
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "iLink-App-Id": ILINK_APP_ID,
            "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
        }
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _api_post(self, endpoint: str, body: dict | None = None) -> dict:
        assert self._client is not None
        url = f"{self.cfg.base_url}/{endpoint}"
        payload = body or {}
        if "base_info" not in payload:
            payload["base_info"] = BASE_INFO
        resp = await self._client.post(url, json=payload, headers=self._make_headers())
        resp.raise_for_status()
        return resp.json()

    async def _api_get(self, endpoint: str, params: dict | None = None, *, auth: bool = True) -> dict:
        assert self._client is not None
        url = f"{self.cfg.base_url}/{endpoint}"
        resp = await self._client.get(url, params=params, headers=self._make_headers(auth=auth))
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # QR Code Login
    # ------------------------------------------------------------------

    async def _fetch_qr_code(self) -> tuple[str, str]:
        data = await self._api_get("ilink/bot/get_bot_qrcode", params={"bot_type": "3"}, auth=False)
        qrcode_id = data.get("qrcode", "")
        qrcode_img = data.get("qrcode_img_content", "")
        if not qrcode_id:
            raise RuntimeError(f"Failed to get QR code: {data}")
        return qrcode_id, (qrcode_img or qrcode_id)

    def _print_qr(self, url: str) -> None:
        try:
            import qrcode as qr_lib

            qr = qr_lib.QRCode(border=1)
            qr.add_data(url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
        except ImportError:
            print(f"\n>>> WeChat login URL: {url}\n")

    async def _qr_login(self) -> bool:
        """QR code login flow. Returns True on success."""
        try:
            refresh_count = 0
            qrcode_id, scan_url = await self._fetch_qr_code()
            self._print_qr(scan_url)

            while self._running:
                try:
                    status_data = await self._api_get(
                        "ilink/bot/get_qrcode_status",
                        params={"qrcode": qrcode_id},
                        auth=False,
                    )
                except Exception:
                    await asyncio.sleep(1)
                    continue

                status = status_data.get("status", "")
                if status == "confirmed":
                    token = status_data.get("bot_token", "")
                    if token:
                        self._token = token
                        self._save_state()
                        logger.info("WeChat login successful")
                        return True
                    return False
                elif status == "expired":
                    refresh_count += 1
                    if refresh_count > MAX_QR_REFRESH_COUNT:
                        logger.warning("QR code expired too many times, giving up")
                        return False
                    qrcode_id, scan_url = await self._fetch_qr_code()
                    self._print_qr(scan_url)
                await asyncio.sleep(1)

        except Exception:
            logger.exception("QR login failed")
        return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.cfg.poll_timeout + 10, connect=30),
            follow_redirects=True,
        )

        if self.cfg.token:
            self._token = self.cfg.token
        elif not self._load_state():
            logger.info("No saved token, starting QR login...")
            self._running = True  # re-set for _qr_login
            if not await self._qr_login():
                logger.error("WeChat login failed")
                self._running = False
                return

        logger.info("WeixinChannel started — polling for messages")
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
            self._client = None
        self._save_state()
        logger.info("WeixinChannel stopped")

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        consecutive_failures = 0
        while self._running:
            try:
                await self._poll_once()
                consecutive_failures = 0
            except asyncio.CancelledError:
                break
            except httpx.TimeoutException:
                continue
            except Exception:
                if not self._running:
                    break
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    consecutive_failures = 0
                    await asyncio.sleep(BACKOFF_DELAY_S)
                else:
                    await asyncio.sleep(RETRY_DELAY_S)

    async def _poll_once(self) -> None:
        remaining = max(0.0, self._session_pause_until - time.time())
        if remaining > 0:
            await asyncio.sleep(remaining)
            self._session_pause_until = 0.0
            return

        assert self._client is not None
        self._client.timeout = httpx.Timeout(self.cfg.poll_timeout + 10, connect=30)

        body = {"get_updates_buf": self._get_updates_buf, "base_info": BASE_INFO}
        data = await self._api_post("ilink/bot/getupdates", body)

        errcode = data.get("errcode", 0)
        if errcode:
            if errcode == ERRCODE_SESSION_EXPIRED:
                self._session_pause_until = time.time() + SESSION_PAUSE_DURATION_S
                logger.warning("WeChat session expired, pausing 60 min")
            return

        new_buf = data.get("get_updates_buf", "")
        if new_buf:
            self._get_updates_buf = new_buf
            self._save_state()

        msgs: list[dict] = data.get("msgs", []) or []
        for msg in msgs:
            try:
                await self._process_message(msg)
            except Exception:
                logger.exception("Error processing WeChat message")

    # ------------------------------------------------------------------
    # Inbound message processing
    # ------------------------------------------------------------------

    async def _process_message(self, msg: dict) -> None:
        if msg.get("message_type") == MESSAGE_TYPE_BOT:
            return

        from_user = msg.get("from_user_id", "") or ""
        if not from_user:
            return

        if self.cfg.allow_from and from_user not in self.cfg.allow_from:
            return

        ctx_token = msg.get("context_token", "")
        if ctx_token:
            self._context_tokens[from_user] = ctx_token
            self._save_state()

        item_list: list[dict] = msg.get("item_list") or []
        parts: list[str] = []
        for item in item_list:
            t = item.get("type", 0)
            if t == ITEM_TEXT:
                txt = (item.get("text_item") or {}).get("text", "")
                if txt:
                    parts.append(txt)
            elif t == ITEM_IMAGE:
                parts.append("[图片]")
            elif t == ITEM_VOICE:
                speech = (item.get("voice_item") or {}).get("text", "")
                parts.append(speech or "[语音]")
            elif t == ITEM_VIDEO:
                parts.append("[视频]")
            elif t == ITEM_FILE:
                fname = (item.get("file_item") or {}).get("file_name", "文件")
                parts.append(f"[文件: {fname}]")

        content = "".join(parts)
        if not content:
            return

        logger.info("WeChat inbound: from=%s content=%s", from_user[:20], content[:100])

        channel_msg = ChannelMessage(
            sender=from_user,
            content=content,
            channel_name="weixin",
            metadata={"message_id": str(msg.get("message_id", int(time.time())))},
        )
        await self.on_receive(channel_msg)

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    async def send(self, message: ChannelMessage) -> bool:
        """Send a ChannelMessage via WeChat iLink. Returns True on success."""
        if not self._client or not self._token:
            return False

        # Route to the sender (as chat_id)
        chat_id = message.metadata.get("chat_id", message.sender)
        if not chat_id:
            logger.warning("WeChat send: no chat_id in metadata or sender")
            return False

        ctx_token = self._context_tokens.get(chat_id, "")
        if not ctx_token:
            logger.warning("WeChat send: no context_token for %s, cannot send", chat_id)
            return False

        content = message.content.strip()
        if not content:
            return True

        chunks = self._split_text(content, WEIXIN_MAX_MESSAGE_LEN)
        for chunk in chunks:
            try:
                await self._send_text(chat_id, chunk, ctx_token)
            except Exception:
                logger.exception("WeChat send failed for %s", chat_id)
                return False

        return True

    async def _send_text(self, to_user: str, text: str, ctx_token: str) -> None:
        client_id = f"aifactory-{uuid.uuid4().hex[:12]}"

        item_list: list[dict] = [{"type": ITEM_TEXT, "text_item": {"text": text}}]
        weixin_msg: dict[str, Any] = {
            "from_user_id": "",
            "to_user_id": to_user,
            "client_id": client_id,
            "message_type": MESSAGE_TYPE_BOT,
            "message_state": MESSAGE_STATE_FINISH,
            "item_list": item_list,
        }
        if ctx_token:
            weixin_msg["context_token"] = ctx_token

        data = await self._api_post(
            "ilink/bot/sendmessage",
            {"msg": weixin_msg, "base_info": BASE_INFO},
        )
        errcode = data.get("errcode", 0)
        if errcode:
            raise RuntimeError(f"WeChat send error (code {errcode}): {data.get('errmsg', '')}")

    @staticmethod
    def _split_text(text: str, max_len: int) -> list[str]:
        """Split long text into max_len chunks."""
        if len(text) <= max_len:
            return [text]
        chunks: list[str] = []
        while len(text) > max_len:
            split_at = text.rfind("\n", 0, max_len)
            if split_at == -1 or split_at < max_len // 2:
                split_at = max_len
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        if text:
            chunks.append(text)
        return chunks


# ---------------------------------------------------------------------------
# AES-128-ECB crypto (for media — matches pic-decrypt.ts)
# ---------------------------------------------------------------------------


def _parse_aes_key(aes_key_b64: str) -> bytes:
    """Parse base64 AES key: raw 16 bytes or hex string → raw bytes."""
    decoded = base64.b64decode(aes_key_b64)
    if len(decoded) == 16:
        return decoded
    if len(decoded) == 32 and re.fullmatch(rb"[0-9a-fA-F]{32}", decoded):
        return bytes.fromhex(decoded.decode("ascii"))
    raise ValueError(f"aes_key must decode to 16 raw bytes or 32-char hex, got {len(decoded)}")


def _encrypt_aes_ecb(data: bytes, aes_key_b64: str) -> bytes:
    try:
        key = _parse_aes_key(aes_key_b64)
    except Exception:
        return data
    pad_len = 16 - len(data) % 16
    padded = data + bytes([pad_len] * pad_len)
    try:
        from Crypto.Cipher import AES
        return AES.new(key, AES.MODE_ECB).encrypt(padded)
    except ImportError:
        pass
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        encryptor = cipher.encryptor()
        return encryptor.update(padded) + encryptor.finalize()
    except ImportError:
        return data


def _decrypt_aes_ecb(data: bytes, aes_key_b64: str) -> bytes:
    try:
        key = _parse_aes_key(aes_key_b64)
    except Exception:
        return data
    decrypted: bytes | None = None
    try:
        from Crypto.Cipher import AES
        decrypted = AES.new(key, AES.MODE_ECB).decrypt(data)
    except ImportError:
        pass
    if decrypted is None:
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            cipher = Cipher(algorithms.AES(key), modes.ECB())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(data) + decryptor.finalize()
        except ImportError:
            return data
    return _pkcs7_unpad_safe(decrypted)


def _pkcs7_unpad_safe(data: bytes, block_size: int = 16) -> bytes:
    if not data or len(data) % block_size != 0:
        return data
    pad_len = data[-1]
    if pad_len < 1 or pad_len > block_size:
        return data
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        return data
    return data[:-pad_len]
