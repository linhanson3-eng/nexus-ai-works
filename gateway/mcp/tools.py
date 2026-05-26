from __future__ import annotations

"""MCP tools — ai-factory capabilities exposed over JSON-RPC 2.0.

Tool design follows Agor's pattern: merged modes (not split tools),
tool discovery built-in, workspace-level read/write, isError standardization.
"""

import asyncio
import json
from pathlib import Path
from typing import Any


def _safe_path(workspace_root: Path, relative: str) -> Path | None:
    """Resolve relative path inside workspace. Returns None if path escapes."""
    resolved = (workspace_root / relative).resolve()
    if not resolved.is_relative_to(workspace_root.resolve()):
        return None
    return resolved


TOOL_DEFINITIONS: list[dict[str, Any]] = [

    # ── Tool discovery ──
    {
        "name": "nexus_list_tools",
        "description": "列出所有可用的 MCP tools，可按关键词搜索",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "可选的搜索关键词，匹配 tool name 和 description",
                },
            },
            "required": [],
        },
    },
    {
        "name": "nexus_describe_tool",
        "description": "获取指定 tool 的详细描述和参数说明",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "tool 名称"},
            },
            "required": ["name"],
        },
    },

    # ── 会话执行 (合并 continue/fork/spawn/btw) ──
    {
        "name": "nexus_execute_task",
        "description": (
            "执行一个 Agent 任务。通过 mode 参数控制执行模式:\n"
            "- continue: 在当前会话中继续执行\n"
            "- fork: 在当前会话的同一层级创建 fork，探索替代方案\n"
            "- spawn: 创建子会话处理子任务\n"
            "- btw: 旁路询问——不阻塞目标 session，完成后自动 callback 结果回调用方 (Phase 2)"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "任务描述"},
                "mode": {
                    "type": "string",
                    "enum": ["continue", "fork", "spawn", "btw"],
                    "default": "continue",
                    "description": "执行模式",
                },
                "parent_session_id": {
                    "type": "string",
                    "description": "父会话 ID (fork/spawn/btw 模式需要)",
                },
                "workshop": {
                    "type": "string",
                    "description": "工作区名称",
                },
                "model": {
                    "type": "string",
                    "description": "模型名称 (可选，如 deepseek/deepseek-v4-pro)",
                },
                "agent_name": {
                    "type": "string",
                    "description": "指定 Agent 名称 (可选，默认使用第一个 Agent)",
                },
            },
            "required": ["task", "workshop"],
        },
    },

    # ── 平台感知 ──
    {
        "name": "nexus_get_status",
        "description": "获取 ai-factory 整体状态: Workshop 列表、Agent 数、看板、运行中任务",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {
                    "type": "string",
                    "description": "可选——指定工作区名称以获取详细状态",
                },
            },
            "required": [],
        },
    },
    {
        "name": "nexus_read_board",
        "description": "读取指定 Workshop 的看板状态（列、卡片、执行进度）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string"},
            },
            "required": ["workshop"],
        },
    },

    # ── Workspace 读写 ──
    {
        "name": "nexus_read_workspace",
        "description": "读取 Workshop 目录中的文件内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
                "path": {"type": "string", "description": "相对于 workspace 根目录的文件路径"},
            },
            "required": ["workshop", "path"],
        },
    },
    {
        "name": "nexus_write_workspace",
        "description": "写入文件到 Workshop 目录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
                "path": {"type": "string", "description": "相对于 workspace 根目录的文件路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["workshop", "path", "content"],
        },
    },
    {
        "name": "nexus_list_workspace",
        "description": "列出 Workshop 目录中的文件",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
                "path": {"type": "string", "description": "相对于 workspace 根目录的子路径 (默认根目录)"},
            },
            "required": ["workshop"],
        },
    },

    # ── 工作流 ──
    {
        "name": "nexus_run_workflow",
        "description": "执行一个工作流模板 (DAG 并行调度)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string"},
                "workflow_name": {"type": "string"},
                "task": {"type": "string"},
            },
            "required": ["workshop", "workflow_name", "task"],
        },
    },

    # ── 会话控制 ──
    {
        "name": "nexus_stop_session",
        "description": "停止正在执行的会话。Agent 发现子任务跑偏或质量不达标时，主动停止该会话",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "要停止的会话 ID"},
                "reason": {"type": "string", "description": "停止原因"},
            },
            "required": ["session_id"],
        },
    },
    # ── 跨模型交叉审查 ──
    {
        "name": "nexus_cross_review",
        "description": (
            "并行启动多个不同模型的 Agent 独立审查同一份代码，汇总对比结论。\n"
            "每个 Reviewer 用 spawn 模式（不继承任何上下文），不同模型独立推理。\n"
            "输出: consensus(多模型共识) + unique(某模型独有) + conflicts(结论冲突)"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
                "target": {"type": "string", "description": "要审查的文件路径 (相对于 workspace)"},
                "models": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "审查模型列表 (至少2个)，如 ['deepseek/deepseek-v4-pro', 'siliconflow/Pro/moonshotai/Kimi-K2.6']",
                },
                "focus": {
                    "type": "string",
                    "description": "审查重点提示 (可选)。如: '安全漏洞'、'性能问题'、'逻辑正确性'",
                },
            },
            "required": ["workshop", "target", "models"],
        },
    },
    # ── 审查修复闭环 ──
    {
        "name": "nexus_review_loop",
        "description": (
            "审查→修复→验证闭环。先交叉审查代码，发现问题后自动修复，再审查验证。\n"
            "流程: cross-review → fix → verify\n"
            "输出: before/after 对比 + 修复率 + 残留问题"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
                "target": {"type": "string", "description": "要审查并修复的文件路径"},
                "models": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "审查模型列表 (至少2个)",
                },
                "fix_model": {
                    "type": "string",
                    "description": "执行修复的模型 (默认用 models[0])",
                },
                "focus": {
                    "type": "string",
                    "description": "审查重点提示 (可选)",
                },
            },
            "required": ["workshop", "target", "models"],
        },
    },
    {
        "name": "nexus_list_sessions",
        "description": "列出当前工作区的所有会话（含父子关系），用于了解 fork/spawn 树结构",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
            },
            "required": ["workshop"],
        },
    },
]


