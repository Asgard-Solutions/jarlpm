"""
Initiative Library API Tests for JarlPM
Tests: List, Get, Duplicate, Archive, Unarchive, Delete, Summary, Search, Filter
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('VITE_BACKEND_URL', 'https://pmcanvas.preview.emergentagent.com')


class TestInitiativeAPI:
    """Initiative Library API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get session cookie
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "test@jarlpm.com", "password": "Test123!"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        # Store user_id for verification
        self.user_id = login_response.json().get("user_id")
        
        yield
        
        # Cleanup: Delete any test epics created during tests
        try:
            response = self.session.get(f"{BASE_URL}/api/initiatives")
            if response.status_code == 200:
                initiatives = response.json().get("initiatives", [])
                for init in initiatives:
                    if init["title"].startswith("TEST_"):
                        self.session.delete(f"{BASE_URL}/api/initiatives/{init['epic_id']}")
        except Exception:
            pass
    
    # ==================== List Initiatives ====================
    
    def test_list_initiatives_requires_auth(self):
        """GET /api/initiatives requires authentication"""
        response = requests.get(f"{BASE_URL}/api/initiatives")
        assert response.status_code == 401
        assert "Not authenticated" in response.json().get("detail", "")
    
    def test_list_initiatives_success(self):
        """GET /api/initiatives returns paginated list"""
        response = self.session.get(f"{BASE_URL}/api/initiatives")
        assert response.status_code == 200
        
        data = response.json()
        assert "initiatives" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_more" in data
        assert isinstance(data["initiatives"], list)
    
    def test_list_initiatives_pagination(self):
        """GET /api/initiatives supports pagination params"""
        response = self.session.get(f"{BASE_URL}/api/initiatives?page=1&page_size=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
    
    # ==================== Summary Stats ====================
    
    def test_summary_requires_auth(self):
        """GET /api/initiatives/stats/summary requires authentication"""
        response = requests.get(f"{BASE_URL}/api/initiatives/stats/summary")
        assert response.status_code == 401
    
    def test_summary_returns_counts(self):
        """GET /api/initiatives/stats/summary returns status counts"""
        response = self.session.get(f"{BASE_URL}/api/initiatives/stats/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "draft" in data
        assert "active" in data
        assert "completed" in data
        assert isinstance(data["total"], int)
        assert isinstance(data["draft"], int)
    
    # ==================== Get Initiative Details ====================
    
    def test_get_initiative_not_found(self):
        """GET /api/initiatives/{epic_id} returns 404 for non-existent"""
        response = self.session.get(f"{BASE_URL}/api/initiatives/epic_nonexistent123")
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
    
    def test_get_initiative_success(self):
        """GET /api/initiatives/{epic_id} returns initiative details"""
        # First create an epic
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_GetDetail_{uuid.uuid4().hex[:8]}"}
        )
        assert create_response.status_code in [200, 201]
        epic_id = create_response.json()["epic_id"]
        
        # Get initiative details
        response = self.session.get(f"{BASE_URL}/api/initiatives/{epic_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["epic_id"] == epic_id
        assert "title" in data
        assert "status" in data
        assert "features_count" in data
        assert "stories_count" in data
        assert "total_points" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    # ==================== Duplicate Initiative ====================
    
    def test_duplicate_initiative_not_found(self):
        """POST /api/initiatives/{epic_id}/duplicate returns 404 for non-existent"""
        response = self.session.post(
            f"{BASE_URL}/api/initiatives/epic_nonexistent123/duplicate",
            json={}
        )
        assert response.status_code == 404
    
    def test_duplicate_initiative_success(self):
        """POST /api/initiatives/{epic_id}/duplicate creates a copy"""
        # First create an epic
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_Duplicate_{uuid.uuid4().hex[:8]}"}
        )
        assert create_response.status_code in [200, 201]
        epic_id = create_response.json()["epic_id"]
        
        # Duplicate it
        response = self.session.post(
            f"{BASE_URL}/api/initiatives/{epic_id}/duplicate",
            json={"new_title": "TEST_Duplicated_Copy"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "new_epic_id" in data
        assert data["new_epic_id"] != epic_id
        assert data["title"] == "TEST_Duplicated_Copy"
        assert "message" in data
        
        # Verify the duplicate exists
        verify_response = self.session.get(f"{BASE_URL}/api/initiatives/{data['new_epic_id']}")
        assert verify_response.status_code == 200
        assert verify_response.json()["title"] == "TEST_Duplicated_Copy"
    
    def test_duplicate_initiative_default_title(self):
        """POST /api/initiatives/{epic_id}/duplicate uses default title if not provided"""
        # First create an epic
        original_title = f"TEST_DupDefault_{uuid.uuid4().hex[:8]}"
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": original_title}
        )
        assert create_response.status_code in [200, 201]
        epic_id = create_response.json()["epic_id"]
        
        # Duplicate without new_title
        response = self.session.post(
            f"{BASE_URL}/api/initiatives/{epic_id}/duplicate",
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "(Copy)" in data["title"]
    
    # ==================== Archive Initiative ====================
    
    def test_archive_initiative_not_found(self):
        """PATCH /api/initiatives/{epic_id}/archive returns 404 for non-existent"""
        response = self.session.patch(f"{BASE_URL}/api/initiatives/epic_nonexistent123/archive")
        assert response.status_code == 404
    
    def test_archive_initiative_success(self):
        """PATCH /api/initiatives/{epic_id}/archive archives the initiative"""
        # First create an epic
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_Archive_{uuid.uuid4().hex[:8]}"}
        )
        assert create_response.status_code in [200, 201]
        epic_id = create_response.json()["epic_id"]
        
        # Archive it
        response = self.session.patch(f"{BASE_URL}/api/initiatives/{epic_id}/archive")
        assert response.status_code == 200
        
        data = response.json()
        assert data["epic_id"] == epic_id
        assert "archived" in data["message"].lower()
    
    # ==================== Unarchive Initiative ====================
    
    def test_unarchive_initiative_not_found(self):
        """PATCH /api/initiatives/{epic_id}/unarchive returns 404 for non-existent"""
        response = self.session.patch(f"{BASE_URL}/api/initiatives/epic_nonexistent123/unarchive")
        assert response.status_code == 404
    
    def test_unarchive_initiative_success(self):
        """PATCH /api/initiatives/{epic_id}/unarchive restores the initiative"""
        # First create and archive an epic
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_Unarchive_{uuid.uuid4().hex[:8]}"}
        )
        assert create_response.status_code in [200, 201]
        epic_id = create_response.json()["epic_id"]
        
        # Archive it
        self.session.patch(f"{BASE_URL}/api/initiatives/{epic_id}/archive")
        
        # Unarchive it
        response = self.session.patch(f"{BASE_URL}/api/initiatives/{epic_id}/unarchive")
        assert response.status_code == 200
        
        data = response.json()
        assert data["epic_id"] == epic_id
        assert "unarchived" in data["message"].lower()
    
    # ==================== Delete Initiative ====================
    
    def test_delete_initiative_not_found(self):
        """DELETE /api/initiatives/{epic_id} returns 404 for non-existent"""
        response = self.session.delete(f"{BASE_URL}/api/initiatives/epic_nonexistent123")
        assert response.status_code == 404
    
    def test_delete_initiative_success(self):
        """DELETE /api/initiatives/{epic_id} permanently deletes the initiative"""
        # First create an epic
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_Delete_{uuid.uuid4().hex[:8]}"}
        )
        assert create_response.status_code in [200, 201]
        epic_id = create_response.json()["epic_id"]
        
        # Delete it
        response = self.session.delete(f"{BASE_URL}/api/initiatives/{epic_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["epic_id"] == epic_id
        assert "deleted" in data["message"].lower()
        
        # Verify it's gone
        verify_response = self.session.get(f"{BASE_URL}/api/initiatives/{epic_id}")
        assert verify_response.status_code == 404
    
    # ==================== Search & Filter ====================
    
    def test_filter_by_status(self):
        """GET /api/initiatives?status=draft filters by status"""
        response = self.session.get(f"{BASE_URL}/api/initiatives?status=draft")
        assert response.status_code == 200
        
        data = response.json()
        # All returned initiatives should be draft
        for init in data["initiatives"]:
            assert init["status"] == "draft"
    
    def test_search_by_title(self):
        """GET /api/initiatives?search=term searches in title"""
        # Create an epic with unique title
        unique_term = f"SEARCHTEST_{uuid.uuid4().hex[:8]}"
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_{unique_term}"}
        )
        assert create_response.status_code in [200, 201]
        
        # Search for it
        response = self.session.get(f"{BASE_URL}/api/initiatives?search={unique_term}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] >= 1
        assert any(unique_term in init["title"] for init in data["initiatives"])
    
    def test_search_no_results(self):
        """GET /api/initiatives?search=nonexistent returns empty list"""
        response = self.session.get(f"{BASE_URL}/api/initiatives?search=NONEXISTENT_TERM_12345")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 0
        assert len(data["initiatives"]) == 0
    
    def test_sort_by_updated_at(self):
        """GET /api/initiatives?sort_by=updated_at&sort_order=desc sorts correctly"""
        response = self.session.get(f"{BASE_URL}/api/initiatives?sort_by=updated_at&sort_order=desc")
        assert response.status_code == 200
        
        data = response.json()
        # Verify descending order
        if len(data["initiatives"]) > 1:
            dates = [init["updated_at"] for init in data["initiatives"]]
            assert dates == sorted(dates, reverse=True)
    
    # ==================== Initiative Data Structure ====================
    
    def test_initiative_summary_structure(self):
        """Initiative summary has all required fields"""
        # Create an epic
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_Structure_{uuid.uuid4().hex[:8]}"}
        )
        assert create_response.status_code in [200, 201]
        
        # Get list
        response = self.session.get(f"{BASE_URL}/api/initiatives")
        assert response.status_code == 200
        
        data = response.json()
        if data["initiatives"]:
            init = data["initiatives"][0]
            # Required fields per spec
            assert "epic_id" in init
            assert "title" in init
            assert "status" in init
            assert "created_at" in init
            assert "updated_at" in init
            # Optional but expected
            assert "features_count" in init
            assert "stories_count" in init
            assert "total_points" in init
    
    def test_initiative_detail_structure(self):
        """Initiative detail has all required fields"""
        # Create an epic
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_DetailStruct_{uuid.uuid4().hex[:8]}"}
        )
        assert create_response.status_code in [200, 201]
        epic_id = create_response.json()["epic_id"]
        
        # Get detail
        response = self.session.get(f"{BASE_URL}/api/initiatives/{epic_id}")
        assert response.status_code == 200
        
        data = response.json()
        # Required fields
        assert "epic_id" in data
        assert "title" in data
        assert "status" in data
        assert "features_count" in data
        assert "stories_count" in data
        assert "total_points" in data
        assert "features" in data
        assert "created_at" in data
        assert "updated_at" in data
        # Optional PRD fields
        assert "problem_statement" in data
        assert "desired_outcome" in data
        assert "epic_summary" in data
        assert "acceptance_criteria" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
