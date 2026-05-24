from __future__ import annotations

"""Tests for API key encryption/decryption."""
import secrets
import pytest
from factory.security.crypto import encrypt, decrypt


class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        plain = "sk-ant-api03-this-is-a-test-key-for-encryption"
        encrypted = encrypt(plain)
        assert encrypted
        assert encrypted != plain
        assert "$e$" not in encrypted  # prefix added by SettingsStore

        decrypted = decrypt(encrypted)
        assert decrypted == plain

    def test_empty_string_passthrough(self):
        assert encrypt("") == ""
        assert decrypt("") == ""

    def test_encryption_is_non_deterministic(self):
        """Same plaintext should produce different ciphertexts (random nonce)."""
        plain = "sk-test-key-12345"
        a = encrypt(plain)
        b = encrypt(plain)
        assert a != b
        assert decrypt(a) == decrypt(b) == plain

    def test_decrypt_invalid_raises(self):
        with pytest.raises(Exception):
            decrypt("!!!!not-valid-base64!!!!")

    def test_long_key(self):
        plain = secrets.token_urlsafe(200)
        encrypted = encrypt(plain)
        assert decrypt(encrypted) == plain

    def test_unicode_key(self):
        plain = "key-with-unicode-chars-测试密钥-🎯"
        encrypted = encrypt(plain)
        assert decrypt(encrypted) == plain
