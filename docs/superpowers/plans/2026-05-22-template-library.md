# 本地模板库 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建本地模板库系统，用户可将车间中验证好的工作流/Agent/角色保存入库，支持浏览搜索和安装复用。

**Architecture:** `LibraryStore` (SQLite 索引 + YAML 正文) 作为核心存储层，FastAPI APIRouter 提供 REST API，CLI `library` 命令组提供命令行入口，前端 `TemplateLibrary` 组件提供 UI。

**Tech Stack:** Python 3.11+, Pydantic v2, SQLite+FTS5, FastAPI, YAML

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `factory/template.py` | **Delete** | 旧 TemplateLibrary，被 LibraryStore 替代 |
| `factory/library/__init__.py` | Create | 模块初始化 |
| `factory/library/models.py` | Create | LibraryEntry Pydantic 模型 |
| `factory/library/store.py` | Create | LibraryStore — SQLite + YAML CRUD |
| `factory/library/test_store.py` | Create | 单元测试 |
| `gateway/routes/library.py` | Create | API 端点 |
| `factory/org.py` | Modify | 移除 TemplateLibrary 引用 |
| `factory/workshop/manager.py` | Modify | 移除 TemplateLibrary 引用 |
| `factory/cli.py` | Modify | 追加 library 命令处理 |
| `entrypoint.py` | Modify | 追加 library 子命令解析 |
| `gateway/server.py` | Modify | 注册 library router |
| `gateway/test_server.py` | Modify | 追加 library API 测试 |
| `webui/src/components/TemplateLibrary.tsx` | Create | 前端「我的模板」页面 |
| `webui/src/lib/types.ts` | Modify | 追加 LibraryEntry 类型 |
| `webui/src/lib/api.ts` | Modify | 追加 library API 调用 |

---

### Task 1: 删除旧 TemplateLibrary 并更新引用

**Files:**
- Delete: `factory/template.py`
- Modify: `factory/org.py`
- Modify: `factory/workshop/manager.py`
- Modify: `entrypoint.py`

- [ ] **Step 1: 删除 factory/template.py**

Run: `rm /Users/linhan/ai-factory/factory/template.py`

- [ ] **Step 2: 更新 factory/org.py — 移除 TemplateLibrary 导入和引用**

在 `factory/org.py` 中：

删除第 11 行的 import：
```python
from factory.template import TemplateLibrary
```

修改第 82 行，`OrgEngine.__init__` 中移除 `self.templates = TemplateLibrary()`：
```python
# 删除这一行
self.templates = TemplateLibrary()
```

修改 `Workshop.__init__` 构造函数（第 19 行），移除 `templates` 参数：
```python
# 旧:
def __init__(self, spec: DepartmentSpec, templates: TemplateLibrary, warehouse: "Warehouse"):
    self._templates = templates

# 新:
def __init__(self, spec: DepartmentSpec, warehouse: "Warehouse"):
    pass  # no templates reference needed
```

修改 `_spawn_agents` 方法（第 40-48 行），移除 `self._templates.create_agent_spec()` 调用。当 agent 有 `template` 字段时，改为直接用 bare AgentSpec 创建（后续由 LibraryStore 接管模板解析）：

```python
# 旧:
tmpl_name = getattr(agent_cfg, "template", "")
spec = self._templates.create_agent_spec(template_name=tmpl_name, name=aname, type=agent_type, model=agent_cfg.model)

# 新:
spec = AgentSpec(
    name=aname,
    type=agent_type,
    model=agent_cfg.model,
    template=tmpl_name,
)
```

修改第 100 行和第 108 行，`Workshop(...)` 调用移除 `templates` 参数：
```python
# 旧:
Workshop(dept_spec, self.templates, self.warehouse)

# 新:
Workshop(dept_spec, self.warehouse)
```

- [ ] **Step 3: 更新 factory/workshop/manager.py — 移除 TemplateLibrary 引用**

修改第 60-61 行：
```python
# 旧:
self.org.templates.create_agent_spec(template_name=aname, name=aname, model=model)

# 新:
AgentSpec(name=aname, model=model)
```

需要追加 import:
```python
from config.schema import AgentSpec
```

- [ ] **Step 4: 更新 entrypoint.py — 移除 TemplateLibrary 相关打印**

修改第 146 行，删除关于模板数量的输出行：
```python
# 删除:
print(f"  Agent 模板: {len(org.templates.list_all())} 个")
```

- [ ] **Step 5: 运行测试确认无回归**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/ gateway/ --tb=short 2>&1 | tail -10`
Expected: 407 passed

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove old TemplateLibrary, prepare for LibraryStore"
```

---

### Task 2: 创建 LibraryEntry 模型

