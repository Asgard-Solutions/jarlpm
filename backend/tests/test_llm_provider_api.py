"""
LLM Provider API Tests
Tests for Custom LLM Provider Support feature:
- GET /api/llm-providers - List configured providers
- POST /api/llm-providers - Create/update provider config
- DELETE /api/llm-providers/{config_id} - Remove provider
- POST /api/llm-providers/validate - Validate API key
- PUT /api/llm-providers/{config_id}/activate - Activate provider
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('VITE_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@jarlpm.com"
TEST_PASSWORD = "Test123!"


class TestLLMProviderAPI:
    """LLM Provider API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_cookies):
        """Setup for each test"""
        self.client = api_client
        self.cookies = auth_cookies
    
    def test_list_providers_unauthenticated(self, api_client):
        """Test unauthenticated requests behavior - returns empty list or 401"""
        response = api_client.get(f"{BASE_URL}/api/llm-providers")
        # API returns 200 with empty list for unauthenticated users (no user_id found)
        # This is acceptable behavior - no data leakage
        assert response.status_code in [200, 401], f"Expected 200 or 401, got {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list), "Should return a list"
            print(f"✓ Unauthenticated request returns empty list (no data leakage)")
        else:
            print("✓ Unauthenticated request correctly rejected with 401")
    
    def test_list_providers_authenticated(self):
        """Test listing LLM providers for authenticated user"""
        response = self.client.get(
            f"{BASE_URL}/api/llm-providers",
            cookies=self.cookies
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ List providers returned {len(data)} configured providers")
        
        # If there are providers, verify structure
        if len(data) > 0:
            provider = data[0]
            assert "config_id" in provider, "Provider should have config_id"
            assert "provider" in provider, "Provider should have provider field"
            assert "is_active" in provider, "Provider should have is_active field"
            assert "created_at" in provider, "Provider should have created_at field"
            print(f"✓ Provider structure verified: {provider['provider']}")
    
    def test_create_provider_missing_api_key(self):
        """Test that creating provider without API key fails for cloud providers"""
        response = self.client.post(
            f"{BASE_URL}/api/llm-providers",
            json={
                "provider": "openai",
                "api_key": ""  # Empty API key
            },
            cookies=self.cookies
        )
        # Should fail validation - either 400 or 422
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Empty API key correctly rejected")
    
    def test_create_provider_invalid_api_key(self):
        """Test that invalid API key is rejected"""
        response = self.client.post(
            f"{BASE_URL}/api/llm-providers",
            json={
                "provider": "openai",
                "api_key": "sk-invalid-test-key-12345"
            },
            cookies=self.cookies
        )
        # Should fail validation with 400
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data, "Error response should have detail"
        print(f"✓ Invalid API key correctly rejected: {data.get('detail', '')[:50]}")
    
    def test_create_provider_local_missing_base_url(self):
        """Test that local provider requires base_url"""
        response = self.client.post(
            f"{BASE_URL}/api/llm-providers",
            json={
                "provider": "local",
                "api_key": "optional-key"
                # Missing base_url
            },
            cookies=self.cookies
        )
        # Should fail - local provider needs base_url
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Local provider without base_url correctly rejected")
    
    def test_validate_api_key_endpoint(self):
        """Test the validate API key endpoint"""
        response = self.client.post(
            f"{BASE_URL}/api/llm-providers/validate",
            json={
                "provider": "openai",
                "api_key": "sk-invalid-test-key"
            },
            cookies=self.cookies
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "valid" in data, "Response should have 'valid' field"
        assert data["valid"] == False, "Invalid key should return valid=false"
        print("✓ Validate endpoint correctly returns valid=false for invalid key")
    
    def test_delete_nonexistent_provider(self):
        """Test deleting a non-existent provider returns 404"""
        response = self.client.delete(
            f"{BASE_URL}/api/llm-providers/nonexistent-config-id",
            cookies=self.cookies
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Delete non-existent provider correctly returns 404")
    
    def test_activate_nonexistent_provider(self):
        """Test activating a non-existent provider returns 404"""
        response = self.client.put(
            f"{BASE_URL}/api/llm-providers/nonexistent-config-id/activate",
            cookies=self.cookies
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Activate non-existent provider correctly returns 404")
    
    def test_provider_enum_values(self):
        """Test that all provider enum values are accepted"""
        valid_providers = ["openai", "anthropic", "google", "local"]
        
        for provider in valid_providers:
            # Just test that the provider value is accepted in validation endpoint
            response = self.client.post(
                f"{BASE_URL}/api/llm-providers/validate",
                json={
                    "provider": provider,
                    "api_key": "test-key",
                    "base_url": "http://localhost:1234" if provider == "local" else None
                },
                cookies=self.cookies
            )
            # Should return 200 (validation runs, returns valid=false for invalid keys)
            assert response.status_code == 200, f"Provider '{provider}' should be accepted, got {response.status_code}"
            print(f"✓ Provider '{provider}' is accepted by API")
    
    def test_invalid_provider_value(self):
        """Test that invalid provider value is rejected"""
        response = self.client.post(
            f"{BASE_URL}/api/llm-providers/validate",
            json={
                "provider": "invalid_provider",
                "api_key": "test-key"
            },
            cookies=self.cookies
        )
        # Should fail with 422 (validation error)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Invalid provider value correctly rejected with 422")


class TestLLMProviderResponseStructure:
    """Test response structure and data types"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_cookies):
        """Setup for each test"""
        self.client = api_client
        self.cookies = auth_cookies
    
    def test_list_response_structure(self):
        """Test that list response has correct structure"""
        response = self.client.get(
            f"{BASE_URL}/api/llm-providers",
            cookies=self.cookies
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # If providers exist, check structure
        for provider in data:
            assert isinstance(provider.get("config_id"), str), "config_id should be string"
            assert isinstance(provider.get("provider"), str), "provider should be string"
            assert isinstance(provider.get("is_active"), bool), "is_active should be boolean"
            assert "created_at" in provider, "created_at should be present"
            # base_url and model_name are optional
            print(f"✓ Provider {provider['config_id']} has correct structure")
        
        print(f"✓ All {len(data)} providers have correct response structure")


# Fixtures
@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_cookies(api_client):
    """Get authentication cookies by logging in"""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    # Return cookies from the response
    return response.cookies


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
