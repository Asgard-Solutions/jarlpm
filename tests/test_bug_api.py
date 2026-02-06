"""
Bug API Tests for JarlPM
Tests CRUD operations, status transitions, and linking for bugs
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://product-ai-4.preview.emergentagent.com')
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"


@pytest.fixture(scope="module")
def api_client():
    """Create authenticated session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_SESSION_TOKEN}"
    })
    return session


@pytest.fixture(scope="module")
def setup_test_user(api_client):
    """Ensure test user exists via test-login"""
    response = api_client.post(f"{BASE_URL}/api/auth/test-login")
    assert response.status_code == 200, f"Test login failed: {response.text}"
    return response.json()


class TestBugCRUD:
    """Bug CRUD operation tests"""
    
    def test_create_standalone_bug(self, api_client, setup_test_user):
        """Test creating a standalone bug (no links)"""
        payload = {
            "title": "TEST_Standalone Bug - Login button not working",
            "description": "The login button on the homepage does not respond to clicks",
            "severity": "high",
            "steps_to_reproduce": "1. Go to homepage\n2. Click login button\n3. Nothing happens",
            "expected_behavior": "Login modal should appear",
            "actual_behavior": "No response to click",
            "environment": "Chrome 120, macOS 14"
        }
        
        response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert response.status_code == 200, f"Create bug failed: {response.text}"
        
        data = response.json()
        assert "bug_id" in data
        assert data["title"] == payload["title"]
        assert data["description"] == payload["description"]
        assert data["severity"] == "high"
        assert data["status"] == "draft"  # Initial status should be draft
        assert data["link_count"] == 0  # Standalone bug
        assert "allowed_transitions" in data
        assert "confirmed" in data["allowed_transitions"]  # Draft can transition to confirmed
        
        # Store bug_id for cleanup
        TestBugCRUD.standalone_bug_id = data["bug_id"]
        print(f"Created standalone bug: {data['bug_id']}")
    
    def test_create_bug_with_priority(self, api_client, setup_test_user):
        """Test creating a bug with priority"""
        payload = {
            "title": "TEST_Bug with Priority - Critical crash",
            "description": "Application crashes on startup",
            "severity": "critical",
            "priority": "p0"
        }
        
        response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert response.status_code == 200, f"Create bug failed: {response.text}"
        
        data = response.json()
        assert data["severity"] == "critical"
        assert data["priority"] == "p0"
        
        TestBugCRUD.priority_bug_id = data["bug_id"]
        print(f"Created bug with priority: {data['bug_id']}")
    
    def test_get_bug(self, api_client, setup_test_user):
        """Test getting a single bug"""
        bug_id = TestBugCRUD.standalone_bug_id
        
        response = api_client.get(f"{BASE_URL}/api/bugs/{bug_id}")
        assert response.status_code == 200, f"Get bug failed: {response.text}"
        
        data = response.json()
        assert data["bug_id"] == bug_id
        assert data["title"] == "TEST_Standalone Bug - Login button not working"
        assert data["status"] == "draft"
        print(f"Retrieved bug: {data['bug_id']}")
    
    def test_list_bugs(self, api_client, setup_test_user):
        """Test listing bugs"""
        response = api_client.get(f"{BASE_URL}/api/bugs")
        assert response.status_code == 200, f"List bugs failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # At least our 2 test bugs
        
        # Verify our test bugs are in the list
        bug_ids = [bug["bug_id"] for bug in data]
        assert TestBugCRUD.standalone_bug_id in bug_ids
        assert TestBugCRUD.priority_bug_id in bug_ids
        print(f"Listed {len(data)} bugs")
    
    def test_list_bugs_filter_by_status(self, api_client, setup_test_user):
        """Test filtering bugs by status"""
        response = api_client.get(f"{BASE_URL}/api/bugs?status=draft")
        assert response.status_code == 200, f"Filter by status failed: {response.text}"
        
        data = response.json()
        for bug in data:
            assert bug["status"] == "draft"
        print(f"Filtered by status=draft: {len(data)} bugs")
    
    def test_list_bugs_filter_by_severity(self, api_client, setup_test_user):
        """Test filtering bugs by severity"""
        response = api_client.get(f"{BASE_URL}/api/bugs?severity=critical")
        assert response.status_code == 200, f"Filter by severity failed: {response.text}"
        
        data = response.json()
        for bug in data:
            assert bug["severity"] == "critical"
        print(f"Filtered by severity=critical: {len(data)} bugs")
    
    def test_list_bugs_filter_standalone(self, api_client, setup_test_user):
        """Test filtering standalone bugs (no links)"""
        response = api_client.get(f"{BASE_URL}/api/bugs?linked=false")
        assert response.status_code == 200, f"Filter standalone failed: {response.text}"
        
        data = response.json()
        for bug in data:
            assert bug["link_count"] == 0
        print(f"Filtered standalone bugs: {len(data)} bugs")
    
    def test_update_bug_in_draft(self, api_client, setup_test_user):
        """Test updating a bug in Draft status"""
        bug_id = TestBugCRUD.standalone_bug_id
        
        update_payload = {
            "title": "TEST_Updated Bug Title",
            "severity": "medium"
        }
        
        response = api_client.patch(f"{BASE_URL}/api/bugs/{bug_id}", json=update_payload)
        assert response.status_code == 200, f"Update bug failed: {response.text}"
        
        data = response.json()
        assert data["title"] == "TEST_Updated Bug Title"
        assert data["severity"] == "medium"
        print(f"Updated bug: {data['bug_id']}")
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/bugs/{bug_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["title"] == "TEST_Updated Bug Title"
        assert get_data["severity"] == "medium"


class TestBugStatusTransitions:
    """Bug status transition tests"""
    
    def test_transition_draft_to_confirmed(self, api_client, setup_test_user):
        """Test transitioning from Draft to Confirmed"""
        # Create a fresh bug for transition testing
        payload = {
            "title": "TEST_Transition Bug",
            "description": "Bug for testing status transitions",
            "severity": "medium"
        }
        create_response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert create_response.status_code == 200
        bug_id = create_response.json()["bug_id"]
        TestBugStatusTransitions.transition_bug_id = bug_id
        
        # Transition to confirmed
        transition_payload = {
            "new_status": "confirmed",
            "notes": "Bug confirmed by QA team"
        }
        response = api_client.post(f"{BASE_URL}/api/bugs/{bug_id}/transition", json=transition_payload)
        assert response.status_code == 200, f"Transition failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "confirmed"
        assert "in_progress" in data["allowed_transitions"]  # Next valid transition
        print(f"Transitioned bug {bug_id} to confirmed")
    
    def test_transition_confirmed_to_in_progress(self, api_client, setup_test_user):
        """Test transitioning from Confirmed to In Progress"""
        bug_id = TestBugStatusTransitions.transition_bug_id
        
        transition_payload = {
            "new_status": "in_progress",
            "notes": "Developer started working on fix"
        }
        response = api_client.post(f"{BASE_URL}/api/bugs/{bug_id}/transition", json=transition_payload)
        assert response.status_code == 200, f"Transition failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "in_progress"
        assert "resolved" in data["allowed_transitions"]
        print(f"Transitioned bug {bug_id} to in_progress")
    
    def test_transition_in_progress_to_resolved(self, api_client, setup_test_user):
        """Test transitioning from In Progress to Resolved"""
        bug_id = TestBugStatusTransitions.transition_bug_id
        
        transition_payload = {
            "new_status": "resolved",
            "notes": "Fix deployed to staging"
        }
        response = api_client.post(f"{BASE_URL}/api/bugs/{bug_id}/transition", json=transition_payload)
        assert response.status_code == 200, f"Transition failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "resolved"
        assert "closed" in data["allowed_transitions"]
        print(f"Transitioned bug {bug_id} to resolved")
    
    def test_transition_resolved_to_closed(self, api_client, setup_test_user):
        """Test transitioning from Resolved to Closed"""
        bug_id = TestBugStatusTransitions.transition_bug_id
        
        transition_payload = {
            "new_status": "closed",
            "notes": "Verified in production"
        }
        response = api_client.post(f"{BASE_URL}/api/bugs/{bug_id}/transition", json=transition_payload)
        assert response.status_code == 200, f"Transition failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "closed"
        assert data["allowed_transitions"] == []  # Terminal state
        print(f"Transitioned bug {bug_id} to closed (terminal)")
    
    def test_invalid_transition_rejected(self, api_client, setup_test_user):
        """Test that invalid transitions are rejected with 400"""
        # Create a new bug in draft status
        payload = {
            "title": "TEST_Invalid Transition Bug",
            "description": "Bug for testing invalid transitions",
            "severity": "low"
        }
        create_response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert create_response.status_code == 200
        bug_id = create_response.json()["bug_id"]
        TestBugStatusTransitions.invalid_transition_bug_id = bug_id
        
        # Try to skip directly to in_progress (invalid: draft -> in_progress)
        transition_payload = {
            "new_status": "in_progress",
            "notes": "Trying to skip confirmed"
        }
        response = api_client.post(f"{BASE_URL}/api/bugs/{bug_id}/transition", json=transition_payload)
        assert response.status_code == 400, f"Expected 400 for invalid transition, got {response.status_code}"
        
        error_data = response.json()
        assert "detail" in error_data
        assert "Invalid transition" in error_data["detail"]
        print(f"Invalid transition correctly rejected: {error_data['detail']}")
    
    def test_update_non_draft_bug_rejected(self, api_client, setup_test_user):
        """Test that updating a non-draft bug is rejected"""
        # First transition the invalid_transition_bug to confirmed
        bug_id = TestBugStatusTransitions.invalid_transition_bug_id
        
        transition_payload = {"new_status": "confirmed"}
        api_client.post(f"{BASE_URL}/api/bugs/{bug_id}/transition", json=transition_payload)
        
        # Now try to update it
        update_payload = {"title": "TEST_Trying to update confirmed bug"}
        response = api_client.patch(f"{BASE_URL}/api/bugs/{bug_id}", json=update_payload)
        assert response.status_code == 400, f"Expected 400 for update on non-draft, got {response.status_code}"
        
        error_data = response.json()
        assert "detail" in error_data
        assert "Draft" in error_data["detail"]
        print(f"Update on non-draft correctly rejected: {error_data['detail']}")


class TestBugStatusHistory:
    """Bug status history tests"""
    
    def test_get_status_history(self, api_client, setup_test_user):
        """Test getting status history for a bug"""
        bug_id = TestBugStatusTransitions.transition_bug_id
        
        response = api_client.get(f"{BASE_URL}/api/bugs/{bug_id}/history")
        assert response.status_code == 200, f"Get history failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 5  # Initial creation + 4 transitions
        
        # Verify history order and content
        # First entry should be creation (from_status is null)
        assert data[0]["from_status"] is None
        assert data[0]["to_status"] == "draft"
        
        # Verify full lifecycle is recorded
        statuses = [(h["from_status"], h["to_status"]) for h in data]
        assert (None, "draft") in statuses
        assert ("draft", "confirmed") in statuses
        assert ("confirmed", "in_progress") in statuses
        assert ("in_progress", "resolved") in statuses
        assert ("resolved", "closed") in statuses
        
        print(f"Status history has {len(data)} entries")


class TestBugLinks:
    """Bug linking tests"""
    
    def test_add_link_to_bug(self, api_client, setup_test_user):
        """Test adding a link to a bug"""
        # Create a bug for linking tests
        payload = {
            "title": "TEST_Bug for Linking",
            "description": "Bug to test linking functionality",
            "severity": "medium"
        }
        create_response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert create_response.status_code == 200
        bug_id = create_response.json()["bug_id"]
        TestBugLinks.link_bug_id = bug_id
        
        # Add a link to an epic
        link_payload = {
            "links": [
                {"entity_type": "epic", "entity_id": "epic_test_123"}
            ]
        }
        response = api_client.post(f"{BASE_URL}/api/bugs/{bug_id}/links", json=link_payload)
        assert response.status_code == 200, f"Add link failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["entity_type"] == "epic"
        assert data[0]["entity_id"] == "epic_test_123"
        
        TestBugLinks.link_id = data[0]["link_id"]
        print(f"Added link {data[0]['link_id']} to bug {bug_id}")
    
    def test_add_multiple_links(self, api_client, setup_test_user):
        """Test adding multiple links at once"""
        bug_id = TestBugLinks.link_bug_id
        
        link_payload = {
            "links": [
                {"entity_type": "feature", "entity_id": "feat_test_456"},
                {"entity_type": "story", "entity_id": "story_test_789"}
            ]
        }
        response = api_client.post(f"{BASE_URL}/api/bugs/{bug_id}/links", json=link_payload)
        assert response.status_code == 200, f"Add multiple links failed: {response.text}"
        
        data = response.json()
        assert len(data) == 2
        print(f"Added {len(data)} more links to bug {bug_id}")
    
    def test_get_links(self, api_client, setup_test_user):
        """Test getting all links for a bug"""
        bug_id = TestBugLinks.link_bug_id
        
        response = api_client.get(f"{BASE_URL}/api/bugs/{bug_id}/links")
        assert response.status_code == 200, f"Get links failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3  # epic + feature + story
        
        entity_types = [link["entity_type"] for link in data]
        assert "epic" in entity_types
        assert "feature" in entity_types
        assert "story" in entity_types
        print(f"Bug has {len(data)} links")
    
    def test_bug_shows_link_count(self, api_client, setup_test_user):
        """Test that bug response includes link count"""
        bug_id = TestBugLinks.link_bug_id
        
        response = api_client.get(f"{BASE_URL}/api/bugs/{bug_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["link_count"] == 3
        print(f"Bug link_count: {data['link_count']}")
    
    def test_filter_linked_bugs(self, api_client, setup_test_user):
        """Test filtering for linked bugs only"""
        response = api_client.get(f"{BASE_URL}/api/bugs?linked=true")
        assert response.status_code == 200
        
        data = response.json()
        for bug in data:
            assert bug["link_count"] > 0
        print(f"Filtered linked bugs: {len(data)}")
    
    def test_remove_link(self, api_client, setup_test_user):
        """Test removing a link from a bug"""
        bug_id = TestBugLinks.link_bug_id
        link_id = TestBugLinks.link_id
        
        response = api_client.delete(f"{BASE_URL}/api/bugs/{bug_id}/links/{link_id}")
        assert response.status_code == 200, f"Remove link failed: {response.text}"
        
        # Verify link is removed
        get_response = api_client.get(f"{BASE_URL}/api/bugs/{bug_id}/links")
        assert get_response.status_code == 200
        links = get_response.json()
        link_ids = [link["link_id"] for link in links]
        assert link_id not in link_ids
        print(f"Removed link {link_id}")


class TestBugSoftDelete:
    """Bug soft delete tests"""
    
    def test_soft_delete_bug(self, api_client, setup_test_user):
        """Test soft deleting a bug"""
        # Create a bug to delete
        payload = {
            "title": "TEST_Bug to Delete",
            "description": "This bug will be soft deleted",
            "severity": "low"
        }
        create_response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert create_response.status_code == 200
        bug_id = create_response.json()["bug_id"]
        
        # Delete the bug
        response = api_client.delete(f"{BASE_URL}/api/bugs/{bug_id}")
        assert response.status_code == 200, f"Delete bug failed: {response.text}"
        
        # Verify bug is not returned in list
        list_response = api_client.get(f"{BASE_URL}/api/bugs")
        assert list_response.status_code == 200
        bug_ids = [bug["bug_id"] for bug in list_response.json()]
        assert bug_id not in bug_ids
        
        # Verify GET returns 404
        get_response = api_client.get(f"{BASE_URL}/api/bugs/{bug_id}")
        assert get_response.status_code == 404
        
        print(f"Soft deleted bug {bug_id}")


class TestBugValidation:
    """Bug validation tests"""
    
    def test_invalid_severity_rejected(self, api_client, setup_test_user):
        """Test that invalid severity is rejected"""
        payload = {
            "title": "TEST_Invalid Severity Bug",
            "description": "Bug with invalid severity",
            "severity": "super_critical"  # Invalid
        }
        
        response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert response.status_code == 400, f"Expected 400 for invalid severity, got {response.status_code}"
        print("Invalid severity correctly rejected")
    
    def test_invalid_priority_rejected(self, api_client, setup_test_user):
        """Test that invalid priority is rejected"""
        payload = {
            "title": "TEST_Invalid Priority Bug",
            "description": "Bug with invalid priority",
            "severity": "medium",
            "priority": "p99"  # Invalid
        }
        
        response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert response.status_code == 400, f"Expected 400 for invalid priority, got {response.status_code}"
        print("Invalid priority correctly rejected")
    
    def test_missing_title_rejected(self, api_client, setup_test_user):
        """Test that missing title is rejected"""
        payload = {
            "description": "Bug without title",
            "severity": "medium"
        }
        
        response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert response.status_code == 422, f"Expected 422 for missing title, got {response.status_code}"
        print("Missing title correctly rejected")
    
    def test_missing_description_rejected(self, api_client, setup_test_user):
        """Test that missing description is rejected"""
        payload = {
            "title": "TEST_Bug without description",
            "severity": "medium"
        }
        
        response = api_client.post(f"{BASE_URL}/api/bugs", json=payload)
        assert response.status_code == 422, f"Expected 422 for missing description, got {response.status_code}"
        print("Missing description correctly rejected")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_bugs(self, api_client, setup_test_user):
        """Clean up all TEST_ prefixed bugs"""
        response = api_client.get(f"{BASE_URL}/api/bugs")
        assert response.status_code == 200
        
        bugs = response.json()
        deleted_count = 0
        
        for bug in bugs:
            if bug["title"].startswith("TEST_"):
                delete_response = api_client.delete(f"{BASE_URL}/api/bugs/{bug['bug_id']}")
                if delete_response.status_code == 200:
                    deleted_count += 1
        
        print(f"Cleaned up {deleted_count} test bugs")
