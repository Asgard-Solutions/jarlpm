"""
Test Delivery Reality API endpoints for JarlPM
Tests: GET /api/delivery-reality/summary, /initiatives, /initiative/{epic_id}
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('VITE_BACKEND_URL', 'https://pm-assistant-3.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "test@jarlpm.com"
TEST_PASSWORD = "Test123!"


@pytest.fixture(scope="module")
def session():
    """Create authenticated session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Login
    login_response = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if login_response.status_code != 200:
        pytest.skip(f"Login failed: {login_response.status_code} - {login_response.text}")
    
    return s


@pytest.fixture(scope="module")
def test_epic_id(session):
    """Create a test epic for testing"""
    unique_id = str(uuid.uuid4())[:8]
    response = session.post(f"{BASE_URL}/api/epics", json={
        "title": f"TEST_DeliveryReality_{unique_id}"
    })
    
    if response.status_code == 201:
        epic_id = response.json().get("epic_id")
        yield epic_id
        # Cleanup - try to delete (may fail due to known constraint issue)
        try:
            session.delete(f"{BASE_URL}/api/initiatives/{epic_id}")
        except:
            pass
    else:
        pytest.skip(f"Failed to create test epic: {response.status_code}")


class TestDeliveryRealitySummary:
    """Tests for GET /api/delivery-reality/summary"""
    
    def test_summary_requires_auth(self):
        """Summary endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/delivery-reality/summary")
        assert response.status_code == 401
        assert "Not authenticated" in response.text
    
    def test_summary_returns_200(self, session):
        """Summary endpoint returns 200 with valid auth"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/summary")
        assert response.status_code == 200
    
    def test_summary_has_delivery_context(self, session):
        """Summary includes delivery_context object"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/summary")
        data = response.json()
        
        assert "delivery_context" in data
        ctx = data["delivery_context"]
        
        # Verify all required fields exist
        assert "num_developers" in ctx
        assert "sprint_cycle_length" in ctx
        assert "points_per_dev_per_sprint" in ctx
        assert "sprint_capacity" in ctx
        assert "two_sprint_capacity" in ctx
    
    def test_summary_has_status_breakdown(self, session):
        """Summary includes status_breakdown with on_track, at_risk, overloaded"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/summary")
        data = response.json()
        
        assert "status_breakdown" in data
        breakdown = data["status_breakdown"]
        
        assert "on_track" in breakdown
        assert "at_risk" in breakdown
        assert "overloaded" in breakdown
        
        # All values should be integers
        assert isinstance(breakdown["on_track"], int)
        assert isinstance(breakdown["at_risk"], int)
        assert isinstance(breakdown["overloaded"], int)
    
    def test_summary_has_totals(self, session):
        """Summary includes total_points and total_active_initiatives"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/summary")
        data = response.json()
        
        assert "total_points_all_active_initiatives" in data
        assert "total_active_initiatives" in data
        
        assert isinstance(data["total_points_all_active_initiatives"], int)
        assert isinstance(data["total_active_initiatives"], int)
    
    def test_summary_capacity_calculation(self, session):
        """Verify capacity calculation: sprint_capacity = num_developers * points_per_dev_per_sprint"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/summary")
        data = response.json()
        ctx = data["delivery_context"]
        
        expected_sprint_capacity = ctx["num_developers"] * ctx["points_per_dev_per_sprint"]
        expected_two_sprint = expected_sprint_capacity * 2
        
        assert ctx["sprint_capacity"] == expected_sprint_capacity
        assert ctx["two_sprint_capacity"] == expected_two_sprint


class TestDeliveryRealityInitiatives:
    """Tests for GET /api/delivery-reality/initiatives"""
    
    def test_initiatives_requires_auth(self):
        """Initiatives endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/delivery-reality/initiatives")
        assert response.status_code == 401
    
    def test_initiatives_returns_200(self, session):
        """Initiatives endpoint returns 200 with valid auth"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiatives")
        assert response.status_code == 200
    
    def test_initiatives_has_delivery_context(self, session):
        """Initiatives response includes delivery_context"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiatives")
        data = response.json()
        
        assert "delivery_context" in data
        assert "num_developers" in data["delivery_context"]
    
    def test_initiatives_has_list(self, session):
        """Initiatives response includes initiatives list"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiatives")
        data = response.json()
        
        assert "initiatives" in data
        assert isinstance(data["initiatives"], list)
    
    def test_initiative_item_structure(self, session, test_epic_id):
        """Each initiative has required fields"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiatives")
        data = response.json()
        
        # Find our test epic
        test_initiative = None
        for init in data["initiatives"]:
            if init["epic_id"] == test_epic_id:
                test_initiative = init
                break
        
        if test_initiative is None:
            pytest.skip("Test epic not found in initiatives list")
        
        # Verify structure
        assert "epic_id" in test_initiative
        assert "title" in test_initiative
        assert "total_points" in test_initiative
        assert "two_sprint_capacity" in test_initiative
        assert "delta" in test_initiative
        assert "assessment" in test_initiative
        assert "stories_count" in test_initiative
    
    def test_initiative_assessment_values(self, session):
        """Assessment values are valid enum values"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiatives")
        data = response.json()
        
        valid_assessments = {"on_track", "at_risk", "overloaded"}
        
        for init in data["initiatives"]:
            assert init["assessment"] in valid_assessments, f"Invalid assessment: {init['assessment']}"


