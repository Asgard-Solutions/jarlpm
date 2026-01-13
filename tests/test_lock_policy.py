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
import sys
import asyncio
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, '/app/backend')

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pm-workspace-2.preview.emergentagent.com').rstrip('/')

# Test user credentials (created by Test Login button)
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"


@pytest.fixture(scope="module")
def auth_headers():
    """Get headers with authentication"""
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TEST_SESSION_TOKEN}'
    }


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
    
    @pytest.fixture(scope="class")
    def test_epic(self, auth_headers):
        """Create a test epic for permissions testing"""
        # Create epic
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Lock Policy Permissions Epic"},
            timeout=10
        )
        assert response.status_code == 201
        epic_id = response.json()["epic_id"]
        yield epic_id
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
    
    def test_permissions_for_draft_epic(self, auth_headers, test_epic):
        """Test permissions for epic in problem_capture (draft) stage"""
        response = requests.get(
            f"{BASE_URL}/api/epics/{test_epic}/permissions",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["epic_id"] == test_epic
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
    
    def test_permissions_for_locked_epic(self, auth_headers):
        """Test permissions for epic in epic_locked stage (Feature Planning Mode)"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        from sqlalchemy import select
        import uuid
        
        async def _create_locked_epic():
            async with AsyncSessionLocal() as session:
                # Get test user ID
                login_response = requests.post(f"{BASE_URL}/api/auth/test-login", timeout=10)
                user_id = login_response.json()["user_id"]
                
                # Create a locked epic directly
                epic_id = f"epic_locktest_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=user_id,
                    title="TEST_Locked Epic for Permissions",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                # Create snapshot
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Test problem statement",
                    desired_outcome="Test desired outcome",
                    epic_summary="Test epic summary",
                    acceptance_criteria=["Criterion 1", "Criterion 2"]
                )
                session.add(snapshot)
                await session.commit()
                
                return epic_id
        
        epic_id = asyncio.run(_create_locked_epic())
        
        try:
            response = requests.get(
                f"{BASE_URL}/api/epics/{epic_id}/permissions",
                headers=auth_headers,
                timeout=10
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["current_stage"] == "epic_locked"
            
            permissions = data["permissions"]
            
            # Epic is locked - no edits allowed
            assert permissions["epic"]["status"] == "locked"
            assert permissions["epic"]["can_edit"] == False
            
            # Features CAN still be created/edited/deleted during Feature Planning Mode
            # (until individually approved)
            assert permissions["features"]["can_create"] == True
            assert permissions["features"]["can_edit"] == True
            assert permissions["features"]["can_delete"] == True
            assert permissions["features"]["is_locked"] == False  # Only locked when ARCHIVED
            
            # Stories CAN still be created/edited/deleted during Feature Planning Mode
            assert permissions["stories"]["can_create"] == True
            assert permissions["stories"]["can_edit"] == True
            assert permissions["stories"]["can_delete"] == True
            assert permissions["stories"]["is_frozen"] == False  # Only frozen when ARCHIVED
            
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


class TestFeatureLockPolicy:
    """Test PUT/DELETE /api/features/{feature_id} respects lock policy"""
    
    @pytest.fixture(scope="class")
    def locked_epic_with_features(self, auth_headers):
        """Create a locked epic with features for testing"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        from db.feature_models import Feature, FeatureStage
        import uuid
        
        async def _create_test_data():
            async with AsyncSessionLocal() as session:
                # Get test user ID
                login_response = requests.post(f"{BASE_URL}/api/auth/test-login", timeout=10)
                user_id = login_response.json()["user_id"]
                
                # Create a locked epic
                epic_id = f"epic_featlock_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=user_id,
                    title="TEST_Feature Lock Policy Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                # Create snapshot
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Test problem",
                    desired_outcome="Test outcome",
                    epic_summary="Test summary",
                    acceptance_criteria=["AC1"]
                )
                session.add(snapshot)
                
                # Create a draft feature (editable)
                draft_feature_id = f"feat_draft_{uuid.uuid4().hex[:8]}"
                draft_feature = Feature(
                    feature_id=draft_feature_id,
                    epic_id=epic_id,
                    title="TEST_Draft Feature",
                    description="A draft feature that can be edited",
                    current_stage=FeatureStage.DRAFT.value,
                    source="manual"
                )
                session.add(draft_feature)
                
                # Create an approved feature (immutable)
                approved_feature_id = f"feat_approved_{uuid.uuid4().hex[:8]}"
                approved_feature = Feature(
                    feature_id=approved_feature_id,
                    epic_id=epic_id,
                    title="TEST_Approved Feature",
                    description="An approved feature that cannot be edited",
                    current_stage=FeatureStage.APPROVED.value,
                    source="manual",
                    approved_at=datetime.now(timezone.utc)
                )
                session.add(approved_feature)
                
                await session.commit()
                
                return {
                    "epic_id": epic_id,
                    "draft_feature_id": draft_feature_id,
                    "approved_feature_id": approved_feature_id
                }
        
        data = asyncio.run(_create_test_data())
        yield data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{data['epic_id']}", headers=auth_headers, timeout=10)
    
    def test_update_draft_feature_succeeds(self, auth_headers, locked_epic_with_features):
        """Test that draft features can be updated during Feature Planning Mode"""
        feature_id = locked_epic_with_features["draft_feature_id"]
        
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
    
    def test_update_approved_feature_fails(self, auth_headers, locked_epic_with_features):
        """Test that approved features cannot be updated (returns 400)"""
        feature_id = locked_epic_with_features["approved_feature_id"]
        
        response = requests.put(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            json={
                "title": "TEST_Should Not Update"
            },
            timeout=10
        )
        assert response.status_code == 400
        assert "approved" in response.json().get("detail", "").lower() or "cannot update" in response.json().get("detail", "").lower()
        print(f"Approved feature correctly rejected update: {feature_id}")
    
    def test_delete_draft_feature_succeeds(self, auth_headers, locked_epic_with_features):
        """Test that draft features can be deleted during Feature Planning Mode"""
        # Create a new draft feature to delete
        epic_id = locked_epic_with_features["epic_id"]
        
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
    
    def test_delete_approved_feature_succeeds(self, auth_headers, locked_epic_with_features):
        """Test that approved features CAN be deleted (lock policy allows deletion)"""
        # Note: The lock policy only prevents deletion when epic is ARCHIVED
        # During Feature Planning Mode (epic_locked), deletion is allowed
        epic_id = locked_epic_with_features["epic_id"]
        
        # Create and approve a feature to delete
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


