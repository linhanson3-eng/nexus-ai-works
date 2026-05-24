from __future__ import annotations

"""Deep Search tool — 2-layer search + structured analysis.

Layer 1: Multi-engine parallel search via SearchRuntime
Layer 2: Per-result content extraction + mode-based analysis

Modes: summary (default), compare, fact_check.
Registered as a configurable agent tool alongside web_search.
"""


import concurrent.futures
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MAX_RESULTS = 5
MAX_RESULTS = 10
MAX_CONTENT_CHARS = 3000
FETCH_TIMEOUT = 15.0

_STRIP_HTML_RE = re.compile(r"<[^>]+>")
_STRIP_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s{2,}")
_MODE_PROMPTS: dict[str, str] = {
    "summary": """## 深度分析 — 摘要模式

对以上搜索结果和正文内容进行综合分析，按以下格式输出：

### 关键发现
- （列出3-5个最重要的发现，每条附上来源）

### 共识观点
- （多个来源共同确认的结论）

### 分歧与争议
- （不同来源之间的观点差异或矛盾）

### 可行动建议
- （基于分析的具体建议）""",
    "compare": """## 深度分析 — 对比模式

对以上搜索结果进行跨来源对比分析：

### 来源一致性
- 各来源在哪些关键点上一致？
- 一致性程度：高/中/低

### 信息差异
- 不同来源提供了哪些独有信息？
- 哪些信息被多次确认？哪些仅单一来源？

### 偏倚评估
- 各来源可能存在的偏倚或立场
- 建议优先参考的来源""",
    "fact_check": """## 深度分析 — 事实核查模式

对以上信息进行逐条验证：

| 声明 | 来源 | 佐证 | 可信度 |
|------|------|------|--------|
| （原文关键声明） | （来源名） | （支持/不支持/未找到） | 高/中/低 |

### 总体可信度评估
- （综合判断）""",
}


def deep_search_handler(arguments: dict[str, Any], context: Any) -> str:
    """Handler for the deep_search tool.

    Layer 1: Runs web search via the agent's SearchRuntime.
    Layer 2: Fetches full page content for each result.
    Output: Formatted results with mode-based analysis framework.
    """
    from factory.vendor.claw_code_agent.agent_tools import (
        ToolExecutionError,
        _require_search_runtime,
        _require_string,
    )

    runtime = _require_search_runtime(context)
    query = _require_string(arguments, "query")
    mode = arguments.get("mode", "summary")
    if mode not in ("summary", "compare", "fact_check"):
        raise ToolExecutionError("mode must be one of: summary, compare, fact_check")
    max_results = min(int(arguments.get("max_results", DEFAULT_MAX_RESULTS)), MAX_RESULTS)
    deep_read = arguments.get("deep_read", True)

    # Layer 1: Search
    try:
        provider, results = runtime.search(query, max_results=max_results, timeout_seconds=context.command_timeout_seconds)
    except Exception as exc:
        raise ToolExecutionError(f"Deep search failed: {exc}") from exc

    lines = [
        "# Deep Search",
        f"- Provider: {provider.name} ({provider.provider})",
        f"- Query: {query}",
        f"- Mode: {mode}",
        f"- Results: {len(results)}",
        "",
    ]

    if not results:
        lines.append("No search results found.")
        return "\n".join(lines)

    # Format search results with snippets
    lines.append("## 搜索结果")
    lines.append("")
    for r in results:
        lines.append(f"{r.rank}. **{r.title}**")
        lines.append(f"   URL: {r.url}")
        if r.snippet:
            lines.append(f"   Snippet: {r.snippet[:300]}")
        lines.append("")

    # Layer 2: Deep read — fetch full content for each result
    if deep_read:
        urls = [r.url for r in results[:max_results]]
        contents = _fetch_all(urls)

        lines.append("---")
        lines.append("")
        lines.append("## 正文抓取")
        lines.append("")

        for i, (result, content) in enumerate(zip(results[:max_results], contents)):
            lines.append(f"### [{result.rank}] {result.title}")
            if content:
                cleaned = _clean_html(content)
                preview = cleaned[:MAX_CONTENT_CHARS]
                if len(cleaned) > MAX_CONTENT_CHARS:
                    preview += f"\n\n*(content truncated, {len(cleaned)} total chars)*"
                lines.append(preview)
            else:
                lines.append("*(无法抓取正文)*")
            lines.append("")

    # Analysis prompts
    analysis_prompt = _MODE_PROMPTS.get(mode, _MODE_PROMPTS["summary"])
    lines.append(analysis_prompt)

    return "\n".join(lines)


def _is_private_host(hostname: str) -> bool:
    """Check if a hostname resolves to a private/reserved IP address."""
    import ipaddress, socket
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        except (socket.gaierror, ValueError):
            return True  # block unresolvable hosts to be safe
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified


def _fetch_all(urls: list[str]) -> list[str]:
    """Fetch multiple URLs in parallel."""
    if not urls:
        return []

    def _fetch_one(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ""
        # Block SSRF: reject private/reserved IPs
        hostname = (parsed.hostname or "").strip("[]")
        if not hostname or _is_private_host(hostname):
            logger.warning("deep_search blocked SSRF attempt: %s", url)
            return ""
        try:
            with httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=False) as client:
                resp = client.get(url, headers={
                    "User-Agent": "Nexus-DeepSearch/1.0",
                    "Accept": "text/html,text/plain,*/*",
                })
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            logger.debug("deep_search fetch failed for %s: %s", url, exc)
            return ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(urls), 5)) as pool:
        return list(pool.map(_fetch_one, urls))


def _clean_html(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = _STRIP_SCRIPT_STYLE.sub(" ", html)
    text = _STRIP_HTML_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub("\n\n", text)
    return text.strip()[:MAX_CONTENT_CHARS * 2]  # generous input to account for cleaning


def create_deep_search_tool() -> Any:
    """Create the deep_search AgentTool for registration."""
    from factory.engine.bridge import AgentTool

    return AgentTool(
        name="deep_search",
        description=(
            "Deep web search with content extraction and structured analysis. "
            "Performs a real web search, fetches full page content for each result, "
            "and provides a mode-based analysis framework. "
            "Modes: summary (key findings + consensus + insights), "
            "compare (cross-source consistency + bias), "
            "fact_check (claim-by-claim verification table)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "mode": {
                    "type": "string",
                    "enum": ["summary", "compare", "fact_check"],
                    "description": "Analysis mode: summary, compare, or fact_check",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Number of results to fetch and analyze (max 10)",
                },
                "deep_read": {
                    "type": "boolean",
                    "description": "Whether to fetch full page content for each result",
                },
            },
            "required": ["query"],
        },
        handler=deep_search_handler,
    )