def _err(text: str) -> dict[str, Any]:
    """Standardized error response with isError flag."""
    return {"content": [{"type": "text", "text": text}], "isError": True}


import re as _re

_VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
_VALID_DIMENSIONS = {"correctness", "security", "robustness", "performance", "maintainability"}


def _normalize_finding(raw: dict) -> dict | None:
    """Validate and normalize a single finding dict. Returns None if invalid."""
    sev = str(raw.get("severity", "")).upper().strip()
    if sev not in _VALID_SEVERITIES:
        return None
    desc = str(raw.get("description", "")).strip()
    if not desc:
        return None
    loc = str(raw.get("location", "")).strip()
    dim = str(raw.get("dimension", "")).lower().strip()
    return {
        "severity": sev,
        "description": desc,
        "location": loc,
        "dimension": dim if dim in _VALID_DIMENSIONS else "",
    }


def _extract_json_findings(text: str) -> list[dict]:
    """Extract findings from JSON block or structured output."""
    findings: list[dict] = []
    # Strategy 1: ```json block
    if "```json" in text:
        block = text.split("```json", 1)[1].split("```", 1)[0]
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict) and "findings" in parsed:
                findings = parsed["findings"]
        except (json.JSONDecodeError, IndexError):
            pass
    # Strategy 2: any ``` block (model might not specify json)
    if not findings and "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            try:
                parsed = json.loads(parts[i])
                if isinstance(parsed, dict) and "findings" in parsed:
                    findings = parsed["findings"]
                    break
            except (json.JSONDecodeError, IndexError):
                continue
    # Strategy 3: raw JSON in the entire text
    if not findings:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "findings" in parsed:
                findings = parsed["findings"]
        except (json.JSONDecodeError, IndexError):
            pass
    return [_normalize_finding(f) for f in findings if _normalize_finding(f)]


def _extract_markdown_findings(text: str) -> list[dict]:
    """Fallback: extract CRITICAL|HIGH|MEDIUM|LOW patterns from markdown lists."""
    findings: list[dict] = []
    sev_pattern = r"^[-*]\s*(?:\*\*)?(CRITICAL|HIGH|MEDIUM|LOW)(?:\*\*)?\s*[:：-]\s*(.+)$"
    for line in text.split("\n"):
        line = line.strip()
        match = _re.match(sev_pattern, line, _re.IGNORECASE)
        if not match:
            # Also match inline patterns: [SEVERITY] or **SEVERITY**:
            match2 = _re.match(r".*?\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s*(.+?)(?:\n|$)", line, _re.IGNORECASE)
            if not match2:
                match2 = _re.match(r".*?\*\*(CRITICAL|HIGH|MEDIUM|LOW)\*\*\s*[:：]\s*(.+?)(?:\n|$)", line, _re.IGNORECASE)
            if match2:
                sev = match2.group(1).upper()
                desc = match2.group(2).strip()
                if desc and len(desc) > 5:
                    findings.append({"severity": sev, "description": desc, "location": "", "dimension": ""})
        else:
            sev = match.group(1).upper()
            desc = match.group(2).strip()
            if desc:
                findings.append({"severity": sev, "description": desc, "location": "", "dimension": ""})
    return findings


def _extract_findings(text: str) -> list[dict]:
    """Multi-format finding extractor: JSON first, markdown fallback."""
    if not text or not text.strip():
        return []
    clean = text.strip()
    findings = _extract_json_findings(clean)
    if not findings:
        findings = _extract_markdown_findings(clean)
    return findings


def _parse_aggregator_output(text: str) -> dict:
    """Multi-strategy JSON parser for aggregator output, with field normalization."""
    if not text or not text.strip():
        return {}
    t = text.strip()
    # Strategy 1: ```json block
    candidate = None
    if "```json" in t:
        try:
            candidate = t.split("```json", 1)[1].split("```", 1)[0].strip()
        except IndexError:
            pass
    # Strategy 2: any ``` block
    if candidate is None and "```" in t:
        parts = t.split("```")
        for i in range(1, len(parts), 2):
            try:
                candidate = parts[i].strip()
                break
            except IndexError:
                continue
    # Strategy 3: raw text
    if candidate is None:
        candidate = t

    try:
        raw = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return {}

    return _normalize_aggregator_fields(raw)