class TestUserStoryLockPolicy:
    """Test PUT/DELETE /api/stories/{story_id} respects lock policy"""
    
    @pytest.fixture(scope="class")
    def locked_epic_with_stories(self, auth_headers):
        """Create a locked epic with approved feature and stories for testing"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        from db.feature_models import Feature, FeatureStage
        from db.user_story_models import UserStory, UserStoryStage
        import uuid
        
        async def _create_test_data():
            async with AsyncSessionLocal() as session:
                # Get test user ID
                login_response = requests.post(f"{BASE_URL}/api/auth/test-login", timeout=10)
                user_id = login_response.json()["user_id"]
                
                # Create a locked epic
                epic_id = f"epic_storylock_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=user_id,
                    title="TEST_Story Lock Policy Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                # Create snapshot
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Test problem",
                    desired_outcome="Test outcome",
                    epic_summary="Test summary",
                    acceptance_criteria=["AC1"]
                )
                session.add(snapshot)
                
                # Create an approved feature (required for stories)
                feature_id = f"feat_storylock_{uuid.uuid4().hex[:8]}"
                feature = Feature(
                    feature_id=feature_id,
                    epic_id=epic_id,
                    title="TEST_Feature for Stories",
                    description="Feature to hold test stories",
                    current_stage=FeatureStage.APPROVED.value,
                    source="manual",
                    approved_at=datetime.now(timezone.utc)
                )
                session.add(feature)
                
                # Create a draft story (editable)
                draft_story_id = f"story_draft_{uuid.uuid4().hex[:8]}"
                draft_story = UserStory(
                    story_id=draft_story_id,
                    feature_id=feature_id,
                    persona="test user",
                    action="edit this story",
                    benefit="test editing",
                    story_text="As a test user, I want to edit this story so that test editing.",
                    current_stage=UserStoryStage.DRAFT.value,
                    source="manual"
                )
                session.add(draft_story)
                
                # Create an approved story (immutable)
                approved_story_id = f"story_approved_{uuid.uuid4().hex[:8]}"
                approved_story = UserStory(
                    story_id=approved_story_id,
                    feature_id=feature_id,
                    persona="test user",
                    action="not edit this story",
                    benefit="test immutability",
                    story_text="As a test user, I want to not edit this story so that test immutability.",
                    current_stage=UserStoryStage.APPROVED.value,
                    source="manual",
                    approved_at=datetime.now(timezone.utc)
                )
                session.add(approved_story)
                
                await session.commit()
                
                return {
                    "epic_id": epic_id,
                    "feature_id": feature_id,
                    "draft_story_id": draft_story_id,
                    "approved_story_id": approved_story_id
                }
        
        data = asyncio.run(_create_test_data())
        yield data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{data['epic_id']}", headers=auth_headers, timeout=10)
    
    def test_update_draft_story_succeeds(self, auth_headers, locked_epic_with_stories):
        """Test that draft stories can be updated during Feature Planning Mode"""
        story_id = locked_epic_with_stories["draft_story_id"]
        
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
    
    def test_update_approved_story_fails(self, auth_headers, locked_epic_with_stories):
        """Test that approved stories cannot be updated (returns 400)"""
        story_id = locked_epic_with_stories["approved_story_id"]
        
        response = requests.put(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            json={
                "persona": "should not update"
            },
            timeout=10
        )
        assert response.status_code == 400
        assert "approved" in response.json().get("detail", "").lower() or "cannot update" in response.json().get("detail", "").lower()
        print(f"Approved story correctly rejected update: {story_id}")
    
    def test_delete_draft_story_succeeds(self, auth_headers, locked_epic_with_stories):
        """Test that draft stories can be deleted during Feature Planning Mode"""
        feature_id = locked_epic_with_stories["feature_id"]
        
        # Create a new draft story to delete
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
    
    def test_delete_approved_story_succeeds(self, auth_headers, locked_epic_with_stories):
        """Test that approved stories CAN be deleted (lock policy allows deletion)"""
        # Note: The lock policy only prevents deletion when epic is ARCHIVED
        # During Feature Planning Mode (epic_locked), deletion is allowed
        feature_id = locked_epic_with_stories["feature_id"]
        
        # Create and approve a story to delete
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
    
    @pytest.fixture(scope="class")
    def locked_epic(self, auth_headers):
        """Create a locked epic for feature testing"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        import uuid
        
        async def _create_locked_epic():
            async with AsyncSessionLocal() as session:
                login_response = requests.post(f"{BASE_URL}/api/auth/test-login", timeout=10)
                user_id = login_response.json()["user_id"]
                
                epic_id = f"epic_feattest_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=user_id,
                    title="TEST_Feature Creation Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Test problem",
                    desired_outcome="Test outcome",
                    epic_summary="Test summary",
                    acceptance_criteria=["AC1"]
                )
                session.add(snapshot)
                await session.commit()
                
                return epic_id
        
        epic_id = asyncio.run(_create_locked_epic())
        yield epic_id
        
        requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
    
    def test_create_feature(self, auth_headers, locked_epic):
        """Test creating a feature for a locked epic"""
        response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
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
    
    def test_approve_feature(self, auth_headers, locked_epic):
        """Test approving a feature locks it"""
        # Create feature
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Feature to Approve",
                "description": "Feature that will be approved",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
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
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)


