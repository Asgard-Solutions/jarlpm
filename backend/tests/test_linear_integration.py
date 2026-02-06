"""
Linear Integration API Tests for JarlPM
Tests the Linear OAuth-based integration endpoints.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@jarlpm.com"
TEST_PASSWORD = "Test123!"

# Test epic ID (locked epic for testing)
TEST_EPIC_ID = "epic_54e41a1b"


class TestLinearIntegration:
    """Linear integration endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get session
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
    def teardown_method(self):
        """Cleanup after each test"""
        self.session.close()

    # ==================== STATUS ENDPOINTS ====================
    
    def test_get_linear_status(self):
        """Test GET /api/integrations/status/linear returns proper status"""
        response = self.session.get(f"{BASE_URL}/api/integrations/status/linear")
        assert response.status_code == 200
        data = response.json()
        assert "connected" in data
        assert "status" in data
        assert data["status"] in ["connected", "disconnected"]
        
    def test_overall_status_includes_linear(self):
        """Test GET /api/integrations/status includes Linear"""
        response = self.session.get(f"{BASE_URL}/api/integrations/status")
        assert response.status_code == 200
        data = response.json()
        assert "linear" in data
        # Linear should have configured = false (OAuth not set)
        
    # ==================== CONNECT ENDPOINTS ====================
    
    def test_connect_requires_callback_url(self):
        """Test POST /api/integrations/linear/connect requires frontend_callback_url"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/linear/connect",
            json={}
        )
        assert response.status_code == 422  # Validation error
        
    def test_connect_returns_error_when_oauth_not_configured(self):
        """Test connect returns error when OAuth credentials not configured"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/linear/connect",
            json={"frontend_callback_url": "http://localhost:3000/settings"}
        )
        # Should return 400 or 520 (server error) because OAuth is not configured
        assert response.status_code in [400, 500, 520]
        
    # ==================== DISCONNECT ENDPOINTS ====================
    
    def test_disconnect_when_not_connected(self):
        """Test POST /api/integrations/linear/disconnect when not connected"""
        response = self.session.post(f"{BASE_URL}/api/integrations/linear/disconnect")
        # Should succeed or return status
        assert response.status_code in [200, 400]
        
    # ==================== DATA ENDPOINTS ====================
    
    def test_get_teams_when_not_connected(self):
        """Test GET /api/integrations/linear/teams returns error when not connected"""
        response = self.session.get(f"{BASE_URL}/api/integrations/linear/teams")
        assert response.status_code == 400
        data = response.json()
        assert "not connected" in data["detail"].lower()
        
    def test_get_labels_when_not_connected(self):
        """Test GET /api/integrations/linear/labels returns error when not connected"""
        response = self.session.get(f"{BASE_URL}/api/integrations/linear/labels")
        assert response.status_code == 400
        
    # ==================== PREVIEW ENDPOINTS ====================
    
    def test_preview_when_not_connected(self):
        """Test POST /api/integrations/linear/preview returns error when not connected"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/linear/preview",
            json={
                "epic_id": TEST_EPIC_ID,
                "push_scope": "epic_features_stories",
                "include_bugs": False
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "not connected" in data["detail"].lower()
        
    def test_preview_requires_epic_id(self):
        """Test preview validates required epic_id field"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/linear/preview",
            json={"push_scope": "epic_only"}
        )
        assert response.status_code in [400, 422]
        
    # ==================== PUSH ENDPOINTS ====================
    
    def test_push_when_not_connected(self):
        """Test POST /api/integrations/linear/push returns error when not connected"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/linear/push",
            json={
                "epic_id": TEST_EPIC_ID,
                "team_id": "team_test",
                "push_scope": "epic_features_stories"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "not connected" in data["detail"].lower()
        
    def test_push_requires_team_id(self):
        """Test push validates required team_id field"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/linear/push",
            json={
                "epic_id": TEST_EPIC_ID,
                "push_scope": "epic_only"
            }
        )
        assert response.status_code in [400, 422]
        
    # ==================== CONFIGURE ENDPOINTS ====================
    
    def test_configure_when_not_connected(self):
        """Test PUT /api/integrations/linear/configure returns error when not connected"""
        response = self.session.put(
            f"{BASE_URL}/api/integrations/linear/configure",
            json={"default_team_id": "team_test"}
        )
        # 400 = not connected, 422 = validation error
        assert response.status_code in [400, 422]


class TestLinearAuthRequired:
    """Test Linear endpoints require authentication"""
    
    def test_status_requires_auth(self):
        """Test status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/integrations/status/linear")
        assert response.status_code == 401
        
    def test_connect_requires_auth(self):
        """Test connect endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/linear/connect",
            json={"frontend_callback_url": "http://localhost:3000"}
        )
        assert response.status_code == 401
        
    def test_disconnect_requires_auth(self):
        """Test disconnect endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/integrations/linear/disconnect")
        assert response.status_code == 401
        
    def test_teams_requires_auth(self):
        """Test teams endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/integrations/linear/teams")
        assert response.status_code == 401
        
    def test_preview_requires_auth(self):
        """Test preview endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/linear/preview",
            json={"epic_id": "test"}
        )
        assert response.status_code == 401
        
    def test_push_requires_auth(self):
        """Test push endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/linear/push",
            json={"epic_id": "test", "team_id": "test"}
        )
        assert response.status_code == 401
        
    def test_configure_requires_auth(self):
        """Test configure endpoint requires authentication"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/linear/configure",
            json={"default_team_id": "test"}
        )
        assert response.status_code in [401, 422]  # 401 if auth checked first, 422 if validation
