#!/usr/bin/env python3
"""
JarlPM Backend API Testing Suite - PostgreSQL Migration Tests
Tests all API endpoints with proper authentication using pytest

Modules tested:
- Health endpoints (/, /health)
- Auth endpoints (/auth/me, /auth/logout)
- Subscription endpoints (/subscription/status)
- Epic CRUD operations (/epics)
- LLM Provider endpoints (/llm-providers)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://epic-forge.preview.emergentagent.com').rstrip('/')


class TestHealthEndpoints:
    """Test basic health check endpoints - no auth required"""
    
    def test_api_root(self):
        """Test API root endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        assert "JarlPM" in data.get("message", "")
    
    def test_health_check(self):
        """Test /api/health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        assert data.get("service") == "jarlpm"


class TestAuthEndpointsUnauthenticated:
    """Test auth endpoints without valid session - should return 401"""
    
    def test_get_me_without_auth(self):
        """Test /api/auth/me without authentication returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
    
    def test_logout_without_auth(self):
        """Test /api/auth/logout without authentication - should still work"""
        response = requests.post(f"{BASE_URL}/api/auth/logout", timeout=10)
        # Logout should work even without auth (just clears cookie)
        assert response.status_code == 200
    
    def test_session_exchange_invalid(self):
        """Test /api/auth/session with invalid session_id"""
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            json={"session_id": "invalid_session_id"},
            timeout=10
        )
        # Should return 401 for invalid session
        assert response.status_code in [401, 500]


class TestSubscriptionEndpointsUnauthenticated:
    """Test subscription endpoints without auth - should return 401"""
    
    def test_subscription_status_without_auth(self):
        """Test /api/subscription/status without authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/status", timeout=10)
        assert response.status_code == 401
    
    def test_create_checkout_without_auth(self):
        """Test /api/subscription/create-checkout without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            json={"origin_url": "https://example.com"},
            timeout=10
        )
        assert response.status_code == 401


class TestEpicEndpointsUnauthenticated:
    """Test epic endpoints without auth - should return 401"""
    
    def test_list_epics_without_auth(self):
        """Test /api/epics without authentication"""
        response = requests.get(f"{BASE_URL}/api/epics", timeout=10)
        assert response.status_code == 401
    
    def test_create_epic_without_auth(self):
        """Test POST /api/epics without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/epics",
            json={"title": "Test Epic"},
            timeout=10
        )
        assert response.status_code == 401
    
    def test_get_epic_without_auth(self):
        """Test GET /api/epics/{id} without authentication"""
        response = requests.get(f"{BASE_URL}/api/epics/epic_test123", timeout=10)
        assert response.status_code == 401
    
    def test_delete_epic_without_auth(self):
        """Test DELETE /api/epics/{id} without authentication"""
        response = requests.delete(f"{BASE_URL}/api/epics/epic_test123", timeout=10)
        assert response.status_code == 401


class TestLLMProviderEndpointsUnauthenticated:
    """Test LLM provider endpoints without auth - should return 401"""
    
    def test_list_llm_providers_without_auth(self):
        """Test /api/llm-providers without authentication"""
        response = requests.get(f"{BASE_URL}/api/llm-providers", timeout=10)
        assert response.status_code == 401
    
    def test_create_llm_provider_without_auth(self):
        """Test POST /api/llm-providers without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/llm-providers",
            json={
                "provider": "openai",
                "api_key": "test_key"
            },
            timeout=10
        )
        assert response.status_code == 401


class TestAPIResponseStructure:
    """Test API response structure and data types"""
    
    def test_health_response_structure(self):
        """Verify health endpoint returns proper JSON structure"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert isinstance(data, dict)
        assert "status" in data
        assert "service" in data
        assert isinstance(data["status"], str)
        assert isinstance(data["service"], str)
    
    def test_root_response_structure(self):
        """Verify root endpoint returns proper JSON structure"""
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert isinstance(data, dict)
        assert "message" in data
        assert "status" in data
    
    def test_401_error_response_structure(self):
        """Verify 401 error responses have proper structure"""
        response = requests.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert response.status_code == 401
        data = response.json()
        
        # FastAPI returns {"detail": "..."} for HTTPException
        assert isinstance(data, dict)
        assert "detail" in data
        assert isinstance(data["detail"], str)


class TestCORSHeaders:
    """Test CORS configuration"""
    
    def test_cors_headers_present(self):
        """Verify CORS headers are present in response"""
        response = requests.options(
            f"{BASE_URL}/api/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET"
            },
            timeout=10
        )
        # Should allow CORS
        assert response.status_code in [200, 204]


class TestInputValidation:
    """Test input validation on endpoints"""
    
    def test_session_exchange_missing_body(self):
        """Test /api/auth/session with missing body"""
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            json={},
            timeout=10
        )
        # Should return 422 for validation error
        assert response.status_code == 422
    
    def test_session_exchange_invalid_json(self):
        """Test /api/auth/session with invalid JSON"""
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            data="not json",
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        # Should return 422 for validation error
        assert response.status_code == 422


class TestEndpointAvailability:
    """Test that all expected endpoints exist"""
    
    def test_auth_endpoints_exist(self):
        """Verify auth endpoints are registered"""
        # /auth/me - should return 401 (not 404)
        response = requests.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert response.status_code != 404, "Endpoint /api/auth/me not found"
        
        # /auth/logout - should return 200 (not 404)
        response = requests.post(f"{BASE_URL}/api/auth/logout", timeout=10)
        assert response.status_code != 404, "Endpoint /api/auth/logout not found"
        
        # /auth/session - should return 422 or 401 (not 404)
        response = requests.post(f"{BASE_URL}/api/auth/session", json={}, timeout=10)
        assert response.status_code != 404, "Endpoint /api/auth/session not found"
    
    def test_subscription_endpoints_exist(self):
        """Verify subscription endpoints are registered"""
        # /subscription/status - should return 401 (not 404)
        response = requests.get(f"{BASE_URL}/api/subscription/status", timeout=10)
        assert response.status_code != 404, "Endpoint /api/subscription/status not found"
        
        # /subscription/create-checkout - should return 401 (not 404)
        response = requests.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            json={"origin_url": "https://example.com"},
            timeout=10
        )
        assert response.status_code != 404, "Endpoint /api/subscription/create-checkout not found"
    
    def test_epic_endpoints_exist(self):
        """Verify epic endpoints are registered"""
        # /epics - should return 401 (not 404)
        response = requests.get(f"{BASE_URL}/api/epics", timeout=10)
        assert response.status_code != 404, "Endpoint /api/epics not found"
        
        # /epics/{id} - should return 401 (not 404)
        response = requests.get(f"{BASE_URL}/api/epics/test_id", timeout=10)
        assert response.status_code != 404, "Endpoint /api/epics/{id} not found"
    
    def test_llm_provider_endpoints_exist(self):
        """Verify LLM provider endpoints are registered"""
        # /llm-providers - should return 401 (not 404)
        response = requests.get(f"{BASE_URL}/api/llm-providers", timeout=10)
        assert response.status_code != 404, "Endpoint /api/llm-providers not found"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
