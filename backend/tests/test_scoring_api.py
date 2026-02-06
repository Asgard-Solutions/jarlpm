"""
Test Scoring API endpoints for JarlPM
Tests RICE and MoSCoW scoring functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('VITE_BACKEND_URL', 'https://pmcanvas.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "test@jarlpm.com"
TEST_PASSWORD = "Test123!"

# Test epic ID
TEST_EPIC_ID = "epic_fbba5b78"


@pytest.fixture(scope="module")
def session():
    """Create authenticated session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Login
    response = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.status_code} - {response.text}")
    
    return s


class TestScoringOptions:
    """Test scoring options endpoint"""
    
    def test_get_scoring_options(self, session):
        """GET /api/scoring/options - Returns scoring options"""
        response = session.get(f"{BASE_URL}/api/scoring/options")
        assert response.status_code == 200
        
        data = response.json()
        assert "moscow_options" in data
        assert "rice_impact_options" in data
        assert "rice_confidence_options" in data
        
        # Verify MoSCoW options
        moscow = data["moscow_options"]
        assert "must_have" in moscow
        assert "should_have" in moscow
        assert "could_have" in moscow
        assert "wont_have" in moscow


class TestScoredItems:
    """Test scored items list endpoint"""
    
    def test_get_scored_items_requires_auth(self):
        """GET /api/scoring/scored-items - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scoring/scored-items")
        assert response.status_code == 401
    
    def test_get_scored_items(self, session):
        """GET /api/scoring/scored-items - Returns scored items"""
        response = session.get(f"{BASE_URL}/api/scoring/scored-items")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
    
    def test_scored_items_structure(self, session):
        """GET /api/scoring/scored-items - Items have correct structure"""
        response = session.get(f"{BASE_URL}/api/scoring/scored-items")
        assert response.status_code == 200
        
        data = response.json()
        if data["total"] > 0:
            item = data["items"][0]
            assert "item_id" in item
            assert "item_type" in item
            assert "title" in item
            assert item["item_type"] in ["epic", "standalone_story", "standalone_bug"]


class TestItemsForScoring:
    """Test items available for scoring endpoint"""
    
    def test_get_items_for_scoring_requires_auth(self):
        """GET /api/scoring/items-for-scoring - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scoring/items-for-scoring")
        assert response.status_code == 401
    
    def test_get_items_for_scoring(self, session):
        """GET /api/scoring/items-for-scoring - Returns available items"""
        response = session.get(f"{BASE_URL}/api/scoring/items-for-scoring")
        assert response.status_code == 200
        
        data = response.json()
        assert "epics" in data
        assert "standalone_stories" in data
        assert "standalone_bugs" in data
        assert isinstance(data["epics"], list)
    
    def test_items_for_scoring_epic_structure(self, session):
        """GET /api/scoring/items-for-scoring - Epics have correct structure"""
        response = session.get(f"{BASE_URL}/api/scoring/items-for-scoring")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["epics"]) > 0:
            epic = data["epics"][0]
            assert "epic_id" in epic
            assert "title" in epic
            assert "has_moscow" in epic


