from __future__ import annotations

""".nexus package — pack/unpack workspace modules for import/export.

A .nexus package is a directory containing:
  nexus.yaml          # manifest (name, version, description)
  agents/*.yaml       # AgentSpec exports
  workflows/*.yaml    # WorkflowTemplate exports
  GUIDE.md            # guide file content
  tools/*.py          # optional custom tools
  chain.yaml          # optional cross-workshop chain
"""


import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


PACKAGE_CATEGORIES = [
    "市场分析", "内容创作", "代码工具", "数据处理",
    "法务合规", "营销推广", "客服支持", "项目管理",
    "金融分析", "教育培训", "医疗健康", "其他",
]

@dataclass
class PackageManifest:
    """A .nexus package manifest."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    category: str = "其他"
    tags: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    has_chain: bool = False
    has_tools: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "tags": self.tags,
            "agents": self.agents,
            "workflows": self.workflows,
            "has_chain": self.has_chain,
            "has_tools": self.has_tools,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageManifest:
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            category=data.get("category", "其他"),
            tags=data.get("tags", []),
            agents=data.get("agents", []),
            workflows=data.get("workflows", []),
            has_chain=data.get("has_chain", False),
            has_tools=data.get("has_tools", False),
        )


def pack_workspace(
    workspace_name: str,
    workspace_path: str,
    agents: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    *,
    guide_file: str = "",
    guide_content: str = "",
    chain: dict[str, Any] | None = None,
    tools_dir: str = "",
    output_dir: str = ".",
    version: str = "1.0.0",
    description: str = "",
    category: str = "其他",
    tags: list[str] | None = None,
) -> Path:
    """Pack a workspace into a .nexus package directory.

    Returns the path to the created package directory.
    """
    pkg_dir = Path(output_dir) / f"{workspace_name}.nexus"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # Manifest
    manifest = PackageManifest(
        name=workspace_name,
        version=version,
        description=description,
        category=category,
        tags=tags or [],
        agents=[a.get("name", "") for a in agents],
        workflows=[w.get("name", "") for w in workflows],
        has_chain=chain is not None,
        has_tools=bool(tools_dir) and Path(tools_dir).is_dir(),
    )
    (pkg_dir / "nexus.yaml").write_text(
        yaml.dump(manifest.to_dict(), allow_unicode=True, sort_keys=False), "utf-8"
    )

    # Agents
    agents_dir = pkg_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    for agent in agents:
        name = agent.get("name", "agent")
        (agents_dir / f"{name}.yaml").write_text(
            yaml.dump(agent, allow_unicode=True, sort_keys=False), "utf-8"
        )

    # Workflows
    wf_dir = pkg_dir / "workflows"
    wf_dir.mkdir(exist_ok=True)
    for wf in workflows:
        name = wf.get("name", "workflow")
        (wf_dir / f"{name}.yaml").write_text(
            yaml.dump(wf, allow_unicode=True, sort_keys=False), "utf-8"
        )

    # Guide file
    if guide_content:
        (pkg_dir / "GUIDE.md").write_text(guide_content, "utf-8")
    elif guide_file and Path(guide_file).exists():
        shutil.copy(guide_file, pkg_dir / "GUIDE.md")

    # Chain
    if chain:
        (pkg_dir / "chain.yaml").write_text(
            yaml.dump(chain, allow_unicode=True, sort_keys=False), "utf-8"
        )

    # Tools
    if tools_dir:
        tools_src = Path(tools_dir)
        if tools_src.is_dir():
            tools_dst = pkg_dir / "tools"
            tools_dst.mkdir(exist_ok=True)
            for f in tools_src.glob("*.py"):
                shutil.copy(f, tools_dst / f.name)

    return pkg_dir


def unpack_package(pkg_dir: str | Path) -> dict[str, Any]:
    """Unpack a .nexus package directory.

    Returns a dict with all package contents ready for import.
    """
    root = Path(pkg_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Package not found: {pkg_dir}")

    manifest_path = root / "nexus.yaml"
    if not manifest_path.exists():
        raise ValueError(f"Invalid package: missing nexus.yaml in {pkg_dir}")

    manifest = PackageManifest.from_dict(
        yaml.safe_load(manifest_path.read_text("utf-8")) or {}
    )

    result: dict[str, Any] = {
        "manifest": manifest.to_dict(),
        "agents": [],
        "workflows": [],
        "guide_content": "",
        "chain": None,
        "tools": [],
    }

    # Agents
    agents_dir = root / "agents"
    if agents_dir.is_dir():
        for f in sorted(agents_dir.glob("*.yaml")):
            data = yaml.safe_load(f.read_text("utf-8"))
            if data:
                result["agents"].append(data)

    # Workflows
    wf_dir = root / "workflows"
    if wf_dir.is_dir():
        for f in sorted(wf_dir.glob("*.yaml")):
            data = yaml.safe_load(f.read_text("utf-8"))
            if data:
                result["workflows"].append(data)

    # Guide
    guide_path = root / "GUIDE.md"
    if guide_path.exists():
        result["guide_content"] = guide_path.read_text("utf-8")

    # Chain
    chain_path = root / "chain.yaml"
    if chain_path.exists():
        result["chain"] = yaml.safe_load(chain_path.read_text("utf-8"))

    # Tools
    tools_dir = root / "tools"
    if tools_dir.is_dir():
        result["tools"] = [f.name for f in tools_dir.glob("*.py")]

    return result


def validate_package(pkg_dir: str | Path) -> list[str]:
    """Validate a .nexus package, returning list of issues (empty = valid)."""
    issues: list[str] = []
    root = Path(pkg_dir)

    if not root.is_dir():
        issues.append(f"Not a directory: {pkg_dir}")
        return issues

    manifest_path = root / "nexus.yaml"
    if not manifest_path.exists():
        issues.append("Missing nexus.yaml")
        return issues

    try:
        data = yaml.safe_load(manifest_path.read_text("utf-8"))
        if not data:
            issues.append("nexus.yaml is empty")
        elif "name" not in data:
            issues.append("nexus.yaml missing 'name' field")
    except Exception as e:
        issues.append(f"Invalid nexus.yaml: {e}")

    return issues