def _normalize_aggregator_fields(raw: dict) -> dict:
    """Map alternative field names from the aggregator model to our standard schema.

    LLMs sometimes rename fields (description→finding, found_by→sources, etc.).
    This normalizer accepts both the canonical names and common alternatives.
    """
    if not isinstance(raw, dict):
        return {}

    out: dict = {}

    # consensus items: normalize description/finding, found_by/sources/models
    consensus_raw = raw.get("consensus", [])
    if isinstance(consensus_raw, list):
        out["consensus"] = []
        for item in consensus_raw:
            if not isinstance(item, dict):
                continue
            desc = item.get("description") or item.get("finding") or item.get("issue") or item.get("title") or ""
            sev = str(item.get("severity", "")).upper()
            found_by = item.get("found_by") or item.get("sources") or item.get("models") or []
            if isinstance(found_by, str):
                found_by = [found_by]
            if desc and sev in _VALID_SEVERITIES:
                out["consensus"].append({
                    "description": desc,
                    "severity": sev,
                    "found_by": list(found_by) if found_by else [],
                })

    # unique: per-model lists of findings
    unique_raw = raw.get("unique", {})
    if isinstance(unique_raw, dict):
        out["unique"] = {}
        for model_name, findings_list in unique_raw.items():
            if not isinstance(findings_list, list):
                continue
            normalized = []
            for f in findings_list:
                if not isinstance(f, dict):
                    continue
                desc = f.get("description") or f.get("finding") or f.get("issue") or f.get("title") or ""
                sev = str(f.get("severity", "")).upper()
                if desc and sev in _VALID_SEVERITIES:
                    normalized.append({"description": desc, "severity": sev})
            if normalized:
                out["unique"][model_name] = normalized

    # conflicts
    conflicts_raw = raw.get("conflicts", [])
    if isinstance(conflicts_raw, list):
        out["conflicts"] = []
        for c in conflicts_raw:
            if not isinstance(c, dict):
                continue
            desc = c.get("description") or c.get("finding") or c.get("issue") or ""
            models = c.get("models") or c.get("severities") or {}
            resolution = c.get("resolution") or c.get("recommendation") or ""
            if desc and isinstance(models, dict):
                out["conflicts"].append({
                    "description": desc,
                    "models": models,
                    "resolution": resolution,
                })

    # verdict
    verdict = str(raw.get("verdict", "")).upper()
    if verdict in ("PASS", "NEEDS_FIX", "REVIEW"):
        out["verdict"] = verdict

    # reasoning
    reasoning = raw.get("reasoning") or raw.get("summary") or ""
    if reasoning:
        out["reasoning"] = str(reasoning)

    return out


async def _build_review_output(
    review_results: list[dict],
    models: list[str],
    target: str,
    workspace_root: Any,
    registry: Any,
) -> dict:
    """Aggregate parallel review results into a structured output dict."""
    from factory.engine.bridge import (
        AgentLoopEngine, EngineConfig, create_agent, create_model_config as _cmc,
    )
    from pathlib import Path as _Path

    per_model: dict[str, list[dict]] = {}
    cost_by_model: dict[str, float] = {}
    for r in review_results:
        per_model[r["model"]] = r.get("findings", [])
        cost_by_model[r["model"]] = r.get("cost_usd", 0.0)

    # LLM Aggregator
    aggregator_output: dict = {}
    if review_results and any(r.get("findings") for r in review_results):
        parts: list[str] = []
        for r in review_results:
            short_model = r["model"].split("/")[-1]
            parts.append(f"## {short_model}")
            if r.get("findings"):
                for j, f in enumerate(r["findings"], 1):
                    parts.append(
                        f"  [{j}] [{f.get('severity', '?')}] {f.get('description', '')}"
                    )
            else:
                parts.append("  (no findings)")

        aggregator_prompt = (
            "你是一个代码审查聚合器。以下是多个 AI 模型对同一份代码的审查结果。\n"
            "任务: 语义去重、标记共识/独有/冲突、给出 verdict 和 reasoning。\n\n"
            "审查结果:\n"
            f"{chr(10).join(parts)}\n\n"
            "重要——字段名不可修改。示例:\n"
            '{"consensus": [{"description": "...", "severity": "CRITICAL", "found_by": ["a", "b"]}],'
            '"unique": {"a": [{"description": "...", "severity": "HIGH"}]},'
            '"conflicts": [], "verdict": "NEEDS_FIX", "reasoning": "..."}'
        )

        agg_model = models[0]
        try:
            agg_model_cfg = _cmc(agg_model, registry=registry)
            ws_dir = _Path(workspace_root) if not isinstance(workspace_root, _Path) else workspace_root
            agg_engine_cfg = EngineConfig(
                cwd=ws_dir, max_turns=5,
                session_directory=str(ws_dir / ".sessions"),
            )
            agg_agent = create_agent(agg_model_cfg, agg_engine_cfg)
            agg_engine = AgentLoopEngine(agg_agent, engine_config=agg_engine_cfg)
            agg_result = await agg_engine.spawn(aggregator_prompt)
            agg_text = getattr(agg_result, "final_output", "") or ""
            aggregator_output = _parse_aggregator_output(agg_text)
            cost_by_model[f"_aggregator({agg_model.split('/')[-1]})"] = (
                getattr(agg_result, "total_cost_usd", 0.0) or 0.0
            )
        except Exception:
            pass

    if aggregator_output:
        consensus = aggregator_output.get("consensus", [])
        unique = aggregator_output.get("unique", {})
        conflicts = aggregator_output.get("conflicts", [])
        verdict = aggregator_output.get("verdict", "REVIEW")
        reasoning = aggregator_output.get("reasoning", "")
    else:
        short_models = {m: m.split("/")[-1] for m in models}
        unique = {
            short_models.get(r["model"], r["model"]): r.get("findings", [])
            for r in review_results if r.get("findings")
        }
        consensus = []
        conflicts = []
        reasoning = ""
        any_critical = any(
            f.get("severity") == "CRITICAL"
            for r in review_results
            for f in r.get("findings", [])
        )
        verdict = "NEEDS_FIX" if any_critical else "REVIEW"

    return {
        "verdict": verdict,
        "reasoning": reasoning,
        "target": target,
        "models": models,
        "cost_by_model": cost_by_model,
        "findings_by_model": {m: per_model.get(m, []) for m in models},
        "consensus": consensus,
        "unique": unique,
        "conflicts": conflicts,
    }


