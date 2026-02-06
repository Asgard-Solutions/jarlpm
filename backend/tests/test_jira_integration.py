"""
Tests for Jira Cloud Integration API endpoints.
These tests verify the integration endpoints work correctly,
even when OAuth credentials are not configured.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from server import app

BASE_URL = "http://test"

@pytest.fixture
def test_credentials():
    return {
        "email": "test@jarlpm.com",
        "password": "Test123!"
    }

@pytest.fixture
async def auth_client(test_credentials):
    """Create an authenticated client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # Login
        response = await client.post("/api/auth/login", json=test_credentials)
        if response.status_code == 200:
            cookies = response.cookies
            client.cookies = cookies
        yield client


class TestJiraStatusEndpoints:
    """Test Jira integration status endpoints."""

    @pytest.mark.asyncio
    async def test_get_jira_status_unauthenticated(self):
        """Test that status endpoint requires authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
            response = await client.get("/api/integrations/status/jira")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_jira_status_authenticated(self, auth_client):
        """Test getting Jira status when authenticated."""
        response = await auth_client.get("/api/integrations/status/jira")
        assert response.status_code in [200, 402]  # 402 if no subscription
        if response.status_code == 200:
            data = response.json()
            assert "connected" in data
            assert "status" in data

    @pytest.mark.asyncio
    async def test_overall_status_includes_jira(self, auth_client):
        """Test that overall status includes Jira."""
        response = await auth_client.get("/api/integrations/status")
        assert response.status_code in [200, 402]
        if response.status_code == 200:
            data = response.json()
            assert "jira" in data


class TestJiraConnectEndpoints:
    """Test Jira OAuth connection endpoints."""

    @pytest.mark.asyncio
    async def test_connect_requires_auth(self):
        """Test that connect endpoint requires authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
            response = await client.post(
                "/api/integrations/jira/connect",
                json={"frontend_callback_url": "http://localhost:3000/settings"}
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_connect_requires_callback_url(self, auth_client):
        """Test that connect requires frontend_callback_url."""
        response = await auth_client.post(
            "/api/integrations/jira/connect",
            json={}
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_connect_returns_oauth_url_or_error(self, auth_client):
        """Test connect endpoint returns OAuth URL or configuration error."""
        response = await auth_client.post(
            "/api/integrations/jira/connect",
            json={"frontend_callback_url": "http://localhost:3000/settings"}
        )
        # Will be 400 if OAuth not configured, or 200 with auth_url
        assert response.status_code in [200, 400, 402]
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data


class TestJiraDisconnectEndpoints:
    """Test Jira disconnect endpoint."""

    @pytest.mark.asyncio
    async def test_disconnect_requires_auth(self):
        """Test that disconnect requires authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
            response = await client.post("/api/integrations/jira/disconnect")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, auth_client):
        """Test disconnect when not connected."""
        response = await auth_client.post("/api/integrations/jira/disconnect")
        assert response.status_code in [200, 400, 402]


class TestJiraDataEndpoints:
    """Test Jira data fetching endpoints."""

    @pytest.mark.asyncio
    async def test_get_sites_requires_connection(self, auth_client):
        """Test sites endpoint when not connected."""
        response = await auth_client.get("/api/integrations/jira/sites")
        assert response.status_code in [400, 402]  # Not connected or no subscription

    @pytest.mark.asyncio
    async def test_get_projects_requires_connection(self, auth_client):
        """Test projects endpoint when not connected."""
        response = await auth_client.get("/api/integrations/jira/projects")
        assert response.status_code in [400, 402]

    @pytest.mark.asyncio
    async def test_get_fields_requires_connection(self, auth_client):
        """Test fields endpoint when not connected."""
        response = await auth_client.get("/api/integrations/jira/fields")
        assert response.status_code in [400, 402]


class TestJiraPushEndpoints:
    """Test Jira push endpoints."""

    @pytest.mark.asyncio
    async def test_preview_requires_auth(self):
        """Test preview requires authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
            response = await client.post(
                "/api/integrations/jira/preview",
                json={"epic_id": "epic_test", "push_scope": "epic_only"}
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_preview_requires_connection(self, auth_client):
        """Test preview when not connected."""
        response = await auth_client.post(
            "/api/integrations/jira/preview",
            json={"epic_id": "epic_test", "push_scope": "epic_only"}
        )
        assert response.status_code in [400, 402]
        if response.status_code == 400:
            data = response.json()
            assert "not connected" in data.get("detail", "").lower() or "jira" in data.get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_push_requires_auth(self):
        """Test push requires authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
            response = await client.post(
                "/api/integrations/jira/push",
                json={
                    "epic_id": "epic_test",
                    "project_key": "PROJ",
                    "push_scope": "epic_only"
                }
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_push_requires_connection(self, auth_client):
        """Test push when not connected."""
        response = await auth_client.post(
            "/api/integrations/jira/push",
            json={
                "epic_id": "epic_test",
                "project_key": "PROJ",
                "push_scope": "epic_only"
            }
        )
        assert response.status_code in [400, 402]

    @pytest.mark.asyncio
    async def test_push_validates_required_fields(self, auth_client):
        """Test push validation for required fields."""
        response = await auth_client.post(
            "/api/integrations/jira/push",
            json={"epic_id": "epic_test"}  # Missing project_key
        )
        assert response.status_code in [400, 402, 422]


class TestJiraConfigureEndpoints:
    """Test Jira configuration endpoint."""

    @pytest.mark.asyncio
    async def test_configure_requires_auth(self):
        """Test configure requires authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=BASE_URL) as client:
            response = await client.put(
                "/api/integrations/jira/configure",
                json={"default_project_key": "PROJ"}
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_configure_requires_connection(self, auth_client):
        """Test configure when not connected."""
        response = await auth_client.put(
            "/api/integrations/jira/configure",
            json={"default_project_key": "PROJ"}
        )
        assert response.status_code in [400, 402]


class TestJiraIssueTypesEndpoints:
    """Test Jira issue types endpoint."""

    @pytest.mark.asyncio
    async def test_get_issue_types_requires_connection(self, auth_client):
        """Test issue types endpoint when not connected."""
        response = await auth_client.get("/api/integrations/jira/projects/PROJ/issue-types")
        assert response.status_code in [400, 402]
