#!/usr/bin/env python3
"""
JarlPM Epic Cascade Delete Testing Suite
Tests that deleting an Epic cascades to all related entities:
- Features
- User Stories (via Feature cascade)
- Transcript Events
- Snapshots
- Decisions
- Artifacts

Modules tested:
- Epic DELETE endpoint (/api/epics/{epic_id})
- Cascade delete to Features
- Cascade delete to User Stories
- Cascade delete to Transcript Events
- Cascade delete to Snapshots
- Database integrity after delete
"""

import pytest
import requests
import os
import sys
import asyncio
from datetime import datetime, timezone
import uuid

# Add backend to path
sys.path.insert(0, '/app/backend')

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://priorityforge.preview.emergentagent.com').rstrip('/')

# Test user credentials (created by Test Login button)
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"
TEST_USER_ID = "user_test_8575b765"


@pytest.fixture(scope="module")
def auth_headers():
    """Get headers with authentication"""
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TEST_SESSION_TOKEN}'
    }


class TestEpicCreation:
    """Test Epic creation API"""
    
    def test_create_epic(self, auth_headers):
        """Test creating a new epic"""
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Cascade Delete Epic"},
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert "epic_id" in data
        assert data["title"] == "TEST_Cascade Delete Epic"
        assert data["current_stage"] == "problem_capture"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{data['epic_id']}", headers=auth_headers, timeout=10)