**Files:**
- Create: `factory/library/__init__.py`
- Create: `factory/library/models.py`

- [ ] **Step 1: 创建 factory/library/__init__.py**

```python
"""Local template library — save, search, and reuse proven templates."""
```

- [ ] **Step 2: 创建 factory/library/models.py**

```python
"""Pydantic models for the local template library."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EntryType(str, Enum):
    WORKFLOW = "workflow"
    AGENT = "agent"
    ROLE = "role"


class LibraryEntry(BaseModel):
    """A saved template in the local library."""

    id: str = ""
    entry_type: EntryType
    name: str
    description: str = ""
    category: str = "其他"
    tags: list[str] = Field(default_factory=list)
    source_workshop: str = ""
    version: str = "1.0.0"
    created_at: str = ""
    body: str = ""  # YAML content of the template


class SaveRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "其他"
    tags: list[str] = Field(default_factory=list)
    workshop: str = ""


class InstallRequest(BaseModel):
    workshop: str
```

- [ ] **Step 3: Commit**

```bash
git add factory/library/__init__.py factory/library/models.py
git commit -m "feat: add LibraryEntry Pydantic models"
```

---

### Task 3: 创建 LibraryStore

**Files:**
- Create: `factory/library/store.py`

- [ ] **Step 1: 创建 factory/library/store.py**

