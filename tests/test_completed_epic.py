"""
Test Completed Epic Review Feature
Tests the new Completed Epic view that shows an expandable tree of Epic → Features → User Stories
when all items are locked/approved.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test session token from existing test data
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"
TEST_USER_ID = "user_test_05279c2b"

# Existing test data IDs
EXISTING_EPIC_ID = "epic_story_test_46de1163"
EXISTING_FEATURE_ID = "feat_story_test_3817da07"


@pytest.fixture
def api_client():
    """Shared requests session with auth"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Cookie": f"session_token={TEST_SESSION_TOKEN}"
    })
    return session


class TestFeaturesForEpicAPI:
    """Test GET /api/features/epic/{epic_id} - List features for an epic"""
    
    def test_list_features_for_epic_success(self, api_client):
        """Test listing features for a locked epic"""
        response = api_client.get(f"{BASE_URL}/api/features/epic/{EXISTING_EPIC_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of features"
        assert len(data) > 0, "Should have at least one feature"
        
        # Verify feature structure
        feature = data[0]
        assert "feature_id" in feature
        assert "epic_id" in feature
        assert "title" in feature
        assert "description" in feature
        assert "current_stage" in feature
        assert feature["epic_id"] == EXISTING_EPIC_ID
        
        print(f"SUCCESS: Found {len(data)} features for epic {EXISTING_EPIC_ID}")
        print(f"  Feature: {feature['title']} - Stage: {feature['current_stage']}")
    
    def test_list_features_for_nonexistent_epic(self, api_client):
        """Test listing features for a non-existent epic returns 404"""
        response = api_client.get(f"{BASE_URL}/api/features/epic/nonexistent_epic_id")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("SUCCESS: Returns 404 for non-existent epic")
    
    def test_list_features_unauthenticated(self):
        """Test listing features without authentication returns 401"""
        response = requests.get(f"{BASE_URL}/api/features/epic/{EXISTING_EPIC_ID}")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: Returns 401 for unauthenticated request")


class TestStoriesForFeatureAPI:
    """Test GET /api/stories/feature/{feature_id} - List stories for a feature"""
    
    def test_list_stories_for_feature_success(self, api_client):
        """Test listing user stories for an approved feature"""
        response = api_client.get(f"{BASE_URL}/api/stories/feature/{EXISTING_FEATURE_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of stories"
        assert len(data) > 0, "Should have at least one story"
        
        # Verify story structure
        story = data[0]
        assert "story_id" in story
        assert "feature_id" in story
        assert "story_text" in story
        assert "current_stage" in story
        assert "persona" in story
        assert "action" in story
        assert "benefit" in story
        assert story["feature_id"] == EXISTING_FEATURE_ID
        
        print(f"SUCCESS: Found {len(data)} stories for feature {EXISTING_FEATURE_ID}")
        for s in data:
            print(f"  Story: {s['story_text'][:60]}... - Stage: {s['current_stage']}")
    
    def test_list_stories_for_nonexistent_feature(self, api_client):
        """Test listing stories for a non-existent feature returns 404"""
        response = api_client.get(f"{BASE_URL}/api/stories/feature/nonexistent_feature_id")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("SUCCESS: Returns 404 for non-existent feature")
    
    def test_list_stories_unauthenticated(self):
        """Test listing stories without authentication returns 401"""
        response = requests.get(f"{BASE_URL}/api/stories/feature/{EXISTING_FEATURE_ID}")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: Returns 401 for unauthenticated request")


class TestEpicAPI:
    """Test Epic API endpoints used by Completed Epic page"""
    
    def test_get_epic_success(self, api_client):
        """Test getting epic details"""
        response = api_client.get(f"{BASE_URL}/api/epics/{EXISTING_EPIC_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "epic_id" in data
        assert "title" in data
        assert "current_stage" in data
        assert data["epic_id"] == EXISTING_EPIC_ID
        assert data["current_stage"] == "epic_locked", "Epic should be locked"
        
        # Check snapshot data (used by Completed Epic page)
        if "snapshot" in data and data["snapshot"]:
            snapshot = data["snapshot"]
            print(f"SUCCESS: Epic has snapshot with problem_statement: {bool(snapshot.get('problem_statement'))}")
            print(f"  desired_outcome: {bool(snapshot.get('desired_outcome'))}")
            print(f"  acceptance_criteria: {len(snapshot.get('acceptance_criteria', []))} items")
        else:
            print("INFO: Epic snapshot is empty or not present")
        
        print(f"SUCCESS: Got epic {data['title']} - Stage: {data['current_stage']}")
    
    def test_get_epic_nonexistent(self, api_client):
        """Test getting non-existent epic returns 404"""
        response = api_client.get(f"{BASE_URL}/api/epics/nonexistent_epic_id")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("SUCCESS: Returns 404 for non-existent epic")


class TestCompletedEpicDataFlow:
    """Test the complete data flow for Completed Epic page"""
    
    def test_full_completed_epic_data_flow(self, api_client):
        """Test loading all data needed for Completed Epic page"""
        # Step 1: Load epic
        epic_response = api_client.get(f"{BASE_URL}/api/epics/{EXISTING_EPIC_ID}")
        assert epic_response.status_code == 200, f"Failed to load epic: {epic_response.text}"
        epic = epic_response.json()
        
        print(f"Step 1: Loaded epic '{epic['title']}' - Stage: {epic['current_stage']}")
        
        # Step 2: Load features for epic
        features_response = api_client.get(f"{BASE_URL}/api/features/epic/{EXISTING_EPIC_ID}")
        assert features_response.status_code == 200, f"Failed to load features: {features_response.text}"
        features = features_response.json()
        
        print(f"Step 2: Loaded {len(features)} features")
        
        # Step 3: Load stories for each feature
        total_stories = 0
        total_story_points = 0
        all_features_approved = True
        all_stories_approved = True
        
        for feature in features:
            stories_response = api_client.get(f"{BASE_URL}/api/stories/feature/{feature['feature_id']}")
            assert stories_response.status_code == 200, f"Failed to load stories for feature {feature['feature_id']}"
            stories = stories_response.json()
            
            total_stories += len(stories)
            
            if feature['current_stage'] != 'approved':
                all_features_approved = False
            
            for story in stories:
                if story.get('story_points'):
                    total_story_points += story['story_points']
                if story['current_stage'] != 'approved':
                    all_stories_approved = False
            
            print(f"  Feature '{feature['title']}': {len(stories)} stories, stage: {feature['current_stage']}")
        
        # Step 4: Verify completion status
        is_fully_complete = (
            epic['current_stage'] == 'epic_locked' and
            all_features_approved and
            all_stories_approved and
            len(features) > 0 and
            total_stories > 0
        )
        
        print(f"\nStep 3: Completion Status:")
        print(f"  Epic locked: {epic['current_stage'] == 'epic_locked'}")
        print(f"  All features approved: {all_features_approved}")
        print(f"  All stories approved: {all_stories_approved}")
        print(f"  Total features: {len(features)}")
        print(f"  Total stories: {total_stories}")
        print(f"  Total story points: {total_story_points}")
        print(f"  Is fully complete: {is_fully_complete}")
        
        assert is_fully_complete, "Epic should be fully complete for this test"
        print("\nSUCCESS: Full Completed Epic data flow verified")


class TestCompletedEpicStats:
    """Test statistics calculation for Completed Epic page"""
    
    def test_calculate_stats(self, api_client):
        """Test calculating stats (features, stories, story points)"""
        # Load features
        features_response = api_client.get(f"{BASE_URL}/api/features/epic/{EXISTING_EPIC_ID}")
        features = features_response.json()
        
        total_features = len(features)
        approved_features = sum(1 for f in features if f['current_stage'] == 'approved')
        
        # Load stories for each feature
        all_stories = []
        for feature in features:
            stories_response = api_client.get(f"{BASE_URL}/api/stories/feature/{feature['feature_id']}")
            stories = stories_response.json()
            all_stories.extend(stories)
        
        total_stories = len(all_stories)
        approved_stories = sum(1 for s in all_stories if s['current_stage'] == 'approved')
        total_story_points = sum(s.get('story_points', 0) or 0 for s in all_stories)
        
        print(f"Stats calculated:")
        print(f"  Total features: {total_features}")
        print(f"  Approved features: {approved_features}")
        print(f"  Total stories: {total_stories}")
        print(f"  Approved stories: {approved_stories}")
        print(f"  Total story points: {total_story_points}")
        
        assert total_features > 0, "Should have at least one feature"
        assert total_stories > 0, "Should have at least one story"
        assert approved_features == total_features, "All features should be approved"
        assert approved_stories == total_stories, "All stories should be approved"
        
        print("SUCCESS: Stats calculation verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
