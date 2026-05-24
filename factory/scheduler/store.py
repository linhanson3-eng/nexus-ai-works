from __future__ import annotations
"""定时任务 JSON 持久化存储。"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .templates import TEMPLATES, Template

DEFAULT_STORE_PATH = Path("~/.nexus/schedules.json").expanduser()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _frequency_to_cron(frequency: str, time_str: str, weekday: int | None, monthday: int | None) -> str:
    """Convert frequency + time to cron expression."""
    parts = time_str.split(":")
    hour = int(parts[0]) if len(parts) > 0 else 9
    minute = int(parts[1]) if len(parts) > 1 else 0

    if frequency == "daily":
        return f"{minute} {hour} * * *"
    elif frequency == "workday":
        return f"{minute} {hour} * * 1-5"
    elif frequency == "weekly":
        d = weekday or 1
        return f"{minute} {hour} * * {d}"
    elif frequency == "monthly":
        d = monthday or 1
        return f"{minute} {hour} {d} * *"
    return f"{minute} {hour} * * *"


class ScheduledTask:
    """Mutable task object for store operations."""

    def __init__(
        self,
        *,
        id: str = "",
        name: str = "",
        prompt: str = "",
        workshop: str = "",
        frequency: str = "daily",
        time_str: str = "09:00",
        weekday: int | None = None,
        monthday: int | None = None,
        timezone: str = "Asia/Shanghai",
        cron_expr: str = "",
        enabled: bool = True,
        model: str = "",
        is_running: bool = False,
        last_run_at: str | None = None,
        last_status: str | None = None,
        last_output: str | None = None,
        next_run_at: str | None = None,
        run_history: list[dict] | None = None,
        consecutive_failures: int = 0,
        run_count: int = 0,
        created_at: str = "",
    ):
        self.id = id or uuid.uuid4().hex[:12]
        self.name = name
        self.prompt = prompt
        self.workshop = workshop
        self.frequency = frequency
        self.time_str = time_str
        self.weekday = weekday
        self.monthday = monthday
        self.timezone = timezone
        self.cron_expr = cron_expr or _frequency_to_cron(frequency, time_str, weekday, monthday)
        self.enabled = enabled
        self.model = model
        self.is_running = is_running
        self.last_run_at = last_run_at
        self.last_status = last_status
        self.last_output = last_output
        self.next_run_at = next_run_at
        self.run_history: list[dict] = run_history or []
        self.consecutive_failures = consecutive_failures
        self.run_count = run_count
        self.created_at = created_at or _now_iso()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "workshop": self.workshop,
            "frequency": self.frequency,
            "time_str": self.time_str,
            "weekday": self.weekday,
            "monthday": self.monthday,
            "timezone": self.timezone,
            "cron_expr": self.cron_expr,
            "enabled": self.enabled,
            "model": self.model,
            "is_running": self.is_running,
            "last_run_at": self.last_run_at,
            "last_status": self.last_status,
            "last_output": self.last_output,
            "next_run_at": self.next_run_at,
            "run_history": self.run_history,
            "consecutive_failures": self.consecutive_failures,
            "run_count": self.run_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ScheduledTask:
        return cls(**d)


class ScheduleStore:
    """JSON file persistence for scheduled tasks."""

    def __init__(self, path: str | Path = DEFAULT_STORE_PATH) -> None:
        self._path = Path(path).expanduser()
        self._tasks: dict[str, ScheduledTask] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._tasks = {}
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._tasks = {tid: ScheduledTask.from_dict(d) for tid, d in data.get("tasks", {}).items()}
        except (json.JSONDecodeError, KeyError):
            self._tasks = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()}}
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    # ── CRUD ──

    def list_all(self) -> list[ScheduledTask]:
        return list(self._tasks.values())

    def get(self, task_id: str) -> ScheduledTask | None:
        return self._tasks.get(task_id)

    def create(self, task: ScheduledTask) -> ScheduledTask:
        self._tasks[task.id] = task
        self._save()
        return task

    def update(self, task_id: str, **fields) -> ScheduledTask | None:
        t = self._tasks.get(task_id)
        if t is None:
            return None
        for k, v in fields.items():
            if hasattr(t, k):
                setattr(t, k, v)
        # Recompute cron if frequency/time changed
        if any(k in fields for k in ("frequency", "time_str", "weekday", "monthday")):
            t.cron_expr = _frequency_to_cron(t.frequency, t.time_str, t.weekday, t.monthday)
        self._save()
        return t

    def delete(self, task_id: str) -> bool:
        if task_id not in self._tasks:
            return False
        del self._tasks[task_id]
        self._save()
        return True

    # ── Operations ──

    def toggle(self, task_id: str) -> ScheduledTask | None:
        t = self._tasks.get(task_id)
        if t is None:
            return None
        t.enabled = not t.enabled
        self._save()
        return t

    def mark_running(self, task_id: str) -> ScheduledTask | None:
        t = self._tasks.get(task_id)
        if t is None:
            return None
        t.is_running = True
        self._save()
        return t

    def record_result(self, task_id: str, *, status: str, output: str, duration_seconds: float) -> ScheduledTask | None:
        t = self._tasks.get(task_id)
        if t is None:
            return None
        now = _now_iso()
        t.is_running = False
        t.last_run_at = now
        t.last_status = status
        t.last_output = output[:200]
        t.run_count += 1

        # Update run history (last 5)
        t.run_history.append({
            "time": now,
            "status": status,
            "duration": round(duration_seconds, 1),
            "output_summary": output[:120],
        })
        if len(t.run_history) > 5:
            t.run_history = t.run_history[-5:]

        # Consecutive failures tracking
        if status == "success":
            t.consecutive_failures = 0
        else:
            t.consecutive_failures += 1
            if t.consecutive_failures >= 3:
                t.enabled = False  # auto-pause

        self._save()
        return t

    # ── Templates ──

    @staticmethod
    def list_templates() -> list[Template]:
        return list(TEMPLATES)

    @staticmethod
    def match_template(user_text: str) -> Template | None:
        """Simple keyword match — no LLM."""
        text = user_text.lower()
        best: Template | None = None
        best_score = 0
        for tmpl in TEMPLATES:
            keywords = set(tmpl.name) | set(tmpl.description) | set(tmpl.preview)
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best = tmpl
        return best if best_score >= 2 else None
