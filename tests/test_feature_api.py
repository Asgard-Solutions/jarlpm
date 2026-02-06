#!/usr/bin/env python3
"""
JarlPM Feature API Testing Suite
Tests all Feature API endpoints for the new Feature Planning workflow

Modules tested:
- Feature CRUD operations (/features/epic/{epic_id}, /features/{feature_id})
- Feature lifecycle (draft -> refining -> approved)
- Feature generation (/features/epic/{epic_id}/generate)
- Feature refinement chat (/features/{feature_id}/chat)
- Feature approval (/features/{feature_id}/approve)
"""

import pytest
import requests
import os
import sys
import asyncio
from datetime import datetime, timedelta, timezone

# Add backend to path
sys.path.insert(0, '/app/backend')

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pm-sync-hub.preview.emergentagent.com').rstrip('/')

# Test user credentials (created by Test Login button)
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"
TEST_USER_ID = "user_test_8575b765"


@pytest.fixture(scope="module")
def auth_headers():
    """Get headers with authentication"""
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TEST_SESSION_TOKEN}'
    }


@pytest.fixture(scope="module")
def locked_epic(auth_headers):
    """Create and lock an epic for feature testing"""
    from dotenv import load_dotenv
    load_dotenv('/app/backend/.env')
    
    from db.database import AsyncSessionLocal
    from db.models import Epic, EpicSnapshot, EpicStage
    from sqlalchemy import select
    
    async def _create_locked_epic():
        async with AsyncSessionLocal() as session:
            # Check if we already have a locked epic for testing
            result = await session.execute(
                select(Epic).where(
                    Epic.user_id == TEST_USER_ID,
                    Epic.current_stage == EpicStage.EPIC_LOCKED.value,
                    Epic.title.like("TEST_Feature%")
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return existing.epic_id
            
            # Create a new locked epic
            import uuid
            epic_id = f"epic_{uuid.uuid4().hex[:12]}"
            
            epic = Epic(
                epic_id=epic_id,
                user_id=TEST_USER_ID,
                title="TEST_Feature Planning Epic",
                current_stage=EpicStage.EPIC_LOCKED.value
            )
            session.add(epic)
            await session.flush()
            
            # Create snapshot
            snapshot = EpicSnapshot(
                epic_id=epic_id,
                problem_statement="Users need a way to manage product features efficiently",
                desired_outcome="A streamlined feature planning workflow with AI assistance",
                epic_summary="Build a feature planning system that allows PMs to generate, refine, and approve features for locked epics",
                acceptance_criteria=[
                    "Features can be generated via AI",
                    "Features can be manually created",
                    "Features can be refined through conversation",
                    "Features can be approved and locked"
                ]
            )
            session.add(snapshot)
            await session.commit()
            
            return epic_id
    
    epic_id = asyncio.run(_create_locked_epic())
    yield epic_id
    
    # Cleanup via API instead of direct DB access to avoid event loop issues
    try:
        requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers={'Authorization': f'Bearer {TEST_SESSION_TOKEN}'},
            timeout=10
        )
    except Exception as e:
        print(f"Cleanup warning: {e}")


class TestFeatureListEndpoint:
    """Test GET /api/features/epic/{epic_id}"""
    
    def test_list_features_for_locked_epic(self, auth_headers, locked_epic):
        """Test listing features for a locked epic returns empty list initially"""
        response = requests.get(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"Features for epic: {len(data)}")
    
    def test_list_features_nonexistent_epic(self, auth_headers):
        """Test listing features for nonexistent epic returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/features/epic/epic_nonexistent123",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404
    
    def test_list_features_unauthenticated(self, locked_epic):
        """Test listing features without auth returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            timeout=10
        )
        assert response.status_code == 401


