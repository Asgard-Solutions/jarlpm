#!/usr/bin/env python3
"""
JarlPM Lock Policy Testing Suite
Tests state-driven locking model across Epics, Features, and User Stories

Modules tested:
- GET /api/epics/{epic_id}/permissions - Returns correct permissions based on epic stage
- PUT /api/features/{feature_id} - Respects lock policy (works during Feature Planning Mode, fails for approved)
- DELETE /api/features/{feature_id} - Respects lock policy
- PUT /api/stories/{story_id} - Respects lock policy (works during Feature Planning Mode, fails for approved)
- DELETE /api/stories/{story_id} - Respects lock policy
- Test login functionality
- Epic creation and stage transitions
- Feature creation and approval flow
- User story creation and approval flow

Lock Policy Design:
- Epic anchors (Problem + Outcome) become immutable after they are set
- Features and User Stories become non-editable when individually approved
- Feature Planning Mode happens when epic is in epic_locked stage
"""

import pytest
import requests
import os

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://product-ai-4.preview.emergentagent.com').rstrip('/')

# Test user credentials (created by Test Login button)
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"


@pytest.fixture(scope="module")
def auth_headers():
    """Get headers with authentication"""
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TEST_SESSION_TOKEN}'
    }


@pytest.fixture(scope="module")
def test_user_id():
    """Get test user ID by calling test-login"""
    response = requests.post(f"{BASE_URL}/api/auth/test-login", timeout=10)
    return response.json()["user_id"]


class TestLoginFunctionality:
    """Test login functionality works correctly"""
    
    def test_test_login_endpoint(self):
        """Test that POST /api/auth/test-login works and returns user data"""
        response = requests.post(
            f"{BASE_URL}/api/auth/test-login",
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert data["email"] == "testuser@jarlpm.dev"
        assert data["subscription_status"] == "active"
        assert data["llm_provider"] == "openai (gpt-4o)"
        print(f"Test login successful: user_id={data['user_id']}")
    
    def test_get_current_user(self, auth_headers):
        """Test that GET /api/auth/me returns current user"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert data["email"] == "testuser@jarlpm.dev"
    
    def test_unauthenticated_request_fails(self):
        """Test that requests without auth return 401"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            timeout=10
        )
        assert response.status_code == 401


