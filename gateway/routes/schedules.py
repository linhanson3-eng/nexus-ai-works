from __future__ import annotations
"""定时任务 API 端点。"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from factory.scheduler.store import ScheduledTask, ScheduleStore
from gateway.auth import require_auth

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _store() -> ScheduleStore:
    return ScheduleStore()


def _engine(request: Request):
    return request.app.state.schedule_engine


# ── CRUD ──


@router.get("", dependencies=[Depends(require_auth)])
async def list_schedules():
    store = _store()
    tasks = store.list_all()
    return JSONResponse(content=[t.to_dict() for t in tasks])


@router.post("", dependencies=[Depends(require_auth)])
async def create_schedule(body: dict, request: Request):
    store = _store()
    task = ScheduledTask(
        name=body.get("name", ""),
        prompt=body.get("prompt", ""),
        workshop=body.get("workshop", ""),
        frequency=body.get("frequency", "daily"),
        time_str=body.get("time_str", "09:00"),
        weekday=body.get("weekday"),
        monthday=body.get("monthday"),
        timezone=body.get("timezone", "Asia/Shanghai"),
        model=body.get("model", ""),
    )
    task = store.create(task)
    _engine(request).add_task(task)
    return JSONResponse(content=task.to_dict(), status_code=201)


@router.put("/{task_id}", dependencies=[Depends(require_auth)])
async def update_schedule(task_id: str, body: dict, request: Request):
    store = _store()
    allowed = {"name", "prompt", "workshop", "frequency", "time_str", "weekday", "monthday", "timezone", "model"}
    updates = {k: v for k, v in body.items() if k in allowed}
    task = store.update(task_id, **updates)
    if task is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    # Re-sync with scheduler
    _engine(request)._remove_job(task_id)
    if task.enabled:
        _engine(request)._add_job(task)
    return JSONResponse(content=task.to_dict())


@router.delete("/{task_id}", dependencies=[Depends(require_auth)])
async def delete_schedule(task_id: str, request: Request):
    store = _store()
    _engine(request)._remove_job(task_id)
    ok = store.delete(task_id)
    if not ok:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content={"deleted": task_id})


# ── Operations ──


@router.post("/{task_id}/toggle", dependencies=[Depends(require_auth)])
async def toggle_schedule(task_id: str, request: Request):
    task = _engine(request).toggle_task(task_id)
    if task is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content=task.to_dict())


@router.post("/{task_id}/run-now", dependencies=[Depends(require_auth)])
async def run_now(task_id: str, request: Request):
    task = _engine(request).run_now(task_id)
    if task is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    if task.is_running:
        return JSONResponse(content={"detail": "Task is already running"}, status_code=409)
    return JSONResponse(content={"status": "triggered", "task_id": task_id})


@router.post("/{task_id}/resume", dependencies=[Depends(require_auth)])
async def resume_schedule(task_id: str, request: Request):
    task = _engine(request).resume_task(task_id)
    if task is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content=task.to_dict())


# ── Templates ──


@router.get("/templates", dependencies=[Depends(require_auth)])
async def list_templates():
    store = _store()
    tmpls = store.list_templates()
    return JSONResponse(content=[
        {
            "name": t.name, "icon": t.icon, "description": t.description,
            "preview": t.preview, "category": t.category,
            "default_frequency": t.default_frequency, "default_time": t.default_time,
        }
        for t in tmpls
    ])


@router.post("/parse", dependencies=[Depends(require_auth)])
async def parse_input(body: dict):
    """Preview: try to match a user's custom input to a template."""
    user_text = body.get("text", "").strip()
    if not user_text:
        return JSONResponse(content={"matched": False})

    store = _store()
    match = store.match_template(user_text)
    if match is not None:
        return JSONResponse(content={
            "matched": True,
            "template_name": match.name,
            "preview": match.preview,
            "prompt": match.prompt,
            "default_frequency": match.default_frequency,
            "default_time": match.default_time,
        })
    return JSONResponse(content={"matched": False})


# ── Chat integration ──


@router.post("/chat", dependencies=[Depends(require_auth)])
async def chat_create(body: dict, request: Request):
    """Natural-language task creation from chat. Returns追问 if time is ambiguous."""
    user_text = body.get("text", "").strip()
    if not user_text:
        return JSONResponse(content={"detail": "Empty text"}, status_code=400)

    store = _store()

    # Parse time
    hour, minute = _extract_time(user_text)
    has_explicit_time = hour is not None

    # Parse frequency
    frequency = "daily"
    if any(w in user_text for w in ("工作日", "周一到周五")):
        frequency = "workday"
    elif "每周" in user_text:
        frequency = "weekly"
    elif "每月" in user_text:
        frequency = "monthly"

    # If time is ambiguous, ask
    if not has_explicit_time:
        return JSONResponse(content={
            "needs_time": True,
            "frequency": frequency,
            "suggestions": ["07:00", "08:00", "09:00", "18:00"],
            "message": "几点执行比较合适？",
        })

    time_str = f"{hour:02d}:{minute:02d}"

    # Try template matching
    match = store.match_template(user_text)

    if match is not None:
        task = ScheduledTask(
            name=match.name,
            prompt=match.prompt,
            workshop=body.get("workshop", ""),
            frequency=frequency,
            time_str=time_str,
        )
        task = store.create(task)
        _engine(request).add_task(task)
        return JSONResponse(content={
            "created": True,
            "task": task.to_dict(),
            "template_matched": True,
            "template_preview": match.preview,
        })

    # No template match — create with raw prompt
    auto_name = _auto_name(user_text)
    task = ScheduledTask(
        name=body.get("name", auto_name),
        prompt=user_text,
        workshop=body.get("workshop", ""),
        frequency=frequency,
        time_str=time_str,
    )
    task = store.create(task)
    _engine(request).add_task(task)
    return JSONResponse(content={
        "created": True,
        "task": task.to_dict(),
        "template_matched": False,
        "auto_name": auto_name,
    })


# ── Helpers ──


def _extract_time(text: str) -> tuple[int | None, int | None]:
    """Extract hour and minute from Chinese time expressions."""
    import re

    # "9点" / "9:30" / "9点半" / "晚上8点" / "早上9点"
    m = re.search(r"(\d{1,2})[点:：](\d{1,2})?", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        # PM offset
        if any(w in text for w in ("下午", "晚上", "傍晚")):
            if hour < 12:
                hour += 12
        elif "中午" in text and hour < 12:
            hour += 12
        return hour, minute

    # "早上" / "上午" / "中午" / "下午" / "晚上" without number
    if any(w in text for w in ("早上", "上午", "早晨")):
        return None, None  # ambiguous — ask
    if "中午" in text:
        return 12, 0
    if "下午" in text:
        return None, None  # ambiguous
    if any(w in text for w in ("晚上", "傍晚")):
        return None, None

    return None, None


def _auto_name(text: str) -> str:
    """Generate a short name from user's text."""
    # Remove common prefixes
    import re
    cleaned = re.sub(r"以后|每天|每小时|工作日|每周|每月|帮我|提醒我|检查|总结|监控", "", text)
    cleaned = cleaned.strip()
    # Take first 6 chars
    return cleaned[:6] if cleaned else "自定义任务"
