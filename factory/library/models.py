from __future__ import annotations
"""Pydantic models for the local template library."""


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
    body: str = ""


class SaveRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "其他"
    tags: list[str] = Field(default_factory=list)
    workshop: str = ""


class InstallRequest(BaseModel):
    workshop: str