class TestDeliveryRealityInitiativeDetail:
    """Tests for GET /api/delivery-reality/initiative/{epic_id}"""
    
    def test_initiative_detail_requires_auth(self, test_epic_id):
        """Initiative detail endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}")
        assert response.status_code == 401
    
    def test_initiative_detail_returns_200(self, session, test_epic_id):
        """Initiative detail returns 200 for valid epic"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}")
        assert response.status_code == 200
    
    def test_initiative_detail_404_for_nonexistent(self, session):
        """Initiative detail returns 404 for non-existent epic"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiative/nonexistent_epic_id")
        assert response.status_code == 404
        assert "not found" in response.text.lower()
    
    def test_initiative_detail_structure(self, session, test_epic_id):
        """Initiative detail has all required fields"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}")
        data = response.json()
        
        # Basic fields
        assert "epic_id" in data
        assert "title" in data
        assert "total_points" in data
        assert "two_sprint_capacity" in data
        assert "delta" in data
        assert "assessment" in data
        
        # Deferral fields
        assert "recommended_defer" in data
        assert "deferred_points" in data
        assert "new_total_points" in data
        assert "new_delta" in data
        
        # Points breakdown
        assert "total_stories" in data
        assert "must_have_points" in data
        assert "should_have_points" in data
        assert "nice_to_have_points" in data
    
    def test_initiative_detail_recommended_defer_is_list(self, session, test_epic_id):
        """recommended_defer is a list"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}")
        data = response.json()
        
        assert isinstance(data["recommended_defer"], list)
    
    def test_initiative_detail_points_breakdown_sum(self, session, test_epic_id):
        """Points breakdown should sum to total_points"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}")
        data = response.json()
        
        breakdown_sum = (
            data["must_have_points"] + 
            data["should_have_points"] + 
            data["nice_to_have_points"]
        )
        
        assert breakdown_sum == data["total_points"], \
            f"Points breakdown ({breakdown_sum}) doesn't match total ({data['total_points']})"
    
    def test_initiative_detail_delta_calculation(self, session, test_epic_id):
        """Delta should be two_sprint_capacity - total_points"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}")
        data = response.json()
        
        expected_delta = data["two_sprint_capacity"] - data["total_points"]
        assert data["delta"] == expected_delta, \
            f"Delta ({data['delta']}) doesn't match expected ({expected_delta})"


class TestDeliveryRealityAssessmentLogic:
    """Tests for assessment calculation logic"""
    
    def test_on_track_when_under_capacity(self, session, test_epic_id):
        """Initiative with 0 points and 0 capacity should be on_track (delta >= 0)"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiative/{test_epic_id}")
        data = response.json()
        
        # With no delivery context configured (0 capacity) and 0 points, delta = 0
        # delta >= 0 means on_track
        if data["delta"] >= 0:
            assert data["assessment"] == "on_track"
    
    def test_assessment_values_are_valid(self, session):
        """All assessments in list are valid enum values"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/initiatives")
        data = response.json()
        
        valid_values = {"on_track", "at_risk", "overloaded"}
        
        for init in data["initiatives"]:
            assert init["assessment"] in valid_values


class TestDeliveryRealityNoCapacityScenario:
    """Tests for scenario when no delivery context is configured"""
    
    def test_no_capacity_shows_zero(self, session):
        """When no delivery context, capacity values are 0"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/summary")
        data = response.json()
        ctx = data["delivery_context"]
        
        # If num_developers is 0, capacity should be 0
        if ctx["num_developers"] == 0:
            assert ctx["sprint_capacity"] == 0
            assert ctx["two_sprint_capacity"] == 0
    
    def test_no_capacity_all_on_track(self, session):
        """With 0 capacity and 0 points, all initiatives should be on_track"""
        response = session.get(f"{BASE_URL}/api/delivery-reality/summary")
        data = response.json()
        
        # If no capacity configured, all should be on_track (delta = 0 - 0 = 0 >= 0)
        if data["delivery_context"]["num_developers"] == 0:
            breakdown = data["status_breakdown"]
            total = breakdown["on_track"] + breakdown["at_risk"] + breakdown["overloaded"]
            
            # All should be on_track when capacity is 0 and points are 0
            assert breakdown["on_track"] == total or total == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
