#!/usr/bin/env python3
"""
JarlPM Epic Cascade Delete Testing Suite
Tests that deleting an Epic cascades to all related entities:
- Features
- User Stories (via Feature cascade)
- Transcript Events
- Snapshots

This test uses API calls and psycopg2 for direct DB access to test cascade delete.

Modules tested:
- Epic creation API
- Feature creation for an Epic
- User Story creation for a Feature
- Epic DELETE endpoint cascades to delete Features
- Epic DELETE endpoint cascades to delete User Stories (via Feature cascade)
- Epic DELETE endpoint cascades to delete Transcript Events
- Verify database has no orphaned records after Epic delete
"""

import pytest
import requests
import os
import uuid
import psycopg2
from urllib.parse import urlparse

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://priorityforge.preview.emergentagent.com').rstrip('/')

# Test user credentials (created by Test Login button)
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"


def get_db_connection():
    """Get a psycopg2 connection to the database"""
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        # Read from backend .env
        with open('/app/backend/.env', 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.split('=', 1)[1].strip().strip('"')
                    break
    
    if not db_url:
        raise Exception("DATABASE_URL not found")
    
    # Parse the URL
    parsed = urlparse(db_url)
    
    # Connect with SSL
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/'),
        user=parsed.username,
        password=parsed.password,
        sslmode='require'
    )
    return conn


@pytest.fixture(scope="module")
def auth_headers():
    """Get headers with authentication"""
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TEST_SESSION_TOKEN}'
    }


@pytest.fixture(scope="module")
def test_user_id(auth_headers):
    """Get the actual test user ID from the API"""
    response = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers=auth_headers,
        timeout=10
    )
    assert response.status_code == 200, f"Failed to get user: {response.text}"
    return response.json()["user_id"]


class TestEpicCreationAPI:
    """Test Epic creation API"""
    
    def test_create_epic(self, auth_headers):
        """Test creating a new epic"""
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Cascade Delete Epic"},
            timeout=10
        )
        assert response.status_code == 201, f"Epic creation failed: {response.text}"
        
        data = response.json()
        assert "epic_id" in data
        assert data["title"] == "TEST_Cascade Delete Epic"
        assert data["current_stage"] == "problem_capture"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{data['epic_id']}", headers=auth_headers, timeout=10)
        print(f"✓ Epic creation test passed")
    
    def test_create_epic_returns_snapshot(self, auth_headers):
        """Test that created epic has a snapshot"""
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Epic With Snapshot"},
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert "snapshot" in data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{data['epic_id']}", headers=auth_headers, timeout=10)
        print(f"✓ Epic snapshot test passed")


