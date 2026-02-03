"""
Test Bug Linking APIs for JarlPM
Tests contextual bug linking to Epics, Features, and User Stories
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBugLinkingAPIs:
    """Test bug linking functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        # Login to get session
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200, f"Test login failed: {response.text}"
        self.user_data = response.json()
        print(f"Logged in as: {self.user_data.get('email')}")
        yield
        # Cleanup - delete test bugs
        self._cleanup_test_data()
    
    def _cleanup_test_data(self):
        """Clean up test data"""
        try:
            # Get all bugs and delete TEST_ prefixed ones
            response = self.session.get(f"{BASE_URL}/api/bugs")
            if response.status_code == 200:
                bugs = response.json()
                for bug in bugs:
                    if bug.get('title', '').startswith('TEST_'):
                        self.session.delete(f"{BASE_URL}/api/bugs/{bug['bug_id']}")
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    # ============================================
    # GET /api/bugs/by-entity/{entity_type}/{entity_id}
    # ============================================
    
    def test_get_bugs_for_entity_empty(self):
        """Test getting bugs for entity with no linked bugs"""
        response = self.session.get(f"{BASE_URL}/api/bugs/by-entity/epic/nonexistent-epic-id")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
        print("✓ GET /api/bugs/by-entity returns empty list for non-existent entity")
    
    def test_get_bugs_for_entity_invalid_type(self):
        """Test getting bugs with invalid entity type"""
        response = self.session.get(f"{BASE_URL}/api/bugs/by-entity/invalid_type/some-id")
        assert response.status_code == 400
        data = response.json()
        assert "Invalid entity type" in data.get('detail', '')
        print("✓ GET /api/bugs/by-entity returns 400 for invalid entity type")
    
    def test_get_bugs_for_entity_valid_types(self):
        """Test that all valid entity types are accepted"""
        for entity_type in ['epic', 'feature', 'story']:
            response = self.session.get(f"{BASE_URL}/api/bugs/by-entity/{entity_type}/test-id")
            assert response.status_code == 200, f"Failed for entity type: {entity_type}"
            print(f"✓ GET /api/bugs/by-entity/{entity_type} returns 200")
    
    # ============================================
    # POST /api/bugs - Create bug with links
    # ============================================
    
    def test_create_bug_with_link(self):
        """Test creating a bug with a link to an entity"""
        bug_data = {
            "title": "TEST_Bug_With_Link",
            "description": "Test bug created with link to epic",
            "severity": "medium",
            "links": [
                {"entity_type": "epic", "entity_id": "test-epic-123"}
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert response.status_code == 200, f"Create bug failed: {response.text}"
        
        data = response.json()
        assert data['title'] == bug_data['title']
        assert data['description'] == bug_data['description']
        assert data['severity'] == bug_data['severity']
        assert 'bug_id' in data
        assert 'links' in data
        assert len(data['links']) == 1
        assert data['links'][0]['entity_type'] == 'epic'
        assert data['links'][0]['entity_id'] == 'test-epic-123'
        assert data['link_count'] == 1
        
        print(f"✓ POST /api/bugs creates bug with link - bug_id: {data['bug_id']}")
        return data['bug_id']
    
    def test_create_bug_with_multiple_links(self):
        """Test creating a bug with multiple links"""
        bug_data = {
            "title": "TEST_Bug_Multiple_Links",
            "description": "Test bug with multiple entity links",
            "severity": "high",
            "links": [
                {"entity_type": "epic", "entity_id": "test-epic-456"},
                {"entity_type": "feature", "entity_id": "test-feature-789"},
                {"entity_type": "story", "entity_id": "test-story-012"}
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert response.status_code == 200, f"Create bug failed: {response.text}"
        
        data = response.json()
        assert len(data['links']) == 3
        assert data['link_count'] == 3
        
        # Verify all entity types are present
        entity_types = [link['entity_type'] for link in data['links']]
        assert 'epic' in entity_types
        assert 'feature' in entity_types
        assert 'story' in entity_types
        
        print(f"✓ POST /api/bugs creates bug with 3 links - bug_id: {data['bug_id']}")
        return data['bug_id']
    
    def test_create_bug_without_links(self):
        """Test creating a bug without any links"""
        bug_data = {
            "title": "TEST_Bug_No_Links",
            "description": "Test bug without any links",
            "severity": "low"
        }
        
        response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert response.status_code == 200, f"Create bug failed: {response.text}"
        
        data = response.json()
        assert data['links'] == []
        assert data['link_count'] == 0
        
        print(f"✓ POST /api/bugs creates bug without links - bug_id: {data['bug_id']}")
        return data['bug_id']
    
    def test_create_bug_with_invalid_link_type(self):
        """Test creating a bug with invalid link entity type"""
        bug_data = {
            "title": "TEST_Bug_Invalid_Link",
            "description": "Test bug with invalid link type",
            "severity": "medium",
            "links": [
                {"entity_type": "invalid_type", "entity_id": "test-id"}
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert response.status_code == 400
        data = response.json()
        assert "Invalid entity type" in data.get('detail', '')
        print("✓ POST /api/bugs returns 400 for invalid link entity type")
    
    # ============================================
    # POST /api/bugs/{bug_id}/links - Add links to existing bug
    # ============================================
    
    def test_add_links_to_existing_bug(self):
        """Test adding links to an existing bug"""
        # First create a bug without links
        bug_data = {
            "title": "TEST_Bug_Add_Links",
            "description": "Test bug for adding links",
            "severity": "medium"
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert create_response.status_code == 200
        bug_id = create_response.json()['bug_id']
        
        # Add links
        links_data = {
            "links": [
                {"entity_type": "epic", "entity_id": "added-epic-123"},
                {"entity_type": "feature", "entity_id": "added-feature-456"}
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/bugs/{bug_id}/links", json=links_data)
        assert response.status_code == 200, f"Add links failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        
        # Verify links were added
        get_response = self.session.get(f"{BASE_URL}/api/bugs/{bug_id}")
        assert get_response.status_code == 200
        bug = get_response.json()
        assert bug['link_count'] == 2
        
        print(f"✓ POST /api/bugs/{bug_id}/links adds links successfully")
        return bug_id
    
    def test_add_links_to_nonexistent_bug(self):
        """Test adding links to a non-existent bug"""
        links_data = {
            "links": [
                {"entity_type": "epic", "entity_id": "test-epic"}
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/bugs/nonexistent-bug-id/links", json=links_data)
        assert response.status_code == 404
        print("✓ POST /api/bugs/{bug_id}/links returns 404 for non-existent bug")
    
    # ============================================
    # DELETE /api/bugs/{bug_id}/links/{link_id} - Remove link
    # ============================================
    
    def test_remove_link_from_bug(self):
        """Test removing a link from a bug"""
        # Create bug with link
        bug_data = {
            "title": "TEST_Bug_Remove_Link",
            "description": "Test bug for removing link",
            "severity": "medium",
            "links": [
                {"entity_type": "epic", "entity_id": "remove-epic-123"}
            ]
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert create_response.status_code == 200
        bug = create_response.json()
        bug_id = bug['bug_id']
        link_id = bug['links'][0]['link_id']
        
        # Remove the link
        response = self.session.delete(f"{BASE_URL}/api/bugs/{bug_id}/links/{link_id}")
        assert response.status_code == 200, f"Remove link failed: {response.text}"
        
        # Verify link was removed
        get_response = self.session.get(f"{BASE_URL}/api/bugs/{bug_id}")
        assert get_response.status_code == 200
        updated_bug = get_response.json()
        assert updated_bug['link_count'] == 0
        assert len(updated_bug['links']) == 0
        
        print(f"✓ DELETE /api/bugs/{bug_id}/links/{link_id} removes link successfully")
    
    def test_remove_nonexistent_link(self):
        """Test removing a non-existent link"""
        # Create bug without links
        bug_data = {
            "title": "TEST_Bug_Remove_Nonexistent",
            "description": "Test bug for removing non-existent link",
            "severity": "low"
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert create_response.status_code == 200
        bug_id = create_response.json()['bug_id']
        
        # Try to remove non-existent link
        response = self.session.delete(f"{BASE_URL}/api/bugs/{bug_id}/links/nonexistent-link-id")
        assert response.status_code == 404
        print("✓ DELETE /api/bugs/{bug_id}/links/{link_id} returns 404 for non-existent link")
    
    # ============================================
    # Integration: Verify bugs appear in by-entity query
    # ============================================
    
    def test_bug_appears_in_entity_query(self):
        """Test that created bug appears in by-entity query"""
        entity_id = f"integration-test-epic-{int(time.time())}"
        
        # Create bug linked to entity
        bug_data = {
            "title": "TEST_Bug_Integration",
            "description": "Test bug for integration test",
            "severity": "critical",
            "links": [
                {"entity_type": "epic", "entity_id": entity_id}
            ]
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert create_response.status_code == 200
        bug_id = create_response.json()['bug_id']
        
        # Query bugs for entity
        response = self.session.get(f"{BASE_URL}/api/bugs/by-entity/epic/{entity_id}")
        assert response.status_code == 200
        
        bugs = response.json()
        assert len(bugs) >= 1
        
        # Find our bug
        found_bug = next((b for b in bugs if b['bug_id'] == bug_id), None)
        assert found_bug is not None, "Created bug not found in entity query"
        assert found_bug['title'] == bug_data['title']
        assert found_bug['severity'] == bug_data['severity']
        
        print(f"✓ Bug {bug_id} appears in /api/bugs/by-entity/epic/{entity_id}")
    
    def test_bug_response_structure(self):
        """Test that bug response has correct structure with severity and status badges"""
        bug_data = {
            "title": "TEST_Bug_Structure",
            "description": "Test bug for response structure",
            "severity": "high",
            "steps_to_reproduce": "1. Do this\n2. Do that",
            "expected_behavior": "Should work",
            "actual_behavior": "Does not work"
        }
        
        response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all required fields for UI display
        assert 'bug_id' in data
        assert 'title' in data
        assert 'description' in data
        assert 'severity' in data
        assert 'status' in data
        assert 'links' in data
        assert 'link_count' in data
        assert 'created_at' in data
        assert 'updated_at' in data
        assert 'allowed_transitions' in data
        
        # Verify severity is valid
        assert data['severity'] in ['critical', 'high', 'medium', 'low']
        
        # Verify status is valid
        assert data['status'] in ['draft', 'confirmed', 'in_progress', 'resolved', 'closed']
        
        print(f"✓ Bug response has correct structure with severity={data['severity']}, status={data['status']}")


class TestBugSeverityAndStatus:
    """Test bug severity and status badges"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200
        yield
        self._cleanup_test_data()
    
    def _cleanup_test_data(self):
        try:
            response = self.session.get(f"{BASE_URL}/api/bugs")
            if response.status_code == 200:
                bugs = response.json()
                for bug in bugs:
                    if bug.get('title', '').startswith('TEST_'):
                        self.session.delete(f"{BASE_URL}/api/bugs/{bug['bug_id']}")
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def test_all_severity_levels(self):
        """Test creating bugs with all severity levels"""
        severities = ['critical', 'high', 'medium', 'low']
        
        for severity in severities:
            bug_data = {
                "title": f"TEST_Bug_Severity_{severity}",
                "description": f"Test bug with {severity} severity",
                "severity": severity
            }
            
            response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
            assert response.status_code == 200, f"Failed for severity: {severity}"
            data = response.json()
            assert data['severity'] == severity
            print(f"✓ Created bug with severity: {severity}")
    
    def test_invalid_severity(self):
        """Test creating bug with invalid severity"""
        bug_data = {
            "title": "TEST_Bug_Invalid_Severity",
            "description": "Test bug with invalid severity",
            "severity": "invalid_severity"
        }
        
        response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert response.status_code == 400
        print("✓ Invalid severity returns 400")
    
    def test_default_status_is_draft(self):
        """Test that new bugs have draft status"""
        bug_data = {
            "title": "TEST_Bug_Default_Status",
            "description": "Test bug for default status",
            "severity": "medium"
        }
        
        response = self.session.post(f"{BASE_URL}/api/bugs", json=bug_data)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'draft'
        print("✓ New bug has default status: draft")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
