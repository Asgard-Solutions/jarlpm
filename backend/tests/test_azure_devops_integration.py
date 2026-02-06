"""
Azure DevOps Integration API Tests for JarlPM
Tests the Azure DevOps PAT-based integration endpoints.
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


class TestAzureDevOpsIntegration:
    """Azure DevOps integration endpoint tests"""
    
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
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code} - {login_response.text}")
        
        yield
        
        # Cleanup
        self.session.close()
    
    # ============================================
    # Status Endpoints
    # ============================================
    
    def test_get_azure_devops_status(self):
        """Test GET /api/integrations/status/azure_devops returns proper status"""
        response = self.session.get(f"{BASE_URL}/api/integrations/status/azure_devops")
        
        # Should return 200 (subscription required check may return 402)
        assert response.status_code in [200, 402], f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # Verify response structure
            assert "status" in data, "Response should contain 'status' field"
            assert "connected" in data, "Response should contain 'connected' field"
            assert data["status"] in ["connected", "disconnected", "error"], f"Invalid status: {data['status']}"
            print(f"Azure DevOps status: {data['status']}, connected: {data['connected']}")
        else:
            print("Subscription required for integrations (402)")
    
    def test_get_all_integrations_status(self):
        """Test GET /api/integrations/status includes azure_devops"""
        response = self.session.get(f"{BASE_URL}/api/integrations/status")
        
        assert response.status_code in [200, 402], f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # Verify azure_devops is in the response
            assert "azure_devops" in data, "Response should contain 'azure_devops' key"
            
            ado_status = data["azure_devops"]
            assert "status" in ado_status, "azure_devops should have 'status' field"
            assert "configured" in ado_status, "azure_devops should have 'configured' field"
            
            # Azure DevOps is PAT-based, so configured should always be True
            assert ado_status["configured"] == True, "Azure DevOps should always be configured (PAT-based)"
            
            print(f"All integrations status retrieved. Azure DevOps: {ado_status}")
        else:
            print("Subscription required for integrations (402)")
    
    # ============================================
    # Connect Endpoint Validation
    # ============================================
    
    def test_connect_azure_devops_requires_org_url_and_pat(self):
        """Test POST /api/integrations/azure-devops/connect requires org_url and pat"""
        # Test with empty body
        response = self.session.post(
            f"{BASE_URL}/api/integrations/azure-devops/connect",
            json={}
        )
        
        # Should return 422 (validation error) or 402 (subscription required)
        assert response.status_code in [422, 402], f"Expected 422 or 402, got: {response.status_code} - {response.text}"
        
        if response.status_code == 422:
            print("Validation error returned as expected for missing fields")
        else:
            print("Subscription required (402)")
    
    def test_connect_azure_devops_missing_pat(self):
        """Test connect endpoint with missing PAT"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/azure-devops/connect",
            json={"organization_url": "https://dev.azure.com/testorg"}
        )
        
        # Should return 422 (validation error) or 402 (subscription required)
        assert response.status_code in [422, 402], f"Expected 422 or 402, got: {response.status_code} - {response.text}"
        print(f"Missing PAT validation: {response.status_code}")
    
    def test_connect_azure_devops_missing_org_url(self):
        """Test connect endpoint with missing organization URL"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/azure-devops/connect",
            json={"pat": "fake_pat_token"}
        )
        
        # Should return 422 (validation error) or 402 (subscription required)
        assert response.status_code in [422, 402], f"Expected 422 or 402, got: {response.status_code} - {response.text}"
        print(f"Missing org_url validation: {response.status_code}")
    
    def test_connect_azure_devops_invalid_pat(self):
        """Test connect endpoint with invalid PAT returns proper error"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/azure-devops/connect",
            json={
                "organization_url": "https://dev.azure.com/testorg",
                "pat": "invalid_pat_token_12345"
            }
        )
        
        # Should return 400 (invalid PAT) or 402 (subscription required)
        assert response.status_code in [400, 402], f"Expected 400 or 402, got: {response.status_code} - {response.text}"
        
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data, "Error response should contain 'detail'"
            print(f"Invalid PAT error: {data['detail']}")
        else:
            print("Subscription required (402)")
    
    # ============================================
    # Disconnect Endpoint
    # ============================================
    
    def test_disconnect_azure_devops_when_not_connected(self):
        """Test POST /api/integrations/azure-devops/disconnect when not connected"""
        response = self.session.post(f"{BASE_URL}/api/integrations/azure-devops/disconnect")
        
        # Should return 200 with status "not_connected" or "disconnected"
        # Or 402 if subscription required
        assert response.status_code in [200, 402], f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data, "Response should contain 'status'"
            assert data["status"] in ["not_connected", "disconnected"], f"Unexpected status: {data['status']}"
            print(f"Disconnect response: {data['status']}")
        else:
            print("Subscription required (402)")
    
    # ============================================
    # Preview Endpoint
    # ============================================
    
    def test_preview_azure_devops_push_not_connected(self):
        """Test POST /api/integrations/azure-devops/preview returns error when not connected"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/azure-devops/preview",
            json={
                "epic_id": TEST_EPIC_ID,
                "push_scope": "epic_features_stories",
                "include_bugs": False
            }
        )
        
        # Should return 400 (not connected) or 402 (subscription required)
        assert response.status_code in [400, 402], f"Expected 400 or 402, got: {response.status_code} - {response.text}"
        
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data, "Error response should contain 'detail'"
            assert "not connected" in data["detail"].lower(), f"Expected 'not connected' error, got: {data['detail']}"
            print(f"Preview error (not connected): {data['detail']}")
        else:
            print("Subscription required (402)")
    
    def test_preview_azure_devops_push_missing_epic_id(self):
        """Test preview endpoint with missing epic_id"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/azure-devops/preview",
            json={
                "push_scope": "epic_features_stories",
                "include_bugs": False
            }
        )
        
        # Should return 422 (validation error) or 402 (subscription required)
        assert response.status_code in [422, 402], f"Expected 422 or 402, got: {response.status_code} - {response.text}"
        print(f"Missing epic_id validation: {response.status_code}")
    
    # ============================================
    # Push Endpoint
    # ============================================
    
    def test_push_azure_devops_not_connected(self):
        """Test POST /api/integrations/azure-devops/push returns error when not connected"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/azure-devops/push",
            json={
                "epic_id": TEST_EPIC_ID,
                "project_name": "TestProject",
                "push_scope": "epic_features_stories",
                "include_bugs": False,
                "dry_run": False
            }
        )
        
        # Should return 400 (not connected) or 402 (subscription required)
        assert response.status_code in [400, 402], f"Expected 400 or 402, got: {response.status_code} - {response.text}"
        
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data, "Error response should contain 'detail'"
            assert "not connected" in data["detail"].lower(), f"Expected 'not connected' error, got: {data['detail']}"
            print(f"Push error (not connected): {data['detail']}")
        else:
            print("Subscription required (402)")
    
    def test_push_azure_devops_missing_project_name(self):
        """Test push endpoint with missing project_name"""
        response = self.session.post(
            f"{BASE_URL}/api/integrations/azure-devops/push",
            json={
                "epic_id": TEST_EPIC_ID,
                "push_scope": "epic_features_stories"
            }
        )
        
        # Should return 422 (validation error) or 402 (subscription required)
        assert response.status_code in [422, 402], f"Expected 422 or 402, got: {response.status_code} - {response.text}"
        print(f"Missing project_name validation: {response.status_code}")
    
    # ============================================
    # Data Endpoints (require connection)
    # ============================================
    
    def test_get_azure_devops_projects_not_connected(self):
        """Test GET /api/integrations/azure-devops/projects when not connected"""
        response = self.session.get(f"{BASE_URL}/api/integrations/azure-devops/projects")
        
        # Should return 400 (not connected) or 402 (subscription required)
        assert response.status_code in [400, 402], f"Expected 400 or 402, got: {response.status_code} - {response.text}"
        
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data, "Error response should contain 'detail'"
            print(f"Projects error (not connected): {data['detail']}")
        else:
            print("Subscription required (402)")
    
    def test_get_azure_devops_test_not_connected(self):
        """Test GET /api/integrations/azure-devops/test when not connected"""
        response = self.session.get(f"{BASE_URL}/api/integrations/azure-devops/test")
        
        # Should return 400 (not connected) or 402 (subscription required) or 200 with error status
        assert response.status_code in [200, 400, 402], f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # Test endpoint may return status: "error" when not connected
            if data.get("status") == "error":
                print(f"Test returned error status: {data.get('error', 'unknown')}")
            else:
                print(f"Test response: {data}")
        elif response.status_code == 400:
            data = response.json()
            print(f"Test error (not connected): {data.get('detail', 'unknown')}")
        else:
            print("Subscription required (402)")


class TestAzureDevOpsIntegrationUnauthenticated:
    """Test Azure DevOps endpoints without authentication"""
    
    def test_status_requires_auth(self):
        """Test that status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/integrations/status/azure_devops")
        assert response.status_code == 401, f"Expected 401, got: {response.status_code}"
        print("Status endpoint requires auth (401)")
    
    def test_connect_requires_auth(self):
        """Test that connect endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/azure-devops/connect",
            json={"organization_url": "https://dev.azure.com/test", "pat": "test"}
        )
        assert response.status_code == 401, f"Expected 401, got: {response.status_code}"
        print("Connect endpoint requires auth (401)")
    
    def test_disconnect_requires_auth(self):
        """Test that disconnect endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/integrations/azure-devops/disconnect")
        assert response.status_code == 401, f"Expected 401, got: {response.status_code}"
        print("Disconnect endpoint requires auth (401)")
    
    def test_preview_requires_auth(self):
        """Test that preview endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/azure-devops/preview",
            json={"epic_id": "test", "push_scope": "epic_only"}
        )
        assert response.status_code == 401, f"Expected 401, got: {response.status_code}"
        print("Preview endpoint requires auth (401)")
    
    def test_push_requires_auth(self):
        """Test that push endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/integrations/azure-devops/push",
            json={"epic_id": "test", "project_name": "test", "push_scope": "epic_only"}
        )
        assert response.status_code == 401, f"Expected 401, got: {response.status_code}"
        print("Push endpoint requires auth (401)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
