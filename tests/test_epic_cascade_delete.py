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
- Database integrity after delete
"""

import pytest
import requests
import os
import sys
import asyncio
from datetime import datetime, timezone
import uuid
import time

# Add backend to path
sys.path.insert(0, '/app/backend')

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://priorityforge.preview.emergentagent.com').rstrip('/')

# Test user credentials (created by Test Login button)
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"


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
        print(f"✓ Epic creation test passed")


class TestFeatureCreationForEpic:
    """Test Feature creation for an Epic"""
    
    def test_create_feature_for_locked_epic(self, auth_headers, test_user_id):
        """Test creating a feature for a locked epic"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        
        # Create a locked epic directly in DB
        async def _create_locked_epic():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_feat_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=test_user_id,
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
        
        try:
            # Create feature via API
            response = requests.post(
                f"{BASE_URL}/api/features/epic/{epic_id}",
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
            assert data["epic_id"] == epic_id
            
            print(f"✓ Feature {data['feature_id']} created for epic {epic_id}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)


class TestUserStoryCreationForFeature:
    """Test User Story creation for a Feature"""
    
    def test_create_story_for_approved_feature(self, auth_headers, test_user_id):
        """Test creating a user story for an approved feature"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        from db.feature_models import Feature, FeatureStage
        
        # Create a locked epic with approved feature
        async def _create_approved_feature():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_story_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=test_user_id,
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
        epic_id = data["epic_id"]
        feature_id = data["feature_id"]
        
        try:
            # Create story via API
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
            
            story_data = response.json()
            assert "story_id" in story_data
            assert story_data["persona"] == "test user"
            assert story_data["feature_id"] == feature_id
            
            print(f"✓ Story {story_data['story_id']} created for feature {feature_id}")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)


class TestEpicCascadeDelete:
    """Test Epic DELETE endpoint cascades to all related entities"""
    
    def test_cascade_delete_features(self, auth_headers, test_user_id):
        """Test that deleting an epic cascades to delete features"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        from db.feature_models import Feature, FeatureStage
        
        # Create epic with feature
        async def _create_epic_with_feature():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_cascade_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=test_user_id,
                    title="TEST_Cascade Feature Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Cascade test problem"
                )
                session.add(snapshot)
                
                feature_id = f"feat_cascade_{uuid.uuid4().hex[:8]}"
                feature = Feature(
                    feature_id=feature_id,
                    epic_id=epic_id,
                    title="TEST_Cascade Feature",
                    description="Feature for cascade test",
                    current_stage=FeatureStage.DRAFT.value,
                    source="manual"
                )
                session.add(feature)
                await session.commit()
                
                return {"epic_id": epic_id, "feature_id": feature_id}
        
        data = asyncio.run(_create_epic_with_feature())
        epic_id = data["epic_id"]
        feature_id = data["feature_id"]
        
        # Verify feature exists
        response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Feature should exist before delete: {response.text}"
        print(f"✓ Feature {feature_id} exists before epic delete")
        
        # Delete epic
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify feature is gone
        response = requests.get(
            f"{BASE_URL}/api/features/{feature_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Feature should return 404 after epic delete: {response.text}"
        print(f"✓ Feature {feature_id} returns 404 after epic delete (cascade)")
    
    def test_cascade_delete_user_stories(self, auth_headers, test_user_id):
        """Test that deleting an epic cascades to delete user stories via feature"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        from db.feature_models import Feature, FeatureStage
        from db.user_story_models import UserStory, UserStoryStage
        
        # Create epic with feature and story
        async def _create_epic_with_story():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_story_cascade_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=test_user_id,
                    title="TEST_Cascade Story Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Story cascade test problem"
                )
                session.add(snapshot)
                
                feature_id = f"feat_story_cascade_{uuid.uuid4().hex[:8]}"
                feature = Feature(
                    feature_id=feature_id,
                    epic_id=epic_id,
                    title="TEST_Cascade Story Feature",
                    description="Feature for story cascade test",
                    current_stage=FeatureStage.APPROVED.value,
                    source="manual",
                    approved_at=datetime.now(timezone.utc)
                )
                session.add(feature)
                await session.flush()
                
                story_id = f"story_cascade_{uuid.uuid4().hex[:8]}"
                story = UserStory(
                    story_id=story_id,
                    feature_id=feature_id,
                    persona="cascade user",
                    action="test cascade",
                    benefit="verify cascade",
                    story_text="As a cascade user, I want to test cascade so that verify cascade.",
                    current_stage=UserStoryStage.DRAFT.value,
                    source="manual"
                )
                session.add(story)
                await session.commit()
                
                return {"epic_id": epic_id, "feature_id": feature_id, "story_id": story_id}
        
        data = asyncio.run(_create_epic_with_story())
        epic_id = data["epic_id"]
        feature_id = data["feature_id"]
        story_id = data["story_id"]
        
        # Verify story exists
        response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Story should exist before delete: {response.text}"
        print(f"✓ Story {story_id} exists before epic delete")
        
        # Delete epic
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify story is gone
        response = requests.get(
            f"{BASE_URL}/api/stories/{story_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Story should return 404 after epic delete: {response.text}"
        print(f"✓ Story {story_id} returns 404 after epic delete (cascade via feature)")
    
    def test_cascade_delete_transcript_events(self, auth_headers, test_user_id):
        """Test that deleting an epic cascades to delete transcript events"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage, EpicTranscriptEvent
        from sqlalchemy import select
        
        # Create epic with transcript events
        async def _create_epic_with_transcript():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_transcript_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=test_user_id,
                    title="TEST_Cascade Transcript Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Transcript cascade test problem"
                )
                session.add(snapshot)
                
                # Add multiple transcript events
                for i in range(3):
                    event = EpicTranscriptEvent(
                        epic_id=epic_id,
                        role="system",
                        content=f"Transcript event {i+1}",
                        stage=EpicStage.EPIC_LOCKED.value
                    )
                    session.add(event)
                
                await session.commit()
                return epic_id
        
        epic_id = asyncio.run(_create_epic_with_transcript())
        
        # Verify transcript events exist
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}/transcript",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        transcript_data = response.json()
        assert len(transcript_data.get("events", [])) >= 3, "Should have at least 3 transcript events"
        print(f"✓ Transcript events exist before epic delete: {len(transcript_data.get('events', []))} events")
        
        # Delete epic
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify transcript events are gone (epic returns 404)
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}/transcript",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404, f"Transcript should return 404 after epic delete: {response.text}"
        print(f"✓ Transcript returns 404 after epic delete (cascade)")
        
        # Verify no orphaned transcript events in DB
        async def _check_orphans():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(EpicTranscriptEvent).where(EpicTranscriptEvent.epic_id == epic_id)
                )
                return list(result.scalars().all())
        
        events = asyncio.run(_check_orphans())
        assert len(events) == 0, f"Orphaned transcript events found: {len(events)}"
        print(f"✓ No orphaned transcript events in database")
    
    def test_cascade_delete_snapshots(self, auth_headers, test_user_id):
        """Test that deleting an epic cascades to delete snapshots"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage
        from sqlalchemy import select
        
        # Create epic with snapshot
        async def _create_epic_with_snapshot():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_snapshot_{uuid.uuid4().hex[:8]}"
                
                epic = Epic(
                    epic_id=epic_id,
                    user_id=test_user_id,
                    title="TEST_Cascade Snapshot Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Snapshot cascade test problem",
                    desired_outcome="Snapshot cascade test outcome",
                    epic_summary="Snapshot cascade test summary",
                    acceptance_criteria=["Criterion 1", "Criterion 2"]
                )
                session.add(snapshot)
                await session.commit()
                
                return epic_id
        
        epic_id = asyncio.run(_create_epic_with_snapshot())
        
        # Verify epic with snapshot exists
        response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200
        epic_data = response.json()
        assert epic_data["snapshot"]["problem_statement"] == "Snapshot cascade test problem"
        print(f"✓ Epic with snapshot exists before delete")
        
        # Delete epic
        response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify no orphaned snapshot in DB
        async def _check_orphans():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(EpicSnapshot).where(EpicSnapshot.epic_id == epic_id)
                )
                return result.scalar_one_or_none()
        
        snapshot = asyncio.run(_check_orphans())
        assert snapshot is None, f"Orphaned snapshot found for epic {epic_id}"
        print(f"✓ No orphaned snapshot in database")


class TestDatabaseIntegrityAfterDelete:
    """Verify database has no orphaned records after Epic delete"""
    
    def test_no_orphaned_records_after_full_delete(self, auth_headers, test_user_id):
        """Verify no orphaned records in database after deleting epic with all children"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from db.database import AsyncSessionLocal
        from db.models import Epic, EpicSnapshot, EpicStage, EpicTranscriptEvent, EpicDecision
        from db.feature_models import Feature, FeatureStage, FeatureConversationEvent
        from db.user_story_models import UserStory, UserStoryStage, UserStoryConversationEvent
        from sqlalchemy import select
        
        # Create full hierarchy
        async def _create_full_hierarchy():
            async with AsyncSessionLocal() as session:
                epic_id = f"epic_full_{uuid.uuid4().hex[:8]}"
                
                # Create epic
                epic = Epic(
                    epic_id=epic_id,
                    user_id=test_user_id,
                    title="TEST_Full Cascade Epic",
                    current_stage=EpicStage.EPIC_LOCKED.value
                )
                session.add(epic)
                await session.flush()
                
                # Create snapshot
                snapshot = EpicSnapshot(
                    epic_id=epic_id,
                    problem_statement="Full cascade problem",
                    desired_outcome="Full cascade outcome",
                    epic_summary="Full cascade summary"
                )
                session.add(snapshot)
                
                # Create transcript events
                for i in range(2):
                    event = EpicTranscriptEvent(
                        epic_id=epic_id,
                        role="system",
                        content=f"Event {i+1}",
                        stage=EpicStage.EPIC_LOCKED.value
                    )
                    session.add(event)
                
                # Create decision
                decision = EpicDecision(
                    epic_id=epic_id,
                    user_id=test_user_id,
                    decision_type="confirm_proposal",
                    from_stage=EpicStage.PROBLEM_CAPTURE.value,
                    to_stage=EpicStage.PROBLEM_CONFIRMED.value
                )
                session.add(decision)
                
                # Create features with stories
                feature_ids = []
                story_ids = []
                for i in range(2):
                    feature_id = f"feat_full_{uuid.uuid4().hex[:8]}"
                    feature = Feature(
                        feature_id=feature_id,
                        epic_id=epic_id,
                        title=f"TEST_Full Feature {i+1}",
                        description=f"Full feature {i+1}",
                        current_stage=FeatureStage.APPROVED.value,
                        source="manual",
                        approved_at=datetime.now(timezone.utc)
                    )
                    session.add(feature)
                    await session.flush()
                    feature_ids.append(feature_id)
                    
                    # Create feature conversation
                    feat_conv = FeatureConversationEvent(
                        feature_id=feature_id,
                        role="system",
                        content=f"Feature {i+1} conversation"
                    )
                    session.add(feat_conv)
                    
                    # Create stories
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
                        await session.flush()
                        story_ids.append(story_id)
                        
                        # Create story conversation
                        story_conv = UserStoryConversationEvent(
                            story_id=story_id,
                            role="system",
                            content=f"Story {j+1} conversation"
                        )
                        session.add(story_conv)
                
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
        
        # Verify all exist
        response = requests.get(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Epic should exist: {response.text}"
        
        for feature_id in feature_ids:
            response = requests.get(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
            assert response.status_code == 200, f"Feature {feature_id} should exist: {response.text}"
        
        for story_id in story_ids:
            response = requests.get(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
            assert response.status_code == 200, f"Story {story_id} should exist: {response.text}"
        
        print(f"✓ All entities verified to exist before delete")
        
        # Delete epic
        response = requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Epic delete should succeed: {response.text}"
        print(f"✓ Epic {epic_id} deleted")
        
        # Verify all are gone via API
        response = requests.get(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
        assert response.status_code == 404, f"Epic should return 404: {response.text}"
        
        for feature_id in feature_ids:
            response = requests.get(f"{BASE_URL}/api/features/{feature_id}", headers=auth_headers, timeout=10)
            assert response.status_code == 404, f"Feature {feature_id} should return 404: {response.text}"
        
        for story_id in story_ids:
            response = requests.get(f"{BASE_URL}/api/stories/{story_id}", headers=auth_headers, timeout=10)
            assert response.status_code == 404, f"Story {story_id} should return 404: {response.text}"
        
        print(f"✓ All entities verified to be deleted via API")
        
        # Verify no orphans in database
        async def _verify_no_orphans():
            async with AsyncSessionLocal() as session:
                # Check snapshots
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
                
                # Check decisions
                result = await session.execute(
                    select(EpicDecision).where(EpicDecision.epic_id == epic_id)
                )
                decisions = list(result.scalars().all())
                assert len(decisions) == 0, f"Orphaned decisions found: {len(decisions)}"
                
                # Check features
                result = await session.execute(
                    select(Feature).where(Feature.epic_id == epic_id)
                )
                features = list(result.scalars().all())
                assert len(features) == 0, f"Orphaned features found: {len(features)}"
                
                # Check feature conversations
                for feature_id in feature_ids:
                    result = await session.execute(
                        select(FeatureConversationEvent).where(FeatureConversationEvent.feature_id == feature_id)
                    )
                    convs = list(result.scalars().all())
                    assert len(convs) == 0, f"Orphaned feature conversations found: {len(convs)}"
                
                # Check stories
                for feature_id in feature_ids:
                    result = await session.execute(
                        select(UserStory).where(UserStory.feature_id == feature_id)
                    )
                    stories = list(result.scalars().all())
                    assert len(stories) == 0, f"Orphaned stories found: {len(stories)}"
                
                # Check story conversations
                for story_id in story_ids:
                    result = await session.execute(
                        select(UserStoryConversationEvent).where(UserStoryConversationEvent.story_id == story_id)
                    )
                    convs = list(result.scalars().all())
                    assert len(convs) == 0, f"Orphaned story conversations found: {len(convs)}"
        
        asyncio.run(_verify_no_orphans())
        
        print(f"✓ No orphaned records in database")
        print(f"✓ Full cascade delete test completed successfully!")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