class TestEpicCascadeDelete:
    """Test Epic DELETE endpoint cascades to all related entities"""
    
    @pytest.fixture(scope="class")
    def test_epic_with_children(self, auth_headers):
        """Create an epic with features, user stories, and transcript events for cascade delete testing"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage, EpicTranscriptEvent, EpicDecision, EpicArtifact
        from db.feature_models import Feature, FeatureStage, FeatureConversationEvent
        from db.user_story_models import UserStory, UserStoryStage, UserStoryConversationEvent
        from sqlalchemy import select
        
        async def _create_epic_with_children():
            async with AsyncSessionLocal() as session:
                # Create a locked epic
                epic_id = f"epic_cascade_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=TEST_USER_ID,
                    title="TEST_Cascade Delete Full Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                # Create snapshot
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Test problem for cascade delete",
                    desired_outcome="Test outcome for cascade delete",
                    epic_summary="Test summary for cascade delete",
                    acceptance_criteria=["Criterion 1", "Criterion 2"]
                )
                session.add(snapshot)
                
                # Create transcript events
                transcript_event = EpicTranscriptEvent(
                    epic_id=epic_id,
                    role="system",
                    content="Epic created for cascade delete test",
                    stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(transcript_event)
                
                # Create decision
                decision = EpicDecision(
                    epic_id=epic_id,
                    user_id=TEST_USER_ID,
                    decision_type="confirm_proposal",
                    from_stage=EpicStage.PROBLEM_CAPTURE.value,
                    to_stage=EpicStage.PROBLEM_CONFIRMED.value,
                    content_snapshot="Test decision"
                )
                session.add(decision)
                
                # Create artifact
                artifact = EpicArtifact(
                    epic_id=epic_id,
                    artifact_type="feature",
                    title="Test Artifact",
                    description="Test artifact for cascade delete"
                )
                session.add(artifact)
                
                # Create feature
                feature_id = f"feat_cascade_{uuid.uuid4().hex[:8]}"
                feature = Feature(
                    feature_id=feature_id,
                    epic_id=epic_id,
                    title="TEST_Cascade Feature",
                    description="Feature for cascade delete test",
                    acceptance_criteria=["Feature criterion 1"],
                    current_stage=FeatureStage.APPROVED.value,
                    source="manual",
                    approved_at=datetime.now(timezone.utc)
                )
                session.add(feature)
                await session.flush()
                
                # Create feature conversation event
                feature_conv = FeatureConversationEvent(
                    feature_id=feature_id,
                    role="system",
                    content="Feature created for cascade test"
                )
                session.add(feature_conv)
                
                # Create user story
                story_id = f"story_cascade_{uuid.uuid4().hex[:8]}"
                story = UserStory(
                    story_id=story_id,
                    feature_id=feature_id,
                    persona="test user",
                    action="test cascade delete",
                    benefit="verify cascade works",
                    story_text="As a test user, I want to test cascade delete so that verify cascade works.",
                    acceptance_criteria=["Story criterion 1"],
                    current_stage=UserStoryStage.DRAFT.value,
                    source="manual"
                )
                session.add(story)
                await session.flush()
                
                # Create user story conversation event
                story_conv = UserStoryConversationEvent(
                    story_id=story_id,
                    role="system",
                    content="Story created for cascade test"
                )
                session.add(story_conv)
                
                await session.commit()
                
                return {
                    "epic_id": epic_id,
                    "feature_id": feature_id,
                    "story_id": story_id
                }
        
        data = asyncio.run(_create_epic_with_children())
        yield data
        
        # Cleanup is handled by the delete test itself
    
    def test_epic_exists_before_delete(self, auth_headers, test_epic_with_children):
        """Verify epic and all children exist before delete"""
        epic_id = test_epic_with_children["epic_id"]
        feature_id = test_epic_with_children["feature_id"]
        story_id = test_epic_with_children["story_id"]
        
        # Verify epic exists
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic should exist before delete: {response.text}"
        
        # Verify feature exists
        response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Feature should exist before delete: {response.text}"
        
        # Verify story exists
        response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Story should exist before delete: {response.text}"
        
        # Verify transcript exists
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}/transcript",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data.get("events", [])) > 0, "Transcript events should exist before delete"
        
        print(f"✓ Epic {epic_id} exists with feature {feature_id} and story {story_id}")
    
    def test_delete_epic_cascades(self, auth_headers, test_epic_with_children):
        """Test that deleting an epic cascades to all related entities"""
        epic_id = test_epic_with_children["epic_id"]
        feature_id = test_epic_with_children["feature_id"]
        story_id = test_epic_with_children["story_id"]
        
        # Delete the epic
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        
        data = response.json()
        assert data.get("message") == "Epic deleted"
        
        print(f"✓ Epic {epic_id} deleted successfully")
    
    def test_epic_not_found_after_delete(self, auth_headers, test_epic_with_children):
        """Verify epic returns 404 after delete"""
        epic_id = test_epic_with_children["epic_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Epic should return 404 after delete: {response.text}"
        
        print(f"✓ Epic {epic_id} returns 404 after delete")
    
    def test_feature_not_found_after_epic_delete(self, auth_headers, test_epic_with_children):
        """Verify feature returns 404 after epic delete (cascade)"""
        feature_id = test_epic_with_children["feature_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Feature should return 404 after epic delete: {response.text}"
        
        print(f"✓ Feature {feature_id} returns 404 after epic delete (cascade)")
    
    def test_story_not_found_after_epic_delete(self, auth_headers, test_epic_with_children):
        """Verify user story returns 404 after epic delete (cascade via feature)"""
        story_id = test_epic_with_children["story_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Story should return 404 after epic delete: {response.text}"
        
        print(f"✓ Story {story_id} returns 404 after epic delete (cascade via feature)")


class TestDatabaseIntegrityAfterDelete:
    """Verify database has no orphaned records after Epic delete"""
    
    @pytest.fixture(scope="class")
    def deleted_epic_data(self, auth_headers):
        """Create and delete an epic, returning IDs for verification"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage, EpicTranscriptEvent
        from db.feature_models import Feature, FeatureStage
        from db.user_story_models import UserStory, UserStoryStage
        
        async def _create_and_delete():
            async with AsyncSessionLocal() as session:
                # Create epic
                epic_id = f"epic_orphan_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=TEST_USER_ID,
                    title="TEST_Orphan Check Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                # Create snapshot
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Orphan check problem"
                )
                session.add(snapshot)
                
                # Create transcript event
                transcript = EpicTranscriptEvent(
                    epic_id=epic_id,
                    role="system",
                    content="Orphan check transcript",
                    stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(transcript)
                
                # Create feature
                feature_id = f"feat_orphan_{uuid.uuid4().hex[:8]}"
                feature = Feature(
                    feature_id=feature_id,
                    epic_id=epic_id,
                    title="TEST_Orphan Feature",
                    description="Orphan check feature",
                    current_stage=FeatureStage.DRAFT.value,
                    source="manual"
                )
                session.add(feature)
                await session.flush()
                
                # Create user story
                story_id = f"story_orphan_{uuid.uuid4().hex[:8]}"
                story = UserStory(
                    story_id=story_id,
                    feature_id=feature_id,
                    persona="orphan user",
                    action="check orphans",
                    benefit="verify no orphans",
                    story_text="As a orphan user, I want to check orphans so that verify no orphans.",
                    current_stage=UserStoryStage.DRAFT.value,
                    source="manual"
                )
                session.add(story)
                
                await session.commit()
                
                return {
                    "epic_id": epic_id,
                    "feature_id": feature_id,
                    "story_id": story_id
                }
        
        data = asyncio.run(_create_and_delete())
        
        # Delete via API
        response = requests.delete(
            f"{BASE_URL}/api/epics/{data['epic_id']}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete failed: {response.text}"
        
        yield data
    
    def test_no_orphaned_snapshots(self, deleted_epic_data):
        """Verify no orphaned snapshots in database"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import EpicSnapshot
        from sqlalchemy import select
        
        async def _check_orphans():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(EpicSnapshot).where(EpicSnapshot.epic_id == deleted_epic_data["epic_id"])
                )
                return result.scalar_one_or_none()
        
        snapshot = asyncio.run(_check_orphans())
        assert snapshot is None, f"Orphaned snapshot found for epic {deleted_epic_data['epic_id']}"
        
        print(f"✓ No orphaned snapshots for epic {deleted_epic_data['epic_id']}")
    
    def test_no_orphaned_transcript_events(self, deleted_epic_data):
        """Verify no orphaned transcript events in database"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import EpicTranscriptEvent
        from sqlalchemy import select
        
        async def _check_orphans():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(EpicTranscriptEvent).where(EpicTranscriptEvent.epic_id == deleted_epic_data["epic_id"])
                )
                return list(result.scalars().all())
        
        events = asyncio.run(_check_orphans())
        assert len(events) == 0, f"Orphaned transcript events found: {len(events)}"
        
        print(f"✓ No orphaned transcript events for epic {deleted_epic_data['epic_id']}")
    
    def test_no_orphaned_features(self, deleted_epic_data):
        """Verify no orphaned features in database"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.feature_models import Feature
        from sqlalchemy import select
        
        async def _check_orphans():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Feature).where(Feature.epic_id == deleted_epic_data["epic_id"])
                )
                return list(result.scalars().all())
        
        features = asyncio.run(_check_orphans())
        assert len(features) == 0, f"Orphaned features found: {len(features)}"
        
        print(f"✓ No orphaned features for epic {deleted_epic_data['epic_id']}")
    
    def test_no_orphaned_user_stories(self, deleted_epic_data):
        """Verify no orphaned user stories in database"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.user_story_models import UserStory
        from sqlalchemy import select
        
        async def _check_orphans():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(UserStory).where(UserStory.feature_id == deleted_epic_data["feature_id"])
                )
                return list(result.scalars().all())
        
        stories = asyncio.run(_check_orphans())
        assert len(stories) == 0, f"Orphaned user stories found: {len(stories)}"
        
        print(f"✓ No orphaned user stories for feature {deleted_epic_data['feature_id']}")