```python
"""LibraryStore — SQLite-indexed, YAML-backed local template library.

Storage layout:
  ~/.nexus/library/
    library.db          SQLite index + FTS5 search
    workflows/          {name}.yaml
    agents/             {name}.yaml
    roles/              {name}.yaml
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from factory.library.models import EntryType, LibraryEntry

LIBRARY_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    entry_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '其他',
    tags TEXT NOT NULL DEFAULT '[]',
    source_workshop TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '1.0.0',
    created_at TEXT NOT NULL,
    body_path TEXT NOT NULL,
    UNIQUE(entry_type, name)
);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    name, description, category, tags, content='entries', content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, name, description, category, tags)
    VALUES (new.rowid, new.name, new.description, new.category, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, name, description, category, tags)
    VALUES ('delete', old.rowid, old.name, old.description, old.category, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, name, description, category, tags)
    VALUES ('delete', old.rowid, old.name, old.description, old.category, old.tags);
    INSERT INTO entries_fts(rowid, name, description, category, tags)
    VALUES (new.rowid, new.name, new.description, new.category, new.tags);
END;
"""


class LibraryStore:
    """Manages saved templates with SQLite index + YAML file storage."""

    def __init__(self, root: str | Path = "~/.nexus/library") -> None:
        self._root = Path(root).expanduser().resolve()
        self._db_path = self._root / "library.db"
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        import sqlite3

        self._root.mkdir(parents=True, exist_ok=True)
        for sub in ("workflows", "agents", "roles"):
            (self._root / sub).mkdir(exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript(LIBRARY_SQL)
        conn.commit()
        conn.close()

    def _conn(self):
        import sqlite3

        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _yaml_path(self, entry_type: EntryType, name: str) -> Path:
        return self._root / f"{entry_type.value}s" / f"{name}.yaml"

    def _row_to_entry(self, row) -> LibraryEntry:
        path = Path(row["body_path"])
        body = path.read_text(encoding="utf-8") if path.exists() else ""
        return LibraryEntry(
            id=row["id"],
            entry_type=EntryType(row["entry_type"]),
            name=row["name"],
            description=row["description"],
            category=row["category"],
            tags=json.loads(row["tags"]),
            source_workshop=row["source_workshop"],
            version=row["version"],
            created_at=row["created_at"],
            body=body,
        )

    # ── Save ──

    def save(
        self,
        entry_type: EntryType,
        name: str,
        body: str,
        description: str = "",
        category: str = "其他",
        tags: list[str] | None = None,
        source_workshop: str = "",
    ) -> LibraryEntry:
        """Save a template to the library. Overwrites if same type+name exists."""
        now = datetime.now(timezone.utc).isoformat()
        entry_id = str(uuid.uuid4())[:8]
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        yaml_path = self._yaml_path(entry_type, name)
        yaml_path.write_text(body, encoding="utf-8")

        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM entries WHERE entry_type = ? AND name = ?",
                (entry_type.value, name),
            ).fetchone()
            if existing:
                entry_id = existing["id"]
                conn.execute(
                    "UPDATE entries SET description=?, category=?, tags=?, "
                    "source_workshop=?, version=?, created_at=?, body_path=? "
                    "WHERE id=?",
                    (description, category, tags_json, source_workshop,
                     "1.0.0", now, str(yaml_path), entry_id),
                )
            else:
                conn.execute(
                    "INSERT INTO entries (id, entry_type, name, description, "
                    "category, tags, source_workshop, version, created_at, body_path) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (entry_id, entry_type.value, name, description, category,
                     tags_json, source_workshop, "1.0.0", now, str(yaml_path)),
                )
            conn.commit()
        finally:
            conn.close()
        return self.get(entry_type, name)  # type: ignore[return-value]

    # ── List ──

    def list_all(
        self,
        entry_type: EntryType,
        search: str = "",
        category: str = "",
        tag: str = "",
    ) -> list[LibraryEntry]:
        """List templates, with optional search/category/tag filter."""
        conn = self._conn()
        try:
            if search:
                rows = conn.execute(
                    "SELECT e.* FROM entries e JOIN entries_fts f ON e.rowid = f.rowid "
                    "WHERE e.entry_type = ? AND entries_fts MATCH ? "
                    "ORDER BY e.created_at DESC",
                    (entry_type.value, search),
                ).fetchall()
            else:
                where = "WHERE entry_type = ?"
                params: list = [entry_type.value]
                if category:
                    where += " AND category = ?"
                    params.append(category)
                rows = conn.execute(
                    f"SELECT * FROM entries {where} ORDER BY created_at DESC",
                    params,
                ).fetchall()

            entries = [self._row_to_entry(r) for r in rows]
            if tag:
                entries = [e for e in entries if tag in e.tags]
            return entries
        finally:
            conn.close()

    # ── Get ──

    def get(self, entry_type: EntryType, name: str) -> LibraryEntry | None:
        """Get a single template by type and name."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM entries WHERE entry_type = ? AND name = ?",
                (entry_type.value, name),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_entry(row)
        finally:
            conn.close()

    # ── Delete ──

    def delete(self, entry_type: EntryType, name: str) -> bool:
        """Delete a template from the library. Returns True if deleted."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT body_path FROM entries WHERE entry_type = ? AND name = ?",
                (entry_type.value, name),
            ).fetchone()
            if row is None:
                return False
            # Remove YAML file
            path = Path(row["body_path"])
            if path.exists():
                path.unlink()
            # Remove DB entry
            conn.execute(
                "DELETE FROM entries WHERE entry_type = ? AND name = ?",
                (entry_type.value, name),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    # ── Install helpers ──

    def install_workflow(self, name: str, workflow_store) -> bool:
        """Install a workflow template from library into WorkflowStore."""
        from factory.workflow.models import WorkflowNode, WorkflowTemplate

        entry = self.get(EntryType.WORKFLOW, name)
        if entry is None:
            return False
        data = yaml.safe_load(entry.body)
        nodes = [WorkflowNode.from_dict(n) for n in data.get("nodes", [])]
        tmpl = WorkflowTemplate(
            name=data["name"],
            description=data.get("description", ""),
            workspace=data.get("workspace", ""),
            nodes=nodes,
        )
        workflow_store.save(tmpl)
        return True

    def install_agent(self, name: str, workshop_name: str, org) -> bool:
        """Install an agent template into a target workshop."""
        from factory.workshop.manager import WorkshopManager

        entry = self.get(EntryType.AGENT, name)
        if entry is None:
            return False
        data = yaml.safe_load(entry.body)
        spec = AgentSpec(**data) if "name" in data else AgentSpec(name=name, **data)

        from factory.kanban import KanbanStore
        mgr = WorkshopManager(org, KanbanStore())
        result = mgr.add_agent(workshop_name, spec)
        return result is not None

    def install_role(self, name: str) -> bool:
        """Install a role template into config/roles/."""
        entry = self.get(EntryType.ROLE, name)
        if entry is None:
            return False
        dest = Path("config/roles") / f"{name}.yaml"
        dest.write_text(entry.body, encoding="utf-8")
        return True


# ── Static helpers for CLI/API ──

def save_workflow_to_library(store: LibraryStore, name: str, org, **meta) -> LibraryEntry:
    """Save a workflow from WorkflowStore into the library."""
    tmpl = org.workflow_store.load(name)
    if tmpl is None:
        raise ValueError(f"Workflow not found: {name}")
    body = yaml.dump(tmpl.to_dict(), allow_unicode=True, default_flow_style=False)
    return store.save(
        entry_type=EntryType.WORKFLOW,
        name=name,
        body=body,
        description=meta.get("description", tmpl.description),
        category=meta.get("category", "其他"),
        tags=meta.get("tags", []),
        source_workshop=meta.get("source_workshop", ""),
    )


def save_agent_to_library(
    store: LibraryStore, name: str, workshop_name: str, org, **meta
) -> LibraryEntry:
    """Save an agent config from a workshop into the library."""
    from factory.kanban import KanbanStore
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(org, KanbanStore())
    agents = mgr.list_agents(workshop_name)
    if agents is None:
        raise ValueError(f"Workshop not found: {workshop_name}")
    target = next((a for a in agents if a["name"] == name), None)
    if target is None:
        raise ValueError(f"Agent not found: {name} in workshop {workshop_name}")
    body = yaml.dump(target, allow_unicode=True, default_flow_style=False)
    return store.save(
        entry_type=EntryType.AGENT,
        name=name,
        body=body,
        description=meta.get("description", ""),
        category=meta.get("category", "其他"),
        tags=meta.get("tags", []),
        source_workshop=workshop_name,
    )


def save_role_to_library(store: LibraryStore, name: str, role_file: str, **meta) -> LibraryEntry:
    """Save a role YAML file into the library."""
    path = Path(role_file)
    if not path.exists():
        raise ValueError(f"Role file not found: {role_file}")
    body = path.read_text(encoding="utf-8")
    return store.save(
        entry_type=EntryType.ROLE,
        name=name,
        body=body,
        description=meta.get("description", ""),
        category=meta.get("category", "其他"),
        tags=meta.get("tags", []),
    )
```

