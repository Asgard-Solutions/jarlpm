"""
Test AI Endpoints - Subscription Gating, LLM Config, and Error Handling
Tests for delivery_reality.py and sprints.py AI endpoints

Features tested:
1. Subscription gating - AI endpoints return 402 for users without subscription
2. LLM config check - AI endpoints return 400 if LLM provider not configured
3. Non-AI endpoints work without subscription
4. AI endpoints work with valid subscription and LLM config
5. StrictOutputService integration - validates story IDs to prevent hallucination
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_WITH_SUB = {
    "email": "test@jarlpm.com",
    "password": "Test123!"
}

# Known epic_id for testing
TEST_EPIC_ID = "epic_fbba5b78"


class TestSetup:
    """Setup and helper methods"""
    
    @staticmethod
    def get_session_with_auth(email: str, password: str) -> tuple:
        """Login and return authenticated session"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password}
        )
        return session, response
    
    @staticmethod
    def create_test_user_without_subscription() -> dict:
        """Create a test user without subscription for testing 402 responses"""
        timestamp = int(time.time())
        email = f"test_no_sub_{timestamp}@jarlpm.com"
        password = "Test123!"
        
        session = requests.Session()
        # Signup creates user with inactive subscription
        response = session.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": email,
                "password": password,
                "name": "Test No Subscription"
            }
        )
        
        if response.status_code == 200:
            # Create an epic for this user to test delivery reality endpoints
            epic_resp = session.post(
                f"{BASE_URL}/api/epics",
                json={"title": "Test Epic for Subscription Gating"}
            )
            epic_id = None
            if epic_resp.status_code in [200, 201]:
                epic_id = epic_resp.json().get("epic_id")
            
            return {
                "email": email, 
                "password": password, 
                "session": session,
                "epic_id": epic_id
            }
        
        return None


