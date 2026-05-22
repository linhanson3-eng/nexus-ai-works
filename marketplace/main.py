"""Marketplace entry point. Mounts admin routes under /admin."""

from marketplace.admin import admin
from marketplace.api import app

app.mount("/admin", admin)