- [ ] **Step 2: Commit**

```bash
git add factory/library/store.py
git commit -m "feat: add LibraryStore with SQLite+FTS5 and YAML storage"
```

---

### Task 4: 编写 LibraryStore 单元测试

**Files:**
- Create: `factory/library/test_store.py`

- [ ] **Step 1: 创建 factory/library/test_store.py**

```python
"""Unit tests for LibraryStore."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from factory.library.models import EntryType
from factory.library.store import LibraryStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        s = LibraryStore(Path(tmp) / "library")
        yield s


class TestLibraryStoreSave:
    def test_save_and_get_workflow(self, store):
        body = "name: test-wf\ndescription: A test workflow\nnodes: []\n"
        entry = store.save(
            EntryType.WORKFLOW, "test-wf", body,
            description="A test workflow",
            category="代码工具",
            tags=["test", "demo"],
        )
        assert entry.name == "test-wf"
        assert entry.entry_type == EntryType.WORKFLOW
        assert entry.category == "代码工具"
        assert "test" in entry.tags
        assert entry.body == body

    def test_save_overwrites_existing(self, store):
        store.save(EntryType.WORKFLOW, "dup", "v1")
        store.save(EntryType.WORKFLOW, "dup", "v2")
        entry = store.get(EntryType.WORKFLOW, "dup")
        assert entry.body == "v2"

    def test_save_different_types_same_name(self, store):
        store.save(EntryType.WORKFLOW, "shared", "wf body")
        store.save(EntryType.AGENT, "shared", "agent body")
        wf = store.get(EntryType.WORKFLOW, "shared")
        ag = store.get(EntryType.AGENT, "shared")
        assert wf.body == "wf body"
        assert ag.body == "agent body"


class TestLibraryStoreList:
    def test_list_empty(self, store):
        assert store.list_all(EntryType.WORKFLOW) == []

    def test_list_by_type(self, store):
        store.save(EntryType.WORKFLOW, "wf1", "body1")
        store.save(EntryType.WORKFLOW, "wf2", "body2")
        store.save(EntryType.AGENT, "ag1", "body3")
        wfs = store.list_all(EntryType.WORKFLOW)
        assert len(wfs) == 2
        ags = store.list_all(EntryType.AGENT)
        assert len(ags) == 1

    def test_list_search(self, store):
        store.save(EntryType.WORKFLOW, "market-analysis", "body", description="市场分析工具")
        store.save(EntryType.WORKFLOW, "code-review", "body", description="代码审查")
        results = store.list_all(EntryType.WORKFLOW, search="市场")
        assert len(results) == 1
        assert results[0].name == "market-analysis"

    def test_list_category_filter(self, store):
        store.save(EntryType.WORKFLOW, "wf1", "b", category="代码工具")
        store.save(EntryType.WORKFLOW, "wf2", "b", category="市场分析")
        results = store.list_all(EntryType.WORKFLOW, category="市场分析")
        assert len(results) == 1


class TestLibraryStoreDelete:
    def test_delete_removes_entry(self, store):
        store.save(EntryType.WORKFLOW, "to-delete", "body")
        assert store.delete(EntryType.WORKFLOW, "to-delete") is True
        assert store.get(EntryType.WORKFLOW, "to-delete") is None

    def test_delete_nonexistent(self, store):
        assert store.delete(EntryType.WORKFLOW, "nonexistent") is False
```

- [ ] **Step 2: 运行测试**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/library/test_store.py -v --tb=short`
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add factory/library/test_store.py
git commit -m "test: add LibraryStore unit tests"
```