class TestUserStoryCreationAndApproval:
    """Test user story creation and approval flow"""
    
    @pytest.fixture(scope="class")
    def approved_feature(self, auth_headers):
        """Create a locked epic with approved feature for story testing"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        from db.feature_models import Feature, FeatureStage
        import uuid
        
        async def _create_test_data():
            async with AsyncSessionLocal() as session:
                login_response = requests.post(f"{BASE_URL}/api/auth/test-login", timeout=10)
                user_id = login_response.json()["user_id"]
                
                epic_id = f"epic_storytest_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=user_id,
                    title="TEST_Story Creation Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Test problem",
                    desired_outcome="Test outcome",
                    epic_summary="Test summary",
                    acceptance_criteria=["AC1"]
                )
                session.add(snapshot)
                
                feature_id = f"feat_storytest_{uuid.uuid4().hex[:8]}"
                feature = Feature(
                    feature_id=feature_id,
                    epic_id=epic_id,
                    title="TEST_Feature for Story Creation",
                    description="Feature to hold test stories",
                    current_stage=FeatureStage.APPROVED.value,
                    source="manual",
                    approved_at=datetime.now(timezone.utc)
                )
                session.add(feature)
                await session.commit()
                
                return {"epic_id": epic_id, "feature_id": feature_id}
        
        data = asyncio.run(_create_test_data())
        yield data["feature_id"]
        
        requests.delete(f"{BASE_URL}/api/epics/{data['epic_id']}", headers=auth_headers, timeout=10)
    
    def test_create_story(self, auth_headers, approved_feature):
        """Test creating a user story for an approved feature"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
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
    
    def test_approve_story(self, auth_headers, approved_feature):
        """Test approving a story locks it"""
        # Create story
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
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
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