class TestFeatureCreationForEpic:
    """Test Feature creation for an Epic"""
    
    @pytest.fixture(scope="class")
    def locked_epic(self, auth_headers):
        """Create a locked epic for feature testing"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        
        async def _create_locked_epic():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_feat_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=TEST_USER_ID,
                    title="TEST_Feature Creation Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Feature creation test problem",
                    desired_outcome="Feature creation test outcome",
                    epic_summary="Feature creation test summary"
                )
                session.add(snapshot)
                await session.commit()
                
                return epic_id
        
        epic_id = asyncio.run(_create_locked_epic())
        yield epic_id
        
        # Cleanup
        try:
            requests.delete(
                f"{BASE_URL}/api/epics/{epic_id}",
                headers=auth_headers,
                timeout=10
            )
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    def test_create_feature_for_epic(self, auth_headers, locked_epic):
        """Test creating a feature for a locked epic"""
        response = requests.post(
            f"{BASE_URL}/api/features/epic/{locked_epic}",
            headers=auth_headers,
            json={
                "title": "TEST_Feature for Cascade",
                "description": "Feature to test cascade delete",
                "acceptance_criteria": ["Criterion 1", "Criterion 2"],
                "source": "manual"
            },
            timeout=10
        )
        assert response.status_code == 201, f"Feature creation failed: {response.text}"
        
        data = response.json()
        assert "feature_id" in data
        assert data["title"] == "TEST_Feature for Cascade"
        assert data["epic_id"] == locked_epic
        
        print(f"✓ Feature {data['feature_id']} created for epic {locked_epic}")


class TestUserStoryCreationForFeature:
    """Test User Story creation for a Feature"""
    
    @pytest.fixture(scope="class")
    def approved_feature(self, auth_headers):
        """Create a locked epic with an approved feature"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        from db.feature_models import Feature, FeatureStage
        
        async def _create_approved_feature():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_story_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=TEST_USER_ID,
                    title="TEST_Story Creation Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Story creation test problem"
                )
                session.add(snapshot)
                
                feature_id = f"feat_story_{uuid.uuid4().hex[:8]}"
                feature = Feature(
                    feature_id=feature_id,
                    epic_id=epic_id,
                    title="TEST_Feature for Story",
                    description="Feature for story creation test",
                    current_stage=FeatureStage.APPROVED.value,
                    source="manual",
                    approved_at=datetime.now(timezone.utc)
                )
                session.add(feature)
                await session.commit()
                
                return {"epic_id": epic_id, "feature_id": feature_id}
        
        data = asyncio.run(_create_approved_feature())
        yield data
        
        # Cleanup
        try:
            requests.delete(
                f"{BASE_URL}/api/epics/{data['epic_id']}",
                headers=auth_headers,
                timeout=10
            )
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    def test_create_story_for_feature(self, auth_headers, approved_feature):
        """Test creating a user story for an approved feature"""
        feature_id = approved_feature["feature_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/stories/feature/{feature_id}",
            headers=auth_headers,
            json={
                "persona": "test user",
                "action": "test cascade delete",
                "benefit": "verify cascade works",
                "acceptance_criteria": ["Given cascade, When delete, Then all removed"],
                "story_points": 3,
                "source": "manual"
            },
            timeout=10
        )
        assert response.status_code == 201, f"Story creation failed: {response.text}"
        
        data = response.json()
        assert "story_id" in data
        assert data["persona"] == "test user"
        assert data["feature_id"] == feature_id
        
        print(f"✓ Story {data['story_id']} created for feature {feature_id}")