---

### Task 5: 创建 Library API 路由

**Files:**
- Create: `gateway/routes/library.py`
- Modify: `gateway/server.py`

- [ ] **Step 1: 创建 gateway/routes/library.py**

```python
"""Local template library API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from factory.library.models import EntryType, InstallRequest, SaveRequest
from factory.library.store import (
    LibraryStore,
    save_agent_to_library,
    save_role_to_library,
    save_workflow_to_library,
)

router = APIRouter(prefix="/api/library", tags=["library"])


def _store() -> LibraryStore:
    return LibraryStore()


def _org(request: Request):
    return request.app.state.org


# ── Save ──


@router.post("/{entry_type}")
async def save_entry(entry_type: str, body: SaveRequest, request: Request):
    try:  # noqa: SIM105
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(
            content={"detail": f"Invalid entry_type: {entry_type}. Use workflow/agent/role."},
            status_code=400,
        )
    store = _store()
    try:
        if et == EntryType.WORKFLOW:
            entry = save_workflow_to_library(
                store, body.name, _org(request),
                description=body.description, category=body.category,
                tags=body.tags, source_workshop=body.workshop,
            )
        elif et == EntryType.AGENT:
            entry = save_agent_to_library(
                store, body.name, body.workshop, _org(request),
                description=body.description, category=body.category,
                tags=body.tags,
            )
        else:
            entry = save_role_to_library(
                store, body.name, body.workshop or "config/roles",
                description=body.description, category=body.category,
                tags=body.tags,
            )
        return JSONResponse(content=entry.model_dump(), status_code=201)
    except ValueError as e:
        return JSONResponse(content={"detail": str(e)}, status_code=404)


# ── List ──


@router.get("/{entry_type}")
async def list_entries(
    entry_type: str,
    search: str = "",
    category: str = "",
    tag: str = "",
):
    try:
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(
            content={"detail": f"Invalid entry_type: {entry_type}"},
            status_code=400,
        )
    entries = _store().list_all(et, search=search, category=category, tag=tag)
    return JSONResponse(content=[e.model_dump() for e in entries])


# ── Get ──


@router.get("/{entry_type}/{name}")
async def get_entry(entry_type: str, name: str):
    try:
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(
            content={"detail": f"Invalid entry_type: {entry_type}"},
            status_code=400,
        )
    entry = _store().get(et, name)
    if entry is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content=entry.model_dump())


# ── Install ──


@router.post("/{entry_type}/{name}/install")
async def install_entry(entry_type: str, name: str, body: InstallRequest, request: Request):
    try:
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(content={"detail": f"Invalid entry_type: {entry_type}"}, status_code=400)
    store = _store()
    entry = store.get(et, name)
    if entry is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    org = _org(request)
    try:
        if et == EntryType.WORKFLOW:
            ok = store.install_workflow(name, org.workflow_store)
        elif et == EntryType.AGENT:
            ok = store.install_agent(name, body.workshop, org)
        else:
            ok = store.install_role(name)
        if not ok:
            return JSONResponse(content={"detail": "Install failed"}, status_code=500)
        return JSONResponse(content={"installed": name, "type": entry_type, "workshop": body.workshop})
    except Exception as e:
        return JSONResponse(content={"detail": str(e)}, status_code=500)


# ── Delete ──


@router.delete("/{entry_type}/{name}")
async def delete_entry(entry_type: str, name: str):
    try:
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(content={"detail": f"Invalid entry_type: {entry_type}"}, status_code=400)
    ok = _store().delete(et, name)
    if not ok:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content={"deleted": name})
```

- [ ] **Step 2: 注册 router 到 gateway/server.py**

在 `gateway/server.py` 的 imports 区追加：
```python
from gateway.routes.library import router as library_router
```

在 `app.include_router(ws_router)` 后面追加：
```python
    app.include_router(library_router)
```

- [ ] **Step 3: 运行现有测试确认无回归**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest gateway/ -v --tb=short 2>&1 | tail -10`
Expected: all existing tests pass

- [ ] **Step 4: Commit**

```bash
git add gateway/routes/library.py gateway/server.py
git commit -m "feat: add library API endpoints"
```

---

### Task 6: 添加 CLI library 命令

**Files:**
- Modify: `factory/cli.py`
- Modify: `entrypoint.py`

- [ ] **Step 1: factory/cli.py 追加 library 命令处理函数**

```python
def cmd_library(args):
    """Template library management commands."""
    if args.library_cmd == "list":
        _library_list(args)
    elif args.library_cmd == "save":
        _library_save(args)
    elif args.library_cmd == "show":
        _library_show(args)
    elif args.library_cmd == "install":
        _library_install(args)
    elif args.library_cmd == "delete":
        _library_delete(args)


