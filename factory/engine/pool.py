from __future__ import annotations

"""Agent pool — concurrency control and lifecycle management.

ThreadPoolExecutor for agent execution + asyncio.Semaphore
for concurrency gating. Inspired by OneManAI's coo_runtime.py pattern.
"""


import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from factory.engine.bridge import AgentLoopEngine, EngineConfig, create_agent

# ── Global thread pool (shared across all workshops) ────────────

from factory.env import env_int as _env_int
_AGENT_POOL_SIZE = _env_int("NX_AGENT_POOL_SIZE", 8, min=1, max=64)
_executor = ThreadPoolExecutor(max_workers=_AGENT_POOL_SIZE, thread_name_prefix="nexus-agent-")


class AgentPool:
    """Manages AgentLoopEngine instances with caching and concurrency control.

    One pool per Nexus process. Agents are cached by key (typically
    workshop_name:agent_name) and reused across requests.
    """

    def __init__(self, max_concurrent: int = 8, default_timeout: float = 600.0):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._default_timeout = default_timeout
        self._agents: dict[str, AgentLoopEngine] = {}
        self._lock = threading.Lock()
        self._active_requests: dict[str, str] = {}

    def get_or_create(
        self,
        key: str,
        model_config: Any,
        engine_config: EngineConfig,
        *,
        append_system_prompt: str | None = None,
    ) -> AgentLoopEngine:
        """Get a cached agent or create a new one."""
        with self._lock:
            if key in self._agents:
                engine = self._agents[key]
                if engine.agent is not None:
                    return engine
            agent = create_agent(
                model_config=model_config,
                engine_config=engine_config,
                append_system_prompt=append_system_prompt,
            )
            engine = AgentLoopEngine(agent, engine_config=engine_config)
            self._agents[key] = engine
            return engine

    def invalidate(self, key: str) -> None:
        """Remove a cached agent (e.g. after config change)."""
        with self._lock:
            engine = self._agents.pop(key, None)
            if engine:
                engine.invalidate()

    def invalidate_all(self) -> None:
        with self._lock:
            for engine in self._agents.values():
                engine.invalidate()
            self._agents.clear()

    async def acquire(self) -> None:
        await self._semaphore.acquire()

    def release(self) -> None:
        self._semaphore.release()

    @property
    def active_count(self) -> int:
        return 8 - self._semaphore._value  # type: ignore[attr-defined]

    async def execute(
        self,
        engine: AgentLoopEngine,
        prompt: str | list[dict],
        *,
        resume: bool = False,
        timeout: float | None = None,
    ) -> Any:
        """Execute an agent run with concurrency control and timeout.

        Args:
            engine: The AgentLoopEngine to execute.
            prompt: User prompt or message list.
            resume: If True, attempt to resume from last session.
            timeout: Override default timeout.

        Returns:
            AgentRunResult from claw-code-agent.
        """
        timeout = timeout or self._default_timeout

        await self._semaphore.acquire()
        try:
            loop = asyncio.get_running_loop()
            if resume:
                future = _executor.submit(
                    _run_in_thread, engine, prompt, resume=True
                )
            else:
                future = _executor.submit(
                    _run_in_thread, engine, prompt, resume=False
                )
            result = await asyncio.wait_for(
                asyncio.wrap_future(future, loop=loop),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            raise
        finally:
            self._semaphore.release()


def _run_in_thread(
    engine: AgentLoopEngine,
    prompt: str | list[dict],
    *,
    resume: bool = False,
) -> Any:
    """Execute agent.run() or agent.resume() in a thread pool worker."""
    import asyncio as _asyncio

    loop = _asyncio.new_event_loop()
    _asyncio.set_event_loop(loop)
    try:
        if resume:
            return loop.run_until_complete(engine.resume(prompt))
        return loop.run_until_complete(engine.run(prompt))
    finally:
        loop.close()


# ── Module-level singleton ──────────────────────────────────────

_pool: AgentPool | None = None


def get_pool() -> AgentPool:
    global _pool
    if _pool is None:
        _pool = AgentPool()
    return _pool