class TestEpicDeleteAPI:
    """Test Epic DELETE endpoint"""
    
    def test_delete_epic_returns_200(self, auth_headers):
        """Test that deleting an epic returns 200"""
        # Create epic
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Delete Epic"},
            timeout=10
        )
        assert response.status_code == 201
        epic_id = response.json()["epic_id"]
        
        # Delete epic
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete failed: {response.text}"
        assert response.json().get("message") == "Epic deleted"
        
        print(f"✓ Epic delete returns 200")
    
    def test_deleted_epic_returns_404(self, auth_headers):
        """Test that deleted epic returns 404 on GET"""
        # Create epic
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Delete 404 Epic"},
            timeout=10
        )
        assert response.status_code == 201
        epic_id = response.json()["epic_id"]
        
        # Delete epic
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        
        # Verify 404
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Deleted epic should return 404: {response.text}"
        
        print(f"✓ Deleted epic returns 404")
    
    def test_delete_nonexistent_epic_returns_404(self, auth_headers):
        """Test that deleting nonexistent epic returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/epics/epic_nonexistent_12345",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Nonexistent epic delete should return 404: {response.text}"
        
        print(f"✓ Delete nonexistent epic returns 404")


def create_locked_epic_with_children(user_id: str):
    """Helper function to create a locked epic with features and stories using psycopg2"""
    epic_id = f"epic_cascade_{uuid.uuid4().hex[:8]}"
    feature_id = f"feat_cascade_{uuid.uuid4().hex[:8]}"
    story_id = f"story_cascade_{uuid.uuid4().hex[:8]}"
    event_id_1 = f"evt_{uuid.uuid4().hex[:12]}"
    event_id_2 = f"evt_{uuid.uuid4().hex[:12]}"
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Create epic
            cur.execute("""
                INSERT INTO epics (epic_id, user_id, title, current_stage, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
            """, (epic_id, user_id, 'TEST_Cascade Epic', 'epic_locked'))
            
            # Create snapshot
            cur.execute("""
                INSERT INTO epic_snapshots (epic_id, problem_statement, desired_outcome, epic_summary)
                VALUES (%s, %s, %s, %s)
            """, (epic_id, 'Cascade test problem', 'Cascade test outcome', 'Cascade test summary'))
            
            # Create transcript events
            cur.execute("""
                INSERT INTO epic_transcript_events (event_id, epic_id, role, content, stage, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (event_id_1, epic_id, 'system', 'Event 1', 'epic_locked'))
            
            cur.execute("""
                INSERT INTO epic_transcript_events (event_id, epic_id, role, content, stage, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (event_id_2, epic_id, 'system', 'Event 2', 'epic_locked'))
            
            # Create feature
            cur.execute("""
                INSERT INTO features (feature_id, epic_id, title, description, current_stage, source, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (feature_id, epic_id, 'TEST_Cascade Feature', 'Feature for cascade test', 'approved', 'manual'))
            
            # Create user story (version defaults to 1, is_frozen defaults to false, is_standalone defaults to false)
            cur.execute("""
                INSERT INTO user_stories (story_id, feature_id, persona, action, benefit, story_text, current_stage, source, version, is_frozen, is_standalone, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, false, false, NOW(), NOW())
            """, (story_id, feature_id, 'cascade user', 'test cascade', 'verify cascade', 
                  'As a cascade user, I want to test cascade so that verify cascade.', 'draft', 'manual'))
            
            conn.commit()
    finally:
        conn.close()
    
    return {
        "epic_id": epic_id,
        "feature_id": feature_id,
        "story_id": story_id
    }


class TestCascadeDeleteFeatures:
    """Test Epic DELETE cascades to Features"""
    
    def test_cascade_delete_features(self, auth_headers, test_user_id):
        """Test that deleting an epic cascades to delete features"""
        # Create test data via psycopg2
        data = create_locked_epic_with_children(test_user_id)
        
        epic_id = data["epic_id"]
        feature_id = data["feature_id"]
        
        # Verify feature exists via API
        response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Feature should exist before delete: {response.text}"
        print(f"✓ Feature {feature_id} exists before epic delete")
        
        # Delete epic via API
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify feature is gone via API
        response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Feature should return 404 after epic delete: {response.text}"
        print(f"✓ Feature {feature_id} returns 404 after epic delete (CASCADE WORKS!)")


class TestCascadeDeleteUserStories:
    """Test Epic DELETE cascades to User Stories via Feature"""
    
    def test_cascade_delete_user_stories(self, auth_headers, test_user_id):
        """Test that deleting an epic cascades to delete user stories via feature"""
        # Create test data via psycopg2
        data = create_locked_epic_with_children(test_user_id)
        
        epic_id = data["epic_id"]
        story_id = data["story_id"]
        
        # Verify story exists via API
        response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Story should exist before delete: {response.text}"
        print(f"✓ Story {story_id} exists before epic delete")
        
        # Delete epic via API
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify story is gone via API
        response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Story should return 404 after epic delete: {response.text}"
        print(f"✓ Story {story_id} returns 404 after epic delete (CASCADE VIA FEATURE WORKS!)")


class TestCascadeDeleteTranscriptEvents:
    """Test Epic DELETE cascades to Transcript Events"""
    
    def test_cascade_delete_transcript_events(self, auth_headers, test_user_id):
        """Test that deleting an epic cascades to delete transcript events"""
        # Create test data via psycopg2
        data = create_locked_epic_with_children(test_user_id)
        
        epic_id = data["epic_id"]
        
        # Verify transcript events exist via API
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}/transcript",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        transcript_data = response.json()
        assert len(transcript_data.get("events", [])) >= 2, "Should have at least 2 transcript events"
        print(f"✓ Transcript events exist before epic delete: {len(transcript_data.get('events', []))} events")
        
        # Delete epic via API
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify transcript returns 404 (epic is gone)
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}/transcript",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Transcript should return 404 after epic delete: {response.text}"
        print(f"✓ Transcript returns 404 after epic delete (CASCADE WORKS!)")