async def run_review_loop(
    *,
    workspace_root: Any,
    target: str,
    models: list[str],
    fix_model: str = "",
    focus: str = "",
    registry: Any,
    agent_spec: Any,
) -> dict:
    """审查→修复→验证闭环。MCP handler 和 WorkflowRunner 的共同入口。

    Returns a dict with verdict, comparison, phases, cost.
    On error, returns {"error": "message"}.
    """
    from factory.engine.bridge import (
        AgentLoopEngine, EngineConfig, create_agent, create_model_config,
    )

    if len(models) < 2:
        return {"error": "models 至少需要 2 个模型"}
    if not fix_model:
        fix_model = models[0]

    target_path = workspace_root / target
    if not target_path.exists():
        return {"error": f"目标文件不存在: {target}"}

    # Validate models
    valid_models: list[str] = []
    for m in models:
        try:
            create_model_config(m, registry=registry)
            valid_models.append(m)
        except (ValueError, Exception):
            pass
    if not valid_models:
        return {"error": "所有模型无效"}
    models = valid_models

    # ── Phase 1: 初始交叉审查 ──
    focus_hint = f"\n审查重点: {focus}" if focus else ""
    review_prompt = (
        f"你是一个严格的代码审查员。审查文件 {target}。用 nexus_read_workspace 读取。\n"
        f"审查维度: 正确性、数据边界、安全性、健壮性、性能、可维护性。\n"
        f"特别注意: 校验输入值范围、配置数据的合法域。"
        f"{focus_hint}\n"
        f"每个发现标注级别: CRITICAL / HIGH / MEDIUM / LOW。\n"
        f"严格按 JSON 格式输出: "
        f'{{"findings": [{{"severity": "HIGH", "description": "问题", "location": "位置", "dimension": "correctness"}}]}}'
    )

    async def _review_one(model_str: str) -> dict:
        model_cfg = create_model_config(model_str, registry=registry)
        engine_cfg = EngineConfig(
            cwd=workspace_root, max_turns=30,
            session_directory=str(workspace_root / ".sessions"),
        )
        agent = create_agent(model_cfg, engine_cfg)
        engine = AgentLoopEngine(agent, engine_config=engine_cfg)
        result = await engine.spawn(review_prompt)
        output_text = getattr(result, "final_output", "") or ""
        findings = _extract_findings(output_text)
        return {
            "model": model_str,
            "session_id": result.session_id or "",
            "findings": findings,
            "turns": getattr(result, "turns", 0),
            "cost_usd": getattr(result, "total_cost_usd", 0.0) or 0.0,
        }

    # Phase 1 reviews + aggregation
    before_reviews = await asyncio.gather(
        *(_review_one(m) for m in models), return_exceptions=True,
    )
    before_results: list[dict] = []
    for r in before_reviews:
        if not isinstance(r, Exception):
            before_results.append(r)

    before = await _build_review_output(
        before_results, models, target, workspace_root, registry,
    )

    if before.get("verdict") == "PASS":
        return {
            "verdict": "PASS", "target": target,
            "comparison": {
                "before": {"consensus": 0, "unique": 0},
                "after": {"consensus": 0, "unique": 0},
                "resolved_consensus": 0, "fix_effective": True,
            },
            "phases": {"before": before},
        }

    # ── Phase 2: Fix ──
    fix_cost = 0.0
    fix_output = ""
    all_issues = (
        before.get("consensus", []) +
        [f for flist in before.get("unique", {}).values() for f in flist]
    )
    if all_issues:
        issues_text = "\n".join(
            f"- [{i.get('severity', '?')}] {i.get('description', '')}"
            for i in all_issues
        )
        fix_prompt = (
            f"修复文件 {target} 中的以下问题。用 nexus_read_workspace 读取，用 nexus_write_workspace 写回。\n"
            f"逐条修复每个问题，不要删掉正常代码。修复后简要说明改了什么。\n"
            f"修复规则: 1) isinstance(x, int) 会错误接受 bool(bool是int子类)，排除bool用 type(x) is int\n"
            f"2) 类型提示统一用 Python 3.10+ 语法 (X | None)，不混用 Union\n"
            f"3) 每个改动考虑边界效应，不引入新问题\n\n"
            f"{issues_text}"
        )
        try:
            fix_model_cfg = create_model_config(fix_model, registry=registry)
            fix_engine_cfg = EngineConfig(
                cwd=workspace_root, max_turns=20,
                session_directory=str(workspace_root / ".sessions"),
            )
            fix_agent = create_agent(fix_model_cfg, fix_engine_cfg)
            fix_engine = AgentLoopEngine(fix_agent, engine_config=fix_engine_cfg)
            fix_result = await fix_engine.spawn(fix_prompt)
            fix_output = getattr(fix_result, "final_output", "") or ""
            fix_cost = getattr(fix_result, "total_cost_usd", 0.0) or 0.0
        except Exception as e:
            fix_output = f"修复失败: {e}"

    # ── Phase 3: Verify ──
    after_reviews = await asyncio.gather(
        *(_review_one(m) for m in models), return_exceptions=True,
    )
    after_results: list[dict] = []
    for r in after_reviews:
        if not isinstance(r, Exception):
            after_results.append(r)

    after = await _build_review_output(
        after_results, models, target, workspace_root, registry,
    )

    # ── Comparison ──
    before_consensus = len(before.get("consensus", []))
    after_consensus = len(after.get("consensus", []))
    before_unique = sum(len(v) for v in before.get("unique", {}).values())
    after_unique = sum(len(v) for v in after.get("unique", {}).values())
    resolved = max(0, before_consensus - after_consensus)
    fixed_verdict = after.get("verdict", "REVIEW")
    fix_effective = resolved > 0 or (
        before.get("verdict") == "NEEDS_FIX" and fixed_verdict != "NEEDS_FIX"
    )

    return {
        "verdict": fixed_verdict,
        "target": target,
        "fix_applied": bool(fix_output),
        "fix_output": fix_output[:2000],
        "comparison": {
            "before": {"consensus": before_consensus, "unique": before_unique},
            "after": {"consensus": after_consensus, "unique": after_unique},
            "resolved_consensus": resolved,
            "fix_effective": fix_effective,
        },
        "cost": {
            "fix_model": fix_cost,
            "before_review": sum(r.get("cost_usd", 0) for r in before_results),
            "after_review": sum(r.get("cost_usd", 0) for r in after_results),
        },
        "phases": {"before": before, "after": after},
    }


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    org: Any,
    kanban_store: Any,
    session_manager: Any,
    mcp_token_payload: dict[str, Any],
    settings_store: Any = None,
) -> dict[str, Any]:
    """Execute a tool call and return MCP-compatible result."""
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(org, kanban_store)
    workshop_name = arguments.get("workshop", "")

    # ── Tool discovery ──

    if tool_name == "nexus_list_tools":
        query = (arguments.get("query", "") or "").lower()
        tools = TOOL_DEFINITIONS
        if query:
            tools = [
                t for t in tools
                if query in t["name"].lower() or query in t["description"].lower()
            ]
        result = [
            {"name": t["name"], "description": t["description"].split("\n")[0]}
            for t in tools
        ]
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}

    if tool_name == "nexus_describe_tool":
        name = arguments["name"]
        for t in TOOL_DEFINITIONS:
            if t["name"] == name:
                return {"content": [{"type": "text", "text": json.dumps(t, ensure_ascii=False, indent=2)}]}
        return _err(f"Tool not found: {name}")

    # ── 平台状态 ──

    if tool_name == "nexus_get_status":
        if workshop_name:
            ws = mgr.get(workshop_name)
            if ws is None:
                return _err(f"工作区 {workshop_name} 不存在")
            status = mgr.status(workshop_name)
            return {"content": [{"type": "text", "text": json.dumps(status, ensure_ascii=False, indent=2)}]}
        status = org.status()
        return {"content": [{"type": "text", "text": json.dumps(status, ensure_ascii=False, indent=2)}]}

    if tool_name == "nexus_read_board":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        status = mgr.status(workshop_name)
        if status is None:
            return _err(f"无法获取 {workshop_name} 状态")
        return {"content": [{"type": "text", "text": json.dumps(status, ensure_ascii=False, indent=2)}]}

    # ── Workspace 读写 ──

    if tool_name == "nexus_read_workspace":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        file_path = _safe_path(ws.workspace, arguments["path"])
        if file_path is None:
            return _err(f"路径越界: {arguments['path']}")
        try:
            content = file_path.read_text("utf-8")
            return {"content": [{"type": "text", "text": content}]}
        except FileNotFoundError:
            return _err(f"文件不存在: {arguments['path']}")
        except UnicodeDecodeError:
            return _err(f"文件不是文本格式: {arguments['path']}")

    if tool_name == "nexus_write_workspace":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        file_path = _safe_path(ws.workspace, arguments["path"])
        if file_path is None:
            return _err(f"路径越界: {arguments['path']}")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(arguments["content"], "utf-8")
        return {"content": [{"type": "text", "text": f"已写入: {arguments['path']}"}]}

    if tool_name == "nexus_list_workspace":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        subpath = _safe_path(ws.workspace, arguments.get("path", "") or ".")
        if subpath is None:
            return _err(f"路径越界: {arguments.get('path', '.')}")
        if not subpath.exists():
            return _err(f"路径不存在: {arguments.get('path', '.')}")
        entries = []
        for p in sorted(subpath.iterdir()):
            entries.append({
                "name": p.name,
                "type": "dir" if p.is_dir() else "file",
                "size": p.stat().st_size if p.is_file() else 0,
            })
        return {"content": [{"type": "text", "text": json.dumps(entries, ensure_ascii=False, indent=2)}]}

    # ── 合并式会话执行 ──

    if tool_name == "nexus_execute_task":
        task = arguments.get("task", "")
        mode = arguments.get("mode", "continue")
        parent_id = arguments.get("parent_session_id", "")
        model = arguments.get("model", "")
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        if not ws.spec.agents:
            return _err("工作区没有 Agent")

        agent_name = arguments.get("agent_name", "")
        if agent_name:
            agent_spec = next((a for a in ws.spec.agents if a.name == agent_name), None)
            if agent_spec is None:
                return _err(f"Agent {agent_name} 不存在于工作区 {workshop_name}")
        else:
            agent_spec = ws.spec.agents[0]

        from factory.engine.bridge import (
            AgentLoopEngine,
            EngineConfig,
            create_agent,
            create_model_config,
        )
        from factory.engine.providers import ProviderRegistry

        # Resolve model + api_key via provider registry (same as runner)
        effective_model = model or getattr(agent_spec, 'model', '') or "deepseek/deepseek-v4-pro"
        if settings_store is not None:
            registry = ProviderRegistry.from_store(settings_store)
        else:
            from factory.settings import SettingsStore
            registry = ProviderRegistry.from_store(SettingsStore())

        model_cfg = create_model_config(effective_model, registry=registry)
        engine_cfg = EngineConfig(
            cwd=ws.workspace,
            max_turns=getattr(agent_spec, 'max_turns', 30),
            session_directory=str(ws.workspace / ".sessions"),
        )
        agent = create_agent(model_cfg, engine_cfg)
        engine = AgentLoopEngine(agent, engine_config=engine_cfg)

        if mode == "fork" and parent_id:
            # Real fork: clone parent's full conversation history, new session ID
            result = await engine.fork(task, parent_id)
        elif mode == "spawn":
            # Real spawn: clean context, no parent history inheritance
            result = await engine.spawn(task)
        elif mode == "btw" and parent_id:
            # Btw: fork variant — ephemeral by-call, auto-callback result to parent
            result = await engine.fork(task, parent_id)
        elif mode == "continue" and parent_id:
            # Resume existing session
            result = await engine.resume(task, parent_id)
        else:
            result = await engine.run(task)

        # Extract fields from AgentRunResult (matches runner.py's conversion)
        output_text = getattr(result, 'final_output', '') or ''
        session_id_out = result.session_id or ""
        stop_reason = getattr(result, 'stop_reason', '') or ''
        is_error = stop_reason and stop_reason not in ("end_turn", "stop", "max_tokens")
        turns_val = getattr(result, 'turns', 0)
        cost_val = getattr(result, 'total_cost_usd', 0.0) or 0.0
        tc = getattr(result, 'tool_calls', None)
        tools_list = tc if isinstance(tc, list) else []

        # Record to SessionTree
        from factory.workflow.session_tree import SessionNode, SessionType, SessionStatus, SessionTree

        st = SessionTree(workshop_name=workshop_name)
        node = SessionNode(
            session_id=session_id_out,
            parent_id=parent_id,
            session_type=SessionType(mode if mode != "continue" else "root"),
            workshop_name=workshop_name,
            task=task,
            status=SessionStatus.FAILED if is_error else SessionStatus.COMPLETED,
            agent_name=agent_spec.name,
            model=effective_model,
            output=output_text[:5000],
            error=stop_reason if is_error else "",
            turns=turns_val,
            cost_usd=cost_val,
            tools_used=tools_list,
        )
        st.add(node)

        output = {
            "session_id": session_id_out,
            "mode": mode,
            "output": output_text[:5000],
            "turns": turns_val,
            "tools_used": tools_list,
            "model": effective_model,
            "error": stop_reason if is_error else None,
        }
        return {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False, indent=2)}]}

    # ── 工作流 ──

    if tool_name == "nexus_run_workflow":
        workflow_name = arguments.get("workflow_name", "")
        task = arguments.get("task", "")
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        from factory.workflow.engine import WorkflowRunner
        tmpl = org.workflow_store.load(workflow_name) if org.workflow_store else None
        if tmpl is None:
            return _err(f"工作流 {workflow_name} 不存在")
        runner = WorkflowRunner(ws)
        result = await runner.run(tmpl, task)
        return {"content": [{"type": "text", "text": result.final_output or str(result.node_results)}]}

    # ── 会话控制 ──

    if tool_name == "nexus_stop_session":
        target_id = arguments["session_id"]
        reason = arguments.get("reason", "手动停止")

        st = SessionTree(workshop_name=workshop_name)
        node = st.get(target_id)
        if node is None:
            return _err(f"会话 {target_id} 不存在")

        # Mark session as failed in the tree
        node.status = SessionStatus.FAILED
        node.error = reason
        st._save()

        return {"content": [{"type": "text", "text": json.dumps({
            "session_id": target_id,
            "status": "stopped",
            "reason": reason,
        }, ensure_ascii=False)}]}

    # ── 跨模型交叉审查 ──

    if tool_name == "nexus_cross_review":
        target = arguments.get("target", "")
        models = arguments.get("models", [])
        focus = arguments.get("focus", "")
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        if len(models) < 2:
            return _err("models 至少需要 2 个模型")
        if not ws.spec.agents:
            return _err("工作区没有 Agent")

        from factory.engine.bridge import (
            AgentLoopEngine,
            EngineConfig,
            create_agent,
            create_model_config,
        )
        from factory.engine.providers import ProviderRegistry
        from factory.workflow.session_tree import (
            SessionNode, SessionType, SessionStatus, SessionTree,
        )

        if settings_store is not None:
            registry = ProviderRegistry.from_store(settings_store)
        else:
            from factory.settings import SettingsStore
            registry = ProviderRegistry.from_store(SettingsStore())

        # ── P1: Validate all models before spawning ──
        valid_models: list[str] = []
        invalid_models: list[dict] = []
        for m in models:
            try:
                create_model_config(m, registry=registry)
                valid_models.append(m)
            except ValueError as e:
                invalid_models.append({"model": m, "reason": str(e)})
            except Exception as e:
                invalid_models.append({"model": m, "reason": str(e)})

        if not valid_models:
            return _err(f"所有模型无效: {json.dumps(invalid_models, ensure_ascii=False)}")
        if invalid_models:
            errors_ = [f"{x['model']}: {x['reason']}" for x in invalid_models]

        models = valid_models

        agent_spec = ws.spec.agents[0]
        workspace_root = ws.workspace
        target_path = workspace_root / target
        if not target_path.exists():
            return _err(f"目标文件不存在: {target}")

        focus_hint = f"\n审查重点: {focus}" if focus else ""
        review_prompt = (
            f"你是一个严格的代码审查员(Reviewer)。你不是来称赞代码的，你是来找问题的。\n"
            f"始终保持怀疑态度。如果代码看起来没有问题，再仔细看一遍。\n\n"
            f"审查文件: {target}\n"
            f"用 nexus_read_workspace 读取文件内容。\n\n"
            f"审查维度:\n"
            f"1. 正确性 — 逻辑错误、边界条件、off-by-one、空值处理\n"
            f"2. 数据边界 — 输入值范围校验、常量/配置值的合法域、负数/零/超限值防护\n"
            f"3. 安全性 — 注入风险、权限检查、敏感数据泄露、路径遍历\n"
            f"4. 健壮性 — 异常处理、类型安全、输入校验、并发安全\n"
            f"5. 性能 — 不必要的计算、内存浪费、N+1 问题\n"
            f"6. 可维护性 — 命名、重复代码、过度耦合、缺少文档\n"
            f"{focus_hint}\n\n"
            f"每个发现标注严重级别:\n"
            f"- CRITICAL: 运行时崩溃、安全漏洞、数据损坏\n"
            f"- HIGH: 业务逻辑错误、明确的 bug\n"
            f"- MEDIUM: 代码质量问题、潜在风险\n"
            f"- LOW: 风格建议、轻微改进\n\n"
            f"严格按以下 JSON 格式输出，不要加任何其他文字:\n"
            f'{{"findings": [{{"severity": "CRITICAL|HIGH|MEDIUM|LOW", '
            f'"dimension": "correctness|security|robustness|performance|maintainability", '
            f'"description": "具体问题描述", "location": "代码位置"}}]}}\n'
            f"如果没有问题，findings 为空数组。"
        )

        async def _run_one_review(model_str: str) -> dict:
            """Spawn one reviewer with given model, return parsed findings."""
            model_cfg = create_model_config(model_str, registry=registry)
            engine_cfg = EngineConfig(
                cwd=workspace_root,
                max_turns=getattr(agent_spec, 'max_turns', 30),
                session_directory=str(workspace_root / ".sessions"),
            )
            agent = create_agent(model_cfg, engine_cfg)
            engine = AgentLoopEngine(agent, engine_config=engine_cfg)
            result = await engine.spawn(review_prompt)

            output_text = getattr(result, 'final_output', '') or ''
            session_id_out = result.session_id or ""
            stop_reason = getattr(result, 'stop_reason', '') or ''
            is_error = stop_reason and stop_reason not in ("end_turn", "stop", "max_tokens")

            # ── P0: Robust finding extraction (multi-format) ──
            findings: list[dict] = _extract_findings(output_text)
            if not findings and not is_error:
                # Output is empty or unparseable — treat as "no findings" (not an error)
                # This is common when the model has nothing to report
                pass

            # Record to SessionTree
            st = SessionTree(workshop_name=workshop_name)
            node = SessionNode(
                session_id=session_id_out,
                parent_id="",
                session_type=SessionType.SPAWN,
                workshop_name=workshop_name,
                task=f"Cross-review {target}",
                status=SessionStatus.FAILED if is_error else SessionStatus.COMPLETED,
                agent_name=agent_spec.name,
                model=model_str,
                output=output_text[:5000],
                error=stop_reason if is_error else "",
                turns=getattr(result, 'turns', 0),
                cost_usd=getattr(result, 'total_cost_usd', 0.0) or 0.0,
                tools_used=[],
            )
            st.add(node)

            return {
                "model": model_str,
                "session_id": session_id_out,
                "findings": findings,
                "turns": getattr(result, 'turns', 0),
                "cost_usd": getattr(result, 'total_cost_usd', 0.0) or 0.0,
                "error": stop_reason if is_error else None,
            }

        # Run all reviewers in parallel
        reviews = await asyncio.gather(
            *(_run_one_review(m) for m in models),
            return_exceptions=True,
        )

        all_results: list[dict] = []
        errors: list[str] = []
        for i, r in enumerate(reviews):
            if isinstance(r, Exception):
                errors.append(f"{models[i]}: {r}")
            else:
                all_results.append(r)

        # Build per-model findings + cost
        per_model: dict[str, list[dict]] = {}
        cost_by_model: dict[str, float] = {}
        for r in all_results:
            per_model[r["model"]] = r["findings"]
            cost_by_model[r["model"]] = r.get("cost_usd", 0.0)

        # ── LLM Aggregator: semantic dedup + cross-model comparison ──
        aggregator_output = {}
        if all_results:
            # Format findings for aggregator prompt
            findings_text_parts = []
            for r in all_results:
                short_model = r["model"].split("/")[-1]
                findings_text_parts.append(f"## {short_model}")
                if r["findings"]:
                    for j, f in enumerate(r["findings"], 1):
                        findings_text_parts.append(
                            f"  [{j}] [{f.get('severity', '?')}] {f.get('description', '')}"
                        )
                else:
                    findings_text_parts.append("  (no findings)")
            findings_block = "\n".join(findings_text_parts)

            aggregator_prompt = (
                "你是一个代码审查聚合器。以下是多个 AI 模型对同一份代码的审查结果。\n"
                "你的任务：\n"
                "1. 语义去重——用不同措辞描述的同一个问题，归为一组\n"
                "2. 标记 consensus——2 个以上模型都发现的问题\n"
                "3. 标记 unique——仅 1 个模型发现的问题\n"
                "4. 标记 conflicts——同一个问题，不同模型给出了不同的严重级别\n"
                "5. 给出 verdict: PASS / NEEDS_FIX / REVIEW\n"
                "6. 给出 reasoning: 1-2 句总结\n\n"
                "审查结果:\n"
                f"{findings_block}\n\n"
                "重要——字段名不可修改，必须是: description, severity, found_by, models, resolution, verdict, reasoning。\n"
                "示例输出 (严格仿照此格式):\n"
                '{"consensus": [{"description": "o.total 应为 o[\"total\"]", "severity": "CRITICAL", "found_by": ["deepseek-v4-pro", "Kimi-K2.6"]}],'
                '"unique": {"deepseek-v4-pro": [{"description": "order_id 无越界检查", "severity": "HIGH"}], "Kimi-K2.6": [{"description": "percent 参数缺校验", "severity": "MEDIUM"}]},'
                '"conflicts": [{"description": "percent 校验缺失", "models": {"deepseek-v4-pro": "HIGH", "Kimi-K2.6": "MEDIUM"}, "resolution": "建议采用 HIGH"}],'
                '"verdict": "NEEDS_FIX",'
                '"reasoning": "共发现 3 个独立问题，其中 1 个为两模型共识(CRITICAL)，需立即修复。"}'
            )

            # Use the first model for aggregation (fastest path)
            agg_model = models[0]
            try:
                agg_model_cfg = create_model_config(agg_model, registry=registry)
                agg_engine_cfg = EngineConfig(
                    cwd=workspace_root,
                    max_turns=5,
                    session_directory=str(workspace_root / ".sessions"),
                )
                agg_agent = create_agent(agg_model_cfg, agg_engine_cfg)
                agg_engine = AgentLoopEngine(agg_agent, engine_config=agg_engine_cfg)
                agg_result = await agg_engine.spawn(aggregator_prompt)

                agg_text = getattr(agg_result, 'final_output', '') or ''
                aggregator_output = _parse_aggregator_output(agg_text)

                cost_by_model[f"_aggregator({agg_model.split('/')[-1]})"] = (
                    getattr(agg_result, 'total_cost_usd', 0.0) or 0.0
                )
            except Exception:
                pass

        # ── Build output: use aggregator results, with structural fallback ──
        aggregator_used = bool(aggregator_output)
        if aggregator_used:
            consensus = aggregator_output.get("consensus", [])
            unique = aggregator_output.get("unique", {})
            conflicts = aggregator_output.get("conflicts", [])
            verdict = aggregator_output.get("verdict", "REVIEW")
            aggregator_reasoning = aggregator_output.get("reasoning", "")
        else:
            # Aggregator failed or produced nothing — build basic structure from raw data
            short_models = {m: m.split("/")[-1] for m in models}
            # Treat all findings as "unique" since we can't dedup without aggregator
            unique = {
                short_models.get(m, m): r["findings"]
                for m, r in zip(models, all_results)
                if r.get("findings")
            }
            consensus = []
            conflicts = []
            aggregator_reasoning = "($$ aggregator 未产出结果，展示原始审查数据)"
            any_critical = any(
                f.get("severity") == "CRITICAL"
                for findings_list in (r.get("findings", []) for r in all_results)
                for f in findings_list
            )
            verdict = "NEEDS_FIX" if any_critical else "REVIEW"

        output = {
            "verdict": verdict,
            "reasoning": aggregator_reasoning,
            "target": target,
            "models": models,
            "cost_by_model": cost_by_model,
            "findings_by_model": {m: per_model.get(m, []) for m in models},
            "consensus": consensus,
            "unique": unique,
            "conflicts": conflicts,
            "errors": errors or None,
        }
        return {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False, indent=2)}]}

    # ── 审查修复闭环 ──

    if tool_name == "nexus_review_loop":
        target = arguments.get("target", "")
        models = arguments.get("models", [])
        focus = arguments.get("focus", "")
        fix_model = arguments.get("fix_model", models[0] if models else "")
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        if not ws.spec.agents:
            return _err("工作区没有 Agent")

        from factory.engine.providers import ProviderRegistry
        if settings_store is not None:
            registry = ProviderRegistry.from_store(settings_store)
        else:
            from factory.settings import SettingsStore
            registry = ProviderRegistry.from_store(SettingsStore())

        result = await run_review_loop(
            workspace_root=ws.workspace,
            target=target,
            models=models,
            fix_model=fix_model,
            focus=focus,
            registry=registry,
            agent_spec=ws.spec.agents[0],
        )
        if result.get("error"):
            return _err(result["error"])
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}

    if tool_name == "nexus_list_sessions":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")

        from factory.workflow.session_tree import SessionTree
        st = SessionTree(workshop_name=workshop_name)
        nodes = st.all_nodes()
        result_list = []
        for n in nodes:
            result_list.append({
                "session_id": n.session_id,
                "parent_id": n.parent_id,
                "type": n.session_type.value if n.session_type else "root",
                "task": n.task[:120],
                "status": n.status.value if n.status else "unknown",
                "agent": n.agent_name,
                "turns": n.turns,
            })
        return {"content": [{"type": "text", "text": json.dumps(result_list, ensure_ascii=False, indent=2)}]}

    return _err(f"Unknown tool: {tool_name}")
