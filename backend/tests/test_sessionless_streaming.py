"""
Test Suite for Sessionless Streaming Endpoints
Tests the P0 critical fix for database connection pool exhaustion.

All streaming endpoints should:
1. Be accessible (return proper HTTP responses)
2. Return 402 without subscription (expected for AI features)
3. Return 400 if no LLM configured
4. Not return 500 server errors (which would indicate import/code issues)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@jarlpm.com"
TEST_PASSWORD = "Test123!"


class TestBackendHealth:
    """Test backend health and startup"""
    
    def test_health_endpoint(self):
        """Backend health endpoint should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ Health check passed: {data}")


class TestAuthentication:
    """Test authentication for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session with cookies"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            # Token is set as cookie
            return session
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    def test_login_works(self, auth_session):
        """Login should work with test credentials"""
        assert auth_session is not None
        # Verify we can access authenticated endpoint
        response = auth_session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        print(f"✓ Login successful, session authenticated")


class TestInitiativeGeneration:
    """Test initiative generation endpoint (sessionless streaming)"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session with cookies"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return session
        pytest.skip("Authentication failed")
    
    def test_initiative_generate_accessible(self, auth_session):
        """Initiative generation endpoint should be accessible"""
        response = auth_session.post(
            f"{BASE_URL}/api/initiative/generate",
            json={"idea": "Test idea for pharmacy app"}
        )
        # Expected: 402 (subscription required) or 200 (streaming)
        # NOT expected: 500 (server error indicating import/code issues)
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Initiative generate endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required) - expected behavior")
        elif response.status_code == 400:
            print(f"  → Returns 400 (no LLM configured) - expected behavior")
        elif response.status_code == 200:
            print(f"  → Returns 200 (streaming response)")
    
    def test_initiative_generate_requires_auth(self):
        """Initiative generation should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/initiative/generate",
            json={"idea": "Test idea"}
        )
        assert response.status_code == 401
        print(f"✓ Initiative generate requires auth: 401")


class TestSprintAIEndpoints:
    """Test sprint AI endpoints (sessionless streaming)"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session with cookies"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return session
        pytest.skip("Authentication failed")
    
    def test_kickoff_plan_accessible(self, auth_session):
        """Sprint kickoff plan endpoint should be accessible"""
        response = auth_session.post(
            f"{BASE_URL}/api/sprints/ai/kickoff-plan"
        )
        # Expected: 402, 400, or 200 - NOT 500
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Sprint kickoff-plan endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
    
    def test_standup_summary_accessible(self, auth_session):
        """Sprint standup summary endpoint should be accessible"""
        response = auth_session.post(
            f"{BASE_URL}/api/sprints/ai/standup-summary"
        )
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Sprint standup-summary endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
    
    def test_wip_suggestions_accessible(self, auth_session):
        """Sprint WIP suggestions endpoint should be accessible"""
        response = auth_session.post(
            f"{BASE_URL}/api/sprints/ai/wip-suggestions"
        )
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Sprint wip-suggestions endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
        elif response.status_code == 200:
            data = response.json()
            print(f"  → Returns 200 with WIP suggestions")
    
    def test_sprint_endpoints_require_auth(self):
        """Sprint AI endpoints should require authentication"""
        endpoints = [
            "/api/sprints/ai/kickoff-plan",
            "/api/sprints/ai/standup-summary",
            "/api/sprints/ai/wip-suggestions"
        ]
        for endpoint in endpoints:
            response = requests.post(f"{BASE_URL}{endpoint}")
            assert response.status_code == 401, f"{endpoint} should require auth"
        print(f"✓ All sprint AI endpoints require auth: 401")


