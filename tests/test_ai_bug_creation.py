"""
Test AI-Assisted Bug Creation Feature
Tests the AI chat endpoint and create-from-proposal endpoint for JarlPM Bug Tracker
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAIBugCreation:
    """Tests for AI-assisted bug creation via conversation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with test user
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200, f"Test login failed: {response.text}"
        
        yield
        
        # Cleanup: Delete any TEST_ prefixed bugs
        try:
            bugs_response = self.session.get(f"{BASE_URL}/api/bugs")
            if bugs_response.status_code == 200:
                bugs = bugs_response.json()
                for bug in bugs:
                    if bug.get('title', '').startswith('TEST_'):
                        self.session.delete(f"{BASE_URL}/api/bugs/{bug['bug_id']}")
        except Exception:
            pass
    
    def test_ai_chat_endpoint_returns_streaming_response(self):
        """Test POST /api/bugs/ai/chat returns streaming SSE response"""
        response = self.session.post(
            f"{BASE_URL}/api/bugs/ai/chat",
            json={
                "content": "Hi, I want to report a bug.",
                "conversation_history": []
            },
            stream=True
        )
        
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'text/event-stream; charset=utf-8'
        
        # Read streaming response
        full_content = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        if data.get('type') == 'chunk':
                            full_content += data.get('content', '')
                        elif data.get('type') == 'done':
                            break
                    except json.JSONDecodeError:
                        pass
        
        # AI should ask about the problem
        assert len(full_content) > 0, "AI should respond with content"
        print(f"AI Response: {full_content[:200]}...")
    
    def test_ai_chat_asks_about_problem_first(self):
        """Test AI asks about the problem as first question"""
        response = self.session.post(
            f"{BASE_URL}/api/bugs/ai/chat",
            json={
                "content": "Hi, I want to report a bug.",
                "conversation_history": []
            },
            stream=True
        )
        
        assert response.status_code == 200
        
        full_content = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        if data.get('type') == 'chunk':
                            full_content += data.get('content', '')
                        elif data.get('type') == 'done':
                            break
                    except json.JSONDecodeError:
                        pass
        
        # AI should ask about the problem
        full_content_lower = full_content.lower()
        assert any(word in full_content_lower for word in ['problem', 'wrong', 'issue', 'experiencing']), \
            f"AI should ask about the problem. Got: {full_content}"
    
    def test_ai_chat_continues_conversation(self):
        """Test AI continues conversation with follow-up questions"""
        response = self.session.post(
            f"{BASE_URL}/api/bugs/ai/chat",
            json={
                "content": "The login button does not work on mobile",
                "conversation_history": [
                    {"role": "user", "content": "Hi, I want to report a bug."},
                    {"role": "assistant", "content": "Of course! Could you tell me more about the problem?"}
                ]
            },
            stream=True
        )
        
        assert response.status_code == 200
        
        full_content = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        if data.get('type') == 'chunk':
                            full_content += data.get('content', '')
                        elif data.get('type') == 'done':
                            break
                    except json.JSONDecodeError:
                        pass
        
        # AI should ask for more details (steps to reproduce, expected behavior, etc.)
        full_content_lower = full_content.lower()
        assert any(word in full_content_lower for word in ['steps', 'reproduce', 'expected', 'happen', 'describe']), \
            f"AI should ask follow-up questions. Got: {full_content}"
    
    def test_ai_chat_generates_proposal_with_enough_info(self):
        """Test AI generates proposal when enough information is provided"""
        # Provide comprehensive bug information in one message
        response = self.session.post(
            f"{BASE_URL}/api/bugs/ai/chat",
            json={
                "content": "Only on mobile Safari on iPhone 15 Pro. It works fine on desktop Chrome.",
                "conversation_history": [
                    {"role": "user", "content": "Hi, I want to report a bug."},
                    {"role": "assistant", "content": "Of course! Could you tell me more about the problem?"},
                    {"role": "user", "content": "The login button does not work on mobile devices"},
                    {"role": "assistant", "content": "Can you describe the steps to reproduce this issue?"},
                    {"role": "user", "content": "1. Open app on iPhone Safari. 2. Go to login page. 3. Enter credentials. 4. Tap login button. Nothing happens."},
                    {"role": "assistant", "content": "What did you expect to happen vs what actually happened?"},
                    {"role": "user", "content": "I expected to be logged in. Instead the button is completely unresponsive."},
                    {"role": "assistant", "content": "Can you confirm what environment you're using?"}
                ]
            },
            stream=True
        )
        
        assert response.status_code == 200
        
        full_content = ""
        proposal = None
        is_complete = False
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        if data.get('type') == 'chunk':
                            full_content += data.get('content', '')
                        elif data.get('type') == 'done':
                            proposal = data.get('proposal')
                            is_complete = data.get('is_complete', False)
                            break
                    except json.JSONDecodeError:
                        pass
        
        # Should have generated a proposal
        assert proposal is not None, f"AI should generate a proposal. Response: {full_content[:500]}"
        assert is_complete == True, "is_complete should be True when proposal is generated"
        
        # Validate proposal structure
        assert 'title' in proposal, "Proposal should have title"
        assert 'description' in proposal, "Proposal should have description"
        assert 'severity' in proposal, "Proposal should have severity"
        assert proposal['severity'] in ['critical', 'high', 'medium', 'low'], \
            f"Invalid severity: {proposal['severity']}"
        
        print(f"Generated proposal: {json.dumps(proposal, indent=2)}")
    
    def test_create_bug_from_proposal_success(self):
        """Test POST /api/bugs/ai/create-from-proposal creates bug correctly"""
        proposal = {
            "title": "TEST_AI Created Bug - Login issue",
            "description": "The login button does not respond on mobile Safari",
            "severity": "high",
            "steps_to_reproduce": "1. Open app on iPhone. 2. Go to login. 3. Tap button.",
            "expected_behavior": "User should be logged in",
            "actual_behavior": "Button is unresponsive",
            "environment": "iPhone 15 Pro, Safari",
            "priority": "p1"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/bugs/ai/create-from-proposal",
            json=proposal
        )
        
        assert response.status_code == 200, f"Create from proposal failed: {response.text}"
        
        bug = response.json()
        
        # Verify bug was created with correct data
        assert bug['title'] == proposal['title']
        assert bug['description'] == proposal['description']
        assert bug['severity'] == proposal['severity']
        assert bug['steps_to_reproduce'] == proposal['steps_to_reproduce']
        assert bug['expected_behavior'] == proposal['expected_behavior']
        assert bug['actual_behavior'] == proposal['actual_behavior']
        assert bug['environment'] == proposal['environment']
        assert bug['priority'] == proposal['priority']
        assert bug['status'] == 'draft', "New bug should be in draft status"
        assert 'bug_id' in bug, "Bug should have bug_id"
        
        print(f"Created bug: {bug['bug_id']}")
        
        # Verify bug can be retrieved
        get_response = self.session.get(f"{BASE_URL}/api/bugs/{bug['bug_id']}")
        assert get_response.status_code == 200
        
        fetched_bug = get_response.json()
        assert fetched_bug['title'] == proposal['title']
    
    def test_create_bug_from_proposal_validates_severity(self):
        """Test create-from-proposal validates severity field"""
        proposal = {
            "title": "TEST_Invalid Severity Bug",
            "description": "Test bug with invalid severity",
            "severity": "invalid_severity"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/bugs/ai/create-from-proposal",
            json=proposal
        )
        
        assert response.status_code == 400, "Should reject invalid severity"
        assert "severity" in response.text.lower()
    
    def test_create_bug_from_proposal_validates_priority(self):
        """Test create-from-proposal validates priority field"""
        proposal = {
            "title": "TEST_Invalid Priority Bug",
            "description": "Test bug with invalid priority",
            "severity": "medium",
            "priority": "invalid_priority"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/bugs/ai/create-from-proposal",
            json=proposal
        )
        
        assert response.status_code == 400, "Should reject invalid priority"
        assert "priority" in response.text.lower()
    
    def test_create_bug_from_proposal_optional_fields(self):
        """Test create-from-proposal works with only required fields"""
        proposal = {
            "title": "TEST_Minimal Bug",
            "description": "Bug with only required fields",
            "severity": "low"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/bugs/ai/create-from-proposal",
            json=proposal
        )
        
        assert response.status_code == 200, f"Should accept minimal proposal: {response.text}"
        
        bug = response.json()
        assert bug['title'] == proposal['title']
        assert bug['severity'] == proposal['severity']
        assert bug['steps_to_reproduce'] is None
        assert bug['expected_behavior'] is None
        assert bug['actual_behavior'] is None
        assert bug['environment'] is None
        assert bug['priority'] is None
    
    def test_ai_chat_requires_authentication(self):
        """Test AI chat endpoint requires authentication"""
        # Create new session without login
        unauthenticated_session = requests.Session()
        unauthenticated_session.headers.update({"Content-Type": "application/json"})
        
        response = unauthenticated_session.post(
            f"{BASE_URL}/api/bugs/ai/chat",
            json={
                "content": "Hi, I want to report a bug.",
                "conversation_history": []
            }
        )
        
        assert response.status_code == 401, "Should require authentication"
    
    def test_create_from_proposal_requires_authentication(self):
        """Test create-from-proposal endpoint requires authentication"""
        unauthenticated_session = requests.Session()
        unauthenticated_session.headers.update({"Content-Type": "application/json"})
        
        response = unauthenticated_session.post(
            f"{BASE_URL}/api/bugs/ai/create-from-proposal",
            json={
                "title": "Test Bug",
                "description": "Test description",
                "severity": "medium"
            }
        )
        
        assert response.status_code == 401, "Should require authentication"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
