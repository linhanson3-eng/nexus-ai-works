"""TokenJuice 压缩管线测试。"""


from factory.tokenjuice.reduce import compact_tool_output, reduce_execution_with_rules
from factory.tokenjuice.rules import load_builtin_rules
from factory.tokenjuice.types import ReduceOptions, ToolExecutionInput


class TestReduceGitStatus:
    def test_git_status_compacted(self):
        rules = load_builtin_rules()
        input = ToolExecutionInput(
            tool_name="exec",
            command="git status",
            stdout="On branch main\n\tmodified:   src/lib.rs\n\tnew file:   src/foo.py\n",
        )
        result = reduce_execution_with_rules(input, rules, ReduceOptions(max_inline_chars=1200))
        assert "lib.rs" in result.inline_text

    def test_git_status_empty_output(self):
        rules = load_builtin_rules()
        input = ToolExecutionInput(
            tool_name="exec",
            command="git status",
            stdout="nothing to commit, working tree clean",
        )
        result = reduce_execution_with_rules(input, rules, ReduceOptions(max_inline_chars=1200))
        assert result.inline_text


class TestCompactToolOutput:
    def test_small_output_passthrough(self):
        result = compact_tool_output("read_file", stdout="small")
        assert result.passthrough

    def test_large_output_not_passthrough(self):
        large = "x" * 600
        result = compact_tool_output("exec", stdout=large, command="npm install")
        assert len(result.inline_text) <= 1200


class TestReduceGeneric:
    def test_unknown_tool_gets_fallback(self):
        rules = load_builtin_rules()
        input = ToolExecutionInput(
            tool_name="unknown_tool_xyz",
            command="unknown_tool_xyz --verbose",
            stdout="some output\n" * 10,
        )
        result = reduce_execution_with_rules(input, rules, ReduceOptions(max_inline_chars=1200))
        assert result.inline_text

    def test_output_clamped_to_max_chars(self):
        rules = load_builtin_rules()
        long_output = "line\n" * 100
        input = ToolExecutionInput(
            tool_name="exec",
            command="npm test",
            stdout=long_output,
        )
        result = reduce_execution_with_rules(input, rules, ReduceOptions(max_inline_chars=500))
        assert len(result.inline_text) <= 500 + 30