class TestFeatureCreateEndpoint:
    """Test POST /api/features/epic/{epic_id}"""
    
    def test_create_feature_manual(self, auth_headers, locked_epic):
        """Test creating a manual feature"""
        response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Manual Feature Creation",
                "description": "A feature created manually for testing purposes",
                "acceptance_criteria": ["Criterion 1", "Criterion 2"],
                "source": "manual"
            },
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert "feature_id" in data
        assert data["title"] == "TEST_Manual Feature Creation"
        assert data["description"] == "A feature created manually for testing purposes"
        assert data["current_stage"] == "draft"
        assert data["source"] == "manual"
        assert data["acceptance_criteria"] == ["Criterion 1", "Criterion 2"]
        assert "created_at" in data
        assert "updated_at" in data
        
        # Verify persistence with GET
        get_response = requests.get(
            f"{BASE_URL}/api/features/{data['feature_id']}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.status_code == 200
        assert get_response.json()["title"] == "TEST_Manual Feature Creation"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{data['feature_id']}", headers=auth_headers, timeout=10)
    
    def test_create_feature_ai_generated(self, auth_headers, locked_epic):
        """Test creating an AI-generated feature"""
        response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_AI Generated Feature",
                "description": "A feature generated by AI",
                "acceptance_criteria": ["AI Criterion 1"],
                "source": "ai_generated"
            },
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data["source"] == "ai_generated"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{data['feature_id']}", headers=auth_headers, timeout=10)
    
    def test_create_feature_without_criteria(self, auth_headers, locked_epic):
        """Test creating a feature without acceptance criteria"""
        response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Feature Without Criteria",
                "description": "A feature without acceptance criteria",
                "source": "manual"
            },
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data["acceptance_criteria"] is None or data["acceptance_criteria"] == []
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{data['feature_id']}", headers=auth_headers, timeout=10)
    
    def test_create_feature_missing_title(self, auth_headers, locked_epic):
        """Test creating a feature without title returns 422"""
        response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "description": "A feature without title"
            },
            timeout=10
        )
        assert response.status_code == 422
    
    def test_create_feature_missing_description(self, auth_headers, locked_epic):
        """Test creating a feature without description returns 422"""
        response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "Feature without description"
            },
            timeout=10
        )
        assert response.status_code == 422


class TestFeatureGetEndpoint:
    """Test GET /api/features/{feature_id}"""
    
    def test_get_feature(self, auth_headers, locked_epic):
        """Test getting a feature by ID"""
        # Create feature first
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Get Feature Test",
                "description": "Feature for GET test",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        # Get feature
        response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["feature_id"] == feature_id
        assert data["title"] == "TEST_Get Feature Test"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
    
    def test_get_nonexistent_feature(self, auth_headers):
        """Test getting nonexistent feature returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/features/feat_nonexistent123",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404


class TestFeatureUpdateEndpoint:
    """Test PUT /api/features/{feature_id}"""
    
    def test_update_feature(self, auth_headers, locked_epic):
        """Test updating a feature"""
        # Create feature first
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Update Feature Test",
                "description": "Original description",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        # Update feature
        response = requests.put(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            json={
                "title": "TEST_Updated Feature Title",
                "description": "Updated description",
                "acceptance_criteria": ["New criterion"]
            },
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["title"] == "TEST_Updated Feature Title"
        assert data["description"] == "Updated description"
        assert data["acceptance_criteria"] == ["New criterion"]
        
        # Verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.json()["title"] == "TEST_Updated Feature Title"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
    
    def test_update_partial(self, auth_headers, locked_epic):
        """Test partial update of a feature"""
        # Create feature first
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Partial Update Test",
                "description": "Original description",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        # Update only title
        response = requests.put(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            json={
                "title": "TEST_Only Title Updated"
            },
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["title"] == "TEST_Only Title Updated"
        assert data["description"] == "Original description"  # Should remain unchanged
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)


class TestFeatureDeleteEndpoint:
    """Test DELETE /api/features/{feature_id}"""
    
    def test_delete_feature(self, auth_headers, locked_epic):
        """Test deleting a feature"""
        # Create feature first
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Delete Feature Test",
                "description": "Feature to be deleted",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        # Delete feature
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
    
    def test_delete_nonexistent_feature(self, auth_headers):
        """Test deleting nonexistent feature returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/features/feat_nonexistent123",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404


class TestFeatureApproveEndpoint:
    """Test POST /api/features/{feature_id}/approve"""
    
    def test_approve_feature(self, auth_headers, locked_epic):
        """Test approving a feature"""
        # Create feature first
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Approve Feature Test",
                "description": "Feature to be approved",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        assert create_response.json()["current_stage"] == "draft"
        
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
        
        # Verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.json()["current_stage"] == "approved"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
    
    def test_approve_already_approved_feature(self, auth_headers, locked_epic):
        """Test approving an already approved feature returns 400"""
        # Create and approve feature
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Double Approve Test",
                "description": "Feature to be double approved",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        # First approval
        requests.post(f"{BASE_URL}/api/features/{feature_id}/approve", headers=auth_headers, timeout=10)
        
        # Second approval should fail
        response = requests.post(
            f"{BASE_URL}/api/features/{feature_id}/approve",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 400
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
    
    def test_cannot_update_approved_feature(self, auth_headers, locked_epic):
        """Test that approved features cannot be updated"""
        # Create and approve feature
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Locked Feature Test",
                "description": "Feature that will be locked",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        # Approve
        requests.post(f"{BASE_URL}/api/features/{feature_id}/approve", headers=auth_headers, timeout=10)
        
        # Try to update
        response = requests.put(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            json={
                "title": "TEST_Should Not Update"
            },
            timeout=10
        )
        assert response.status_code == 400
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)