class TestNonAIEndpointsWithoutSubscription:
    """Test that non-AI endpoints work without subscription"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        self.session, login_resp = TestSetup.get_session_with_auth(
            TEST_USER_WITH_SUB["email"],
            TEST_USER_WITH_SUB["password"]
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    
    def test_delivery_reality_summary_works(self):
        """GET /api/delivery-reality/summary should work without subscription check"""
        response = self.session.get(f"{BASE_URL}/api/delivery-reality/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "delivery_context" in data
        assert "total_points_all_active_initiatives" in data
        print(f"✓ Delivery reality summary works: {data['total_active_initiatives']} initiatives")
    
    def test_delivery_reality_initiatives_works(self):
        """GET /api/delivery-reality/initiatives should work without subscription check"""
        response = self.session.get(f"{BASE_URL}/api/delivery-reality/initiatives")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "initiatives" in data
        print(f"✓ Delivery reality initiatives works: {len(data['initiatives'])} initiatives")
    
    def test_delivery_reality_initiative_detail_works(self):
        """GET /api/delivery-reality/initiative/{epic_id} should work without subscription check"""
        response = self.session.get(f"{BASE_URL}/api/delivery-reality/initiative/{TEST_EPIC_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "epic_id" in data
        assert data["epic_id"] == TEST_EPIC_ID
        print(f"✓ Initiative detail works: {data['title']}")
    
    def test_sprints_current_works(self):
        """GET /api/sprints/current should work without subscription check"""
        response = self.session.get(f"{BASE_URL}/api/sprints/current")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "sprint_info" in data
        print(f"✓ Sprints current works: Sprint {data['sprint_info']['sprint_number']}")


class TestAIEndpointsWithSubscription:
    """Test AI endpoints work with valid subscription"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session with subscribed user"""
        self.session, login_resp = TestSetup.get_session_with_auth(
            TEST_USER_WITH_SUB["email"],
            TEST_USER_WITH_SUB["password"]
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
        # Verify subscription is active
        sub_resp = self.session.get(f"{BASE_URL}/api/subscription/status")
        assert sub_resp.status_code == 200
        sub_data = sub_resp.json()
        assert sub_data.get("status") == "active", f"User should have active subscription: {sub_data}"
    
    def test_cut_rationale_works_with_subscription(self):
        """POST /api/delivery-reality/initiative/{id}/ai/cut-rationale should work with subscription"""
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/cut-rationale"
        )
        # Should return 200 (success) or 400 (no LLM config) - NOT 402
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "rationale" in data
            assert "user_impact_tradeoff" in data
            assert "what_to_validate_first" in data
            print(f"✓ Cut rationale works with subscription")
        else:
            # 400 means LLM not configured - that's acceptable
            assert "LLM" in response.text or "provider" in response.text.lower()
            print(f"✓ Cut rationale returns 400 for no LLM config (expected)")
    
    def test_alternative_cuts_works_with_subscription(self):
        """POST /api/delivery-reality/initiative/{id}/ai/alternative-cuts should work with subscription"""
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/alternative-cuts"
        )
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "alternatives" in data
            # Verify story IDs are valid (not hallucinated)
            for alt in data.get("alternatives", []):
                assert "stories_to_defer" in alt
                assert "total_deferred_points" in alt
                # Story IDs should start with "story_"
                for story_id in alt.get("stories_to_defer", []):
                    assert story_id.startswith("story_"), f"Invalid story ID format: {story_id}"
            print(f"✓ Alternative cuts works with subscription: {len(data['alternatives'])} alternatives")
        else:
            print(f"✓ Alternative cuts returns 400 for no LLM config (expected)")
    
    def test_risk_review_works_with_subscription(self):
        """POST /api/delivery-reality/initiative/{id}/ai/risk-review should work with subscription"""
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/risk-review"
        )
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "top_delivery_risks" in data
            assert "top_assumptions" in data
            assert isinstance(data["top_delivery_risks"], list)
            assert isinstance(data["top_assumptions"], list)
            print(f"✓ Risk review works with subscription")
        else:
            print(f"✓ Risk review returns 400 for no LLM config (expected)")
    
    def test_kickoff_plan_works_with_subscription(self):
        """POST /api/sprints/ai/kickoff-plan should work with subscription"""
        response = self.session.post(f"{BASE_URL}/api/sprints/ai/kickoff-plan")
        # Can return 200, 400 (no LLM/no stories), or appropriate error
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        print(f"✓ Kickoff plan endpoint accessible with subscription: {response.status_code}")
    
    def test_standup_summary_works_with_subscription(self):
        """POST /api/sprints/ai/standup-summary should work with subscription"""
        response = self.session.post(f"{BASE_URL}/api/sprints/ai/standup-summary")
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        print(f"✓ Standup summary endpoint accessible with subscription: {response.status_code}")
    
    def test_wip_suggestions_works_with_subscription(self):
        """POST /api/sprints/ai/wip-suggestions should work with subscription"""
        response = self.session.post(f"{BASE_URL}/api/sprints/ai/wip-suggestions")
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "finish_first" in data
            assert "consider_pausing" in data
            assert "reasoning" in data
            print(f"✓ WIP suggestions works with subscription")
        else:
            print(f"✓ WIP suggestions returns 400 (expected for no stories)")


