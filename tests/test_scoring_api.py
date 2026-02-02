"""
Test Suite for RICE and MoSCoW Scoring API Endpoints
Tests all scoring endpoints for Epics, Features, User Stories, and Bugs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data IDs created in database
TEST_EPIC_ID = "epic_test_scoring_001"
TEST_FEATURE_ID = "feat_test_scoring_001"
TEST_STORY_ID = "story_test_scoring_001"
TEST_BUG_ID = "bug_test_scoring_001"


@pytest.fixture(scope="module")
def session():
    """Create authenticated session via test-login"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    
    # Login via test-login endpoint
    response = s.post(f"{BASE_URL}/api/auth/test-login")
    assert response.status_code == 200, f"Test login failed: {response.text}"
    
    return s


class TestScoringOptions:
    """Test /api/scoring/options endpoint"""
    
    def test_get_scoring_options_success(self, session):
        """GET /api/scoring/options - Returns all scoring options"""
        response = session.get(f"{BASE_URL}/api/scoring/options")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify MoSCoW options
        assert "moscow_options" in data
        assert data["moscow_options"]["must_have"] == "Must Have"
        assert data["moscow_options"]["should_have"] == "Should Have"
        assert data["moscow_options"]["could_have"] == "Could Have"
        assert data["moscow_options"]["wont_have"] == "Won't Have"
        
        # Verify RICE impact options
        assert "rice_impact_options" in data
        assert "0.25" in data["rice_impact_options"] or 0.25 in data["rice_impact_options"]
        
        # Verify RICE confidence options
        assert "rice_confidence_options" in data