def _library_list(args):
    from factory.library.store import LibraryStore
    from factory.library.models import EntryType

    et = EntryType(args.type)
    store = LibraryStore()
    search = getattr(args, "search", "") or ""
    category = getattr(args, "category", "") or ""
    entries = store.list_all(et, search=search, category=category)
    type_name = {"workflow": "生产方案", "agent": "智能体配置", "role": "岗位规格"}
    print(f"\n  我的模板 — {type_name.get(args.type, args.type)} ({len(entries)}):")
    if not entries:
        print("    (暂无)")
        return
    for e in entries:
        tags = f" [{', '.join(e.tags)}]" if e.tags else ""
        print(f"    [{e.category}] {e.name} v{e.version}{tags}")
        if e.description:
            print(f"      {e.description[:100]}")
        if e.source_workshop:
            print(f"      来源: {e.source_workshop}")


def _library_save(args):
    from factory.library.store import (
        LibraryStore,
        save_workflow_to_library,
        save_agent_to_library,
    )
    from factory.org import OrgEngine

    store = LibraryStore()
    org = OrgEngine("config/org.yaml")
    org.create_all()
    desc = getattr(args, "desc", "") or ""
    tags = [t.strip() for t in (getattr(args, "tags", "") or "").split(",") if t.strip()]
    category = getattr(args, "category", "其他") or "其他"
    workshop = getattr(args, "workshop", "") or ""

    try:
        if args.type == "workflow":
            entry = save_workflow_to_library(
                store, args.name, org,
                description=desc, category=category, tags=tags,
            )
        elif args.type == "agent":
            entry = save_agent_to_library(
                store, args.name, workshop, org,
                description=desc, category=category, tags=tags,
            )
        else:
            print(f"  不支持的类型: {args.type}")
            return
        print(f"  已入库: [{entry.category}] {entry.name}")
    except ValueError as e:
        print(f"  入库失败: {e}")


def _library_show(args):
    from factory.library.store import LibraryStore
    from factory.library.models import EntryType

    store = LibraryStore()
    entry = store.get(EntryType(args.type), args.name)
    if entry is None:
        print(f"  模板 '{args.name}' 不存在")
        return
    print(f"\n  {entry.name} v{entry.version}")
    print(f"  类型: {entry.entry_type.value}")
    print(f"  分类: {entry.category}")
    if entry.tags:
        print(f"  标签: {', '.join(entry.tags)}")
    if entry.description:
        print(f"  说明: {entry.description}")
    if entry.source_workshop:
        print(f"  来源: {entry.source_workshop}")
    print(f"  入库: {entry.created_at}")
    if entry.body:
        print(f"\n  --- 内容 ---")
        print(f"  {entry.body[:2000]}")


def _library_install(args):
    from factory.library.store import LibraryStore
    from factory.library.models import EntryType
    from factory.org import OrgEngine

    store = LibraryStore()
    org = OrgEngine("config/org.yaml")
    org.create_all()
    et = EntryType(args.type)
    workshop = getattr(args, "workshop", "") or ""

    if et == EntryType.WORKFLOW:
        ok = store.install_workflow(args.name, org.workflow_store)
    elif et == EntryType.AGENT:
        if not workshop:
            print("  Agent 安装需要指定 --workshop")
            return
        ok = store.install_agent(args.name, workshop, org)
    elif et == EntryType.ROLE:
        ok = store.install_role(args.name)
    else:
        print(f"  不支持的类型: {args.type}")
        return

    if ok:
        print(f"  已安装: {args.name} ({args.type})")
    else:
        print(f"  安装失败: 模板 '{args.name}' 不存在")


def _library_delete(args):
    from factory.library.store import LibraryStore
    from factory.library.models import EntryType

    store = LibraryStore()
    ok = store.delete(EntryType(args.type), args.name)
    if ok:
        print(f"  已删除: {args.name}")
    else:
        print(f"  模板 '{args.name}' 不存在")
```

- [ ] **Step 2: entrypoint.py 追加 library 子命令解析**

在 `entrypoint.py` 中，`# module` 解析块后面追加：