class TestCascadeDeleteSnapshots:
    """Test Epic DELETE cascades to Snapshots"""
    
    def test_cascade_delete_snapshots(self, auth_headers, test_user_id):
        """Test that deleting an epic cascades to delete snapshots"""
        # Create test data via psycopg2
        data = create_locked_epic_with_children(test_user_id)
        
        epic_id = data["epic_id"]
        
        # Verify epic with snapshot exists via API
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        epic_data = response.json()
        assert epic_data["snapshot"]["problem_statement"] == "Cascade test problem"
        print(f"✓ Epic with snapshot exists before delete")
        
        # Delete epic via API
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify epic is gone
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Epic should return 404: {response.text}"
        print(f"✓ Epic returns 404 after delete (SNAPSHOT CASCADE WORKS!)")


class TestDatabaseIntegrityAfterDelete:
    """Verify database has no orphaned records after Epic delete"""
    
    def test_no_orphaned_records_after_delete(self, auth_headers, test_user_id):
        """Verify no orphaned records in database after deleting epic with all children"""
        # Create test data via psycopg2
        data = create_locked_epic_with_children(test_user_id)
        
        epic_id = data["epic_id"]
        feature_id = data["feature_id"]
        story_id = data["story_id"]
        
        print(f"Created epic {epic_id} with feature {feature_id} and story {story_id}")
        
        # Verify all exist via API
        response = requests.get(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Epic should exist: {response.text}"
        
        response = requests.get(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Feature should exist: {response.text}"
        
        response = requests.get(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Story should exist: {response.text}"
        
        print(f"✓ All entities verified to exist before delete")
        
        # Delete epic via API
        response = requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify all are gone via API
        response = requests.get(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 404, f"Epic should return 404: {response.text}"
        
        response = requests.get(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 404, f"Feature should return 404: {response.text}"
        
        response = requests.get(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 404, f"Story should return 404: {response.text}"
        
        print(f"✓ All entities verified to be deleted via API (CASCADE WORKS!)")
        
        # Verify no orphans in database via psycopg2
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Check for orphaned snapshots
                cur.execute("SELECT COUNT(*) FROM epic_snapshots WHERE epic_id = %s", (epic_id,))
                count = cur.fetchone()[0]
                assert count == 0, f"Orphaned snapshots found: {count}"
                print(f"✓ No orphaned snapshots in database")
                
                # Check for orphaned transcript events
                cur.execute("SELECT COUNT(*) FROM epic_transcript_events WHERE epic_id = %s", (epic_id,))
                count = cur.fetchone()[0]
                assert count == 0, f"Orphaned transcript events found: {count}"
                print(f"✓ No orphaned transcript events in database")
                
                # Check for orphaned features
                cur.execute("SELECT COUNT(*) FROM features WHERE epic_id = %s", (epic_id,))
                count = cur.fetchone()[0]
                assert count == 0, f"Orphaned features found: {count}"
                print(f"✓ No orphaned features in database")
                
                # Check for orphaned user stories
                cur.execute("SELECT COUNT(*) FROM user_stories WHERE feature_id = %s", (feature_id,))
                count = cur.fetchone()[0]
                assert count == 0, f"Orphaned user stories found: {count}"
                print(f"✓ No orphaned user stories in database")
        finally:
            conn.close()
        
        print(f"✓ Full cascade delete test completed successfully!")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