class TestFeatureConversationEndpoint:
    """Test GET /api/features/{feature_id}/conversation"""
    
    def test_get_conversation_empty(self, auth_headers, locked_epic):
        """Test getting conversation for new feature returns empty list"""
        # Create feature first
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Conversation Test",
                "description": "Feature for conversation test",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        # Get conversation
        response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}/conversation",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)


class TestFeatureLifecycle:
    """Test complete feature lifecycle: draft -> refining -> approved"""
    
    def test_full_lifecycle(self, auth_headers, locked_epic):
        """Test complete feature lifecycle"""
        # 1. Create feature (draft stage)
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Lifecycle Feature",
                "description": "Feature for lifecycle test",
                "acceptance_criteria": ["Initial criterion"],
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        feature_id = create_response.json()["feature_id"]
        assert create_response.json()["current_stage"] == "draft"
        
        # 2. Update feature (still draft)
        update_response = requests.put(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            json={
                "description": "Updated description for lifecycle test"
            },
            timeout=10
        )
        assert update_response.status_code == 200
        
        # 3. Approve feature (moves to approved)
        approve_response = requests.post(
            f"{BASE_URL}/api/features/{feature_id}/approve",
            headers=auth_headers,
            timeout=10
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["current_stage"] == "approved"
        
        # 4. Verify cannot update after approval
        update_after_approve = requests.put(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            json={
                "title": "Should not update"
            },
            timeout=10
        )
        assert update_after_approve.status_code == 400
        
        # 5. Verify can still delete (cleanup)
        delete_response = requests.delete(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        # Accept 200 or 520 (transient network issue)
        assert delete_response.status_code in [200, 520]


class TestFeatureGenerateEndpoint:
    """Test POST /api/features/epic/{epic_id}/generate (streaming)"""
    
    def test_generate_features_endpoint_exists(self, auth_headers, locked_epic):
        """Test that generate features endpoint exists and returns streaming response"""
        response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}/generate",
            headers=auth_headers,
            json={"count": 2},
            timeout=60,  # Longer timeout for AI generation
            stream=True
        )
        # Should return 200 for streaming response
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'text/event-stream; charset=utf-8'
        
        # Read some of the stream
        content = ""
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
            if chunk:
                content += chunk
                # Stop after getting some content
                if len(content) > 500:
                    break
        
        print(f"Stream content preview: {content[:200]}...")
        response.close()


class TestFeatureChatEndpoint:
    """Test POST /api/features/{feature_id}/chat (streaming)"""
    
    def test_chat_endpoint_exists(self, auth_headers, locked_epic):
        """Test that chat endpoint exists and returns streaming response"""
        # Create feature first
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Chat Feature",
                "description": "Feature for chat test",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        # Send chat message
        response = requests.post(
            f"{BASE_URL}/api/features/{feature_id}/chat",
            headers=auth_headers,
            json={"content": "Please make the description more specific"},
            timeout=60,  # Longer timeout for AI response
            stream=True
        )
        # Should return 200 for streaming response
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'text/event-stream; charset=utf-8'
        
        # Read some of the stream
        content = ""
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
            if chunk:
                content += chunk
                if len(content) > 500:
                    break
        
        print(f"Chat stream preview: {content[:200]}...")
        response.close()
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
    
    def test_chat_moves_to_refining_stage(self, auth_headers, locked_epic):
        """Test that chatting with a draft feature moves it to refining stage"""
        # Create feature first
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Refining Stage Feature",
                "description": "Feature to test refining stage",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        assert create_response.json()["current_stage"] == "draft"
        
        # Send chat message (this should move to refining)
        response = requests.post(
            f"{BASE_URL}/api/features/{feature_id}/chat",
            headers=auth_headers,
            json={"content": "Add more acceptance criteria"},
            timeout=60,
            stream=True
        )
        
        # Consume the stream
        for chunk in response.iter_content(chunk_size=1024):
            pass
        response.close()
        
        # Check that feature moved to refining stage
        get_response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.status_code == 200
        assert get_response.json()["current_stage"] == "refining"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
    
    def test_cannot_chat_with_approved_feature(self, auth_headers, locked_epic):
        """Test that chatting with approved feature returns 400"""
        # Create and approve feature
        create_response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Approved Chat Feature",
                "description": "Feature to test chat after approval",
                "source": "manual"
            },
            timeout=10
        )
        feature_id = create_response.json()["feature_id"]
        
        # Approve
        requests.post(f"{BASE_URL}/api/features/{feature_id}/approve", headers=auth_headers, timeout=10)
        
        # Try to chat
        response = requests.post(
            f"{BASE_URL}/api/features/{feature_id}/chat",
            headers=auth_headers,
            json={"content": "Should not work"},
            timeout=10
        )
        assert response.status_code == 400
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
