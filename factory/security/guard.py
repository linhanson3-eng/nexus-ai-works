"""Security guard — shell whitelist, path traversal prevention, secret detection.

Enforces the platform's security model: dead rules > LLM judgment.
All agent tool calls pass through these checks before execution.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

# ── Shell command safety ──────────────────────────────────────────

FORBIDDEN_COMMANDS: tuple[str, ...] = (
    "rm -rf /", "rm -rf ~", "rm -rf .",
    "sudo ", "chmod 777", "mkfs.",
    ":(){ :|:& };:",  # fork bomb
    ">/dev/sda", "dd if=",
    "curl.*|.*sh", "wget.*|.*sh",
    "chown -R /", "mv / /dev/null",
)

FORBIDDEN_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p) for p in [
        r"rm\s+-rf\s+/",
        r"sudo\s+rm",
        r"mkfs\.\w+",
        r"dd\s+if=.*of=/dev",
        r">\s*/dev/sd[a-z]",
        r"chmod\s+777\s+/",
        r"curl\s+.*\|\s*(ba)?sh",
        r"wget\s+.*\|\s*(ba)?sh",
        r"eval\s+",
    ]
)

ALLOWED_COMMANDS: tuple[str, ...] = (
    "ls", "cat", "head", "tail", "grep", "find",
    "git", "python", "python3", "node", "npm", "npx",
    "echo", "mkdir", "touch", "cp", "mv", "rm",
    "curl", "wget", "pip", "pip3", "poetry",
)


@dataclass(frozen=True)
class ShellCheckResult:
    allowed: bool
    command: str = ""
    reason: str = ""


def check_shell_command(command: str) -> ShellCheckResult:
    """Validate a shell command against the safety whitelist.

    Returns ShellCheckResult with allowed=False if the command
    contains dangerous patterns or falls outside the whitelist.
    """
    cmd = command.strip()
    if not cmd:
        return ShellCheckResult(allowed=False, command=cmd, reason="empty command")

    # Check forbidden patterns first
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(cmd):
            return ShellCheckResult(
                allowed=False, command=cmd,
                reason=f"matches forbidden pattern: {pattern.pattern}",
            )

    # Extract base command
    base = cmd.split()[0] if cmd.split() else ""
    base_name = os.path.basename(base)

    if base_name in ALLOWED_COMMANDS:
        return ShellCheckResult(allowed=True, command=cmd)

    return ShellCheckResult(
        allowed=False, command=cmd,
        reason=f"'{base_name}' not in allowed commands whitelist",
    )


# ── Path traversal prevention ─────────────────────────────────────

FORBIDDEN_PATHS: tuple[str, ...] = (
    "/etc/passwd", "/etc/shadow", "/etc/ssh",
    "~/.ssh", "~/.aws", "~/.claude",
    "/proc", "/sys", "/dev",
)


def sanitize_path(path: str, workspace_root: str) -> str:
    """Sanitize a file path, preventing traversal outside the workspace.

    Relative paths are resolved against the workspace root.
    Raises ValueError if the resolved path escapes the workspace.
    """
    root = Path(workspace_root).expanduser().resolve()

    p = Path(path).expanduser()
    if not p.is_absolute():
        p = root / p
    resolved = p.resolve()

    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: '{path}' resolves outside workspace '{root}'"
        )

    # Check against forbidden paths (check both original and resolved)
    resolved_str = str(resolved)
    original_str = str(p.expanduser())
    for forbidden in FORBIDDEN_PATHS:
        expanded = os.path.expanduser(forbidden)
        if resolved_str.startswith(expanded) or original_str.startswith(expanded):
            raise ValueError(f"Access to forbidden path: {forbidden}")

    return str(resolved)


# ── Secret detection ──────────────────────────────────────────────

SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("AWS Access Key", r"AKIA[0-9A-Z]{16}"),
    ("AWS Secret Key", r"(?i)aws.*secret.*['\"]?[0-9a-zA-Z\/+]{40}"),
    ("GitHub Token", r"gh[pous]_[0-9a-zA-Z]{20,}"),
    ("GitHub PAT", r"github_pat_[0-9a-zA-Z]{22,}"),
    ("OpenAI API Key", r"sk-[0-9a-zA-Z]{32,}"),
    ("Anthropic API Key", r"sk-ant-[0-9a-zA-Z-]{32,}"),
    ("Generic API Key", r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?\w{20,}"),
    ("Private Key", r"-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----"),
    ("JWT Token", r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
)


@dataclass(frozen=True)
class SecretDetectResult:
    found: bool
    secrets: tuple[tuple[str, str], ...] = ()  # (type, matched_text)
    count: int = 0


def detect_secrets(content: str) -> SecretDetectResult:
    """Scan content for hardcoded secrets.

    Returns SecretDetectResult with found=True and details
    if any secret patterns are detected.
    """
    found: list[tuple[str, str]] = []
    for secret_type, pattern in SECRET_PATTERNS:
        for match in re.finditer(pattern, content):
            matched = match.group(0)
            found.append((secret_type, matched[:20] + "..."))

    return SecretDetectResult(
        found=len(found) > 0,
        secrets=tuple(found),
        count=len(found),
    )


# ── Input sanitization ────────────────────────────────────────────


def sanitize_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
