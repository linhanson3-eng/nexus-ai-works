"""TokenJuice 规则匹配分类。

参考 OpenHuman tokenjuice/classify.rs。
"""

from factory.tokenjuice.rules import CompiledRule
from factory.tokenjuice.types import ToolExecutionInput


def classify(input: ToolExecutionInput, rules: list[CompiledRule]) -> CompiledRule | None:
    """为工具输出匹配最佳规则。"""
    best_score = 0.0
    best_rule: CompiledRule | None = None

    for rule in rules:
        score = _score_rule(input, rule)
        if score > best_score:
            best_score = score
            best_rule = rule

    if best_rule is None and rules:
        # 使用最后一个规则作为 fallback（通常是 generic/fallback）
        best_rule = rules[-1]

    return best_rule


def _score_rule(input: ToolExecutionInput, rule: CompiledRule) -> float:
    score = rule.priority * 1000.0

    argv = input.effective_argv
    argv0 = argv[0] if argv else ""
    command = input.command or " ".join(argv)

    # tool_names 匹配（权重最高）
    if rule.tool_names and input.tool_name:
        for tn in rule.tool_names:
            if tn.lower() == input.tool_name.lower():
                score += 200.0
                break

    # argv0 精确匹配
    if rule.argv0 and argv0:
        for a0 in rule.argv0:
            if a0.lower() == argv0.lower():
                score += 100.0
                break

    # argv_includes 子组匹配（每组内 AND，组间 OR）
    if rule.argv_includes:
        for group in rule.argv_includes:
            if isinstance(group, str):
                group = [group]
            if any(
                all(term.lower() in arg.lower() for term in group)
                for arg in argv
            ):
                score += 40.0

    # command_includes 命令子串匹配
    if rule.command_includes:
        cmd_lower = command.lower()
        for ci in rule.command_includes:
            if ci.lower() in cmd_lower:
                score += 25.0

    # tool_name 子串匹配（更松）
    if rule.tool_names and input.tool_name:
        for tn in rule.tool_names:
            if tn.lower() in input.tool_name.lower():
                score += 10.0

    return score
