from __future__ import annotations
"""SQLite data store for the Solution Marketplace."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from marketplace.models import MarketplacePackage, PlanType, Subscription, UserInfo

STORE_SQL = """
CREATE TABLE IF NOT EXISTS packages (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    long_description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    author TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '1.0.0',
    icon_url TEXT NOT NULL DEFAULT '',
    screenshots TEXT NOT NULL DEFAULT '[]',
    plan_monthly_price INTEGER NOT NULL DEFAULT 0,
    plan_yearly_price INTEGER NOT NULL DEFAULT 0,
    package_url TEXT NOT NULL DEFAULT '',
    package_size INTEGER NOT NULL DEFAULT 0,
    download_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS subscriptions (
    user_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    plan_type TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, package_id)
);
"""


class MarketplaceStore:
    """SQLite-backed store for marketplace data."""

    def __init__(self, db_path: str | Path = "~/.factory/marketplace.db") -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        import sqlite3

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript(STORE_SQL)
        conn.commit()
        conn.close()

    _cached_conn: "sqlite3.Connection | None" = None

    def _conn(self) -> "sqlite3.Connection":
        import sqlite3
        if self._cached_conn is not None:
            return self._cached_conn
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        self._cached_conn = conn
        return conn

    # ── Packages ──────────────────────────────────────────────────────

    def list_packages(self, category: str = "") -> list[MarketplacePackage]:
        """List all packages, optionally filtered by category."""
        conn = self._conn()
        try:
            if category:
                rows = conn.execute(
                    "SELECT * FROM packages WHERE category = ? ORDER BY updated_at DESC",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM packages ORDER BY updated_at DESC"
                ).fetchall()
            return [self._row_to_package(row) for row in rows]
        finally:
            pass

    def get_package(self, package_id: str) -> MarketplacePackage | None:
        """Get a single package by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM packages WHERE id = ?", (package_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_package(row)
        finally:
            pass  # cached conn, keep alive

    def save_package(self, pkg: MarketplacePackage) -> None:
        """Insert or update a package."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO packages
                   (id, name, description, long_description, category, tags,
                    author, version, icon_url, screenshots,
                    plan_monthly_price, plan_yearly_price,
                    package_url, package_size, download_count,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pkg.id,
                    pkg.name,
                    pkg.description,
                    pkg.long_description,
                    pkg.category,
                    json.dumps(pkg.tags, ensure_ascii=False),
                    pkg.author,
                    pkg.version,
                    pkg.icon_url,
                    json.dumps(pkg.screenshots, ensure_ascii=False),
                    pkg.plan_monthly_price,
                    pkg.plan_yearly_price,
                    pkg.package_url,
                    pkg.package_size,
                    pkg.download_count,
                    pkg.created_at,
                    pkg.updated_at,
                ),
            )
            conn.commit()
        finally:
            pass  # cached conn, keep alive

    def delete_package(self, package_id: str) -> bool:
        """Delete a package. Returns True if it existed."""
        conn = self._conn()
        try:
            cursor = conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            pass  # cached conn, keep alive

    def increment_download(self, package_id: str) -> None:
        """Increment the download counter for a package."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE packages SET download_count = download_count + 1 WHERE id = ?",
                (package_id,),
            )
            conn.commit()
        finally:
            pass  # cached conn, keep alive

    # ── Users ─────────────────────────────────────────────────────────

    def create_user(self, username: str, password_hash: str) -> UserInfo | None:
        """Create a new user. Returns UserInfo on success, None if username taken."""
        conn = self._conn()
        try:
            user_id = uuid.uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            cursor = conn.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, username, password_hash, now),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return UserInfo(user_id=user_id, username=username)
        finally:
            pass  # cached conn, keep alive

    def get_user(self, username: str) -> dict | None:
        """Get user row by username. Returns raw dict or None."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            pass  # cached conn, keep alive

    # ── Subscriptions ─────────────────────────────────────────────────

    def get_subscriptions(self, user_id: str) -> list[Subscription]:
        """Get all subscriptions for a user."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? AND expires_at > ?",
                (user_id, datetime.now(timezone.utc).isoformat()),
            ).fetchall()
            return [self._row_to_subscription(row) for row in rows]
        finally:
            pass  # cached conn, keep alive

    def has_access(self, user_id: str, package_id: str) -> bool:
        """Check if a user has access to a package.

        VIP users always have access. Otherwise checks for an active subscription.
        """
        conn = self._conn()
        try:
            # Check VIP status
            user_row = conn.execute(
                "SELECT 1 FROM subscriptions WHERE user_id = ? AND plan_type = 'vip' "
                "AND expires_at > ?",
                (user_id, datetime.now(timezone.utc).isoformat()),
            ).fetchone()
            if user_row is not None:
                return True

            # Check specific package subscription
            sub_row = conn.execute(
                "SELECT 1 FROM subscriptions WHERE user_id = ? AND package_id = ? "
                "AND expires_at > ?",
                (user_id, package_id, datetime.now(timezone.utc).isoformat()),
            ).fetchone()
            return sub_row is not None
        finally:
            pass  # cached conn, keep alive

    def activate_subscription(
        self,
        user_id: str,
        package_id: str,
        plan_type: PlanType,
        duration_months: int = 1,
    ) -> Subscription:
        """Activate a subscription. Upserts — extends if already exists."""
        conn = self._conn()
        try:
            now = datetime.now(timezone.utc)

            # Determine the new expiration
            existing = conn.execute(
                "SELECT expires_at FROM subscriptions WHERE user_id = ? AND package_id = ?",
                (user_id, package_id),
            ).fetchone()
            if existing and existing["expires_at"]:
                try:
                    base = datetime.fromisoformat(existing["expires_at"])
                    if base < now:
                        base = now
                except (ValueError, TypeError):
                    base = now
            else:
                base = now

            expires_at = (base + timedelta(days=duration_months * 30)).isoformat()
            created_at = now.isoformat()

            conn.execute(
                """INSERT OR REPLACE INTO subscriptions
                   (user_id, package_id, plan_type, expires_at, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, package_id, plan_type.value, expires_at, created_at),
            )
            conn.commit()

            return Subscription(
                user_id=user_id,
                package_id=package_id,
                plan_type=plan_type,
                expires_at=expires_at,
                created_at=created_at,
            )
        finally:
            pass  # cached conn, keep alive

    # ── Row deserialization ───────────────────────────────────────────

    @staticmethod
    def _row_to_package(row) -> MarketplacePackage:
        return MarketplacePackage(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            long_description=row["long_description"],
            category=row["category"],
            tags=json.loads(row["tags"]),
            author=row["author"],
            version=row["version"],
            icon_url=row["icon_url"],
            screenshots=json.loads(row["screenshots"]),
            plan_monthly_price=row["plan_monthly_price"],
            plan_yearly_price=row["plan_yearly_price"],
            package_url=row["package_url"],
            package_size=row["package_size"],
            download_count=row["download_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_subscription(row) -> Subscription:
        return Subscription(
            user_id=row["user_id"],
            package_id=row["package_id"],
            plan_type=PlanType(row["plan_type"]),
            expires_at=row["expires_at"],
            created_at=row["created_at"],
        )
