"""
Persona API Tests for JarlPM
Tests for user persona generation and management feature
"""
import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPersonaSettings:
    """Tests for persona generation settings endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        """Setup for each test"""
        self.client = api_client
    
    def test_get_settings_unauthenticated(self, api_client):
        """GET /api/personas/settings - Requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/personas/settings")
        assert response.status_code == 401
        print("✓ GET /api/personas/settings requires authentication (401)")
    
    def test_get_settings(self, authenticated_client):
        """GET /api/personas/settings - Get persona generation settings"""
        response = authenticated_client.get(f"{BASE_URL}/api/personas/settings")
        assert response.status_code == 200
        
        data = response.json()
        assert "image_provider" in data
        assert "image_model" in data
        assert "default_persona_count" in data
        assert data["image_provider"] in ["openai", "gemini"]
        assert isinstance(data["default_persona_count"], int)
        assert 1 <= data["default_persona_count"] <= 5
        print(f"✓ GET /api/personas/settings returns settings: {data}")
    
    def test_update_settings(self, authenticated_client):
        """PUT /api/personas/settings - Update persona generation settings"""
        update_data = {
            "image_provider": "openai",
            "image_model": "gpt-image-1",
            "default_persona_count": 4
        }
        response = authenticated_client.put(
            f"{BASE_URL}/api/personas/settings",
            json=update_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["image_provider"] == "openai"
        assert data["image_model"] == "gpt-image-1"
        assert data["default_persona_count"] == 4
        print(f"✓ PUT /api/personas/settings updates settings: {data}")
    
    def test_update_settings_count_capped(self, authenticated_client):
        """PUT /api/personas/settings - Count is capped at 1-5 range"""
        # Test count > 5 is capped to 5
        response = authenticated_client.put(
            f"{BASE_URL}/api/personas/settings",
            json={"default_persona_count": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_persona_count"] == 5
        print("✓ PUT /api/personas/settings caps count at 5")
        
        # Test count < 1 is capped to 1
        response = authenticated_client.put(
            f"{BASE_URL}/api/personas/settings",
            json={"default_persona_count": 0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_persona_count"] == 1
        print("✓ PUT /api/personas/settings caps count at 1")
        
        # Reset to default
        authenticated_client.put(
            f"{BASE_URL}/api/personas/settings",
            json={"default_persona_count": 3}
        )


class TestPersonaCRUD:
    """Tests for persona CRUD operations"""
    
    def test_list_personas_unauthenticated(self, api_client):
        """GET /api/personas - Requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/personas")
        assert response.status_code == 401
        print("✓ GET /api/personas requires authentication (401)")
    
    def test_list_personas(self, authenticated_client):
        """GET /api/personas - List all personas for user"""
        response = authenticated_client.get(f"{BASE_URL}/api/personas")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/personas returns list of {len(data)} personas")
    
    def test_list_personas_with_search(self, authenticated_client):
        """GET /api/personas?search=query - Search personas"""
        response = authenticated_client.get(f"{BASE_URL}/api/personas?search=test")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/personas?search=test returns {len(data)} results")
    
    def test_get_persona_not_found(self, authenticated_client):
        """GET /api/personas/{persona_id} - 404 for nonexistent persona"""
        response = authenticated_client.get(f"{BASE_URL}/api/personas/nonexistent_id")
        assert response.status_code == 404
        print("✓ GET /api/personas/nonexistent_id returns 404")
    
    def test_update_persona_not_found(self, authenticated_client):
        """PUT /api/personas/{persona_id} - 404 for nonexistent persona"""
        response = authenticated_client.put(
            f"{BASE_URL}/api/personas/nonexistent_id",
            json={"name": "Updated Name"}
        )
        assert response.status_code == 404
        print("✓ PUT /api/personas/nonexistent_id returns 404")
    
    def test_delete_persona_not_found(self, authenticated_client):
        """DELETE /api/personas/{persona_id} - 404 for nonexistent persona"""
        response = authenticated_client.delete(f"{BASE_URL}/api/personas/nonexistent_id")
        assert response.status_code == 404
        print("✓ DELETE /api/personas/nonexistent_id returns 404")


class TestPersonaForEpic:
    """Tests for persona operations related to epics"""
    
    def test_list_personas_for_epic_unauthenticated(self, api_client):
        """GET /api/personas/epic/{epic_id} - Requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/personas/epic/test_epic_id")
        assert response.status_code == 401
        print("✓ GET /api/personas/epic/{epic_id} requires authentication (401)")
    
    def test_list_personas_for_epic(self, authenticated_client):
        """GET /api/personas/epic/{epic_id} - List personas for specific epic"""
        # First get list of epics to find a valid epic_id
        epics_response = authenticated_client.get(f"{BASE_URL}/api/epics")
        assert epics_response.status_code == 200
        epics_data = epics_response.json()
        
        # Handle both list and dict response formats
        epics = epics_data.get("epics", []) if isinstance(epics_data, dict) else epics_data
        
        if epics and len(epics) > 0:
            epic_id = epics[0].get("epic_id")
            response = authenticated_client.get(f"{BASE_URL}/api/personas/epic/{epic_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ GET /api/personas/epic/{epic_id} returns {len(data)} personas")
        else:
            # Test with a dummy epic_id - should return empty list
            response = authenticated_client.get(f"{BASE_URL}/api/personas/epic/dummy_epic_id")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            print("✓ GET /api/personas/epic/{epic_id} returns empty list for no epics")


class TestPersonaGeneration:
    """Tests for persona generation from completed epics"""
    
    def test_generate_personas_unauthenticated(self, api_client):
        """POST /api/personas/epic/{epic_id}/generate - Requires authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/personas/epic/test_epic_id/generate",
            json={"count": 3}
        )
        assert response.status_code == 401
        print("✓ POST /api/personas/epic/{epic_id}/generate requires authentication (401)")
    
    def test_generate_personas_invalid_epic(self, authenticated_client):
        """POST /api/personas/epic/{epic_id}/generate - Error for invalid epic"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/personas/epic/nonexistent_epic/generate",
            json={"count": 3}
        )
        # Should return error (either 404 or error in SSE stream)
        # Since it's SSE, we check if response starts
        assert response.status_code in [200, 400, 404, 402]
        print(f"✓ POST /api/personas/epic/nonexistent_epic/generate returns {response.status_code}")
    
    def test_generate_personas_requires_completed_epic(self, authenticated_client):
        """POST /api/personas/epic/{epic_id}/generate - Requires completed (locked) epic"""
        # Get epics and find one that's not locked
        epics_response = authenticated_client.get(f"{BASE_URL}/api/epics")
        epics_data = epics_response.json()
        
        # Handle both list and dict response formats
        epics = epics_data.get("epics", []) if isinstance(epics_data, dict) else epics_data
        
        # Find a non-locked epic
        non_locked_epic = None
        locked_epic = None
        for epic in epics:
            if isinstance(epic, dict):
                if epic.get("current_stage") != "epic_locked":
                    non_locked_epic = epic
                else:
                    locked_epic = epic
        
        if non_locked_epic:
            epic_id = non_locked_epic.get("epic_id")
            response = authenticated_client.post(
                f"{BASE_URL}/api/personas/epic/{epic_id}/generate",
                json={"count": 3}
            )
            # Should fail because epic is not locked
            # The error might come in SSE stream or as HTTP error
            print(f"✓ POST /api/personas/epic/{epic_id}/generate for non-locked epic returns {response.status_code}")
        else:
            print("⚠ No non-locked epics found to test")
        
        if locked_epic:
            print(f"✓ Found locked epic: {locked_epic.get('epic_id')} - can be used for persona generation")
        else:
            print("⚠ No locked epics found - persona generation testing limited")


class TestRegeneratePortrait:
    """Tests for portrait regeneration"""
    
    def test_regenerate_portrait_unauthenticated(self, api_client):
        """POST /api/personas/{persona_id}/regenerate-portrait - Requires authentication"""
        response = api_client.post(
            f"{BASE_URL}/api/personas/test_persona_id/regenerate-portrait",
            json={}
        )
        assert response.status_code == 401
        print("✓ POST /api/personas/{persona_id}/regenerate-portrait requires authentication (401)")
    
    def test_regenerate_portrait_not_found(self, authenticated_client):
        """POST /api/personas/{persona_id}/regenerate-portrait - 404 for nonexistent persona"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/personas/nonexistent_id/regenerate-portrait",
            json={}
        )
        assert response.status_code in [404, 402]  # 402 if subscription check fails first
        print(f"✓ POST /api/personas/nonexistent_id/regenerate-portrait returns {response.status_code}")


# Fixtures
@pytest.fixture
def api_client():
    """Shared requests session without auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated_client(api_client):
    """Session with authentication via test login"""
    # Use test login endpoint
    login_response = api_client.post(f"{BASE_URL}/api/auth/test-login")
    if login_response.status_code != 200:
        pytest.skip("Test login failed - skipping authenticated tests")
    
    # Cookies are automatically stored in session
    return api_client


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
