"""
Rate Limiting Tests for JarlPM

Tests that critical endpoints are properly rate-limited and return
429 status codes when limits are exceeded.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
import asyncio

# Import the FastAPI app
import sys
sys.path.insert(0, '/app/backend')
from server import app


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
async def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestRateLimitingConfiguration:
    """Test that rate limiting is properly configured."""
    
    def test_limiter_exists_on_app(self):
        """Verify limiter is attached to app state."""
        assert hasattr(app.state, 'limiter')
        assert app.state.limiter is not None
    
    def test_rate_limit_exception_handler_registered(self):
        """Verify custom exception handler is registered."""
        from slowapi.errors import RateLimitExceeded
        # Check that the exception handler is in the app's exception handlers
        assert RateLimitExceeded in app.exception_handlers


class TestRateLimitConfiguration:
    """Test rate limit configuration values."""
    
    def test_rate_limits_defined(self):
        """Verify all expected rate limits are defined."""
        from services.rate_limit import RATE_LIMITS
        
        expected_keys = [
            "auth_login",
            "auth_signup", 
            "auth_password_reset",
            "ai_generate",
            "ai_chat",
            "integration_push",
            "integration_preview",
            "api_read",
            "api_write"
        ]
        
        for key in expected_keys:
            assert key in RATE_LIMITS, f"Missing rate limit key: {key}"
            assert isinstance(RATE_LIMITS[key], str), f"Rate limit {key} should be a string"
            # Verify format is like "5/minute"
            assert "/" in RATE_LIMITS[key], f"Rate limit {key} should have format 'N/period'"
    
    def test_auth_limits_are_strict(self):
        """Auth endpoints should have stricter limits."""
        from services.rate_limit import RATE_LIMITS
        
        # Parse the rate limits to compare
        def parse_limit(limit_str):
            count = int(limit_str.split('/')[0])
            return count
        
        auth_login_limit = parse_limit(RATE_LIMITS["auth_login"])
        auth_signup_limit = parse_limit(RATE_LIMITS["auth_signup"])
        api_read_limit = parse_limit(RATE_LIMITS["api_read"])
        
        # Auth should be stricter than general API
        assert auth_login_limit < api_read_limit, "Auth login should be stricter than API read"
        assert auth_signup_limit < api_read_limit, "Auth signup should be stricter than API read"


class TestKeyFunctions:
    """Test rate limiting key functions."""
    
    def test_get_ip_only(self):
        """Test IP-only key function."""
        from services.rate_limit import get_ip_only
        from fastapi import Request
        from unittest.mock import MagicMock
        
        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        
        result = get_ip_only(mock_request)
        assert result.startswith("ip:")
    
    def test_get_user_id_or_ip_with_user(self):
        """Test user-aware key function with authenticated user."""
        from services.rate_limit import get_user_id_or_ip
        from fastapi import Request
        from unittest.mock import MagicMock
        
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.user_id = "user_123"
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        
        result = get_user_id_or_ip(mock_request)
        assert result == "user:user_123"
    
    def test_get_user_id_or_ip_without_user(self):
        """Test user-aware key function falls back to IP."""
        from services.rate_limit import get_user_id_or_ip
        from fastapi import Request
        from unittest.mock import MagicMock
        
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.user_id = None
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        
        result = get_user_id_or_ip(mock_request)
        assert result.startswith("ip:")


class TestRateLimitExceededHandler:
    """Test the custom rate limit exceeded handler."""
    
    def test_handler_returns_429(self):
        """Test that handler returns 429 status code."""
        from services.rate_limit import rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from fastapi import Request
        from unittest.mock import MagicMock
        
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.user_id = None
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/auth/login"
        mock_request.method = "POST"
        
        exc = RateLimitExceeded("5/minute")
        
        response = rate_limit_exceeded_handler(mock_request, exc)
        
        assert response.status_code == 429
    
    def test_handler_includes_retry_after(self):
        """Test that handler includes Retry-After header."""
        from services.rate_limit import rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from fastapi import Request
        from unittest.mock import MagicMock
        
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.user_id = None
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/auth/login"
        mock_request.method = "POST"
        
        exc = RateLimitExceeded("5/minute")
        
        response = rate_limit_exceeded_handler(mock_request, exc)
        
        assert "Retry-After" in response.headers


class TestDecoratorShortcuts:
    """Test decorator shortcut functions."""
    
    def test_limit_auth_creates_decorator(self):
        """Test limit_auth returns a decorator."""
        from services.rate_limit import limit_auth
        
        decorator = limit_auth()
        assert callable(decorator)
    
    def test_limit_ai_creates_decorator(self):
        """Test limit_ai returns a decorator."""
        from services.rate_limit import limit_ai
        
        decorator = limit_ai()
        assert callable(decorator)
    
    def test_limit_integration_creates_decorator(self):
        """Test limit_integration returns a decorator."""
        from services.rate_limit import limit_integration
        
        decorator = limit_integration()
        assert callable(decorator)
    
    def test_limit_api_read_creates_decorator(self):
        """Test limit_api_read returns a decorator."""
        from services.rate_limit import limit_api_read
        
        decorator = limit_api_read()
        assert callable(decorator)
    
    def test_limit_api_write_creates_decorator(self):
        """Test limit_api_write returns a decorator."""
        from services.rate_limit import limit_api_write
        
        decorator = limit_api_write()
        assert callable(decorator)


class TestEndpointRateLimiting:
    """Test that endpoints have rate limiting applied."""
    
    @pytest.mark.anyio
    async def test_login_rate_limited(self, client):
        """Test that login endpoint is rate-limited."""
        # Make more requests than the limit allows (5/minute)
        responses = []
        for i in range(8):
            response = await client.post(
                "/api/auth/login",
                json={"email": f"test{i}@example.com", "password": "wrongpassword"},
                headers={"X-Forwarded-For": "192.168.1.100"}
            )
            responses.append(response)
        
        # At least one should be rate limited (429)
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes, f"Expected at least one 429, got: {status_codes}"
    
    @pytest.mark.anyio
    async def test_signup_rate_limited(self, client):
        """Test that signup endpoint is rate-limited."""
        # Make more requests than the limit allows (3/minute)
        responses = []
        for i in range(6):
            response = await client.post(
                "/api/auth/signup",
                json={
                    "email": f"ratelimit_test_{i}@example.com",
                    "password": "TestPassword123!",
                    "name": f"Test User {i}"
                },
                headers={"X-Forwarded-For": "192.168.1.101"}
            )
            responses.append(response)
        
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes, f"Expected at least one 429, got: {status_codes}"
    
    @pytest.mark.anyio
    async def test_forgot_password_rate_limited(self, client):
        """Test that forgot-password endpoint is rate-limited."""
        # Make more requests than the limit allows (3/minute)
        responses = []
        for i in range(6):
            response = await client.post(
                "/api/auth/forgot-password",
                json={"email": f"forgottest{i}@example.com"},
                headers={"X-Forwarded-For": "192.168.1.102"}
            )
            responses.append(response)
        
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes, f"Expected at least one 429, got: {status_codes}"
    
    @pytest.mark.anyio
    async def test_health_endpoint_not_rate_limited(self, client):
        """Test that health check is not aggressively rate-limited."""
        responses = []
        for _ in range(10):
            response = await client.get("/api/health")
            responses.append(response)
        
        # All should succeed (health endpoint shouldn't be rate-limited)
        assert all(r.status_code == 200 for r in responses)


class TestRateLimitResponseFormat:
    """Test the format of rate limit exceeded responses."""
    
    @pytest.mark.anyio
    async def test_rate_limit_response_has_correct_fields(self, client):
        """Test that 429 response has all required fields."""
        # Trigger rate limiting
        responses = []
        for i in range(10):
            response = await client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrong"},
                headers={"X-Forwarded-For": "192.168.1.200"}
            )
            responses.append(response)
            if response.status_code == 429:
                break
        
        # Find the 429 response
        rate_limited = [r for r in responses if r.status_code == 429]
        
        if rate_limited:
            response = rate_limited[0]
            data = response.json()
            
            # Check required fields
            assert "detail" in data, "Response should have 'detail' field"
            assert "error_code" in data, "Response should have 'error_code' field"
            assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
            assert "retry_after_seconds" in data, "Response should have 'retry_after_seconds' field"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
