from __future__ import annotations
"""Integration tests for marketplace API."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(tmp_path):
    """Create an async test client with a fresh temp-db store per test.

    Replaces the api module's store instance with one backed by a temp db.
    Also redirects PACKAGES_DIR so download tests work with temp files.
    """
    import marketplace.store as ms
    import marketplace.api as api_module

    # Replace the store with a fresh temp-db instance for this test.
    api_module.store = ms.MarketplaceStore(str(tmp_path / "test.db"))

    # Redirect packages directory for download tests.
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()
    api_module.PACKAGES_DIR = packages_dir

    transport = ASGITransport(app=api_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestCatalog:
    """Tests for catalog listing and package detail endpoints."""

    async def test_catalog_empty(self, client):
        """GET /api/catalog returns an empty list when no packages exist."""
        response = await client.get("/api/catalog")
        assert response.status_code == 200
        assert response.json() == []

    async def test_catalog_with_packages(self, client):
        """GET /api/catalog returns all saved packages."""
        import marketplace.api as api
        from marketplace.models import MarketplacePackage

        pkg1 = MarketplacePackage(
            id="pkg-1", name="Package One", description="First", category="ai"
        )
        pkg2 = MarketplacePackage(
            id="pkg-2", name="Package Two", description="Second", category="data"
        )
        api.store.save_package(pkg1)
        api.store.save_package(pkg2)

        response = await client.get("/api/catalog")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {p["name"] for p in data}
        assert names == {"Package One", "Package Two"}

    async def test_catalog_category_filter(self, client):
        """GET /api/catalog?category=... returns only matching packages."""
        import marketplace.api as api
        from marketplace.models import MarketplacePackage

        api.store.save_package(
            MarketplacePackage(id="p1", name="AI One", category="ai")
        )
        api.store.save_package(
            MarketplacePackage(id="p2", name="Data One", category="data")
        )
        api.store.save_package(
            MarketplacePackage(id="p3", name="AI Two", category="ai")
        )

        response = await client.get("/api/catalog", params={"category": "ai"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(p["category"] == "ai" for p in data)

        # Verify the unfiltered call still returns everything.
        all_resp = await client.get("/api/catalog")
        assert len(all_resp.json()) == 3

    async def test_catalog_category_no_match(self, client):
        """Filtering by a nonexistent category returns an empty list."""
        response = await client.get(
            "/api/catalog", params={"category": "nonexistent"}
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_package_detail(self, client):
        """GET /api/packages/{id} returns full package information."""
        import marketplace.api as api
        from marketplace.models import MarketplacePackage

        pkg = MarketplacePackage(
            id="detail-1",
            name="Detail Package",
            description="Short desc",
            long_description="Long description text",
            category="tools",
            tags=["python", "cli"],
            author="test-author",
            version="2.3.1",
            icon_url="https://example.com/icon.png",
            screenshots=["https://example.com/shot1.png"],
            plan_monthly_price=1990,
            plan_yearly_price=19900,
            package_url="https://example.com/pkg.zip",
            package_size=4096,
        )
        api.store.save_package(pkg)

        response = await client.get("/api/packages/detail-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "detail-1"
        assert data["name"] == "Detail Package"
        assert data["description"] == "Short desc"
        assert data["long_description"] == "Long description text"
        assert data["category"] == "tools"
        assert data["tags"] == ["python", "cli"]
        assert data["author"] == "test-author"
        assert data["version"] == "2.3.1"
        assert data["icon_url"] == "https://example.com/icon.png"
        assert data["screenshots"] == ["https://example.com/shot1.png"]
        assert data["plan_monthly_price"] == 1990
        assert data["plan_yearly_price"] == 19900
        assert data["package_url"] == "https://example.com/pkg.zip"
        assert data["package_size"] == 4096

    async def test_package_detail_not_found(self, client):
        """GET /api/packages/{id} returns 404 for an unknown package."""
        response = await client.get("/api/packages/nonexistent-id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Package not found"


class TestAuth:
    """Tests for registration, login, and auth-protected endpoints."""

    async def test_register_and_login(self, client):
        """Register creates a user and returns a valid token; login also works."""
        # Register a new user.
        reg_resp = await client.post(
            "/api/auth/register",
            json={"username": "testuser", "password": "secret123"},
        )
        assert reg_resp.status_code == 200
        reg_data = reg_resp.json()
        assert "token" in reg_data
        assert reg_data["user"]["username"] == "testuser"
        assert reg_data["user"]["user_id"]
        token = reg_data["token"]

        # Use the token to call /me.
        me_resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["username"] == "testuser"
        assert me_data["user_id"] == reg_data["user"]["user_id"]
        assert me_data["is_vip"] is False

        # Login with the same credentials.
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "secret123"},
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        assert "token" in login_data
        assert login_data["user"]["username"] == "testuser"
        assert login_data["user"]["is_vip"] is False

    async def test_login_invalid_credentials(self, client):
        """Login with wrong password or nonexistent user returns 401."""
        # Register a user first.
        await client.post(
            "/api/auth/register",
            json={"username": "realuser", "password": "correctpw"},
        )

        # Wrong password.
        resp = await client.post(
            "/api/auth/login",
            json={"username": "realuser", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

        # Nonexistent user.
        resp = await client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "irrelevant"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

    async def test_register_duplicate(self, client):
        """Registering the same username twice returns 409 Conflict."""
        payload = {"username": "dupuser", "password": "secret123"}

        r1 = await client.post("/api/auth/register", json=payload)
        assert r1.status_code == 200

        r2 = await client.post("/api/auth/register", json=payload)
        assert r2.status_code == 409
        assert r2.json()["detail"] == "Username already taken"

    async def test_register_short_username(self, client):
        """Register with username < 3 chars returns 400."""
        resp = await client.post(
            "/api/auth/register",
            json={"username": "ab", "password": "secret123"},
        )
        assert resp.status_code == 400
        assert "at least 3" in resp.json()["detail"]

    async def test_register_short_password(self, client):
        """Register with password < 6 chars returns 400."""
        resp = await client.post(
            "/api/auth/register",
            json={"username": "validuser", "password": "12345"},
        )
        assert resp.status_code == 400
        assert "at least 6" in resp.json()["detail"]

    async def test_me_without_auth(self, client):
        """GET /api/auth/me without a token returns 401."""
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_with_invalid_token(self, client):
        """GET /api/auth/me with a garbage token returns 401."""
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer garbage-token"},
        )
        assert resp.status_code == 401


class TestDownload:
    """Tests for the package download endpoint."""

    async def test_download_without_auth(self, client):
        """GET /download without an auth header returns 401."""
        response = await client.get("/api/packages/some-pkg/download")
        assert response.status_code == 401

    async def test_download_without_subscription(self, client):
        """Authenticated user without a subscription gets 403."""
        import marketplace.api as api
        from marketplace.models import MarketplacePackage

        # Publish a package.
        api.store.save_package(
            MarketplacePackage(id="dl-pkg", name="DL", category="tools")
        )

        # Register and get a token.
        reg_resp = await client.post(
            "/api/auth/register",
            json={"username": "dluser", "password": "secret123"},
        )
        token = reg_resp.json()["token"]

        # Attempt download without an active subscription.
        resp = await client.get(
            "/api/packages/dl-pkg/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "active subscription" in resp.json()["detail"]

    async def test_download_success(self, client):
        """Authenticated user with an active subscription receives the file."""
        import marketplace.api as api
        from marketplace.models import MarketplacePackage, PlanType

        package_id = "dl-success"

        # Publish a package.
        api.store.save_package(
            MarketplacePackage(id=package_id, name="DL OK", category="tools")
        )

        # Create the .nexus.zip file in the temp packages directory.
        zip_path = api.PACKAGES_DIR / f"{package_id}.nexus.zip"
        zip_content = b"fake-zip-binary-content"
        zip_path.write_bytes(zip_content)

        # Register a user.
        reg_resp = await client.post(
            "/api/auth/register",
            json={"username": "dluser2", "password": "secret123"},
        )
        reg_data = reg_resp.json()
        token = reg_data["token"]
        user_id = reg_data["user"]["user_id"]

        # Activate a subscription.
        api.store.activate_subscription(
            user_id=user_id,
            package_id=package_id,
            plan_type=PlanType.monthly,
            duration_months=1,
        )

        # Download should succeed.
        resp = await client.get(
            f"/api/packages/{package_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "application/zip"
        assert resp.content == zip_content

    async def test_download_package_not_found(self, client):
        """Downloading a package that does not exist in the catalog returns 404 from file check."""
        import marketplace.api as api
        from marketplace.models import MarketplacePackage, PlanType

        # Register a user and give them a subscription to a package
        # that exists in the subscriptions table but has no file on disk.
        api.store.save_package(
            MarketplacePackage(id="no-file-pkg", name="No File", category="tools")
        )

        reg_resp = await client.post(
            "/api/auth/register",
            json={"username": "nofileuser", "password": "secret123"},
        )
        reg_data = reg_resp.json()
        token = reg_data["token"]
        user_id = reg_data["user"]["user_id"]

        api.store.activate_subscription(
            user_id=user_id,
            package_id="no-file-pkg",
            plan_type=PlanType.monthly,
        )

        resp = await client.get(
            "/api/packages/no-file-pkg/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestMySubscriptions:
    """Tests for the /api/my endpoint."""

    async def test_my_without_auth(self, client):
        """GET /api/my without a token returns 401."""
        resp = await client.get("/api/my")
        assert resp.status_code == 401

    async def test_my_empty(self, client):
        """New user has no subscriptions."""
        reg_resp = await client.post(
            "/api/auth/register",
            json={"username": "nosubs", "password": "secret123"},
        )
        token = reg_resp.json()["token"]

        resp = await client.get(
            "/api/my",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_my_with_subscriptions(self, client):
        """User with active subscriptions sees them listed."""
        import marketplace.api as api
        from marketplace.models import MarketplacePackage, PlanType

        api.store.save_package(
            MarketplacePackage(id="my-pkg", name="My Pkg", category="tools")
        )

        reg_resp = await client.post(
            "/api/auth/register",
            json={"username": "subuser", "password": "secret123"},
        )
        reg_data = reg_resp.json()
        token = reg_data["token"]
        user_id = reg_data["user"]["user_id"]

        api.store.activate_subscription(
            user_id=user_id,
            package_id="my-pkg",
            plan_type=PlanType.monthly,
            duration_months=3,
        )

        resp = await client.get(
            "/api/my",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["package_id"] == "my-pkg"
        assert data[0]["plan_type"] == "monthly"
        assert data[0]["user_id"] == user_id