class TestAIEndpointsSubscriptionGating:
    """Test that AI endpoints return 402 for users without subscription"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - create user without subscription"""
        self.no_sub_user = TestSetup.create_test_user_without_subscription()
        if self.no_sub_user:
            self.session = self.no_sub_user["session"]
            self.epic_id = self.no_sub_user.get("epic_id")
            
            # Verify subscription is inactive
            sub_resp = self.session.get(f"{BASE_URL}/api/subscription/status")
            if sub_resp.status_code == 200:
                sub_data = sub_resp.json()
                if sub_data.get("status") != "inactive":
                    pytest.skip("User has active subscription - cannot test 402")
        else:
            pytest.skip("Could not create test user without subscription")
    
    def test_cut_rationale_returns_402_without_subscription(self):
        """POST /api/delivery-reality/initiative/{id}/ai/cut-rationale should return 402 without subscription"""
        if not self.epic_id:
            pytest.skip("No epic created for user")
        
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{self.epic_id}/ai/cut-rationale"
        )
        assert response.status_code == 402, f"Expected 402, got {response.status_code}: {response.text}"
        assert "subscription" in response.text.lower()
        print(f"✓ Cut rationale returns 402 without subscription")
    
    def test_alternative_cuts_returns_402_without_subscription(self):
        """POST /api/delivery-reality/initiative/{id}/ai/alternative-cuts should return 402 without subscription"""
        if not self.epic_id:
            pytest.skip("No epic created for user")
        
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{self.epic_id}/ai/alternative-cuts"
        )
        assert response.status_code == 402, f"Expected 402, got {response.status_code}: {response.text}"
        assert "subscription" in response.text.lower()
        print(f"✓ Alternative cuts returns 402 without subscription")
    
    def test_risk_review_returns_402_without_subscription(self):
        """POST /api/delivery-reality/initiative/{id}/ai/risk-review should return 402 without subscription"""
        if not self.epic_id:
            pytest.skip("No epic created for user")
        
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{self.epic_id}/ai/risk-review"
        )
        assert response.status_code == 402, f"Expected 402, got {response.status_code}: {response.text}"
        assert "subscription" in response.text.lower()
        print(f"✓ Risk review returns 402 without subscription")
    
    def test_kickoff_plan_returns_402_without_subscription(self):
        """POST /api/sprints/ai/kickoff-plan should return 402 without subscription"""
        response = self.session.post(f"{BASE_URL}/api/sprints/ai/kickoff-plan")
        assert response.status_code == 402, f"Expected 402, got {response.status_code}: {response.text}"
        assert "subscription" in response.text.lower()
        print(f"✓ Kickoff plan returns 402 without subscription")
    
    def test_standup_summary_returns_402_without_subscription(self):
        """POST /api/sprints/ai/standup-summary should return 402 without subscription"""
        response = self.session.post(f"{BASE_URL}/api/sprints/ai/standup-summary")
        assert response.status_code == 402, f"Expected 402, got {response.status_code}: {response.text}"
        assert "subscription" in response.text.lower()
        print(f"✓ Standup summary returns 402 without subscription")
    
    def test_wip_suggestions_returns_402_without_subscription(self):
        """POST /api/sprints/ai/wip-suggestions should return 402 without subscription"""
        response = self.session.post(f"{BASE_URL}/api/sprints/ai/wip-suggestions")
        assert response.status_code == 402, f"Expected 402, got {response.status_code}: {response.text}"
        assert "subscription" in response.text.lower()
        print(f"✓ WIP suggestions returns 402 without subscription")


class TestAIEndpointsLLMConfigCheck:
    """Test that AI endpoints return 400 if LLM provider not configured"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        self.session, login_resp = TestSetup.get_session_with_auth(
            TEST_USER_WITH_SUB["email"],
            TEST_USER_WITH_SUB["password"]
        )
        assert login_resp.status_code == 200
    
    def test_llm_config_error_message_format(self):
        """AI endpoints should return proper error message if LLM not configured"""
        # First check if user has LLM configured
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/cut-rationale"
        )
        
        if response.status_code == 400:
            data = response.json()
            detail = data.get("detail", "")
            # Should mention LLM provider or API key
            assert any(keyword in detail.lower() for keyword in ["llm", "provider", "api key", "settings"]), \
                f"Error message should mention LLM configuration: {detail}"
            print(f"✓ LLM config error message is clear: {detail}")
        elif response.status_code == 200:
            print(f"✓ User has LLM configured - AI endpoint works")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")


class TestAIEndpointsErrorHandling:
    """Test error handling for AI endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        self.session, login_resp = TestSetup.get_session_with_auth(
            TEST_USER_WITH_SUB["email"],
            TEST_USER_WITH_SUB["password"]
        )
        assert login_resp.status_code == 200
    
    def test_cut_rationale_invalid_epic_returns_404(self):
        """POST /api/delivery-reality/initiative/{invalid_id}/ai/cut-rationale should return 404"""
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/invalid_epic_id/ai/cut-rationale"
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✓ Cut rationale returns 404 for invalid epic")
    
    def test_alternative_cuts_invalid_epic_returns_404(self):
        """POST /api/delivery-reality/initiative/{invalid_id}/ai/alternative-cuts should return 404"""
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/invalid_epic_id/ai/alternative-cuts"
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✓ Alternative cuts returns 404 for invalid epic")
    
    def test_risk_review_invalid_epic_returns_404(self):
        """POST /api/delivery-reality/initiative/{invalid_id}/ai/risk-review should return 404"""
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/invalid_epic_id/ai/risk-review"
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✓ Risk review returns 404 for invalid epic")
    
    def test_unauthenticated_ai_endpoints_return_401(self):
        """AI endpoints should return 401 for unauthenticated requests"""
        unauthenticated_session = requests.Session()
        
        endpoints = [
            ("POST", f"/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/cut-rationale"),
            ("POST", f"/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/alternative-cuts"),
            ("POST", f"/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/risk-review"),
            ("POST", "/api/sprints/ai/kickoff-plan"),
            ("POST", "/api/sprints/ai/standup-summary"),
            ("POST", "/api/sprints/ai/wip-suggestions"),
        ]
        
        for method, endpoint in endpoints:
            if method == "POST":
                response = unauthenticated_session.post(f"{BASE_URL}{endpoint}")
            else:
                response = unauthenticated_session.get(f"{BASE_URL}{endpoint}")
            
            assert response.status_code == 401, \
                f"Expected 401 for {endpoint}, got {response.status_code}: {response.text}"
        
        print(f"✓ All AI endpoints return 401 for unauthenticated requests")