class TestEpicScores:
    """Test epic scores detail endpoint"""
    
    def test_get_epic_scores_requires_auth(self):
        """GET /api/scoring/epic/{epic_id}/scores - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/scores")
        assert response.status_code == 401
    
    def test_get_epic_scores(self, session):
        """GET /api/scoring/epic/{epic_id}/scores - Returns epic scores"""
        response = session.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/scores")
        assert response.status_code == 200
        
        data = response.json()
        assert "epic_id" in data
        assert "title" in data
        assert "features" in data
        assert "stories" in data
        assert "bugs" in data
    
    def test_get_epic_scores_features_structure(self, session):
        """GET /api/scoring/epic/{epic_id}/scores - Features have correct structure"""
        response = session.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/scores")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["features"]) > 0:
            feature = data["features"][0]
            assert "feature_id" in feature
            assert "title" in feature
            assert "moscow_score" in feature
            assert "rice_reach" in feature
            assert "rice_impact" in feature
            assert "rice_confidence" in feature
            assert "rice_effort" in feature
            assert "rice_total" in feature
    
    def test_get_epic_scores_stories_structure(self, session):
        """GET /api/scoring/epic/{epic_id}/scores - Stories have correct structure"""
        response = session.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/scores")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["stories"]) > 0:
            story = data["stories"][0]
            assert "story_id" in story
            assert "title" in story
            assert "rice_reach" in story
            assert "rice_total" in story
    
    def test_get_epic_scores_not_found(self, session):
        """GET /api/scoring/epic/{epic_id}/scores - Returns 404 for non-existent epic"""
        response = session.get(f"{BASE_URL}/api/scoring/epic/nonexistent_epic/scores")
        assert response.status_code == 404


class TestEpicMoSCoW:
    """Test epic MoSCoW scoring endpoints"""
    
    def test_get_epic_moscow(self, session):
        """GET /api/scoring/epic/{epic_id}/moscow - Returns epic MoSCoW score"""
        response = session.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow")
        assert response.status_code == 200
        
        data = response.json()
        assert "epic_id" in data
        assert "moscow_score" in data
    
    def test_update_epic_moscow(self, session):
        """PUT /api/scoring/epic/{epic_id}/moscow - Updates epic MoSCoW score"""
        response = session.put(
            f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow",
            json={"score": "must_have"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["moscow_score"] == "must_have"
    
    def test_update_epic_moscow_invalid_score(self, session):
        """PUT /api/scoring/epic/{epic_id}/moscow - Rejects invalid score"""
        response = session.put(
            f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow",
            json={"score": "invalid_score"}
        )
        assert response.status_code == 400


class TestFeatureScoring:
    """Test feature scoring endpoints"""
    
    @pytest.fixture
    def feature_id(self, session):
        """Get a feature ID from the test epic"""
        response = session.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/scores")
        if response.status_code == 200:
            data = response.json()
            if len(data["features"]) > 0:
                return data["features"][0]["feature_id"]
        pytest.skip("No features available for testing")
    
    def test_get_feature_scores(self, session, feature_id):
        """GET /api/scoring/feature/{feature_id} - Returns feature scores"""
        response = session.get(f"{BASE_URL}/api/scoring/feature/{feature_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "feature_id" in data
        assert "moscow_score" in data
        assert "rice_reach" in data
        assert "rice_total" in data
    
    def test_update_feature_moscow(self, session, feature_id):
        """PUT /api/scoring/feature/{feature_id}/moscow - Updates feature MoSCoW"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{feature_id}/moscow",
            json={"score": "should_have"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["moscow_score"] == "should_have"
    
    def test_update_feature_rice(self, session, feature_id):
        """PUT /api/scoring/feature/{feature_id}/rice - Updates feature RICE"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{feature_id}/rice",
            json={
                "reach": 5,
                "impact": 2.0,
                "confidence": 0.8,
                "effort": 2.0
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["rice_reach"] == 5
        assert data["rice_impact"] == 2.0
        assert data["rice_confidence"] == 0.8
        assert data["rice_effort"] == 2.0
        # RICE = (5 * 2.0 * 0.8) / 2.0 = 4.0
        assert data["rice_total"] == 4.0


class TestStoryScoring:
    """Test story RICE scoring endpoints"""
    
    @pytest.fixture
    def story_id(self, session):
        """Get a story ID from the test epic"""
        response = session.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/scores")
        if response.status_code == 200:
            data = response.json()
            if len(data["stories"]) > 0:
                return data["stories"][0]["story_id"]
        pytest.skip("No stories available for testing")
    
    def test_get_story_rice(self, session, story_id):
        """GET /api/scoring/story/{story_id} - Returns story RICE score"""
        response = session.get(f"{BASE_URL}/api/scoring/story/{story_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "story_id" in data
        assert "rice_reach" in data
        assert "rice_total" in data
    
    def test_update_story_rice(self, session, story_id):
        """PUT /api/scoring/story/{story_id}/rice - Updates story RICE"""
        response = session.put(
            f"{BASE_URL}/api/scoring/story/{story_id}/rice",
            json={
                "reach": 3,
                "impact": 1.0,
                "confidence": 0.8,
                "effort": 1.0
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["rice_reach"] == 3
        # RICE = (3 * 1.0 * 0.8) / 1.0 = 2.4
        assert data["rice_total"] == 2.4


class TestBulkScoring:
    """Test bulk scoring endpoints"""
    
    def test_bulk_score_all_requires_auth(self):
        """POST /api/scoring/epic/{epic_id}/bulk-score-all - Requires authentication"""
        response = requests.post(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/bulk-score-all")
        assert response.status_code == 401
    
    def test_bulk_score_all_requires_llm(self, session):
        """POST /api/scoring/epic/{epic_id}/bulk-score-all - Requires LLM config"""
        response = session.post(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/bulk-score-all")
        # Should return 400 if no LLM configured, or 200 if LLM is configured
        assert response.status_code in [200, 400, 402]
        
        if response.status_code == 400:
            data = response.json()
            assert "LLM" in data.get("detail", "") or "provider" in data.get("detail", "").lower()


class TestDataPersistence:
    """Test that scores are persisted correctly"""
    
    def test_feature_score_persistence(self, session):
        """Verify feature scores persist after update"""
        # Get a feature
        response = session.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/scores")
        assert response.status_code == 200
        
        data = response.json()
        if len(data["features"]) == 0:
            pytest.skip("No features available")
        
        feature_id = data["features"][0]["feature_id"]
        
        # Update MoSCoW
        update_response = session.put(
            f"{BASE_URL}/api/scoring/feature/{feature_id}/moscow",
            json={"score": "must_have"}
        )
        assert update_response.status_code == 200
        
        # Verify persistence by fetching again
        verify_response = session.get(f"{BASE_URL}/api/scoring/feature/{feature_id}")
        assert verify_response.status_code == 200
        
        verify_data = verify_response.json()
        assert verify_data["moscow_score"] == "must_have"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
