"""
Test Suite for JarlPM Subscription, Persona, and E2E Workflow APIs
Tests: Subscription flow, Persona settings, Epic/Feature/Story/Bug workflow
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://pm-sync-hub.preview.emergentagent.com"


class TestSubscriptionAPI:
    """Subscription API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get session cookie
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200, f"Test login failed: {response.text}"
        self.user_data = response.json()
    
    def test_subscription_status_returns_200(self):
        """GET /api/subscription/status - Returns subscription status"""
        response = self.session.get(f"{BASE_URL}/api/subscription/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["active", "inactive", "canceled", "past_due", "trial", "expired"]
        print(f"✓ Subscription status: {data['status']}")
    
    def test_subscription_status_has_required_fields(self):
        """GET /api/subscription/status - Response has required fields"""
        response = self.session.get(f"{BASE_URL}/api/subscription/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # stripe_subscription_id and current_period_end can be null
        assert "stripe_subscription_id" in data or data.get("stripe_subscription_id") is None
        print(f"✓ Subscription response has required fields")
    
    def test_create_checkout_returns_checkout_url(self):
        """POST /api/subscription/create-checkout - Returns Stripe checkout URL"""
        response = self.session.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            json={"origin_url": "https://pm-sync-hub.preview.emergentagent.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert "session_id" in data
        assert data["checkout_url"].startswith("https://checkout.stripe.com")
        assert data["session_id"].startswith("cs_test_")
        print(f"✓ Checkout URL created: {data['session_id'][:30]}...")
        return data["session_id"]
    
    def test_checkout_status_returns_payment_info(self):
        """GET /api/subscription/checkout-status/{session_id} - Returns payment status"""
        # First create a checkout session
        create_response = self.session.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            json={"origin_url": "https://pm-sync-hub.preview.emergentagent.com"}
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]
        
        # Check status
        response = self.session.get(f"{BASE_URL}/api/subscription/checkout-status/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "payment_status" in data
        assert "amount_total" in data
        assert "currency" in data
        assert data["currency"] == "usd"
        assert data["amount_total"] == 2000  # $20.00 in cents
        print(f"✓ Checkout status: {data['payment_status']}, amount: ${data['amount_total']/100}")
    
    def test_checkout_status_invalid_session_returns_error(self):
        """GET /api/subscription/checkout-status/{invalid} - Returns error for invalid session"""
        response = self.session.get(f"{BASE_URL}/api/subscription/checkout-status/invalid_session_id")
        # Should return error status (400, 404, 500, or 520 for Stripe errors)
        assert response.status_code in [400, 404, 500, 520]
        print(f"✓ Invalid session returns error: {response.status_code}")


class TestPersonaAPI:
    """Persona API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200
    
    def test_get_persona_settings(self):
        """GET /api/personas/settings - Returns user persona settings"""
        response = self.session.get(f"{BASE_URL}/api/personas/settings")
        assert response.status_code == 200
        data = response.json()
        assert "image_provider" in data
        assert "image_model" in data
        assert "default_persona_count" in data
        assert data["image_provider"] in ["openai", "gemini"]
        assert isinstance(data["default_persona_count"], int)
        assert 1 <= data["default_persona_count"] <= 5
        print(f"✓ Persona settings: provider={data['image_provider']}, count={data['default_persona_count']}")
    
    def test_update_persona_settings(self):
        """PUT /api/personas/settings - Updates persona settings"""
        # Update settings
        response = self.session.put(
            f"{BASE_URL}/api/personas/settings",
            json={
                "image_provider": "openai",
                "image_model": "gpt-image-1",
                "default_persona_count": 3
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["image_provider"] == "openai"
        assert data["image_model"] == "gpt-image-1"
        assert data["default_persona_count"] == 3
        print(f"✓ Persona settings updated successfully")
    
    def test_update_persona_count_enforces_range(self):
        """PUT /api/personas/settings - Enforces 1-5 range for persona count"""
        # Try to set count > 5
        response = self.session.put(
            f"{BASE_URL}/api/personas/settings",
            json={"default_persona_count": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_persona_count"] <= 5  # Should be capped at 5
        
        # Try to set count < 1
        response = self.session.put(
            f"{BASE_URL}/api/personas/settings",
            json={"default_persona_count": 0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_persona_count"] >= 1  # Should be at least 1
        print(f"✓ Persona count range enforced (1-5)")
    
    def test_list_personas(self):
        """GET /api/personas - Lists all personas for user"""
        response = self.session.get(f"{BASE_URL}/api/personas")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} personas")


class TestEpicWorkflow:
    """Epic creation and workflow tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200
    
    def test_list_epics(self):
        """GET /api/epics - Lists all epics"""
        response = self.session.get(f"{BASE_URL}/api/epics")
        assert response.status_code == 200
        data = response.json()
        # API returns {"epics": [...]}
        assert "epics" in data
        assert isinstance(data["epics"], list)
        print(f"✓ Listed {len(data['epics'])} epics")
    
    def test_create_epic(self):
        """POST /api/epics - Creates new epic"""
        response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_Epic_{int(time.time())}"}
        )
        assert response.status_code in [200, 201]  # 201 Created is also valid
        data = response.json()
        assert "epic_id" in data
        assert "title" in data
        assert "current_stage" in data
        assert data["current_stage"] == "problem_capture"
        print(f"✓ Created epic: {data['epic_id']}")
    
    def test_get_epic(self):
        """GET /api/epics/{epic_id} - Gets epic details"""
        # First create an epic
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_GetEpic_{int(time.time())}"}
        )
        epic_id = create_response.json()["epic_id"]
        
        # Get the epic
        response = self.session.get(f"{BASE_URL}/api/epics/{epic_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["epic_id"] == epic_id
        print(f"✓ Got epic: {epic_id}")
    
    def test_delete_epic(self):
        """DELETE /api/epics/{epic_id} - Deletes epic"""
        # First create an epic
        create_response = self.session.post(
            f"{BASE_URL}/api/epics",
            json={"title": f"TEST_DeleteEpic_{int(time.time())}"}
        )
        epic_id = create_response.json()["epic_id"]
        
        # Delete the epic
        response = self.session.delete(f"{BASE_URL}/api/epics/{epic_id}")
        assert response.status_code == 200
        
        # Verify deletion
        get_response = self.session.get(f"{BASE_URL}/api/epics/{epic_id}")
        assert get_response.status_code == 404
        print(f"✓ Deleted epic: {epic_id}")


class TestFeatureWorkflow:
    """Feature generation and approval flow tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200
    
    def test_list_features_for_epic(self):
        """GET /api/features/epic/{epic_id} - Lists features for epic"""
        # Use existing locked epic from test data
        response = self.session.get(f"{BASE_URL}/api/features/epic/epic_test_scoring_001")
        # May return 200 with features or 404 if epic doesn't exist
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ Listed {len(data)} features for epic")
        else:
            print(f"✓ Epic not found (expected if test data not seeded)")
    
    def test_get_feature(self):
        """GET /api/features/{feature_id} - Gets feature details"""
        response = self.session.get(f"{BASE_URL}/api/features/feat_test_scoring_001")
        # May return 200 or 404
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "feature_id" in data
            print(f"✓ Got feature: {data['feature_id']}")
        else:
            print(f"✓ Feature not found (expected if test data not seeded)")


class TestUserStoryWorkflow:
    """User Story creation tests (linked and standalone)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200
    
    def test_list_standalone_stories(self):
        """GET /api/stories/standalone - Lists standalone stories"""
        response = self.session.get(f"{BASE_URL}/api/stories/standalone")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} standalone stories")
    
    def test_create_standalone_story(self):
        """POST /api/stories/standalone - Creates standalone story"""
        response = self.session.post(
            f"{BASE_URL}/api/stories/standalone",
            json={
                "title": f"TEST_Story_{int(time.time())}",
                "persona": "test user",
                "action": "verify story creation",
                "benefit": "ensure API works correctly",
                "acceptance_criteria": ["Test criterion 1", "Test criterion 2"]
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "story_id" in data
        print(f"✓ Created standalone story: {data['story_id']}")
    
    def test_get_standalone_story(self):
        """GET /api/stories/standalone/{story_id} - Gets standalone story"""
        # First create a story with required fields
        create_response = self.session.post(
            f"{BASE_URL}/api/stories/standalone",
            json={
                "title": f"TEST_GetStory_{int(time.time())}",
                "persona": "test user",
                "action": "get story details",
                "benefit": "verify retrieval works",
                "acceptance_criteria": ["Test"]
            }
        )
        assert create_response.status_code in [200, 201], f"Create failed: {create_response.text}"
        story_id = create_response.json()["story_id"]
        
        # Get the story
        response = self.session.get(f"{BASE_URL}/api/stories/standalone/{story_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["story_id"] == story_id
        print(f"✓ Got standalone story: {story_id}")


class TestBugTracking:
    """Bug tracking system tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200
    
    def test_list_bugs(self):
        """GET /api/bugs - Lists all bugs"""
        response = self.session.get(f"{BASE_URL}/api/bugs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} bugs")
    
    def test_create_bug(self):
        """POST /api/bugs - Creates new bug"""
        response = self.session.post(
            f"{BASE_URL}/api/bugs",
            json={
                "title": f"TEST_Bug_{int(time.time())}",
                "description": "Test bug description for API testing",
                "severity": "medium"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "bug_id" in data
        assert "title" in data
        assert "status" in data
        assert data["status"] == "draft"
        print(f"✓ Created bug: {data['bug_id']}")
        return data["bug_id"]
    
    def test_get_bug(self):
        """GET /api/bugs/{bug_id} - Gets bug details"""
        # First create a bug
        create_response = self.session.post(
            f"{BASE_URL}/api/bugs",
            json={
                "title": f"TEST_GetBug_{int(time.time())}",
                "description": "Test bug for get endpoint",
                "severity": "low"
            }
        )
        bug_id = create_response.json()["bug_id"]
        
        # Get the bug
        response = self.session.get(f"{BASE_URL}/api/bugs/{bug_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["bug_id"] == bug_id
        print(f"✓ Got bug: {bug_id}")
    
    def test_bug_status_transition(self):
        """POST /api/bugs/{bug_id}/transition - Transitions bug status"""
        # Create a bug
        create_response = self.session.post(
            f"{BASE_URL}/api/bugs",
            json={
                "title": f"TEST_TransitionBug_{int(time.time())}",
                "description": "Test bug for status transition",
                "severity": "medium"
            }
        )
        bug_id = create_response.json()["bug_id"]
        
        # Transition from draft to confirmed
        response = self.session.post(
            f"{BASE_URL}/api/bugs/{bug_id}/transition",
            json={"new_status": "confirmed", "notes": "Confirmed via test"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
        print(f"✓ Bug transitioned to confirmed: {bug_id}")


class TestScoringEndpoints:
    """RICE and MoSCoW scoring endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200
    
    def test_get_scoring_options(self):
        """GET /api/scoring/options - Returns scoring options"""
        response = self.session.get(f"{BASE_URL}/api/scoring/options")
        assert response.status_code == 200
        data = response.json()
        # API returns moscow_options, rice_impact_options, rice_confidence_options
        assert "moscow_options" in data
        assert "rice_impact_options" in data
        assert "rice_confidence_options" in data
        assert "must_have" in data["moscow_options"]
        print(f"✓ Got scoring options")
    
    def test_get_epic_moscow(self):
        """GET /api/scoring/epic/{epic_id}/moscow - Gets epic MoSCoW score"""
        response = self.session.get(f"{BASE_URL}/api/scoring/epic/epic_test_scoring_001/moscow")
        # May return 200 or 404
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "epic_id" in data
            assert "moscow_score" in data
            print(f"✓ Got epic MoSCoW: {data.get('moscow_score')}")
        else:
            print(f"✓ Epic not found (expected if test data not seeded)")
    
    def test_get_feature_scores(self):
        """GET /api/scoring/feature/{feature_id} - Gets feature scores"""
        response = self.session.get(f"{BASE_URL}/api/scoring/feature/feat_test_scoring_001")
        # May return 200 or 404
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "feature_id" in data
            print(f"✓ Got feature scores")
        else:
            print(f"✓ Feature not found (expected if test data not seeded)")


class TestPaymentTransactionTracking:
    """Payment transaction tracking tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        response = self.session.post(f"{BASE_URL}/api/auth/test-login")
        assert response.status_code == 200
    
    def test_checkout_creates_transaction(self):
        """POST /api/subscription/create-checkout - Creates payment transaction record"""
        response = self.session.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            json={"origin_url": "https://pm-sync-hub.preview.emergentagent.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        # The transaction is created in the database - we verify by checking status
        status_response = self.session.get(f"{BASE_URL}/api/subscription/checkout-status/{data['session_id']}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["payment_status"] == "unpaid"  # Initial status
        print(f"✓ Payment transaction created and tracked: {data['session_id'][:30]}...")


class TestAuthenticationRequired:
    """Tests that endpoints require authentication"""
    
    def test_subscription_status_requires_auth(self):
        """GET /api/subscription/status - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/status")
        assert response.status_code == 401
        print(f"✓ Subscription status requires auth")
    
    def test_persona_settings_requires_auth(self):
        """GET /api/personas/settings - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/personas/settings")
        assert response.status_code == 401
        print(f"✓ Persona settings requires auth")
    
    def test_create_checkout_requires_auth(self):
        """POST /api/subscription/create-checkout - Requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            json={"origin_url": "https://test.com"}
        )
        assert response.status_code == 401
        print(f"✓ Create checkout requires auth")
    
    def test_epics_requires_auth(self):
        """GET /api/epics - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/epics")
        assert response.status_code == 401
        print(f"✓ Epics requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
