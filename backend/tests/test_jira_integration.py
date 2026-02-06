"""
Jira Cloud Integration API Tests for JarlPM
Tests the Jira OAuth-based integration endpoints.
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


class TestJiraIntegration:
    """Jira integration endpoint tests"""
    
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
    
    def test_get_jira_status(self):
        """Test GET /api/integrations/status/jira returns proper status"""
        response = self.session.get(f"{BASE_URL}/api/integrations/status/jira")
        assert response.status_code == 200
        data = response.json()
        assert "connected" in data
        assert "status" in data
        assert data["status"] in ["connected", "disconnected"]
        
    def test_overall_status_includes_jira(self):
        """Test GET /api/integrations/status includes Jira"""
        response = self.session.get(f"{BASE_URL}/api/integrations/status")
        assert response.status_code == 200
        data = response.json()
        assert "jira" in data
        
    # ==================== CONNECT ENDPOINTS ====================
    
    def test_connect_requires_callback_url(self):
        """Test POST /api/integrations/jira/connect requires frontend_callback_url"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/jira/connect",
            json={}
        )
        assert response.status_code == 422  # Validation error
        
    def test_connect_returns_error_when_oauth_not_configured(self):
        """Test connect returns error when OAuth credentials not configured"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/jira/connect",
            json={"frontend_callback_url": "http://localhost:3000/settings"}
        )
        # Should return 400 because OAuth is not configured on server
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "oauth" in data["detail"].lower() or "credential" in data["detail"].lower() or "configured" in data["detail"].lower()
        
    # ==================== DISCONNECT ENDPOINTS ====================
    
    def test_disconnect_when_not_connected(self):
        """Test POST /api/integrations/jira/disconnect when not connected"""
        response = self.session.post(f"{BASE_URL}/api/integrations/jira/disconnect")
        # Should succeed or return status
        assert response.status_code in [200, 400]
        
    # ==================== DATA ENDPOINTS ====================
    
    def test_get_sites_when_not_connected(self):
        """Test GET /api/integrations/jira/sites returns error when not connected"""
        response = self.session.get(f"{BASE_URL}/api/integrations/jira/sites")
        assert response.status_code == 400
        data = response.json()
        assert "not connected" in data["detail"].lower()
        
    def test_get_projects_when_not_connected(self):
        """Test GET /api/integrations/jira/projects returns error when not connected"""
        response = self.session.get(f"{BASE_URL}/api/integrations/jira/projects")
        assert response.status_code == 400
        
    def test_get_fields_when_not_connected(self):
        """Test GET /api/integrations/jira/fields returns error when not connected"""
        response = self.session.get(f"{BASE_URL}/api/integrations/jira/fields")
        assert response.status_code == 400
        
    def test_get_issue_types_when_not_connected(self):
        """Test GET /api/integrations/jira/projects/{key}/issue-types returns error"""
        response = self.session.get(f"{BASE_URL}/api/integrations/jira/projects/PROJ/issue-types")
        assert response.status_code == 400
        
    # ==================== PREVIEW ENDPOINTS ====================
    
    def test_preview_when_not_connected(self):
        """Test POST /api/integrations/jira/preview returns error when not connected"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/jira/preview",
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
            f"{BASE_URL}/api/integrations/jira/preview",
            json={"push_scope": "epic_only"}
        )
        assert response.status_code in [400, 422]
        
    # ==================== PUSH ENDPOINTS ====================
    
    def test_push_when_not_connected(self):
        """Test POST /api/integrations/jira/push returns error when not connected"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/jira/push",
            json={
                "epic_id": TEST_EPIC_ID,
                "project_key": "PROJ",
                "push_scope": "epic_features_stories"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "not connected" in data["detail"].lower()
        
    def test_push_requires_project_key(self):
        """Test push validates required project_key field"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/jira/push",
            json={
                "epic_id": TEST_EPIC_ID,
                "push_scope": "epic_only"
            }
        )
        assert response.status_code in [400, 422]
        
    # ==================== CONFIGURE ENDPOINTS ====================
    
    def test_configure_when_not_connected(self):
        """Test PUT /api/integrations/jira/configure returns error when not connected"""
        response = self.session.put(
            f"{BASE_URL}/api/integrations/jira/configure",
            json={"default_project_key": "PROJ"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "not connected" in data["detail"].lower()


class TestJiraAuthRequired:
    """Test Jira endpoints require authentication"""
    
    def test_status_requires_auth(self):
        """Test status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/integrations/status/jira")
        assert response.status_code == 401
        
    def test_connect_requires_auth(self):
        """Test connect endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/jira/connect",
            json={"frontend_callback_url": "http://localhost:3000"}
        )
        assert response.status_code == 401
        
    def test_disconnect_requires_auth(self):
        """Test disconnect endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/integrations/jira/disconnect")
        assert response.status_code == 401
        
    def test_sites_requires_auth(self):
        """Test sites endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/integrations/jira/sites")
        assert response.status_code == 401
        
    def test_projects_requires_auth(self):
        """Test projects endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/integrations/jira/projects")
        assert response.status_code == 401
        
    def test_preview_requires_auth(self):
        """Test preview endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/jira/preview",
            json={"epic_id": "test"}
        )
        assert response.status_code == 401
        
    def test_push_requires_auth(self):
        """Test push endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/jira/push",
            json={"epic_id": "test", "project_key": "PROJ"}
        )
        assert response.status_code == 401
        
    def test_configure_requires_auth(self):
        """Test configure endpoint requires authentication"""
        response = requests.put(
            f"{BASE_URL}/api/integrations/jira/configure",
            json={}
        )
        assert response.status_code == 401
