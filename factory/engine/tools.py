"""Tool mapping and security filtering for Nexus Agent Engine.

Maps Nexus symbolic tool names to claw-code-agent tool names,
and filters the tool registry based on AgentSpec.permissions and tools list.
"""

from __future__ import annotations

from typing import Any

# ── Symbolic name → claw-code-agent tool name ──────────────────

TOOL_NAME_MAP: dict[str, str] = {
    # Filesystem
    "read_file": "read_file",
    "write_file": "write_file",
    "edit_file": "edit_file",
    "grep": "grep_search",
    "glob": "glob_search",
    "list_dir": "list_dir",
    "notebook_edit": "notebook_edit",
    # Shell
    "bash": "bash",
    # Search / Web
    "web_search": "web_search",
    "web_fetch": "web_fetch",
    "deep_search": "deep_search",
    "search_status": "search_status",
    "search_list_providers": "search_list_providers",
    "search_activate_provider": "search_activate_provider",
    # Agent delegation
    "agent_spawn": "Agent",
    "delegate_agent": "delegate_agent",
    # Skills
    "skill": "Skill",
    # Interactive
    "ask_user": "ask_user_question",
    # MCP
    "mcp_list_tools": "mcp_list_tools",
    "mcp_call_tool": "mcp_call_tool",
    "mcp_list_resources": "mcp_list_resources",
    "mcp_read_resource": "mcp_read_resource",
    # Task management
    "task_list": "task_list",
    "task_create": "task_create",
    "task_update": "task_update",
    "task_start": "task_start",
    "task_complete": "task_complete",
    # Plan
    "plan_get": "plan_get",
    "update_plan": "update_plan",
    "plan_clear": "plan_clear",
    "enter_plan_mode": "EnterPlanMode",
    "exit_plan_mode": "ExitPlanMode",
    # Config
    "config_get": "config_get",
    "config_set": "config_set",
    "config_list": "config_list",
    # Worktree
    "worktree_enter": "worktree_enter",
    "worktree_exit": "worktree_exit",
    "worktree_status": "worktree_status",
    # Remote / Account
    "remote_status": "remote_status",
    "account_status": "account_status",
    # Misc
    "sleep": "sleep",
    "tool_search": "tool_search",
}

# ── Tool categories (Agent-Graph 2.0 inspired classification) ──

TOOL_CATEGORIES: dict[str, str] = {
    "read_file": "query",
    "write_file": "design",
    "edit_file": "design",
    "grep_search": "query",
    "glob_search": "query",
    "list_dir": "query",
    "notebook_edit": "design",
    "bash": "design",
    "web_search": "query",
    "web_fetch": "query",
    "search_status": "query",
    "search_list_providers": "query",
    "search_activate_provider": "design",
    "Agent": "collaboration",
    "delegate_agent": "collaboration",
    "Skill": "collaboration",
    "ask_user_question": "collaboration",
    "mcp_list_tools": "query",
    "mcp_call_tool": "collaboration",
    "mcp_list_resources": "query",
    "mcp_read_resource": "query",
    "task_list": "query",
    "task_create": "design",
    "task_update": "design",
    "task_start": "design",
    "task_complete": "design",
    "plan_get": "query",
    "update_plan": "design",
    "plan_clear": "design",
    "EnterPlanMode": "design",
    "ExitPlanMode": "design",
    "config_get": "query",
    "config_set": "design",
    "config_list": "query",
    "worktree_enter": "design",
    "worktree_exit": "design",
    "worktree_status": "query",
    "remote_status": "query",
    "account_status": "query",
    "sleep": "collaboration",
    "tool_search": "query",
}

# ── Tool names blocked by permission settings ───────────────────

SHELL_TOOLS: frozenset[str] = frozenset({"bash"})
FILE_WRITE_TOOLS: frozenset[str] = frozenset({
    "write_file", "edit_file", "notebook_edit",
})
SUBAGENT_TOOLS: frozenset[str] = frozenset({"Agent", "delegate_agent"})


def resolve_tools(
    tool_names: list[str],
    *,
    allow_shell: bool = True,
    allow_write: bool = True,
    allow_subagent: bool = True,
) -> set[str]:
    """Resolve Nexus tool names to claw-code tool names with permission filtering.

    Args:
        tool_names: List of Nexus symbolic tool names. Empty list means "all".
        allow_shell: Whether shell commands are allowed.
        allow_write: Whether file writes are allowed.
        allow_subagent: Whether sub-agent spawning is allowed.

    Returns:
        Set of claw-code-agent tool names allowed for this agent.
    """
    if not tool_names:
        # "all" → start with all mapped tools
        resolved = set(TOOL_NAME_MAP.values())
    else:
        resolved = set()
        for name in tool_names:
            mapped = TOOL_NAME_MAP.get(name)
            if mapped is not None:
                resolved.add(mapped)

    # Apply permission filters
    if not allow_shell:
        resolved -= SHELL_TOOLS
    if not allow_write:
        resolved -= FILE_WRITE_TOOLS
    if not allow_subagent:
        resolved -= SUBAGENT_TOOLS

    return resolved


def build_tool_registry(
    base_registry: dict[str, Any],
    allowed_tools: set[str],
) -> dict[str, Any]:
    """Filter a full tool registry to only include allowed tools.

    Args:
        base_registry: The full claw-code-agent tool registry.
        allowed_tools: Set of tool names to keep.

    Returns:
        Filtered tool registry dict.
    """
    return {
        name: tool
        for name, tool in base_registry.items()
        if name in allowed_tools
    }


def get_tool_category(tool_name: str) -> str:
    return TOOL_CATEGORIES.get(tool_name, "query")
