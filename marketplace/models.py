from __future__ import annotations
"""Pydantic v2 models for the Solution Marketplace."""

from enum import Enum

from pydantic import BaseModel, Field


class PlanType(str, Enum):
    """Subscription plan type."""

    monthly = "monthly"
    yearly = "yearly"
    vip = "vip"


class MarketplacePackage(BaseModel):
    """A workshop solution package listed in the marketplace."""

    id: str = ""
    name: str = ""
    description: str = ""
    long_description: str = ""
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    author: str = ""
    version: str = "1.0.0"
    icon_url: str = ""
    screenshots: list[str] = Field(default_factory=list)
    plan_monthly_price: int = 0  # cents
    plan_yearly_price: int = 0  # cents
    package_url: str = ""
    package_size: int = 0
    download_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class Subscription(BaseModel):
    """A user's subscription to a marketplace package."""

    user_id: str
    package_id: str
    plan_type: PlanType
    expires_at: str = ""
    created_at: str = ""


class UserInfo(BaseModel):
    """Public user information returned by the API."""

    user_id: str
    username: str
    is_vip: bool = False


class LoginRequest(BaseModel):
    """Request body for login."""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """Request body for registration."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response after login/register."""

    token: str
    user: UserInfo


class ActivateRequest(BaseModel):
    """Request body for activating (purchasing) a subscription."""

    user_id: str
    package_id: str
    plan_type: PlanType
    duration_months: int = 1
