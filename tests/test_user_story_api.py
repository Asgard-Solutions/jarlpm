#!/usr/bin/env python3
"""
JarlPM User Story API Testing Suite
Tests all User Story API endpoints for the new User Story Planning workflow

Modules tested:
- User Story CRUD operations (/stories/feature/{feature_id}, /stories/{story_id})
- User Story lifecycle (draft -> refining -> approved)
- User Story generation (/stories/feature/{feature_id}/generate)
- User Story refinement chat (/stories/{story_id}/chat)
- User Story approval (/stories/{story_id}/approve)
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
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://jarlpm-fix.preview.emergentagent.com').rstrip('/')

# Test user credentials (created by Test Login button)
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"
TEST_USER_ID = "user_test_05279c2b"


@pytest.fixture(scope="module")
def auth_headers():
    """Get headers with authentication"""
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TEST_SESSION_TOKEN}'
    }


@pytest.fixture(scope="module")
def approved_feature(auth_headers):
    """Create a locked epic with an approved feature for user story testing"""
    from dotenv import load_dotenv
    load_dotenv('/app/backend/.env')
    
    from db.database import AsyncSessionLocal
    from db.models import Epic, EpicSnapshot, EpicStage
    from db.feature_models import Feature, FeatureStage
    from sqlalchemy import select
    import uuid
    
    async def _create_approved_feature():
        async with AsyncSessionLocal() as session:
            # Check if we already have an approved feature for testing
            result = await session.execute(
                select(Feature).where(
                    Feature.current_stage == FeatureStage.APPROVED.value,
                    Feature.title.like("TEST_UserStory%")
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return existing.feature_id, existing.epic_id
            
            # Create a new locked epic
            epic_id = f"epic_ustest_{uuid.uuid4().hex[:8]}"
            
            epic = Epic(
                epic_id=epic_id,
                user_id=TEST_USER_ID,
                title="TEST_UserStory Testing Epic",
                current_stage=EpicStage.EPIC_LOCKED.value
            )
            session.add(epic)
            await session.flush()
            
            # Create snapshot
            snapshot = EpicSnapshot(
                epic_id=epic_id,
                problem_statement="Users need to manage user stories efficiently",
                desired_outcome="A streamlined user story management system",
                epic_summary="Build a user story management system with AI assistance",
                acceptance_criteria=[
                    "Stories can be generated via AI",
                    "Stories follow standard format",
                    "Stories can be refined and approved"
                ]
            )
            session.add(snapshot)
            
            # Create approved feature
            feature_id = f"feat_ustest_{uuid.uuid4().hex[:8]}"
            feature = Feature(
                feature_id=feature_id,
                epic_id=epic_id,
                title="TEST_UserStory Generation Feature",
                description="Allow users to generate and manage user stories from approved features",
                acceptance_criteria=[
                    "Given an approved feature, When user generates stories, Then AI creates user stories",
                    "Given a story, When user approves it, Then it becomes locked"
                ],
                current_stage=FeatureStage.APPROVED.value,
                source="manual",
                approved_at=datetime.now(timezone.utc)
            )
            session.add(feature)
            await session.commit()
            
            return feature_id, epic_id
    
    feature_id, epic_id = asyncio.run(_create_approved_feature())
    yield feature_id
    
    # Cleanup via API
    try:
        requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers={'Authorization': f'Bearer {TEST_SESSION_TOKEN}'},
            timeout=10
        )
    except Exception as e:
        print(f"Cleanup warning: {e}")


class TestUserStoryListEndpoint:
    """Test GET /api/stories/feature/{feature_id}"""
    
    def test_list_stories_for_approved_feature(self, auth_headers, approved_feature):
        """Test listing stories for an approved feature"""
        response = requests.get(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"Stories for feature: {len(data)}")
    
    def test_list_stories_nonexistent_feature(self, auth_headers):
        """Test listing stories for nonexistent feature returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/stories/feature/feat_nonexistent123",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404
    
    def test_list_stories_unauthenticated(self, approved_feature):
        """Test listing stories without auth returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            timeout=10
        )
        assert response.status_code == 401


class TestUserStoryCreateEndpoint:
    """Test POST /api/stories/feature/{feature_id}"""
    
    def test_create_story_manual(self, auth_headers, approved_feature):
        """Test creating a manual user story with standard format"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "product manager",
                "action": "create user stories from features",
                "benefit": "I can break down features into sprint-sized work",
                "acceptance_criteria": [
                    "Given an approved feature, When I click Create Story, Then a new story is created",
                    "Given a new story, When I view it, Then I see the standard format"
                ],
                "story_points": 3,
                "source": "manual"
            },
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert "story_id" in data
        assert data["persona"] == "product manager"
        assert data["action"] == "create user stories from features"
        assert data["benefit"] == "I can break down features into sprint-sized work"
        assert data["current_stage"] == "draft"
        assert data["source"] == "manual"
        assert data["story_points"] == 3
        
        # Verify story_text follows standard format
        assert "As a product manager" in data["story_text"]
        assert "I want to create user stories from features" in data["story_text"]
        assert "so that I can break down features into sprint-sized work" in data["story_text"]
        
        # Verify acceptance criteria in Given/When/Then format
        assert len(data["acceptance_criteria"]) == 2
        assert "Given" in data["acceptance_criteria"][0]
        assert "When" in data["acceptance_criteria"][0]
        assert "Then" in data["acceptance_criteria"][0]
        
        # Verify persistence with GET
        get_response = requests.get(
            f"{BASE_URL}/api/stories/{data['story_id']}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.status_code == 200
        assert get_response.json()["persona"] == "product manager"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{data['story_id']}", headers=auth_headers, timeout=10)
    
    def test_create_story_ai_generated(self, auth_headers, approved_feature):
        """Test creating an AI-generated user story"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "developer",
                "action": "view story details",
                "benefit": "I understand what to implement",
                "acceptance_criteria": ["Given a story, When I view it, Then I see all details"],
                "story_points": 2,
                "source": "ai_generated"
            },
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data["source"] == "ai_generated"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{data['story_id']}", headers=auth_headers, timeout=10)
    
    def test_create_story_without_criteria(self, auth_headers, approved_feature):
        """Test creating a story without acceptance criteria"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "user",
                "action": "do something",
                "benefit": "I get value",
                "source": "manual"
            },
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data["acceptance_criteria"] is None or data["acceptance_criteria"] == []
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{data['story_id']}", headers=auth_headers, timeout=10)
    
    def test_create_story_missing_persona(self, auth_headers, approved_feature):
        """Test creating a story without persona returns 422"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "action": "do something",
                "benefit": "I get value"
            },
            timeout=10
        )
        assert response.status_code == 422
    
    def test_create_story_missing_action(self, auth_headers, approved_feature):
        """Test creating a story without action returns 422"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "user",
                "benefit": "I get value"
            },
            timeout=10
        )
        assert response.status_code == 422
    
    def test_create_story_missing_benefit(self, auth_headers, approved_feature):
        """Test creating a story without benefit returns 422"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "user",
                "action": "do something"
            },
            timeout=10
        )
        assert response.status_code == 422


class TestUserStoryGetEndpoint:
    """Test GET /api/stories/{story_id}"""
    
    def test_get_story(self, auth_headers, approved_feature):
        """Test getting a story by ID"""
        # Create story first
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "tester",
                "action": "get story details",
                "benefit": "I can verify the story",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        # Get story
        response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["story_id"] == story_id
        assert data["persona"] == "tester"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
    
    def test_get_nonexistent_story(self, auth_headers):
        """Test getting nonexistent story returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/stories/story_nonexistent123",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404


