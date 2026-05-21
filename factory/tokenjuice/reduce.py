"""TokenJuice 5 步压缩管线。

参考 OpenHuman tokenjuice/reduce.rs (928 行 Rust)。
将冗长的工具输出压缩为紧凑的 inline text。
"""

from __future__ import annotations

import re
from pathlib import Path

from factory.tokenjuice.classify import classify as classify_input
from factory.tokenjuice.rules import CompiledRule, load_rules
from factory.tokenjuice.types import CompactResult, ReduceOptions, ToolExecutionInput


def reduce_execution_with_rules(
    input: ToolExecutionInput,
    rules: list[CompiledRule],
    options: ReduceOptions | None = None,
) -> CompactResult:
    opts = options or ReduceOptions()
    result = CompactResult()

    # Step 1 + 2: Classify
    matched = classify_input(input, rules)
    if matched is None:
        result.inline_text = _clamp(input.output, opts.max_inline_chars)
        result.passthrough = True
        return result

    result.rule_id = matched.id

    # Step 3: Apply filters (skip/keep)
    text = _apply_filters(input.output, matched)

    # Step 4: Apply transforms
    transforms = matched.transforms or {}
    if transforms.get("strip_ansi", False):
        text = _strip_ansi(text)
    if transforms.get("trim", True):
        text = text.strip()
    if transforms.get("dedupe", False):
        text = _dedupe_lines(text)

    # Special post-processors
    if "git-status" in matched.id:
        text = _post_git_status(text)
    elif "gh" in matched.id or matched.id == "cloud/gh":
        text = _post_gh(text)

    # Step 5: Format
    summarize = matched.summarize or {}
    head = summarize.get("head", 20)
    tail = summarize.get("tail", 5)
    lines = text.split("\n")
    if len(lines) > head + tail:
        text = "\n".join(lines[:head]) + f"\n... ({len(lines) - head - tail} more lines)\n" + "\n".join(lines[-tail:])

    result.inline_text = _clamp(text, opts.max_inline_chars)
    result.preview_text = _clamp(text, opts.max_preview_chars)
    result.stats["original_chars"] = len(input.output)
    result.stats["compressed_chars"] = len(result.inline_text)
    result.stats["compression_ratio"] = (
        len(result.inline_text) / max(1, len(input.output))
    )
    return result


def compact_tool_output(
    tool_name: str,
    stdout: str | None = None,
    stderr: str | None = None,
    command: str = "",
    rules: list[CompiledRule] | None = None,
) -> CompactResult:
    """每次工具调用后调用此函数压缩输出。"""
    if rules is None:
        rules = load_rules()

    input = ToolExecutionInput(
        tool_name=tool_name,
        command=command,
        stdout=stdout,
        stderr=stderr,
    )

    # 小输出直接透传
    if len(input.output) < 512:
        return CompactResult(
            inline_text=input.output,
            passthrough=True,
            stats={"original_chars": len(input.output), "compressed_chars": len(input.output)},
        )

    result = reduce_execution_with_rules(input, rules)
    # 如果压缩效果不好，直接透传
    if result.compression_ratio > 0.95:
        result.inline_text = _clamp(input.output, 1200)
        result.passthrough = True
    return result


def _apply_filters(text: str, rule: CompiledRule) -> str:
    """应用 skip/keep 过滤器。"""
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        if rule.skip_patterns:
            if any(p.search(line) for p in rule.skip_patterns):
                continue
        if rule.keep_patterns:
            if not any(p.search(line) for p in rule.keep_patterns):
                continue
        result.append(line)
    return "\n".join(result)


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def _dedupe_lines(text: str) -> str:
    seen: set[str] = set()
    result: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            result.append(line)
        elif not stripped:
            result.append(line)
    return "\n".join(result)


def _post_git_status(text: str) -> str:
    """将 git status 输出简化为 modified | added | deleted 列表。"""
    lines: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("M ") or line.startswith(" M"):
            lines.append(f"M: {line[2:].strip()}")
        elif line.startswith("A ") or line.startswith("??"):
            lines.append(f"A: {line[2:].strip()}")
        elif line.startswith("D ") or line.startswith(" D"):
            lines.append(f"D: {line[2:].strip()}")
    return "\n".join(lines) if lines else text


def _post_gh(text: str) -> str:
    """压缩 gh CLI 输出。"""
    lines = [l for l in text.split("\n") if l.strip() and "https" not in l]
    return "\n".join(lines[:10])


def _clamp(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + f"\n... (truncated, {len(text)} total chars)"