class TestEpicMoSCoWScoring:
    """Test Epic MoSCoW scoring endpoints"""
    
    def test_get_epic_moscow_success(self, session):
        """GET /api/scoring/epic/{id}/moscow - Returns epic MoSCoW score"""
        response = session.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow")
        assert response.status_code == 200
        
        data = response.json()
        assert "epic_id" in data
        assert data["epic_id"] == TEST_EPIC_ID
        assert "moscow_score" in data
        assert "moscow_label" in data
    
    def test_get_epic_moscow_not_found(self, session):
        """GET /api/scoring/epic/{id}/moscow - Returns 404 for nonexistent epic"""
        response = session.get(f"{BASE_URL}/api/scoring/epic/nonexistent_epic/moscow")
        assert response.status_code == 404
    
    def test_update_epic_moscow_must_have(self, session):
        """PUT /api/scoring/epic/{id}/moscow - Updates to must_have"""
        response = session.put(
            f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow",
            json={"score": "must_have"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["moscow_score"] == "must_have"
        assert data["moscow_label"] == "Must Have"
    
    def test_update_epic_moscow_should_have(self, session):
        """PUT /api/scoring/epic/{id}/moscow - Updates to should_have"""
        response = session.put(
            f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow",
            json={"score": "should_have"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["moscow_score"] == "should_have"
        assert data["moscow_label"] == "Should Have"
    
    def test_update_epic_moscow_could_have(self, session):
        """PUT /api/scoring/epic/{id}/moscow - Updates to could_have"""
        response = session.put(
            f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow",
            json={"score": "could_have"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["moscow_score"] == "could_have"
        assert data["moscow_label"] == "Could Have"
    
    def test_update_epic_moscow_wont_have(self, session):
        """PUT /api/scoring/epic/{id}/moscow - Updates to wont_have"""
        response = session.put(
            f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow",
            json={"score": "wont_have"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["moscow_score"] == "wont_have"
        assert data["moscow_label"] == "Won't Have"
    
    def test_update_epic_moscow_invalid_score(self, session):
        """PUT /api/scoring/epic/{id}/moscow - Returns 400 for invalid score"""
        response = session.put(
            f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow",
            json={"score": "invalid_score"}
        )
        assert response.status_code == 400
        assert "must be one of" in response.json()["detail"]
    
    def test_update_epic_moscow_not_found(self, session):
        """PUT /api/scoring/epic/{id}/moscow - Returns 404 for nonexistent epic"""
        response = session.put(
            f"{BASE_URL}/api/scoring/epic/nonexistent_epic/moscow",
            json={"score": "must_have"}
        )
        assert response.status_code == 404


class TestFeatureScoring:
    """Test Feature scoring endpoints (MoSCoW + RICE)"""
    
    def test_get_feature_scores_success(self, session):
        """GET /api/scoring/feature/{id} - Returns feature scores"""
        response = session.get(f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "feature_id" in data
        assert data["feature_id"] == TEST_FEATURE_ID
        assert "moscow_score" in data
        assert "rice_reach" in data
        assert "rice_impact" in data
        assert "rice_confidence" in data
        assert "rice_effort" in data
        assert "rice_total" in data
    
    def test_get_feature_scores_not_found(self, session):
        """GET /api/scoring/feature/{id} - Returns 404 for nonexistent feature"""
        response = session.get(f"{BASE_URL}/api/scoring/feature/nonexistent_feature")
        assert response.status_code == 404
    
    def test_update_feature_moscow_success(self, session):
        """PUT /api/scoring/feature/{id}/moscow - Updates MoSCoW score"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/moscow",
            json={"score": "must_have"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["moscow_score"] == "must_have"
        assert data["moscow_label"] == "Must Have"
    
    def test_update_feature_moscow_invalid(self, session):
        """PUT /api/scoring/feature/{id}/moscow - Returns 400 for invalid score"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/moscow",
            json={"score": "invalid"}
        )
        assert response.status_code == 400
    
    def test_update_feature_rice_success(self, session):
        """PUT /api/scoring/feature/{id}/rice - Updates RICE score"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/rice",
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
    
    def test_update_feature_rice_invalid_reach(self, session):
        """PUT /api/scoring/feature/{id}/rice - Returns 400 for invalid reach"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/rice",
            json={
                "reach": 15,  # Invalid: must be 1-10
                "impact": 2.0,
                "confidence": 0.8,
                "effort": 2.0
            }
        )
        assert response.status_code == 422 or response.status_code == 400
    
    def test_update_feature_rice_invalid_impact(self, session):
        """PUT /api/scoring/feature/{id}/rice - Returns 400 for invalid impact"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/rice",
            json={
                "reach": 5,
                "impact": 5.0,  # Invalid: must be 0.25, 0.5, 1, 2, or 3
                "confidence": 0.8,
                "effort": 2.0
            }
        )
        assert response.status_code == 400
    
    def test_update_feature_rice_invalid_confidence(self, session):
        """PUT /api/scoring/feature/{id}/rice - Returns 400 for invalid confidence"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/rice",
            json={
                "reach": 5,
                "impact": 2.0,
                "confidence": 0.9,  # Invalid: must be 0.5, 0.8, or 1.0
                "effort": 2.0
            }
        )
        assert response.status_code == 400
    
    def test_update_feature_rice_invalid_effort(self, session):
        """PUT /api/scoring/feature/{id}/rice - Returns 400 for invalid effort"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/rice",
            json={
                "reach": 5,
                "impact": 2.0,
                "confidence": 0.8,
                "effort": 15.0  # Invalid: must be 0.5-10
            }
        )
        assert response.status_code == 422 or response.status_code == 400


class TestUserStoryRICEScoring:
    """Test User Story RICE scoring endpoints"""
    
    def test_get_story_rice_success(self, session):
        """GET /api/scoring/story/{id} - Returns story RICE score"""
        response = session.get(f"{BASE_URL}/api/scoring/story/{TEST_STORY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "story_id" in data
        assert data["story_id"] == TEST_STORY_ID
        assert "rice_reach" in data
        assert "rice_impact" in data
        assert "rice_confidence" in data
        assert "rice_effort" in data
        assert "rice_total" in data
    
    def test_get_story_rice_not_found(self, session):
        """GET /api/scoring/story/{id} - Returns 404 for nonexistent story"""
        response = session.get(f"{BASE_URL}/api/scoring/story/nonexistent_story")
        assert response.status_code == 404
    
    def test_update_story_rice_success(self, session):
        """PUT /api/scoring/story/{id}/rice - Updates RICE score"""
        response = session.put(
            f"{BASE_URL}/api/scoring/story/{TEST_STORY_ID}/rice",
            json={
                "reach": 3,
                "impact": 1.0,
                "confidence": 1.0,
                "effort": 1.0
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["rice_reach"] == 3
        assert data["rice_impact"] == 1.0
        assert data["rice_confidence"] == 1.0
        assert data["rice_effort"] == 1.0
        # RICE = (3 * 1.0 * 1.0) / 1.0 = 3.0
        assert data["rice_total"] == 3.0
    
    def test_update_story_rice_invalid_values(self, session):
        """PUT /api/scoring/story/{id}/rice - Returns 400 for invalid values"""
        response = session.put(
            f"{BASE_URL}/api/scoring/story/{TEST_STORY_ID}/rice",
            json={
                "reach": 0,  # Invalid: must be 1-10
                "impact": 1.0,
                "confidence": 1.0,
                "effort": 1.0
            }
        )
        assert response.status_code == 422 or response.status_code == 400


class TestBugRICEScoring:
    """Test Bug RICE scoring endpoints"""
    
    def test_get_bug_rice_success(self, session):
        """GET /api/scoring/bug/{id} - Returns bug RICE score"""
        response = session.get(f"{BASE_URL}/api/scoring/bug/{TEST_BUG_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "bug_id" in data
        assert data["bug_id"] == TEST_BUG_ID
        assert "rice_reach" in data
        assert "rice_impact" in data
        assert "rice_confidence" in data
        assert "rice_effort" in data
        assert "rice_total" in data
    
    def test_get_bug_rice_not_found(self, session):
        """GET /api/scoring/bug/{id} - Returns 404 for nonexistent bug"""
        response = session.get(f"{BASE_URL}/api/scoring/bug/nonexistent_bug")
        assert response.status_code == 404
    
    def test_update_bug_rice_success(self, session):
        """PUT /api/scoring/bug/{id}/rice - Updates RICE score"""
        response = session.put(
            f"{BASE_URL}/api/scoring/bug/{TEST_BUG_ID}/rice",
            json={
                "reach": 8,
                "impact": 3.0,
                "confidence": 0.5,
                "effort": 0.5
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["rice_reach"] == 8
        assert data["rice_impact"] == 3.0
        assert data["rice_confidence"] == 0.5
        assert data["rice_effort"] == 0.5
        # RICE = (8 * 3.0 * 0.5) / 0.5 = 24.0
        assert data["rice_total"] == 24.0
    
    def test_update_bug_rice_invalid_values(self, session):
        """PUT /api/scoring/bug/{id}/rice - Returns 400 for invalid values"""
        response = session.put(
            f"{BASE_URL}/api/scoring/bug/{TEST_BUG_ID}/rice",
            json={
                "reach": 5,
                "impact": 4.0,  # Invalid: must be 0.25, 0.5, 1, 2, or 3
                "confidence": 0.8,
                "effort": 1.0
            }
        )
        assert response.status_code == 400


class TestScoringAuthentication:
    """Test that scoring endpoints require authentication"""
    
    def test_scoring_options_no_auth(self):
        """GET /api/scoring/options - Works without auth (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/scoring/options")
        # This endpoint may or may not require auth - just verify it doesn't crash
        assert response.status_code in [200, 401]
    
    def test_epic_moscow_no_auth(self):
        """GET /api/scoring/epic/{id}/moscow - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scoring/epic/{TEST_EPIC_ID}/moscow")
        assert response.status_code == 401
    
    def test_feature_scores_no_auth(self):
        """GET /api/scoring/feature/{id} - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}")
        assert response.status_code == 401
    
    def test_story_rice_no_auth(self):
        """GET /api/scoring/story/{id} - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scoring/story/{TEST_STORY_ID}")
        assert response.status_code == 401
    
    def test_bug_rice_no_auth(self):
        """GET /api/scoring/bug/{id} - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scoring/bug/{TEST_BUG_ID}")
        assert response.status_code == 401


class TestRICECalculation:
    """Test RICE score calculation accuracy"""
    
    def test_rice_calculation_feature(self, session):
        """Verify RICE calculation: (Reach * Impact * Confidence) / Effort"""
        # Set specific values
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/rice",
            json={
                "reach": 10,
                "impact": 3.0,
                "confidence": 1.0,
                "effort": 5.0
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        # RICE = (10 * 3.0 * 1.0) / 5.0 = 6.0
        expected_rice = (10 * 3.0 * 1.0) / 5.0
        assert data["rice_total"] == expected_rice
    
    def test_rice_calculation_minimum_values(self, session):
        """Test RICE with minimum valid values"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/rice",
            json={
                "reach": 1,
                "impact": 0.25,
                "confidence": 0.5,
                "effort": 10.0
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        # RICE = (1 * 0.25 * 0.5) / 10.0 = 0.0125 -> rounded to 0.01
        expected_rice = round((1 * 0.25 * 0.5) / 10.0, 2)
        assert data["rice_total"] == expected_rice
    
    def test_rice_calculation_maximum_values(self, session):
        """Test RICE with maximum valid values"""
        response = session.put(
            f"{BASE_URL}/api/scoring/feature/{TEST_FEATURE_ID}/rice",
            json={
                "reach": 10,
                "impact": 3.0,
                "confidence": 1.0,
                "effort": 0.5
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        # RICE = (10 * 3.0 * 1.0) / 0.5 = 60.0
        expected_rice = (10 * 3.0 * 1.0) / 0.5
        assert data["rice_total"] == expected_rice


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