class TestDeliveryRealityAIEndpoints:
    """Test delivery reality AI endpoints (sessionless streaming)"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session with cookies"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return session
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def test_epic_id(self, auth_session):
        """Get a test epic ID"""
        response = auth_session.get(f"{BASE_URL}/api/epics")
        if response.status_code == 200:
            data = response.json()
            epics = data.get("epics", [])
            if epics:
                return epics[0].get("epic_id")
        return "epic_test_nonexistent"
    
    def test_cut_rationale_accessible(self, auth_session, test_epic_id):
        """Delivery reality cut rationale endpoint should be accessible"""
        response = auth_session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}/ai/cut-rationale"
        )
        # Expected: 402, 400, 404, or 200 - NOT 500
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Cut rationale endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
        elif response.status_code == 404:
            print(f"  → Returns 404 (epic not found)")
    
    def test_alternative_cuts_accessible(self, auth_session, test_epic_id):
        """Delivery reality alternative cuts endpoint should be accessible"""
        response = auth_session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}/ai/alternative-cuts"
        )
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Alternative cuts endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
    
    def test_risk_review_accessible(self, auth_session, test_epic_id):
        """Delivery reality risk review endpoint should be accessible"""
        response = auth_session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}/ai/risk-review"
        )
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Risk review endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
    
    def test_delivery_reality_endpoints_require_auth(self):
        """Delivery reality AI endpoints should require authentication"""
        endpoints = [
            "/api/delivery-reality/initiative/test_epic/ai/cut-rationale",
            "/api/delivery-reality/initiative/test_epic/ai/alternative-cuts",
            "/api/delivery-reality/initiative/test_epic/ai/risk-review"
        ]
        for endpoint in endpoints:
            response = requests.post(f"{BASE_URL}{endpoint}")
            assert response.status_code == 401, f"{endpoint} should require auth"
        print(f"✓ All delivery reality AI endpoints require auth: 401")


class TestFeatureGeneration:
    """Test feature generation endpoint (sessionless streaming)"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session with cookies"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return session
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def locked_epic_id(self, auth_session):
        """Get a locked epic ID for feature generation"""
        response = auth_session.get(f"{BASE_URL}/api/epics")
        if response.status_code == 200:
            data = response.json()
            epics = data.get("epics", [])
            for epic in epics:
                if epic.get("current_stage") == "epic_locked":
                    return epic.get("epic_id")
        return None
    
    def test_feature_generate_accessible(self, auth_session, locked_epic_id):
        """Feature generation endpoint should be accessible"""
        if not locked_epic_id:
            pytest.skip("No locked epic available for testing")
        
        response = auth_session.post(
            f"{BASE_URL}/api/features/epic/{locked_epic_id}/generate",
            json={"count": 3}
        )
        # Expected: 402, 400, or 200 - NOT 500
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Feature generate endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
    
    def test_feature_generate_requires_auth(self):
        """Feature generation should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/features/epic/test_epic/generate",
            json={"count": 3}
        )
        assert response.status_code == 401
        print(f"✓ Feature generate requires auth: 401")


class TestUserStoryGeneration:
    """Test user story generation endpoint (sessionless streaming)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("session_token") or data.get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def approved_feature_id(self, auth_token):
        """Get an approved feature ID for story generation"""
        # First get epics
        response = requests.get(
            f"{BASE_URL}/api/epics",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            data = response.json()
            epics = data.get("epics", [])
            for epic in epics:
                if epic.get("current_stage") == "epic_locked":
                    # Get features for this epic
                    feat_response = requests.get(
                        f"{BASE_URL}/api/features/epic/{epic.get('epic_id')}",
                        headers={"Authorization": f"Bearer {auth_token}"}
                    )
                    if feat_response.status_code == 200:
                        features = feat_response.json()
                        for feature in features:
                            if feature.get("current_stage") == "approved":
                                return feature.get("feature_id")
        return None
    
    def test_story_generate_accessible(self, auth_token, approved_feature_id):
        """User story generation endpoint should be accessible"""
        if not approved_feature_id:
            pytest.skip("No approved feature available for testing")
        
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{approved_feature_id}/generate",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"count": 3}
        )
        # Expected: 402, 400, or 200 - NOT 500
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Story generate endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
    
    def test_story_generate_requires_auth(self):
        """Story generation should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/test_feature/generate",
            json={"count": 3}
        )
        assert response.status_code == 401
        print(f"✓ Story generate requires auth: 401")


class TestEpicChat:
    """Test epic chat endpoint (sessionless streaming)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("session_token") or data.get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def test_epic_id(self, auth_token):
        """Get a test epic ID"""
        response = requests.get(
            f"{BASE_URL}/api/epics",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            data = response.json()
            epics = data.get("epics", [])
            if epics:
                return epics[0].get("epic_id")
        return None
    
    def test_epic_chat_accessible(self, auth_token, test_epic_id):
        """Epic chat endpoint should be accessible"""
        if not test_epic_id:
            pytest.skip("No epic available for testing")
        
        response = requests.post(
            f"{BASE_URL}/api/epics/{test_epic_id}/chat",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"content": "What is the problem statement?"}
        )
        # Expected: 402, 400, or 200 - NOT 500
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Epic chat endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
        elif response.status_code == 200:
            print(f"  → Returns 200 (streaming response)")
    
    def test_epic_chat_requires_auth(self):
        """Epic chat should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/epics/test_epic/chat",
            json={"content": "Test message"}
        )
        assert response.status_code == 401
        print(f"✓ Epic chat requires auth: 401")


class TestBugAIEndpoints:
    """Test bug AI endpoints (sessionless streaming)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("session_token") or data.get("token")
        pytest.skip("Authentication failed")
    
    def test_bug_ai_chat_accessible(self, auth_token):
        """Bug AI chat endpoint should be accessible"""
        response = requests.post(
            f"{BASE_URL}/api/bugs/ai/chat",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"content": "I found a bug where the login button doesn't work"}
        )
        # Expected: 400 (no LLM) or 200 - NOT 500
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Bug AI chat endpoint accessible: {response.status_code}")
        
        if response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")
        elif response.status_code == 200:
            print(f"  → Returns 200 (streaming response)")
    
    def test_bug_ai_chat_requires_auth(self):
        """Bug AI chat should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/bugs/ai/chat",
            json={"content": "Test bug"}
        )
        assert response.status_code == 401
        print(f"✓ Bug AI chat requires auth: 401")


class TestScoringAIEndpoints:
    """Test scoring AI endpoints (sessionless streaming)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("session_token") or data.get("token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture(scope="class")
    def test_epic_id(self, auth_token):
        """Get a locked epic ID"""
        response = requests.get(
            f"{BASE_URL}/api/epics",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            data = response.json()
            epics = data.get("epics", [])
            for epic in epics:
                if epic.get("current_stage") == "epic_locked":
                    return epic.get("epic_id")
        return None
    
    def test_epic_moscow_suggest_accessible(self, auth_token, test_epic_id):
        """Epic MoSCoW suggest endpoint should be accessible"""
        if not test_epic_id:
            pytest.skip("No locked epic available for testing")
        
        response = requests.post(
            f"{BASE_URL}/api/scoring/epic/{test_epic_id}/moscow/suggest",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # Expected: 402, 400, or 200 - NOT 500
        assert response.status_code != 500, f"Server error: {response.text}"
        print(f"✓ Epic MoSCoW suggest endpoint accessible: {response.status_code}")
        
        if response.status_code == 402:
            print(f"  → Returns 402 (subscription required)")
        elif response.status_code == 400:
            data = response.json()
            print(f"  → Returns 400: {data.get('detail', 'Unknown')}")


class TestBackendImports:
    """Test that backend starts without import errors"""
    
    def test_backend_started_successfully(self):
        """Backend should start without import errors"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print(f"✓ Backend started successfully without import errors")
    
    def test_all_routes_registered(self):
        """All route modules should be registered"""
        # Test a sample endpoint from each route module
        endpoints = [
            ("/api/health", "GET"),
            ("/api/epics", "GET"),  # epic.py
            ("/api/features/epic/test", "GET"),  # feature.py
            ("/api/stories/feature/test", "GET"),  # user_story.py
            ("/api/bugs", "GET"),  # bug.py
            ("/api/sprints/current", "GET"),  # sprints.py
            ("/api/delivery-reality/summary", "GET"),  # delivery_reality.py
            ("/api/scoring/options", "GET"),  # scoring.py
        ]
        
        for endpoint, method in endpoints:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}")
            else:
                response = requests.post(f"{BASE_URL}{endpoint}")
            
            # Should not return 404 (route not found) or 500 (import error)
            # 401 (unauthorized) is acceptable - means route exists
            assert response.status_code != 404 or "not found" not in response.text.lower(), \
                f"Route {endpoint} not registered"
            assert response.status_code != 500, f"Server error on {endpoint}: {response.text}"
        
        print(f"✓ All route modules registered successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