class TestEpicPermissionsEndpoint:
    """Test GET /api/epics/{epic_id}/permissions endpoint"""
    
    def test_permissions_for_draft_epic(self, auth_headers):
        """Test permissions for epic in problem_capture (draft) stage"""
        # Create a new epic (starts in problem_capture stage)
        create_response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Permissions Draft Epic"},
            timeout=10
        )
        assert create_response.status_code == 201
        epic_id = create_response.json()["epic_id"]
        
        try:
            response = requests.get(
                f"{BASE_URL}/api/epics/{epic_id}/permissions",
                headers=auth_headers,
                timeout=10
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["epic_id"] == epic_id
            assert data["current_stage"] == "problem_capture"
            
            permissions = data["permissions"]
            
            # Epic permissions in draft stage
            assert permissions["epic"]["status"] == "draft"
            assert permissions["epic"]["can_edit"] == True
            assert permissions["epic"]["fields"]["title"] == True
            assert permissions["epic"]["fields"]["problem_statement"] == True
            
            # Features can be created/edited/deleted
            assert permissions["features"]["can_create"] == True
            assert permissions["features"]["can_edit"] == True
            assert permissions["features"]["can_delete"] == True
            assert permissions["features"]["is_locked"] == False
            
            # Stories can be created/edited/deleted
            assert permissions["stories"]["can_create"] == True
            assert permissions["stories"]["can_edit"] == True
            assert permissions["stories"]["can_delete"] == True
            assert permissions["stories"]["is_frozen"] == False
            
            print(f"Draft epic permissions verified: {epic_id}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
    
    def test_permissions_nonexistent_epic(self, auth_headers):
        """Test permissions for nonexistent epic returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/epics/epic_nonexistent123/permissions",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404
    
    def test_permissions_unauthenticated(self):
        """Test permissions without auth returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/epics/epic_any/permissions",
            timeout=10
        )
        assert response.status_code == 401


class TestFeatureLockPolicyViaAPI:
    """Test PUT/DELETE /api/features/{feature_id} respects lock policy using existing test data"""
    
    def test_update_draft_feature_succeeds(self, auth_headers):
        """Test that draft features can be updated during Feature Planning Mode"""
        # Use existing locked epic from previous tests
        # First, find a locked epic with features
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing - need to create one via full workflow")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Create a draft feature
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            json={
                "title": "TEST_Draft Feature for Update",
                "description": "A draft feature that can be edited",
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        feature_id = create_response.json()["feature_id"]
        
        try:
            # Update the draft feature
            response = requests.put(
                f"{BASE_URL}/api/features/{feature_id}",
                headers=auth_headers,
                json={
                    "title": "TEST_Updated Draft Feature",
                    "description": "Updated description"
                },
                timeout=10
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["title"] == "TEST_Updated Draft Feature"
            assert data["description"] == "Updated description"
            print(f"Draft feature updated successfully: {feature_id}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
    
    def test_update_approved_feature_fails(self, auth_headers):
        """Test that approved features cannot be updated (returns 400)"""
        # Find a locked epic
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Create and approve a feature
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            json={
                "title": "TEST_Feature to Approve",
                "description": "Feature that will be approved and locked",
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        feature_id = create_response.json()["feature_id"]
        
        try:
            # Approve the feature
            approve_response = requests.post(
                f"{BASE_URL}/api/features/{feature_id}/approve",
                headers=auth_headers,
                timeout=10
            )
            assert approve_response.status_code == 200
            assert approve_response.json()["current_stage"] == "approved"
            
            # Try to update the approved feature - should fail
            response = requests.put(
                f"{BASE_URL}/api/features/{feature_id}",
                headers=auth_headers,
                json={
                    "title": "TEST_Should Not Update"
                },
                timeout=10
            )
            assert response.status_code == 400
            print(f"Approved feature correctly rejected update: {feature_id}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
    
    def test_delete_draft_feature_succeeds(self, auth_headers):
        """Test that draft features can be deleted during Feature Planning Mode"""
        # Find a locked epic
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Create a draft feature to delete
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            json={
                "title": "TEST_Feature to Delete",
                "description": "This feature will be deleted",
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        feature_id = create_response.json()["feature_id"]
        
        # Delete the feature
        response = requests.delete(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        # Verify deleted
        get_response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.status_code == 404
        print(f"Draft feature deleted successfully: {feature_id}")
    
    def test_delete_approved_feature_succeeds(self, auth_headers):
        """Test that approved features CAN be deleted during Feature Planning Mode"""
        # Note: Lock policy only prevents deletion when epic is ARCHIVED
        # Find a locked epic
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Create and approve a feature
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            json={
                "title": "TEST_Approved Feature to Delete",
                "description": "This approved feature will be deleted",
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        feature_id = create_response.json()["feature_id"]
        
        # Approve the feature
        approve_response = requests.post(
            f"{BASE_URL}/api/features/{feature_id}/approve",
            headers=auth_headers,
            timeout=10
        )
        assert approve_response.status_code == 200
        
        # Delete the approved feature (should succeed during Feature Planning Mode)
        response = requests.delete(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        print(f"Approved feature deleted successfully during Feature Planning Mode: {feature_id}")


class TestUserStoryLockPolicyViaAPI:
    """Test PUT/DELETE /api/stories/{story_id} respects lock policy"""
    
    def test_update_draft_story_succeeds(self, auth_headers):
        """Test that draft stories can be updated during Feature Planning Mode"""
        # Find an approved feature
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Get features for this epic
        features_response = requests.get(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert features_response.status_code == 200
        
        approved_features = [f for f in features_response.json() if f["current_stage"] == "approved"]
        
        if not approved_features:
            pytest.skip("No approved feature available for testing")
        
        feature_id = approved_features[0]["feature_id"]
        
        # Create a draft story
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{feature_id}",
            headers=auth_headers,
            json={
                "persona": "test user",
                "action": "update this story",
                "benefit": "test updating",
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        try:
            # Update the draft story
            response = requests.put(
                f"{BASE_URL}/api/stories/{story_id}",
                headers=auth_headers,
                json={
                    "persona": "updated user",
                    "action": "perform updated action",
                    "story_points": 5
                },
                timeout=10
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["persona"] == "updated user"
            assert data["action"] == "perform updated action"
            assert data["story_points"] == 5
            print(f"Draft story updated successfully: {story_id}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
    
    def test_update_approved_story_fails(self, auth_headers):
        """Test that approved stories cannot be updated (returns 400)"""
        # Find an approved feature
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Get features for this epic
        features_response = requests.get(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert features_response.status_code == 200
        
        approved_features = [f for f in features_response.json() if f["current_stage"] == "approved"]
        
        if not approved_features:
            pytest.skip("No approved feature available for testing")
        
        feature_id = approved_features[0]["feature_id"]
        
        # Create and approve a story
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{feature_id}",
            headers=auth_headers,
            json={
                "persona": "approval user",
                "action": "be approved",
                "benefit": "test immutability",
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        try:
            # Approve the story
            approve_response = requests.post(
                f"{BASE_URL}/api/stories/{story_id}/approve",
                headers=auth_headers,
                timeout=10
            )
            assert approve_response.status_code == 200
            assert approve_response.json()["current_stage"] == "approved"
            
            # Try to update the approved story - should fail
            response = requests.put(
                f"{BASE_URL}/api/stories/{story_id}",
                headers=auth_headers,
                json={
                    "persona": "should not update"
                },
                timeout=10
            )
            assert response.status_code == 400
            print(f"Approved story correctly rejected update: {story_id}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
    
    def test_delete_draft_story_succeeds(self, auth_headers):
        """Test that draft stories can be deleted during Feature Planning Mode"""
        # Find an approved feature
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Get features for this epic
        features_response = requests.get(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert features_response.status_code == 200
        
        approved_features = [f for f in features_response.json() if f["current_stage"] == "approved"]
        
        if not approved_features:
            pytest.skip("No approved feature available for testing")
        
        feature_id = approved_features[0]["feature_id"]
        
        # Create a draft story to delete
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{feature_id}",
            headers=auth_headers,
            json={
                "persona": "delete user",
                "action": "be deleted",
                "benefit": "test deletion",
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        # Delete the story
        response = requests.delete(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        # Verify deleted
        get_response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.status_code == 404
        print(f"Draft story deleted successfully: {story_id}")
    
    def test_delete_approved_story_succeeds(self, auth_headers):
        """Test that approved stories CAN be deleted during Feature Planning Mode"""
        # Find an approved feature
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Get features for this epic
        features_response = requests.get(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert features_response.status_code == 200
        
        approved_features = [f for f in features_response.json() if f["current_stage"] == "approved"]
        
        if not approved_features:
            pytest.skip("No approved feature available for testing")
        
        feature_id = approved_features[0]["feature_id"]
        
        # Create and approve a story
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{feature_id}",
            headers=auth_headers,
            json={
                "persona": "approved delete user",
                "action": "be approved then deleted",
                "benefit": "test approved deletion",
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        # Approve the story
        approve_response = requests.post(
            f"{BASE_URL}/api/stories/{story_id}/approve",
            headers=auth_headers,
            timeout=10
        )
        assert approve_response.status_code == 200
        
        # Delete the approved story (should succeed during Feature Planning Mode)
        response = requests.delete(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        print(f"Approved story deleted successfully during Feature Planning Mode: {story_id}")


class TestEpicCreationAndTransition:
    """Test epic creation and transition through stages"""
    
    def test_create_epic(self, auth_headers):
        """Test creating a new epic starts in problem_capture stage"""
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_New Epic Creation"},
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert "epic_id" in data
        assert data["title"] == "TEST_New Epic Creation"
        assert data["current_stage"] == "problem_capture"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{data['epic_id']}", headers=auth_headers, timeout=10)
        print(f"Epic created successfully: {data['epic_id']}")
    
    def test_get_epic(self, auth_headers):
        """Test getting an epic by ID"""
        # Create epic
        create_response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Get Epic Test"},
            timeout=10
        )
        epic_id = create_response.json()["epic_id"]
        
        # Get epic
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["epic_id"] == epic_id
        assert data["title"] == "TEST_Get Epic Test"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
    
    def test_list_epics(self, auth_headers):
        """Test listing all epics for user"""
        response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "epics" in data
        assert isinstance(data["epics"], list)
    
    def test_delete_epic(self, auth_headers):
        """Test deleting an epic"""
        # Create epic
        create_response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Delete Epic Test"},
            timeout=10
        )
        epic_id = create_response.json()["epic_id"]
        
        # Delete epic
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        # Verify deleted
        get_response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.status_code == 404


class TestFeatureCreationAndApproval:
    """Test feature creation and approval flow"""
    
    def test_create_feature_for_locked_epic(self, auth_headers):
        """Test creating a feature for a locked epic"""
        # Find a locked epic
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            json={
                "title": "TEST_New Feature",
                "description": "A new feature for testing",
                "acceptance_criteria": ["AC1", "AC2"],
                "source": "manual"
            },
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert "feature_id" in data
        assert data["title"] == "TEST_New Feature"
        assert data["current_stage"] == "draft"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{data['feature_id']}", headers=auth_headers, timeout=10)
    
    def test_approve_feature_locks_it(self, auth_headers):
        """Test approving a feature locks it"""
        # Find a locked epic
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Create feature
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            json={
                "title": "TEST_Feature to Approve",
                "description": "Feature that will be approved",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        try:
            # Approve feature
            response = requests.post(
                f"{BASE_URL}/api/features/{feature_id}/approve",
                headers=auth_headers,
                timeout=10
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["current_stage"] == "approved"
            assert data["approved_at"] is not None
            
            # Verify cannot update after approval
            update_response = requests.put(
                f"{BASE_URL}/api/features/{feature_id}",
                headers=auth_headers,
                json={"title": "Should Not Update"},
                timeout=10
            )
            assert update_response.status_code == 400
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)


class TestUserStoryCreationAndApproval:
    """Test user story creation and approval flow"""
    
    def test_create_story_for_approved_feature(self, auth_headers):
        """Test creating a user story for an approved feature"""
        # Find an approved feature
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Get features for this epic
        features_response = requests.get(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert features_response.status_code == 200
        
        approved_features = [f for f in features_response.json() if f["current_stage"] == "approved"]
        
        if not approved_features:
            pytest.skip("No approved feature available for testing")
        
        feature_id = approved_features[0]["feature_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{feature_id}",
            headers=auth_headers,
            json={
                "persona": "test user",
                "action": "create a story",
                "benefit": "test story creation",
                "acceptance_criteria": ["Given X, When Y, Then Z"],
                "story_points": 3,
                "source": "manual"
            },
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert "story_id" in data
        assert data["persona"] == "test user"
        assert data["current_stage"] == "draft"
        assert "As a test user" in data["story_text"]
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{data['story_id']}", headers=auth_headers, timeout=10)
    
    def test_approve_story_locks_it(self, auth_headers):
        """Test approving a story locks it"""
        # Find an approved feature
        epics_response = requests.get(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            timeout=10
        )
        assert epics_response.status_code == 200
        
        locked_epics = [e for e in epics_response.json()["epics"] if e["current_stage"] == "epic_locked"]
        
        if not locked_epics:
            pytest.skip("No locked epic available for testing")
        
        epic_id = locked_epics[0]["epic_id"]
        
        # Get features for this epic
        features_response = requests.get(
            f"{BASE_URL}/api/features/epic/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert features_response.status_code == 200
        
        approved_features = [f for f in features_response.json() if f["current_stage"] == "approved"]
        
        if not approved_features:
            pytest.skip("No approved feature available for testing")
        
        feature_id = approved_features[0]["feature_id"]
        
        # Create story
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{feature_id}",
            headers=auth_headers,
            json={
                "persona": "approval user",
                "action": "be approved",
                "benefit": "test approval",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        try:
            # Approve story
            response = requests.post(
                f"{BASE_URL}/api/stories/{story_id}/approve",
                headers=auth_headers,
                timeout=10
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["current_stage"] == "approved"
            assert data["approved_at"] is not None
            
            # Verify cannot update after approval
            update_response = requests.put(
                f"{BASE_URL}/api/stories/{story_id}",
                headers=auth_headers,
                json={"persona": "should not update"},
                timeout=10
            )
            assert update_response.status_code == 400
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
