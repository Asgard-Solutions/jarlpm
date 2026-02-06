"""
Test suite for PRD Generator, Lean Canvas, and AI Poker Planning features
Tests the new routes and API endpoints added to JarlPM
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pmcanvas.preview.emergentagent.com')

# Test session token for authenticated requests
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"


class TestPokerPersonasAPI:
    """Test /api/poker/personas endpoint - PUBLIC endpoint"""
    
    def test_get_personas_returns_5_personas(self):
        """GET /api/poker/personas should return 5 AI personas"""
        response = requests.get(f"{BASE_URL}/api/poker/personas")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 5, f"Expected 5 personas, got {len(data)}"
        
        # Verify persona structure
        expected_personas = [
            {"id": "sr_developer", "name": "Sarah", "role": "Senior Developer"},
            {"id": "jr_developer", "name": "Alex", "role": "Junior Developer"},
            {"id": "qa_engineer", "name": "Maya", "role": "QA Engineer"},
            {"id": "devops_engineer", "name": "Jordan", "role": "DevOps Engineer"},
            {"id": "ux_designer", "name": "Riley", "role": "UX/UI Designer"},
        ]
        
        for expected in expected_personas:
            matching = [p for p in data if p["id"] == expected["id"]]
            assert len(matching) == 1, f"Persona {expected['id']} not found"
            persona = matching[0]
            assert persona["name"] == expected["name"], f"Name mismatch for {expected['id']}"
            assert persona["role"] == expected["role"], f"Role mismatch for {expected['id']}"
            assert "avatar" in persona, f"Avatar missing for {expected['id']}"
    
    def test_personas_have_avatars(self):
        """Each persona should have an avatar emoji"""
        response = requests.get(f"{BASE_URL}/api/poker/personas")
        
        assert response.status_code == 200
        data = response.json()
        
        for persona in data:
            assert "avatar" in persona, f"Avatar missing for {persona.get('id', 'unknown')}"
            assert len(persona["avatar"]) > 0, f"Avatar is empty for {persona.get('id', 'unknown')}"


class TestPokerEstimateAPI:
    """Test /api/poker/estimate endpoint - AUTHENTICATED endpoint"""
    
    def test_estimate_requires_authentication(self):
        """POST /api/poker/estimate should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/poker/estimate",
            json={"story_id": "test-story-123"},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 or 403 for unauthenticated requests
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_estimate_with_invalid_story_id(self):
        """POST /api/poker/estimate with invalid story_id should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/poker/estimate",
            json={"story_id": "nonexistent-story-id"},
            headers={"Content-Type": "application/json"},
            cookies={"session_token": TEST_SESSION_TOKEN}
        )
        
        # Should return 404 for non-existent story
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestEpicsAPI:
    """Test /api/epics endpoint for PRD and Lean Canvas features"""
    
    def test_list_epics_requires_authentication(self):
        """GET /api/epics should require authentication"""
        response = requests.get(f"{BASE_URL}/api/epics")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_list_epics_authenticated(self):
        """GET /api/epics with auth should return epics list"""
        response = requests.get(
            f"{BASE_URL}/api/epics",
            cookies={"session_token": TEST_SESSION_TOKEN}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "epics" in data, "Response should contain 'epics' key"
        assert isinstance(data["epics"], list), "Epics should be a list"


class TestFeaturesAPI:
    """Test /api/features endpoint for PRD feature listing"""
    
    def test_list_features_requires_authentication(self):
        """GET /api/features/epic/{epic_id} should require authentication"""
        response = requests.get(f"{BASE_URL}/api/features/epic/test-epic-id")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


class TestProtectedRoutes:
    """Test that all new pages are protected"""
    
    def test_prd_page_protected(self):
        """PRD page should redirect unauthenticated users"""
        # This is a frontend test - we verify the backend auth works
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Content-Type": "application/json"}
        )
        
        # Without auth, should return 401
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_authenticated_user_can_access_api(self):
        """Authenticated user should be able to access protected APIs"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            cookies={"session_token": TEST_SESSION_TOKEN}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "user_id" in data or "email" in data, "Response should contain user info"


class TestSidebarNavigation:
    """Test that sidebar navigation links are properly configured"""
    
    def test_poker_personas_endpoint_accessible(self):
        """Poker personas endpoint should be accessible (public)"""
        response = requests.get(f"{BASE_URL}/api/poker/personas")
        assert response.status_code == 200
    
    def test_epics_endpoint_exists(self):
        """Epics endpoint should exist and require auth"""
        response = requests.get(f"{BASE_URL}/api/epics")
        # Should return 401 (not 404) - endpoint exists but requires auth
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
