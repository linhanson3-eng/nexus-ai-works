from __future__ import annotations
"""APScheduler 调度引擎 — 启停、增删、并发保护。"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

from .store import ScheduledTask, ScheduleStore
from factory.env import env_int

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 3
EXECUTION_TIMEOUT = env_int("SCHEDULE_EXECUTION_TIMEOUT", 600, min=10, max=3600)


class ScheduleEngine:
    """Manages APScheduler lifecycle for Nexus scheduled tasks."""

    def __init__(self, store: ScheduleStore | None = None) -> None:
        self._store = store or ScheduleStore()
        self._scheduler: BackgroundScheduler | None = None
        self._executor = None  # type: ignore[assignment] — set via configure

    def configure(self, executor) -> None:
        """Set the async executor for running agent tasks."""
        self._executor = executor

    # ── Lifecycle ──

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self._scheduler.start()
        # Load all enabled tasks from store
        for task in self._store.list_all():
            if task.enabled:
                self._add_job(task)
        logger.info("ScheduleEngine started — %d jobs loaded", len(self._scheduler.get_jobs()))

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("ScheduleEngine stopped")

    # ── Job management ──

    def _add_job(self, task: ScheduledTask) -> None:
        if self._scheduler is None:
            return
        try:
            self._scheduler.add_job(
                self._execute,
                CronTrigger.from_crontab(task.cron_expr, timezone=task.timezone or "Asia/Shanghai"),
                args=(task.id,),
                id=task.id,
                name=task.name,
                replace_existing=True,
            )
        except Exception as exc:
            logger.error("Failed to add job %s: %s", task.id, exc)

    def _remove_job(self, task_id: str) -> None:
        if self._scheduler is None:
            return
        try:
            self._scheduler.remove_job(task_id)
        except JobLookupError:
            pass

    def add_task(self, task: ScheduledTask) -> None:
        if task.enabled:
            self._add_job(task)

    def remove_task(self, task_id: str) -> None:
        self._remove_job(task_id)

    def toggle_task(self, task_id: str) -> ScheduledTask | None:
        task = self._store.toggle(task_id)
        if task is None:
            return None
        if task.enabled:
            self._add_job(task)
        else:
            self._remove_job(task_id)
        return task

    def run_now(self, task_id: str) -> ScheduledTask | None:
        """Trigger immediate execution, unless already running."""
        task = self._store.get(task_id)
        if task is None:
            return None
        if task.is_running:
            logger.info("Task %s is already running — skipping", task_id)
            return task
        if self._executor is not None:
            self._executor(task)
        return task

    def resume_task(self, task_id: str) -> ScheduledTask | None:
        """Resume a paused task: reset failures, re-enable, re-add job."""
        task = self._store.update(task_id, enabled=True, consecutive_failures=0)
        if task is None:
            return None
        self._add_job(task)
        return task

    def get_next_run(self, task_id: str) -> str | None:
        if self._scheduler is None:
            return None
        try:
            job = self._scheduler.get_job(task_id)
            if job is None or job.next_run_time is None:
                return None
            return job.next_run_time.isoformat()
        except (JobLookupError, AttributeError):
            return None

    # ── Execution ──

    def _execute(self, task_id: str) -> None:
        """Called by APScheduler when a job fires."""
        task = self._store.get(task_id)
        if task is None:
            self._remove_job(task_id)
            return
        if task.is_running:
            logger.info("Job %s skipped — still running", task_id)
            return

        self._store.mark_running(task_id)
        try:
            if self._executor is not None:
                self._executor(task)
        except Exception as exc:
            logger.exception("ScheduleEngine execution failed for %s: %s", task_id, exc)
            self._store.record_result(task_id, status="failed", output=str(exc), duration_seconds=0)