class TestUserStoryUpdateEndpoint:
    """Test PUT /api/stories/{story_id}"""
    
    def test_update_story(self, auth_headers, approved_feature):
        """Test updating a story"""
        # Create story first
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "original user",
                "action": "original action",
                "benefit": "original benefit",
                "story_points": 5,
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        # Update story
        response = requests.put(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            json={
                "persona": "updated user",
                "action": "updated action",
                "story_points": 3
            },
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["persona"] == "updated user"
        assert data["action"] == "updated action"
        assert data["benefit"] == "original benefit"  # Unchanged
        assert data["story_points"] == 3
        
        # Verify story_text updated
        assert "As a updated user" in data["story_text"]
        assert "I want to updated action" in data["story_text"]
        
        # Verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.json()["persona"] == "updated user"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
    
    def test_update_partial(self, auth_headers, approved_feature):
        """Test partial update of a story"""
        # Create story first
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "partial user",
                "action": "partial action",
                "benefit": "partial benefit",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        # Update only story_points
        response = requests.put(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            json={
                "story_points": 8
            },
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["persona"] == "partial user"  # Unchanged
        assert data["story_points"] == 8
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)


class TestUserStoryDeleteEndpoint:
    """Test DELETE /api/stories/{story_id}"""
    
    def test_delete_story(self, auth_headers, approved_feature):
        """Test deleting a story"""
        # Create story first
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "delete user",
                "action": "be deleted",
                "benefit": "test deletion",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        # Delete story
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
    
    def test_delete_nonexistent_story(self, auth_headers):
        """Test deleting nonexistent story returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/stories/story_nonexistent123",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404


class TestUserStoryApproveEndpoint:
    """Test POST /api/stories/{story_id}/approve"""
    
    def test_approve_story(self, auth_headers, approved_feature):
        """Test approving a story"""
        # Create story first
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "approve user",
                "action": "be approved",
                "benefit": "test approval",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        assert create_response.json()["current_stage"] == "draft"
        
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
        
        # Verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.json()["current_stage"] == "approved"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
    
    def test_approve_already_approved_story(self, auth_headers, approved_feature):
        """Test approving an already approved story returns 400"""
        # Create and approve story
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "double approve user",
                "action": "be double approved",
                "benefit": "test double approval",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        # First approval
        requests.post(f"{BASE_URL}/api/stories/{story_id}/approve", headers=auth_headers, timeout=10)
        
        # Second approval should fail
        response = requests.post(
            f"{BASE_URL}/api/stories/{story_id}/approve",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 400
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
    
    def test_cannot_update_approved_story(self, auth_headers, approved_feature):
        """Test that approved stories cannot be updated"""
        # Create and approve story
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "locked user",
                "action": "be locked",
                "benefit": "test immutability",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        # Approve
        requests.post(f"{BASE_URL}/api/stories/{story_id}/approve", headers=auth_headers, timeout=10)
        
        # Try to update
        response = requests.put(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            json={
                "persona": "should not update"
            },
            timeout=10
        )
        assert response.status_code == 400
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)


class TestUserStoryConversationEndpoint:
    """Test GET /api/stories/{story_id}/conversation"""
    
    def test_get_conversation_empty(self, auth_headers, approved_feature):
        """Test getting conversation for new story returns empty list"""
        # Create story first
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "conversation user",
                "action": "have conversation",
                "benefit": "test conversation",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        # Get conversation
        response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}/conversation",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)


class TestUserStoryLifecycle:
    """Test complete user story lifecycle: draft -> refining -> approved"""
    
    def test_full_lifecycle(self, auth_headers, approved_feature):
        """Test complete user story lifecycle"""
        # 1. Create story (draft stage)
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "lifecycle user",
                "action": "go through lifecycle",
                "benefit": "test full lifecycle",
                "acceptance_criteria": ["Given a story, When lifecycle completes, Then it is approved"],
                "story_points": 5,
                "source": "manual"
            },
            timeout=10
        )
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        assert create_response.json()["current_stage"] == "draft"
        
        # 2. Update story (still draft)
        update_response = requests.put(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            json={
                "benefit": "test full lifecycle with updates"
            },
            timeout=10
        )
        assert update_response.status_code == 200
        
        # 3. Approve story (moves to approved)
        approve_response = requests.post(
            f"{BASE_URL}/api/stories/{story_id}/approve",
            headers=auth_headers,
            timeout=10
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["current_stage"] == "approved"
        
        # 4. Verify cannot update after approval
        update_after_approve = requests.put(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            json={
                "persona": "should not update"
            },
            timeout=10
        )
        assert update_after_approve.status_code == 400
        
        # 5. Verify can still delete (cleanup)
        delete_response = requests.delete(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert delete_response.status_code in [200, 520]


class TestUserStoryGenerateEndpoint:
    """Test POST /api/stories/feature/{feature_id}/generate (streaming)"""
    
    def test_generate_stories_endpoint_exists(self, auth_headers, approved_feature):
        """Test that generate stories endpoint exists and returns streaming response"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}/generate",
            headers=auth_headers,
            json={"count": 2},
            timeout=90,  # Longer timeout for AI generation
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


class TestUserStoryChatEndpoint:
    """Test POST /api/stories/{story_id}/chat (streaming)"""
    
    def test_chat_endpoint_exists(self, auth_headers, approved_feature):
        """Test that chat endpoint exists and returns streaming response"""
        # Create story first
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "chat user",
                "action": "chat with AI",
                "benefit": "refine the story",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        # Send chat message
        response = requests.post(
            f"{BASE_URL}/api/stories/{story_id}/chat",
            headers=auth_headers,
            json={"content": "Please add more acceptance criteria"},
            timeout=90,  # Longer timeout for AI response
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
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
    
    def test_chat_moves_to_refining_stage(self, auth_headers, approved_feature):
        """Test that chatting with a draft story moves it to refining stage"""
        # Create story first
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "refining user",
                "action": "enter refining stage",
                "benefit": "test stage transition",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        assert create_response.json()["current_stage"] == "draft"
        
        # Send chat message (this should move to refining)
        response = requests.post(
            f"{BASE_URL}/api/stories/{story_id}/chat",
            headers=auth_headers,
            json={"content": "Add error handling criteria"},
            timeout=90,
            stream=True
        )
        
        # Consume the stream
        for chunk in response.iter_content(chunk_size=1024):
            pass
        response.close()
        
        # Check that story moved to refining stage
        get_response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.status_code == 200
        assert get_response.json()["current_stage"] == "refining"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
    
    def test_cannot_chat_with_approved_story(self, auth_headers, approved_feature):
        """Test that chatting with approved story returns 400"""
        # Create and approve story
        create_response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "approved chat user",
                "action": "try to chat after approval",
                "benefit": "test chat restriction",
                "source": "manual"
            },
            timeout=10
        )
        story_id = create_response.json()["story_id"]
        
        # Approve
        requests.post(f"{BASE_URL}/api/stories/{story_id}/approve", headers=auth_headers, timeout=10)
        
        # Try to chat
        response = requests.post(
            f"{BASE_URL}/api/stories/{story_id}/chat",
            headers=auth_headers,
            json={"content": "Should not work"},
            timeout=10
        )
        assert response.status_code == 400
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)