```python
    # library
    lib_p = sub.add_parser("library", help="模板库管理")
    lib_sub = lib_p.add_subparsers(dest="library_cmd")
    # list
    lib_list = lib_sub.add_parser("list", help="列出模板")
    lib_list.add_argument("type", choices=["workflow", "agent", "role"], help="模板类型")
    lib_list.add_argument("--search", default="", help="搜索关键词")
    lib_list.add_argument("--category", default="", help="按分类过滤")
    # save
    lib_save = lib_sub.add_parser("save", help="保存模板到库")
    lib_save.add_argument("type", choices=["workflow", "agent"], help="模板类型")
    lib_save.add_argument("name", help="模板名称")
    lib_save.add_argument("--workshop", "-w", default="", help="来源车间")
    lib_save.add_argument("--desc", default="", help="说明")
    lib_save.add_argument("--tags", default="", help="标签，逗号分隔")
    lib_save.add_argument("--category", default="其他", help="分类")
    # show
    lib_show = lib_sub.add_parser("show", help="查看模板详情")
    lib_show.add_argument("type", choices=["workflow", "agent", "role"], help="模板类型")
    lib_show.add_argument("name", help="模板名称")
    # install
    lib_install = lib_sub.add_parser("install", help="安装模板")
    lib_install.add_argument("type", choices=["workflow", "agent", "role"], help="模板类型")
    lib_install.add_argument("name", help="模板名称")
    lib_install.add_argument("--workshop", "-w", default="", help="目标车间")
    # delete
    lib_delete = lib_sub.add_parser("delete", help="删除模板")
    lib_delete.add_argument("type", choices=["workflow", "agent", "role"], help="模板类型")
    lib_delete.add_argument("name", help="模板名称")
```

在导入区追加：
```python
from factory.cli import (
    ...,
    cmd_library,
)
```

在 dispatch 区追加：
```python
    elif args.command == "library":
        cmd_library(args)
```

- [ ] **Step 3: 验证 CLI help 正常**

Run: `cd /Users/linhan/ai-factory && python3 entrypoint.py library --help`
Expected: 显示 library 帮助信息

- [ ] **Step 4: Commit**

```bash
git add factory/cli.py entrypoint.py
git commit -m "feat: add library CLI commands"
```

---

### Task 7: 前端 TemplateLibrary 组件 + API 类型

**Files:**
- Modify: `webui/src/lib/types.ts`
- Modify: `webui/src/lib/api.ts`
- Create: `webui/src/components/TemplateLibrary.tsx`
- Modify: `webui/src/App.tsx`

- [ ] **Step 1: webui/src/lib/types.ts 追加类型**

```typescript
export interface LibraryEntry {
  id: string;
  entry_type: "workflow" | "agent" | "role";
  name: string;
  description: string;
  category: string;
  tags: string[];
  source_workshop: string;
  version: string;
  created_at: string;
  body: string;
}
```

- [ ] **Step 2: webui/src/lib/api.ts 追加 library API**

```typescript
  // Library
  listLibrary: (type: string, search?: string, category?: string) =>
    get<LibraryEntry[]>(`/library/${type}?search=${search || ""}&category=${category || ""}`),
  getLibraryEntry: (type: string, name: string) =>
    get<LibraryEntry>(`/library/${type}/${encodeURIComponent(name)}`),
  saveToLibrary: (type: string, data: { name: string; description?: string; category?: string; tags?: string[]; workshop?: string }) =>
    post<LibraryEntry>(`/library/${type}`, data),
  installFromLibrary: (type: string, name: string, workshop: string) =>
    post<{ installed: string }>(`/library/${type}/${encodeURIComponent(name)}/install`, { workshop }),
  deleteFromLibrary: (type: string, name: string) =>
    del(`/library/${type}/${encodeURIComponent(name)}`),
```

- [ ] **Step 3: 创建 webui/src/components/TemplateLibrary.tsx**

React 组件，功能：
- 三个 Tab：生产方案 / 智能体配置 / 岗位规格
- 搜索框 + 分类下拉
- 模板列表（名称、分类、标签、来源、版本）
- 安装按钮（弹出选择目标车间）
- 删除按钮

