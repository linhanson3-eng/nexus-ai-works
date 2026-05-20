"""制品仓库 — OB 知识库读写接口。

Agent 不直接写文件系统，所有产出物通过此接口写入制品仓库。
"""

from datetime import datetime
from pathlib import Path
from typing import Any


class Warehouse:
    """OB 知识库制品仓库。

    结构：
    OB/
    ├── 开发部/
    ├── 市场分析部/
    ├── 自媒体运营部/
    ├── 车间记忆/       ← 车间级记忆（Consolidator 写入）
    ├── 工厂记忆/       ← 工厂级记忆（Dream 写入）
    └── INDEX.md       ← 自动维护的产品目录
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "INDEX.md"

    def write(self, department: str, filename: str, content: str) -> Path:
        """写入制品。自动创建车间目录。"""
        dept_dir = self.root / department
        dept_dir.mkdir(parents=True, exist_ok=True)

        path = dept_dir / filename
        path.write_text(content, encoding="utf-8")
        self._update_index(department, filename)
        return path

    def read(self, department: str, filename: str) -> str:
        """只读消费其他车间的制品。"""
        path = self.root / department / filename
        if not path.exists():
            raise FileNotFoundError(f"制品不存在: {department}/{filename}")
        return path.read_text(encoding="utf-8")

    def read_dept(self, department: str) -> list[Path]:
        """列出某个车间的所有制品。"""
        dept_dir = self.root / department
        if not dept_dir.exists():
            return []
        return sorted(dept_dir.glob("*.md"))

    def link(self, from_dept: str, from_file: str, to_dept: str, to_file: str) -> str:
        """建立 Obsidian [[双向链接]]。"""
        link = f"[[{to_dept}/{to_file}]]"
        path = self.root / from_dept / from_file
        if path.exists():
            current = path.read_text(encoding="utf-8")
            if link not in current:
                path.write_text(
                    current.rstrip() + f"\n\n相关：{link}\n", encoding="utf-8"
                )
        return link

    def write_memory(self, level: str, name: str, content: str) -> Path:
        """写入记忆文件。

        level: "agent" | "workshop" | "factory"
        """
        memory_dirs = {
            "agent": self.root / "Agent记忆",
            "workshop": self.root / "车间记忆",
            "factory": self.root / "工厂记忆",
        }
        target = memory_dirs.get(level, self.root / "Agent记忆")
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def read_memory(self, level: str, name: str) -> str:
        """读取记忆文件。"""
        memory_dirs = {
            "agent": self.root / "Agent记忆",
            "workshop": self.root / "车间记忆",
            "factory": self.root / "工厂记忆",
        }
        path = memory_dirs[level] / f"{name}.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def index(self) -> dict[str, list[str]]:
        """扫描所有制品，按车间分组返回文件名列表。"""
        result: dict[str, list[str]] = {}
        for dept_dir in self.root.iterdir():
            if dept_dir.is_dir() and not dept_dir.name.startswith("."):
                files = [f.name for f in dept_dir.glob("*.md")]
                if files:
                    result[dept_dir.name] = files
        return result

    def _update_index(self, department: str, filename: str) -> None:
        """更新 INDEX.md。"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{ts}] **{department}** / {filename}\n"
        if self._index_path.exists():
            content = self._index_path.read_text(encoding="utf-8")
            if f"{department} / {filename}" not in content:
                content = entry + content
        else:
            content = f"# 制品仓库索引\n\n{entry}"
        self._index_path.write_text(content, encoding="utf-8")
