"""
Test Standalone User Stories API
Tests for standalone user stories that are not linked to any feature.
Endpoints tested:
- GET /api/stories/standalone - List all standalone user stories
- POST /api/stories/standalone - Create a standalone user story manually
- GET /api/stories/standalone/{story_id} - Get a specific standalone story
- PUT /api/stories/standalone/{story_id} - Update a standalone story
- DELETE /api/stories/standalone/{story_id} - Delete a standalone story
- POST /api/stories/standalone/{story_id}/approve - Approve and lock a standalone story
- POST /api/stories/ai/chat - AI-assisted story creation conversation (streaming)
- POST /api/stories/ai/create-from-proposal - Create story from AI proposal
"""
import pytest
import requests
import os
import json
import time

# Read from .env file directly
def get_base_url():
    env_path = '/app/frontend/.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip().strip('"\'')
    return os.environ.get('REACT_APP_BACKEND_URL', 'https://jarlpm-planner.preview.emergentagent.com').rstrip('/')

BASE_URL = get_base_url()

@pytest.fixture(scope="module")
def session():
    """Create a requests session with auth"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Get test login session
    response = s.post(f"{BASE_URL}/api/auth/test-login")
    if response.status_code == 200:
        print(f"Test login successful")
    else:
        pytest.skip(f"Test login failed: {response.status_code}")
    
    return s


@pytest.fixture(scope="module")
def created_story_id(session):
    """Create a test story and return its ID for other tests"""
    data = {
        "title": "TEST_Standalone Story for Testing",
        "persona": "test user",
        "action": "run automated tests",
        "benefit": "ensure the API works correctly",
        "acceptance_criteria": [
            "Given a test user, When they run tests, Then all tests pass"
        ],
        "story_points": 3,
        "source": "manual"
    }
    response = session.post(f"{BASE_URL}/api/stories/standalone", json=data)
    if response.status_code == 201:
        story = response.json()
        yield story["story_id"]
        # Cleanup
        session.delete(f"{BASE_URL}/api/stories/standalone/{story['story_id']}")
    else:
        pytest.skip(f"Failed to create test story: {response.status_code}")


class TestStandaloneStoriesAPI:
    """Test standalone user stories CRUD operations"""
    
    def test_list_standalone_stories(self, session):
        """GET /api/stories/standalone - List all standalone stories"""
        response = session.get(f"{BASE_URL}/api/stories/standalone")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"SUCCESS: Listed {len(data)} standalone stories")
    
    def test_list_standalone_stories_with_stage_filter(self, session):
        """GET /api/stories/standalone?stage=draft - Filter by stage"""
        response = session.get(f"{BASE_URL}/api/stories/standalone?stage=draft")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # All returned stories should be in draft stage
        for story in data:
            assert story["current_stage"] == "draft", f"Expected draft stage, got {story['current_stage']}"
        print(f"SUCCESS: Listed {len(data)} draft standalone stories")
    
    def test_create_standalone_story(self, session):
        """POST /api/stories/standalone - Create a standalone story"""
        data = {
            "title": "TEST_Create Standalone Story",
            "persona": "product manager",
            "action": "create standalone user stories",
            "benefit": "track work independently of features",
            "acceptance_criteria": [
                "Given a PM, When they create a story, Then it appears in the list",
                "Given a story, When it's standalone, Then feature_id is null"
            ],
            "story_points": 2,
            "source": "manual"
        }
        
        response = session.post(f"{BASE_URL}/api/stories/standalone", json=data)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        
        story = response.json()
        assert story["title"] == data["title"], "Title mismatch"
        assert story["persona"] == data["persona"], "Persona mismatch"
        assert story["action"] == data["action"], "Action mismatch"
        assert story["benefit"] == data["benefit"], "Benefit mismatch"
        assert story["is_standalone"] == True, "Should be standalone"
        assert story["feature_id"] is None, "Feature ID should be null"
        assert story["current_stage"] == "draft", "Should start in draft stage"
        assert story["story_points"] == 2, "Story points mismatch"
        assert "story_id" in story, "Should have story_id"
        
        # Verify story text is properly formatted
        expected_text = f"As a {data['persona']}, I want to {data['action']} so that {data['benefit']}."
        assert story["story_text"] == expected_text, f"Story text mismatch: {story['story_text']}"
        
        print(f"SUCCESS: Created standalone story {story['story_id']}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/stories/standalone/{story['story_id']}")
    
    def test_create_standalone_story_minimal(self, session):
        """POST /api/stories/standalone - Create with minimal required fields"""
        data = {
            "title": "TEST_Minimal Story",
            "persona": "user",
            "action": "do something",
            "benefit": "get value"
        }
        
        response = session.post(f"{BASE_URL}/api/stories/standalone", json=data)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        
        story = response.json()
        assert story["title"] == data["title"]
        assert story["is_standalone"] == True
        assert story["story_points"] is None, "Story points should be null when not provided"
        
        print(f"SUCCESS: Created minimal standalone story {story['story_id']}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/stories/standalone/{story['story_id']}")
    
    def test_get_standalone_story(self, session, created_story_id):
        """GET /api/stories/standalone/{story_id} - Get a specific story"""
        response = session.get(f"{BASE_URL}/api/stories/standalone/{created_story_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        story = response.json()
        assert story["story_id"] == created_story_id, "Story ID mismatch"
        assert story["is_standalone"] == True, "Should be standalone"
        assert "persona" in story, "Should have persona"
        assert "action" in story, "Should have action"
        assert "benefit" in story, "Should have benefit"
        
        print(f"SUCCESS: Retrieved standalone story {created_story_id}")
    
    def test_get_nonexistent_story(self, session):
        """GET /api/stories/standalone/{story_id} - 404 for nonexistent story"""
        response = session.get(f"{BASE_URL}/api/stories/standalone/nonexistent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("SUCCESS: Got 404 for nonexistent story")
    
    def test_update_standalone_story(self, session, created_story_id):
        """PUT /api/stories/standalone/{story_id} - Update a story"""
        update_data = {
            "persona": "updated test user",
            "action": "run updated tests",
            "benefit": "verify updates work",
            "story_points": 5
        }
        
        response = session.put(f"{BASE_URL}/api/stories/standalone/{created_story_id}", json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        story = response.json()
        assert story["persona"] == update_data["persona"], "Persona not updated"
        assert story["action"] == update_data["action"], "Action not updated"
        assert story["benefit"] == update_data["benefit"], "Benefit not updated"
        assert story["story_points"] == update_data["story_points"], "Story points not updated"
        
        # Verify story text is updated
        expected_text = f"As a {update_data['persona']}, I want to {update_data['action']} so that {update_data['benefit']}."
        assert story["story_text"] == expected_text, f"Story text not updated: {story['story_text']}"
        
        print(f"SUCCESS: Updated standalone story {created_story_id}")
    
    def test_update_acceptance_criteria(self, session, created_story_id):
        """PUT /api/stories/standalone/{story_id} - Update acceptance criteria"""
        update_data = {
            "acceptance_criteria": [
                "Given updated context, When action happens, Then result occurs",
                "Given another context, When another action, Then another result"
            ]
        }
        
        response = session.put(f"{BASE_URL}/api/stories/standalone/{created_story_id}", json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        story = response.json()
        assert len(story["acceptance_criteria"]) == 2, "Should have 2 acceptance criteria"
        assert story["acceptance_criteria"][0] == update_data["acceptance_criteria"][0]
        
        print(f"SUCCESS: Updated acceptance criteria for story {created_story_id}")
    
    def test_delete_standalone_story(self, session):
        """DELETE /api/stories/standalone/{story_id} - Delete a story"""
        # First create a story to delete
        data = {
            "title": "TEST_Story to Delete",
            "persona": "tester",
            "action": "delete stories",
            "benefit": "clean up test data"
        }
        create_response = session.post(f"{BASE_URL}/api/stories/standalone", json=data)
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        # Delete the story
        response = session.delete(f"{BASE_URL}/api/stories/standalone/{story_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify it's deleted
        get_response = session.get(f"{BASE_URL}/api/stories/standalone/{story_id}")
        assert get_response.status_code == 404, "Story should be deleted"
        
        print(f"SUCCESS: Deleted standalone story {story_id}")
    
    def test_approve_standalone_story(self, session):
        """POST /api/stories/standalone/{story_id}/approve - Approve and lock a story"""
        # Create a story to approve
        data = {
            "title": "TEST_Story to Approve",
            "persona": "approver",
            "action": "approve stories",
            "benefit": "lock them for implementation"
        }
        create_response = session.post(f"{BASE_URL}/api/stories/standalone", json=data)
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        # Approve the story
        response = session.post(f"{BASE_URL}/api/stories/standalone/{story_id}/approve")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        story = response.json()
        assert story["current_stage"] == "approved", f"Expected approved stage, got {story['current_stage']}"
        assert story["approved_at"] is not None, "Should have approved_at timestamp"
        
        print(f"SUCCESS: Approved standalone story {story_id}")
        
        # Cleanup - Note: approved stories cannot be deleted via normal endpoint
        # This is expected behavior
    
    def test_cannot_update_approved_story(self, session):
        """PUT /api/stories/standalone/{story_id} - Cannot update approved story"""
        # Create and approve a story
        data = {
            "title": "TEST_Approved Story No Update",
            "persona": "user",
            "action": "test update lock",
            "benefit": "verify approved stories are locked"
        }
        create_response = session.post(f"{BASE_URL}/api/stories/standalone", json=data)
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        # Approve it
        approve_response = session.post(f"{BASE_URL}/api/stories/standalone/{story_id}/approve")
        assert approve_response.status_code == 200
        
        # Try to update - should fail
        update_data = {"persona": "hacker"}
        response = session.put(f"{BASE_URL}/api/stories/standalone/{story_id}", json=update_data)
        assert response.status_code == 409, f"Expected 409 Conflict, got {response.status_code}"
        
        print(f"SUCCESS: Cannot update approved story (got 409)")
    
    def test_cannot_delete_approved_story(self, session):
        """DELETE /api/stories/standalone/{story_id} - Cannot delete approved story"""
        # Create and approve a story
        data = {
            "title": "TEST_Approved Story No Delete",
            "persona": "user",
            "action": "test delete lock",
            "benefit": "verify approved stories cannot be deleted"
        }
        create_response = session.post(f"{BASE_URL}/api/stories/standalone", json=data)
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        # Approve it
        approve_response = session.post(f"{BASE_URL}/api/stories/standalone/{story_id}/approve")
        assert approve_response.status_code == 200
        
        # Try to delete - should fail
        response = session.delete(f"{BASE_URL}/api/stories/standalone/{story_id}")
        assert response.status_code == 409, f"Expected 409 Conflict, got {response.status_code}"
        
        print(f"SUCCESS: Cannot delete approved story (got 409)")


class TestAIStoryCreation:
    """Test AI-assisted story creation endpoints"""
    
    def test_ai_chat_endpoint(self, session):
        """POST /api/stories/ai/chat - AI chat returns streaming response"""
        data = {
            "content": "Hi, I want to create a user story.",
            "conversation_history": []
        }
        
        response = session.post(
            f"{BASE_URL}/api/stories/ai/chat",
            json=data,
            stream=True
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "text/event-stream" in response.headers.get("content-type", ""), "Should be SSE stream"
        
        # Read some of the stream
        chunks = []
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    event_data = json.loads(line[6:])
                    chunks.append(event_data)
                    if event_data.get("type") == "done":
                        break
                except json.JSONDecodeError:
                    pass
            if len(chunks) > 20:  # Limit chunks to avoid timeout
                break
        
        assert len(chunks) > 0, "Should receive at least one chunk"
        print(f"SUCCESS: AI chat returned {len(chunks)} chunks")
    
    def test_ai_chat_continues_conversation(self, session):
        """POST /api/stories/ai/chat - AI continues conversation with history"""
        # First message
        data1 = {
            "content": "I want to create a story about user authentication",
            "conversation_history": []
        }
        
        response1 = session.post(f"{BASE_URL}/api/stories/ai/chat", json=data1, stream=True)
        assert response1.status_code == 200
        
        # Collect first response
        first_response = ""
        for line in response1.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    event_data = json.loads(line[6:])
                    if event_data.get("type") == "chunk":
                        first_response += event_data.get("content", "")
                    if event_data.get("type") == "done":
                        break
                except json.JSONDecodeError:
                    pass
        
        # Second message with history
        data2 = {
            "content": "The persona is a registered user who wants to log in securely",
            "conversation_history": [
                {"role": "user", "content": data1["content"]},
                {"role": "assistant", "content": first_response}
            ]
        }
        
        response2 = session.post(f"{BASE_URL}/api/stories/ai/chat", json=data2, stream=True)
        assert response2.status_code == 200, f"Expected 200, got {response2.status_code}"
        
        print("SUCCESS: AI chat continues conversation with history")
    
    def test_create_from_proposal(self, session):
        """POST /api/stories/ai/create-from-proposal - Create story from AI proposal"""
        proposal = {
            "title": "TEST_User Login Story",
            "persona": "registered user",
            "action": "log in to my account securely",
            "benefit": "I can access my personalized dashboard",
            "acceptance_criteria": [
                "Given a registered user, When they enter valid credentials, Then they are logged in",
                "Given a user, When they enter invalid credentials, Then they see an error message"
            ],
            "story_points": 3
        }
        
        response = session.post(f"{BASE_URL}/api/stories/ai/create-from-proposal", json=proposal)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        story = response.json()
        assert story["title"] == proposal["title"], "Title mismatch"
        assert story["persona"] == proposal["persona"], "Persona mismatch"
        assert story["action"] == proposal["action"], "Action mismatch"
        assert story["benefit"] == proposal["benefit"], "Benefit mismatch"
        assert story["is_standalone"] == True, "Should be standalone"
        assert story["source"] == "ai_generated", "Source should be ai_generated"
        assert story["story_points"] == proposal["story_points"], "Story points mismatch"
        
        print(f"SUCCESS: Created story from proposal: {story['story_id']}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/stories/standalone/{story['story_id']}")
    
    def test_create_from_proposal_minimal(self, session):
        """POST /api/stories/ai/create-from-proposal - Create with minimal fields"""
        proposal = {
            "title": "TEST_Minimal AI Story",
            "persona": "user",
            "action": "do something",
            "benefit": "get value"
        }
        
        response = session.post(f"{BASE_URL}/api/stories/ai/create-from-proposal", json=proposal)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        story = response.json()
        assert story["title"] == proposal["title"]
        assert story["source"] == "ai_generated"
        
        print(f"SUCCESS: Created minimal story from proposal: {story['story_id']}")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/stories/standalone/{story['story_id']}")


class TestStandaloneStoryChat:
    """Test chat/refine endpoint for standalone stories"""
    
    def test_chat_with_standalone_story(self, session):
        """POST /api/stories/standalone/{story_id}/chat - Refine story via chat"""
        # Create a story first
        data = {
            "title": "TEST_Story for Chat",
            "persona": "developer",
            "action": "refine user stories",
            "benefit": "improve story quality"
        }
        create_response = session.post(f"{BASE_URL}/api/stories/standalone", json=data)
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        # Chat with the story
        chat_data = {"content": "Can you make the acceptance criteria more specific?"}
        response = session.post(
            f"{BASE_URL}/api/stories/standalone/{story_id}/chat",
            json=chat_data,
            stream=True
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/event-stream" in response.headers.get("content-type", ""), "Should be SSE stream"
        
        # Read some chunks
        chunks = []
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    event_data = json.loads(line[6:])
                    chunks.append(event_data)
                    if event_data.get("type") == "done":
                        break
                except json.JSONDecodeError:
                    pass
            if len(chunks) > 20:
                break
        
        assert len(chunks) > 0, "Should receive chunks"
        print(f"SUCCESS: Chat with standalone story returned {len(chunks)} chunks")
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/stories/standalone/{story_id}")
    
    def test_cannot_chat_with_approved_story(self, session):
        """POST /api/stories/standalone/{story_id}/chat - Cannot refine approved story"""
        # Create and approve a story
        data = {
            "title": "TEST_Approved Story No Chat",
            "persona": "user",
            "action": "test chat lock",
            "benefit": "verify approved stories cannot be refined"
        }
        create_response = session.post(f"{BASE_URL}/api/stories/standalone", json=data)
        assert create_response.status_code == 201
        story_id = create_response.json()["story_id"]
        
        # Approve it
        approve_response = session.post(f"{BASE_URL}/api/stories/standalone/{story_id}/approve")
        assert approve_response.status_code == 200
        
        # Try to chat - should fail
        chat_data = {"content": "Try to refine this"}
        response = session.post(f"{BASE_URL}/api/stories/standalone/{story_id}/chat", json=chat_data)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        print("SUCCESS: Cannot chat with approved story (got 400)")


class TestAuthRequired:
    """Test that endpoints require authentication"""
    
    def test_list_requires_auth(self):
        """GET /api/stories/standalone - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/stories/standalone")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: List standalone stories requires auth")
    
    def test_create_requires_auth(self):
        """POST /api/stories/standalone - Requires authentication"""
        data = {"title": "Test", "persona": "user", "action": "test", "benefit": "test"}
        response = requests.post(f"{BASE_URL}/api/stories/standalone", json=data)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: Create standalone story requires auth")
    
    def test_ai_chat_requires_auth(self):
        """POST /api/stories/ai/chat - Requires authentication"""
        data = {"content": "test", "conversation_history": []}
        response = requests.post(f"{BASE_URL}/api/stories/ai/chat", json=data)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: AI chat requires auth")
    
    def test_create_from_proposal_requires_auth(self):
        """POST /api/stories/ai/create-from-proposal - Requires authentication"""
        data = {"title": "Test", "persona": "user", "action": "test", "benefit": "test"}
        response = requests.post(f"{BASE_URL}/api/stories/ai/create-from-proposal", json=data)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: Create from proposal requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