```tsx
import { useState, useEffect } from "react";
import { api } from "../lib/api";
import type { LibraryEntry } from "../lib/types";

const TYPE_LABELS: Record<string, string> = {
  workflow: "生产方案",
  agent: "智能体配置",
  role: "岗位规格",
};

export function TemplateLibrary() {
  const [activeType, setActiveType] = useState("workflow");
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<LibraryEntry | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.listLibrary(activeType, search);
      setEntries(data);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [activeType, search]);

  const handleInstall = async (entry: LibraryEntry) => {
    const workshop = prompt("目标车间名称:");
    if (!workshop) return;
    try {
      await api.installFromLibrary(entry.entry_type, entry.name, workshop);
      alert(`已安装到 ${workshop}`);
    } catch (e: any) {
      alert(`安装失败: ${e.message}`);
    }
  };

  const handleDelete = async (entry: LibraryEntry) => {
    if (!confirm(`确定删除「${entry.name}」?`)) return;
    try {
      await api.deleteFromLibrary(entry.entry_type, entry.name);
      load();
    } catch (e: any) {
      alert(`删除失败: ${e.message}`);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">我的模板</h1>

      {/* Type tabs */}
      <div className="flex gap-2 mb-4">
        {["workflow", "agent", "role"].map((t) => (
          <button
            key={t}
            onClick={() => { setActiveType(t); setSelected(null); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeType === t
                ? "bg-amber-500 text-black"
                : "bg-zinc-800 text-zinc-400 hover:text-white"
            }`}
          >
            {TYPE_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Search */}
      <input
        type="text"
        placeholder="搜索模板..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full px-4 py-2 mb-4 bg-zinc-900 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500"
      />

      {/* Content */}
      <div className="flex gap-6">
        {/* List */}
        <div className="flex-1 space-y-2">
          {loading ? (
            <p className="text-zinc-500">加载中...</p>
          ) : entries.length === 0 ? (
            <p className="text-zinc-500">暂无模板。使用 CLI 入库或在车间中保存。</p>
          ) : (
            entries.map((e) => (
              <div
                key={e.id}
                onClick={() => setSelected(e)}
                className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                  selected?.id === e.id
                    ? "border-amber-500 bg-zinc-800"
                    : "border-zinc-800 bg-zinc-900 hover:border-zinc-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-white">{e.name}</span>
                  <span className="text-xs text-zinc-500">{e.version}</span>
                </div>
                {e.description && (
                  <p className="text-sm text-zinc-400 mt-1">{e.description}</p>
                )}
                <div className="flex gap-2 mt-2">
                  <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                    {e.category}
                  </span>
                  {e.source_workshop && (
                    <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-500">
                      {e.source_workshop}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="w-80 flex-shrink-0">
            <div className="p-4 rounded-lg border border-zinc-800 bg-zinc-900 sticky top-4">
              <h2 className="text-lg font-bold text-white mb-2">{selected.name}</h2>
              <p className="text-sm text-zinc-400 mb-3">{selected.description || "无说明"}</p>
              <div className="flex flex-wrap gap-1 mb-3">
                {selected.tags.map((t) => (
                  <span key={t} className="text-xs px-2 py-0.5 rounded bg-amber-900/30 text-amber-400">
                    {t}
                  </span>
                ))}
              </div>
              <div className="text-xs text-zinc-500 space-y-1 mb-4">
                <p>分类: {selected.category}</p>
                <p>版本: {selected.version}</p>
                {selected.source_workshop && <p>来源: {selected.source_workshop}</p>}
                <p>入库: {selected.created_at}</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleInstall(selected)}
                  className="flex-1 px-3 py-2 bg-amber-500 text-black rounded-lg text-sm font-medium hover:bg-amber-400 transition-colors"
                >
                  安装
                </button>
                <button
                  onClick={() => handleDelete(selected)}
                  className="px-3 py-2 bg-red-900/30 text-red-400 rounded-lg text-sm hover:bg-red-900/50 transition-colors"
                >
                  删除
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: App.tsx 追加路由**

在 `webui/src/App.tsx` 中：
```tsx
import { TemplateLibrary } from "./components/TemplateLibrary";

// 在 Routes 中追加:
<Route path="/library" element={<ErrorBoundary><TemplateLibrary /></ErrorBoundary>} />
```

- [ ] **Step 5: 验证 TypeScript 编译**

Run: `cd /Users/linhan/ai-factory/webui && npx tsc --noEmit 2>&1 | grep -v WorkflowEditor`
Expected: no new errors

- [ ] **Step 6: Commit**

```bash
git add webui/src/lib/types.ts webui/src/lib/api.ts webui/src/components/TemplateLibrary.tsx webui/src/App.tsx
git commit -m "feat: add TemplateLibrary frontend component"
```

---

### Task 8: 最终验证

- [ ] **Step 1: 运行全量测试**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/ gateway/ --tb=short 2>&1 | tail -5`
Expected: all tests pass (407 + new library tests)

- [ ] **Step 2: 验证 CLI 完整流程**

```bash
# 先创建一个 workflow 模板（使用已有的）
python3 entrypoint.py workflow list
# 入库
python3 entrypoint.py library save workflow 模块生产线 --desc "自动化模块生产流水线" --tags "生产,自动化" --category "代码工具"
# 列出
python3 entrypoint.py library list workflow
# 查看
python3 entrypoint.py library show workflow 模块生产线
# 删除
python3 entrypoint.py library delete workflow 模块生产线
```

- [ ] **Step 3: 运行覆盖率**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/library/ --cov=factory.library --cov-report=term-missing`
Expected: coverage >= 80%

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: complete local template library implementation"
```