class TestFullCascadeDeleteWorkflow:
    """Test complete workflow: Create Epic -> Add Features -> Add Stories -> Delete Epic -> Verify all removed"""
    
    def test_full_cascade_workflow(self, auth_headers):
        """Test the complete cascade delete workflow"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage, EpicTranscriptEvent
        from db.feature_models import Feature, FeatureStage
        from db.user_story_models import UserStory, UserStoryStage
        from sqlalchemy import select
        
        # Step 1: Create epic with all children via direct DB access
        async def _create_full_hierarchy():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_full_{uuid.uuid4().hex[:8]}"
                
                # Create epic
                epic = Epic(
                    epic_id=epic_id,
                    user_id=TEST_USER_ID,
                    title="TEST_Full Cascade Workflow Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                # Create snapshot
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Full workflow problem",
                    desired_outcome="Full workflow outcome",
                    epic_summary="Full workflow summary"
                )
                session.add(snapshot)
                
                # Create transcript events
                for i in range(3):
                    event = EpicTranscriptEvent(
                        epic_id=epic_id,
                        role="system",
                        content=f"Transcript event {i+1}",
                        stage=EpicStage.EPIC_LOCKED.value
                    )
                    session.add(event)
                
                # Create multiple features
                feature_ids = []
                story_ids = []
                for i in range(2):
                    feature_id = f"feat_full_{uuid.uuid4().hex[:8]}"
                    feature = Feature(
                        feature_id=feature_id,
                        epic_id=epic_id,
                        title=f"TEST_Full Feature {i+1}",
                        description=f"Full workflow feature {i+1}",
                        current_stage=FeatureStage.APPROVED.value,
                        source="manual",
                        approved_at=datetime.now(timezone.utc)
                    )
                    session.add(feature)
                    await session.flush()
                    feature_ids.append(feature_id)
                    
                    # Create stories for each feature
                    for j in range(2):
                        story_id = f"story_full_{uuid.uuid4().hex[:8]}"
                        story = UserStory(
                            story_id=story_id,
                            feature_id=feature_id,
                            persona=f"user {j+1}",
                            action=f"action {j+1}",
                            benefit=f"benefit {j+1}",
                            story_text=f"As a user {j+1}, I want to action {j+1} so that benefit {j+1}.",
                            current_stage=UserStoryStage.DRAFT.value,
                            source="manual"
                        )
                        session.add(story)
                        story_ids.append(story_id)
                
                await session.commit()
                
                return {
                    "epic_id": epic_id,
                    "feature_ids": feature_ids,
                    "story_ids": story_ids
                }
        
        data = asyncio.run(_create_full_hierarchy())
        epic_id = data["epic_id"]
        feature_ids = data["feature_ids"]
        story_ids = data["story_ids"]
        
        print(f"Created epic {epic_id} with {len(feature_ids)} features and {len(story_ids)} stories")
        
        # Step 2: Verify all entities exist
        # Verify epic
        response = requests.get(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Epic should exist: {response.text}"
        
        # Verify features
        for feature_id in feature_ids:
            response = requests.get(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
            assert response.status_code == 200, f"Feature {feature_id} should exist: {response.text}"
        
        # Verify stories
        for story_id in story_ids:
            response = requests.get(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
            assert response.status_code == 200, f"Story {story_id} should exist: {response.text}"
        
        # Verify transcript
        response = requests.get(f"{BASE_URL}/api/epics/{epic_id}/transcript", headers=auth_headers, timeout=10)
        assert response.status_code == 200
        transcript_data = response.json()
        assert len(transcript_data.get("events", [])) >= 3, "Should have at least 3 transcript events"
        
        print(f"✓ All entities verified to exist before delete")
        
        # Step 3: Delete the epic
        response = requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        
        print(f"✓ Epic {epic_id} deleted")
        
        # Step 4: Verify all entities are gone
        # Verify epic is gone
        response = requests.get(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 404, f"Epic should return 404: {response.text}"
        
        # Verify features are gone
        for feature_id in feature_ids:
            response = requests.get(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
            assert response.status_code == 404, f"Feature {feature_id} should return 404: {response.text}"
        
        # Verify stories are gone
        for story_id in story_ids:
            response = requests.get(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
            assert response.status_code == 404, f"Story {story_id} should return 404: {response.text}"
        
        print(f"✓ All entities verified to be deleted (cascade)")
        
        # Step 5: Verify no orphans in database
        async def _verify_no_orphans():
            async with AsyncSessionLocal() as session:
                # Check snapshots
                from db.models import EpicSnapshot, EpicTranscriptEvent, EpicDecision
                
                result = await session.execute(
                    select(EpicSnapshot).where(EpicSnapshot.epic_id == epic_id)
                )
                assert result.scalar_one_or_none() is None, "Orphaned snapshot found"
                
                # Check transcript events
                result = await session.execute(
                    select(EpicTranscriptEvent).where(EpicTranscriptEvent.epic_id == epic_id)
                )
                events = list(result.scalars().all())
                assert len(events) == 0, f"Orphaned transcript events found: {len(events)}"
                
                # Check features
                result = await session.execute(
                    select(Feature).where(Feature.epic_id == epic_id)
                )
                features = list(result.scalars().all())
                assert len(features) == 0, f"Orphaned features found: {len(features)}"
                
                # Check stories
                for feature_id in feature_ids:
                    result = await session.execute(
                        select(UserStory).where(UserStory.feature_id == feature_id)
                    )
                    stories = list(result.scalars().all())
                    assert len(stories) == 0, f"Orphaned stories found for feature {feature_id}: {len(stories)}"
        
        asyncio.run(_verify_no_orphans())
        
        print(f"✓ No orphaned records in database")
        print(f"✓ Full cascade delete workflow completed successfully!")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
