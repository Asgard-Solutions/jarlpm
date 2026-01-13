#!/usr/bin/env python3
"""
Seed script to create test data for lock policy testing.
Creates a locked epic with approved features and user stories.
"""

import requests
import os
import sys
import asyncio
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pm-workspace-2.preview.emergentagent.com').rstrip('/')
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"


def create_locked_epic_with_data():
    """Create a locked epic with approved feature and stories for testing"""
    from dotenv import load_dotenv
    load_dotenv('/app/backend/.env')
    
    # First ensure test user exists
    login_response = requests.post(f"{BASE_URL}/api/auth/test-login", timeout=10)
    if login_response.status_code != 200:
        print(f"Failed to login: {login_response.text}")
        return None
    
    user_id = login_response.json()["user_id"]
    print(f"Test user: {user_id}")
    
    # Import database models
    from db.database import AsyncSessionLocal
    from db.models import Epic, EpicSnapshot, EpicStage
    from db.feature_models import Feature, FeatureStage
    from db.user_story_models import UserStory, UserStoryStage
    import uuid
    
    async def _create_data():
        async with AsyncSessionLocal() as session:
            # Create a locked epic
            epic_id = f"epic_locktest_{uuid.uuid4().hex[:8]}"
            
            epic = Epic(
                epic_id=epic_id,
                user_id=user_id,
                title="TEST_Lock Policy Testing Epic",
                current_stage=EpicStage.EPIC_LOCKED.value
            )
            session.add(epic)
            await session.flush()
            
            # Create snapshot
            snapshot = EpicSnapshot(
                epic_id=epic_id,
                problem_statement="Users need a way to manage product features efficiently with proper locking",
                desired_outcome="A streamlined feature planning workflow with state-driven locking",
                epic_summary="Build a feature planning system with lock policy enforcement",
                acceptance_criteria=[
                    "Features can be created during Feature Planning Mode",
                    "Approved features cannot be edited",
                    "User stories can be created for approved features",
                    "Approved stories cannot be edited"
                ],
                epic_locked_at=datetime.now(timezone.utc)
            )
            session.add(snapshot)
            
            # Create an approved feature
            approved_feature_id = f"feat_approved_{uuid.uuid4().hex[:8]}"
            approved_feature = Feature(
                feature_id=approved_feature_id,
                epic_id=epic_id,
                title="TEST_Approved Feature for Stories",
                description="An approved feature that can have user stories",
                acceptance_criteria=[
                    "Given a feature, When approved, Then it becomes immutable",
                    "Given an approved feature, When stories are created, Then they start in draft"
                ],
                current_stage=FeatureStage.APPROVED.value,
                source="manual",
                approved_at=datetime.now(timezone.utc)
            )
            session.add(approved_feature)
            
            # Create a draft feature
            draft_feature_id = f"feat_draft_{uuid.uuid4().hex[:8]}"
            draft_feature = Feature(
                feature_id=draft_feature_id,
                epic_id=epic_id,
                title="TEST_Draft Feature",
                description="A draft feature that can be edited",
                current_stage=FeatureStage.DRAFT.value,
                source="manual"
            )
            session.add(draft_feature)
            
            # Create an approved story
            approved_story_id = f"story_approved_{uuid.uuid4().hex[:8]}"
            approved_story = UserStory(
                story_id=approved_story_id,
                feature_id=approved_feature_id,
                persona="product manager",
                action="view locked features",
                benefit="I understand what cannot be changed",
                story_text="As a product manager, I want to view locked features so that I understand what cannot be changed.",
                acceptance_criteria=[
                    "Given an approved feature, When I view it, Then I see a lock icon",
                    "Given an approved feature, When I try to edit, Then I see an error"
                ],
                current_stage=UserStoryStage.APPROVED.value,
                source="manual",
                story_points=3,
                approved_at=datetime.now(timezone.utc)
            )
            session.add(approved_story)
            
            # Create a draft story
            draft_story_id = f"story_draft_{uuid.uuid4().hex[:8]}"
            draft_story = UserStory(
                story_id=draft_story_id,
                feature_id=approved_feature_id,
                persona="developer",
                action="edit draft stories",
                benefit="I can refine requirements",
                story_text="As a developer, I want to edit draft stories so that I can refine requirements.",
                current_stage=UserStoryStage.DRAFT.value,
                source="manual",
                story_points=2
            )
            session.add(draft_story)
            
            await session.commit()
            
            return {
                "epic_id": epic_id,
                "approved_feature_id": approved_feature_id,
                "draft_feature_id": draft_feature_id,
                "approved_story_id": approved_story_id,
                "draft_story_id": draft_story_id
            }
    
    return asyncio.run(_create_data())


if __name__ == "__main__":
    result = create_locked_epic_with_data()
    if result:
        print(f"\nCreated test data:")
        print(f"  Epic ID: {result['epic_id']}")
        print(f"  Approved Feature ID: {result['approved_feature_id']}")
        print(f"  Draft Feature ID: {result['draft_feature_id']}")
        print(f"  Approved Story ID: {result['approved_story_id']}")
        print(f"  Draft Story ID: {result['draft_story_id']}")
    else:
        print("Failed to create test data")
        sys.exit(1)
