"""
Export API Tests for JarlPM
Tests export functionality for Jira/Azure DevOps file exports
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestExportAPI:
    """Export API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session and create test epic"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login via test-login
        login_response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert login_response.status_code == 200, f"Test login failed: {login_response.text}"
        
        # Create test epic
        epic_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": "TEST_Export_Epic"}
        )
        assert epic_response.status_code == 201, f"Epic creation failed: {epic_response.text}"
        self.epic_id = epic_response.json()["epic_id"]
        
        yield
        
        # Cleanup - delete test epic
        try:
            self.session.delete(f"{BASE_URL}/api/epics/{self.epic_id}")
        except:
            pass
    
    # ============================================
    # Field Mappings Tests
    # ============================================
    
    def test_get_field_mappings_returns_200(self):
        """GET /api/export/field-mappings returns 200"""
        response = self.session.get(f"{BASE_URL}/api/export/field-mappings")
        assert response.status_code == 200
    
    def test_get_field_mappings_contains_jira_mapping(self):
        """Field mappings contain Jira configuration"""
        response = self.session.get(f"{BASE_URL}/api/export/field-mappings")
        data = response.json()
        
        assert "jira" in data
        assert "epic" in data["jira"]
        assert "feature" in data["jira"]
        assert "user_story" in data["jira"]
        assert "bug" in data["jira"]
    
    def test_get_field_mappings_contains_azure_mapping(self):
        """Field mappings contain Azure DevOps configuration"""
        response = self.session.get(f"{BASE_URL}/api/export/field-mappings")
        data = response.json()
        
        assert "azure_devops" in data
        assert "epic" in data["azure_devops"]
        assert "feature" in data["azure_devops"]
        assert "user_story" in data["azure_devops"]
        assert "bug" in data["azure_devops"]
    
    def test_get_field_mappings_contains_descriptions(self):
        """Field mappings contain human-readable descriptions"""
        response = self.session.get(f"{BASE_URL}/api/export/field-mappings")
        data = response.json()
        
        assert "description" in data
        assert "jira" in data["description"]
        assert "azure_devops" in data["description"]
    
    # ============================================
    # Export Preview Tests
    # ============================================
    
    def test_export_preview_returns_200(self):
        """GET /api/export/preview/{epic_id} returns 200"""
        response = self.session.get(f"{BASE_URL}/api/export/preview/{self.epic_id}")
        assert response.status_code == 200
    
    def test_export_preview_contains_epic_title(self):
        """Export preview contains epic title"""
        response = self.session.get(f"{BASE_URL}/api/export/preview/{self.epic_id}")
        data = response.json()
        
        assert "epic_title" in data
        assert data["epic_title"] == "TEST_Export_Epic"
    
    def test_export_preview_contains_counts(self):
        """Export preview contains feature, story, and bug counts"""
        response = self.session.get(f"{BASE_URL}/api/export/preview/{self.epic_id}")
        data = response.json()
        
        assert "feature_count" in data
        assert "story_count" in data
        assert "bug_count" in data
        assert isinstance(data["feature_count"], int)
        assert isinstance(data["story_count"], int)
        assert isinstance(data["bug_count"], int)
    
    def test_export_preview_contains_items_list(self):
        """Export preview contains items list"""
        response = self.session.get(f"{BASE_URL}/api/export/preview/{self.epic_id}")
        data = response.json()
        
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) >= 1  # At least the epic
        assert data["items"][0]["type"] == "Epic"
    
    def test_export_preview_nonexistent_epic_returns_404(self):
        """Export preview for nonexistent epic returns 404"""
        response = self.session.get(f"{BASE_URL}/api/export/preview/nonexistent_epic_id")
        assert response.status_code == 404
    
    # ============================================
    # File Export Tests - Jira CSV
    # ============================================
    
    def test_export_jira_csv_returns_200(self):
        """POST /api/export/file with jira_csv format returns 200"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "jira_csv",
                "include_bugs": True
            }
        )
        assert response.status_code == 200
    
    def test_export_jira_csv_returns_csv_content(self):
        """Jira CSV export returns valid CSV content"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "jira_csv",
                "include_bugs": True
            }
        )
        
        content = response.text
        assert "Issue Type" in content
        assert "Summary" in content
        assert "Epic" in content
        assert "TEST_Export_Epic" in content
    
    def test_export_jira_csv_has_correct_content_type(self):
        """Jira CSV export has text/csv content type"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "jira_csv",
                "include_bugs": True
            }
        )
        
        assert "text/csv" in response.headers.get("Content-Type", "")
    
    # ============================================
    # File Export Tests - Azure DevOps CSV
    # ============================================
    
    def test_export_azure_csv_returns_200(self):
        """POST /api/export/file with azure_devops_csv format returns 200"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "azure_devops_csv",
                "include_bugs": True
            }
        )
        assert response.status_code == 200
    
    def test_export_azure_csv_returns_csv_content(self):
        """Azure DevOps CSV export returns valid CSV content"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "azure_devops_csv",
                "include_bugs": True
            }
        )
        
        content = response.text
        assert "Work Item Type" in content
        assert "Title" in content
        assert "Epic" in content
        assert "TEST_Export_Epic" in content
    
    # ============================================
    # File Export Tests - JSON
    # ============================================
    
    def test_export_json_returns_200(self):
        """POST /api/export/file with json format returns 200"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "json",
                "include_bugs": True
            }
        )
        assert response.status_code == 200
    
    def test_export_json_returns_valid_json(self):
        """JSON export returns valid JSON structure"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "json",
                "include_bugs": True
            }
        )
        
        data = response.json()
        assert "exported_at" in data
        assert "source" in data
        assert data["source"] == "JarlPM"
        assert "epic" in data
        assert "bugs" in data
        assert "field_mappings" in data
    
    def test_export_json_contains_epic_data(self):
        """JSON export contains epic data"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "json",
                "include_bugs": True
            }
        )
        
        data = response.json()
        assert data["epic"]["title"] == "TEST_Export_Epic"
        assert data["epic"]["epic_id"] == self.epic_id
    
    # ============================================
    # File Export Tests - Markdown
    # ============================================
    
    def test_export_markdown_returns_200(self):
        """POST /api/export/file with markdown format returns 200"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "markdown",
                "include_bugs": True
            }
        )
        assert response.status_code == 200
    
    def test_export_markdown_returns_markdown_content(self):
        """Markdown export returns valid markdown content"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "markdown",
                "include_bugs": True
            }
        )
        
        content = response.text
        assert "# TEST_Export_Epic" in content
        assert "**Stage:**" in content
    
    # ============================================
    # Error Handling Tests
    # ============================================
    
    def test_export_file_nonexistent_epic_returns_404(self):
        """File export for nonexistent epic returns 404"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": "nonexistent_epic_id",
                "format": "json",
                "include_bugs": True
            }
        )
        assert response.status_code == 404
    
    def test_export_file_invalid_format_returns_422(self):
        """File export with invalid format returns 422"""
        response = self.session.post(
            f"{BASE_URL}/api/export/file",
            json={
                "epic_id": self.epic_id,
                "format": "invalid_format",
                "include_bugs": True
            }
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