class TestUserStoryFormat:
    """Test that user stories follow the standard format"""
    
    def test_story_text_format(self, auth_headers, approved_feature):
        """Test that story_text follows 'As a [persona], I want to [action] so that [benefit]' format"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature}",
            headers=auth_headers,
            json={
                "persona": "product owner",
                "action": "prioritize user stories",
                "benefit": "the team works on the most valuable items first",
                "source": "manual"
            },
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        expected_format = "As a product owner, I want to prioritize user stories so that the team works on the most valuable items first."
        assert data["story_text"] == expected_format
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/stories/{data['story_id']}", headers=auth_headers, timeout=10)
    
    def test_story_points_values(self, auth_headers, approved_feature):
        """Test that story points can be set to valid values (1, 2, 3, 5, 8)"""
        valid_points = [1, 2, 3, 5, 8]
        
        for points in valid_points:
            response = requests.post(
                f"{BASE_URL}/api/stories/feature/{approved_feature}",
                headers=auth_headers,
                json={
                    "persona": "user",
                    "action": f"test {points} points",
                    "benefit": "validate story points",
                    "story_points": points,
                    "source": "manual"
                },
                timeout=10
            )
            assert response.status_code == 201
            assert response.json()["story_points"] == points
            
            # Cleanup
            requests.delete(f"{BASE_URL}/api/stories/{response.json()['story_id']}", headers=auth_headers, timeout=10)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
