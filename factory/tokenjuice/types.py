from __future__ import annotations

"""TokenJuice 数据类型。

参考 OpenHuman tokenjuice/types.rs。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolExecutionInput:
    tool_name: str = ""
    argv: list[str] | None = None
    command: str = ""
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int = 0

    @property
    def effective_argv(self) -> list[str]:
        if self.argv:
            return self.argv
        if self.command:
            return self.command.split()
        return []

    @property
    def output(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[stderr]\n{self.stderr}")
        return "\n".join(parts)


@dataclass
class CompactResult:
    inline_text: str = ""
    preview_text: str = ""
    facts: dict[str, Any] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)
    rule_id: str = ""
    passthrough: bool = False

    @property
    def compression_ratio(self) -> float:
        return self.stats.get("compression_ratio", 1.0)


@dataclass
class ReduceOptions:
    max_inline_chars: int = 1200
    max_preview_chars: int = 4000
    strategy: str = "compact"
