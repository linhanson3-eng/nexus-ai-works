"""TokenJuice — 工具输出压缩引擎。

从 OpenHuman (Rust) 移植到 Python。5 步压缩管线。
"""

from factory.tokenjuice.reduce import compact_tool_output, reduce_execution_with_rules
from factory.tokenjuice.rules import load_rules, load_builtin_rules
from factory.tokenjuice.types import CompactResult, ToolExecutionInput, ReduceOptions

__all__ = [
    "compact_tool_output",
    "reduce_execution_with_rules",
    "load_rules",
    "load_builtin_rules",
    "CompactResult",
    "ToolExecutionInput",
    "ReduceOptions",
]
