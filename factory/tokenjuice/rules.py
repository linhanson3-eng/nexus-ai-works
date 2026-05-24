from __future__ import annotations

"""TokenJuice 规则加载 — 3 层覆盖：builtin → user → project。

参考 OpenHuman tokenjuice/rules/loader.rs。
"""


import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

_CAMEL_TO_SNAKE_MAP = {
    "toolNames": "tool_names",
    "argvIncludes": "argv_includes",
    "commandIncludes": "command_includes",
    "skipPatterns": "skip_patterns",
    "keepPatterns": "keep_patterns",
    "stripAnsi": "strip_ansi",
    "dedupeAdjacent": "dedupe",
    "trimEmptyEdges": "trim_empty_edges",
}


def _camel_to_snake(key: str) -> str:
    return _CAMEL_TO_SNAKE_MAP.get(key, key)

BUILTIN_RULES_DIR = Path(__file__).parent / "rules"


class RuleOrigin(str, Enum):
    BUILTIN = "builtin"
    USER = "user"
    PROJECT = "project"


@dataclass
class CompiledRule:
    id: str
    description: str = ""
    tool_names: list[str] | None = None
    argv0: list[str] | None = None
    argv_includes: list[str] | None = None
    command_includes: list[str] | None = None
    skip_patterns: list[re.Pattern] | None = None
    keep_patterns: list[re.Pattern] | None = None
    transforms: dict[str, Any] | None = None
    summarize: dict[str, Any] | None = None
    priority: int = 0
    origin: RuleOrigin = RuleOrigin.BUILTIN

    @classmethod
    def from_json(cls, id: str, data: dict, origin: RuleOrigin = RuleOrigin.BUILTIN) -> "CompiledRule":
        match = data.get("match", data)
        match = {_camel_to_snake(k): v for k, v in match.items()}
        filters = data.get("filters", {})
        filters = {_camel_to_snake(k): v for k, v in filters.items()} if filters else {}
        transforms = data.get("transforms", {})
        transforms = {_camel_to_snake(k): v for k, v in transforms.items()} if transforms else {}
        summarize = data.get("summarize", {})
        skip_raw = filters.get("skip_patterns", [])
        keep_raw = filters.get("keep_patterns", [])

        return cls(
            id=id,
            description=data.get("description", ""),
            tool_names=match.get("tool_names"),
            argv0=match.get("argv0"),
            argv_includes=match.get("argv_includes"),
            command_includes=match.get("command_includes"),
            skip_patterns=[re.compile(p, re.IGNORECASE) for p in skip_raw] if skip_raw else None,
            keep_patterns=[re.compile(p, re.IGNORECASE) for p in keep_raw] if keep_raw else None,
            transforms=transforms if transforms else None,
            summarize=summarize if summarize else None,
            priority=data.get("priority", match.get("priority", 0)),
            origin=origin,
        )


def load_builtin_rules() -> list[CompiledRule]:
    rules: list[CompiledRule] = []
    if not BUILTIN_RULES_DIR.exists():
        return rules

    for f in sorted(BUILTIN_RULES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            rule_id = f.stem
            rules.append(CompiledRule.from_json(rule_id, data, RuleOrigin.BUILTIN))
        except (json.JSONDecodeError, KeyError):
            continue
    return rules


def load_user_rules() -> list[CompiledRule]:
    return _load_rules_from_dir(
        Path.home() / ".config" / "tokenjuice" / "rules", RuleOrigin.USER
    )


def load_project_rules(cwd: Path | None = None) -> list[CompiledRule]:
    return _load_rules_from_dir(
        (cwd or Path.cwd()) / ".tokenjuice" / "rules", RuleOrigin.PROJECT
    )


def load_rules(cwd: Path | None = None) -> list[CompiledRule]:
    """按优先级加载全部规则：builtin → user → project。

    高层同名规则覆盖底层。
    """
    rules_map: dict[str, CompiledRule] = {}
    for rule in load_builtin_rules():
        rules_map[rule.id] = rule
    for rule in load_user_rules():
        rules_map[rule.id] = rule
    for rule in load_project_rules(cwd):
        rules_map[rule.id] = rule

    # 按 priority 降序排列，generic/fallback 在最后
    sorted_rules = sorted(rules_map.values(), key=lambda r: (-r.priority, r.id))
    fallback = sorted_rules.pop() if sorted_rules else None
    if fallback:
        sorted_rules.append(fallback)
    return sorted_rules


def _load_rules_from_dir(directory: Path, origin: RuleOrigin) -> list[CompiledRule]:
    rules: list[CompiledRule] = []
    if not directory.exists():
        return rules
    for f in sorted(directory.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            rule_id = f.stem
            rules.append(CompiledRule.from_json(rule_id, data, origin))
        except (json.JSONDecodeError, KeyError):
            continue
    return rules