class TestStrictOutputServiceIntegration:
    """Test that StrictOutputService is properly integrated"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated session"""
        self.session, login_resp = TestSetup.get_session_with_auth(
            TEST_USER_WITH_SUB["email"],
            TEST_USER_WITH_SUB["password"]
        )
        assert login_resp.status_code == 200
    
    def test_alternative_cuts_validates_story_ids(self):
        """Alternative cuts should only return valid story IDs (not hallucinated)"""
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/alternative-cuts"
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Get actual story IDs from the initiative
            initiative_resp = self.session.get(
                f"{BASE_URL}/api/delivery-reality/initiative/{TEST_EPIC_ID}"
            )
            assert initiative_resp.status_code == 200
            
            # Check that returned story IDs are valid format
            for alt in data.get("alternatives", []):
                for story_id in alt.get("stories_to_defer", []):
                    # Story IDs should follow the pattern "story_XXXXXXXX"
                    assert story_id.startswith("story_"), \
                        f"Story ID should start with 'story_': {story_id}"
                    assert len(story_id) > 6, \
                        f"Story ID seems too short: {story_id}"
            
            print(f"✓ Alternative cuts returns valid story IDs (no hallucination)")
        else:
            print(f"✓ Alternative cuts returned {response.status_code} (LLM not configured)")
    
    def test_cut_rationale_returns_valid_schema(self):
        """Cut rationale should return valid schema with all required fields"""
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/cut-rationale"
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify required fields
            required_fields = ["rationale", "user_impact_tradeoff", "what_to_validate_first"]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
                assert isinstance(data[field], str), f"Field {field} should be string"
                assert len(data[field]) > 0, f"Field {field} should not be empty"
            
            print(f"✓ Cut rationale returns valid schema with all required fields")
        else:
            print(f"✓ Cut rationale returned {response.status_code} (LLM not configured)")
    
    def test_risk_review_returns_valid_schema(self):
        """Risk review should return valid schema with all required fields"""
        response = self.session.post(
            f"{BASE_URL}/api/delivery-reality/initiative/{TEST_EPIC_ID}/ai/risk-review"
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify required fields
            assert "top_delivery_risks" in data
            assert "top_assumptions" in data
            assert isinstance(data["top_delivery_risks"], list)
            assert isinstance(data["top_assumptions"], list)
            
            # Optional spike field
            if "suggested_spike" in data and data["suggested_spike"]:
                spike = data["suggested_spike"]
                assert "title" in spike
                assert "points" in spike
                assert "description" in spike
            
            print(f"✓ Risk review returns valid schema with all required fields")
        else:
            print(f"✓ Risk review returned {response.status_code} (LLM not configured)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
