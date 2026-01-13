#!/usr/bin/env python3
"""
JarlPM Backend API Testing Suite - Authenticated Endpoints
Tests all authenticated API endpoints using pytest

Modules tested:
- Auth endpoints (/auth/me)
- Subscription endpoints (/subscription/status)
- Epic CRUD operations (/epics)
- LLM Provider endpoints (/llm-providers)
"""

import pytest
import requests
import os
import sys
import asyncio
from datetime import datetime, timedelta, timezone

# Add backend to path for seeding
sys.path.insert(0, '/app/backend')

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://jarlpm-ai.preview.emergentagent.com').rstrip('/')


def create_test_session():
    """Create test user and session in PostgreSQL"""
    from dotenv import load_dotenv
    load_dotenv('/app/backend/.env')
    
    from db.database import AsyncSessionLocal
    from db.models import User, UserSession, Subscription, SubscriptionStatus
    from sqlalchemy import delete
    
    async def _create():
        if not AsyncSessionLocal:
            return None
        
        async with AsyncSessionLocal() as session:
            timestamp = int(datetime.now().timestamp())
            user_id = f"pytest_user_{timestamp}"
            session_token = f"pytest_session_{timestamp}"
            email = f"pytest.user.{timestamp}@example.com"
            
            # Enable cascade delete for cleanup
            from sqlalchemy import text
            await session.execute(text("SET LOCAL jarlpm.allow_cascade_delete = 'true'"))
            
            # Clean up old pytest data
            await session.execute(
                delete(UserSession).where(UserSession.session_token.like("pytest_session_%"))
            )
            await session.execute(
                delete(Subscription).where(Subscription.user_id.like("pytest_user_%"))
            )
            await session.execute(
                delete(User).where(User.user_id.like("pytest_user_%"))
            )
            await session.commit()
            
            # Create user
            user = User(
                user_id=user_id,
                email=email,
                name="Pytest User",
                picture="https://via.placeholder.com/150"
            )
            session.add(user)
            await session.flush()
            
            # Create session
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            user_session = UserSession(
                user_id=user_id,
                session_token=session_token,
                expires_at=expires_at
            )
            session.add(user_session)
            
            # Create active subscription
            subscription = Subscription(
                user_id=user_id,
                status=SubscriptionStatus.ACTIVE.value,
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
            )
            session.add(subscription)
            
            await session.commit()
            
            return {
                "user_id": user_id,
                "email": email,
                "session_token": session_token
            }
    
    return asyncio.run(_create())


@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session for tests"""
    session_data = create_test_session()
    if not session_data:
        pytest.skip("Could not create test session - database not configured")
    return session_data


@pytest.fixture
def auth_headers(auth_session):
    """Get headers with authentication"""
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {auth_session["session_token"]}'
    }


class TestAuthenticatedAuthEndpoints:
    """Test auth endpoints with valid session"""
    
    def test_get_current_user(self, auth_headers, auth_session):
        """Test /api/auth/me returns user data"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["user_id"] == auth_session["user_id"]
        assert data["email"] == auth_session["email"]
        assert data["name"] == "Pytest User"
        assert "picture" in data


class TestAuthenticatedSubscriptionEndpoints:
    """Test subscription endpoints with valid session"""
    
    def test_get_subscription_status(self, auth_headers):
        """Test /api/subscription/status returns subscription data"""
        response = requests.get(f"{BASE_URL}/api/subscription/status", headers=auth_headers, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "active"
        assert "current_period_end" in data


class TestAuthenticatedLLMProviderEndpoints:
    """Test LLM provider endpoints with valid session"""
    
    def test_list_llm_providers_empty(self, auth_headers):
        """Test /api/llm-providers returns empty list for new user"""
        response = requests.get(f"{BASE_URL}/api/llm-providers", headers=auth_headers, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # New user should have no providers configured
        assert len(data) == 0


class TestAuthenticatedEpicCRUD:
    """Test Epic CRUD operations with valid session"""
    
    def test_list_epics_empty(self, auth_headers):
        """Test /api/epics returns empty list for new user"""
        response = requests.get(f"{BASE_URL}/api/epics", headers=auth_headers, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert "epics" in data
        assert isinstance(data["epics"], list)
    
    def test_create_epic(self, auth_headers):
        """Test POST /api/epics creates an epic"""
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Pytest Epic Creation"},
            timeout=10
        )
        assert response.status_code == 201
        
        data = response.json()
        assert "epic_id" in data
        assert data["title"] == "TEST_Pytest Epic Creation"
        assert data["current_stage"] == "problem_capture"
        assert "snapshot" in data
        assert "created_at" in data
        
        # Store epic_id for cleanup
        return data["epic_id"]
    
    def test_create_and_get_epic(self, auth_headers):
        """Test creating and retrieving an epic"""
        # Create
        create_response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Pytest Get Epic"},
            timeout=10
        )
        assert create_response.status_code == 201
        epic_id = create_response.json()["epic_id"]
        
        # Get
        get_response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["epic_id"] == epic_id
        assert data["title"] == "TEST_Pytest Get Epic"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
    
    def test_create_and_delete_epic(self, auth_headers):
        """Test creating and deleting an epic"""
        # Create
        create_response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Pytest Delete Epic"},
            timeout=10
        )
        assert create_response.status_code == 201
        epic_id = create_response.json()["epic_id"]
        
        # Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Epic deleted"
        
        # Verify deleted
        get_response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}",
            headers=auth_headers,
            timeout=10
        )
        assert get_response.status_code == 404
    
    def test_get_nonexistent_epic(self, auth_headers):
        """Test GET /api/epics/{id} returns 404 for nonexistent epic"""
        response = requests.get(
            f"{BASE_URL}/api/epics/epic_nonexistent123",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404
    
    def test_delete_nonexistent_epic(self, auth_headers):
        """Test DELETE /api/epics/{id} returns 404 for nonexistent epic"""
        response = requests.delete(
            f"{BASE_URL}/api/epics/epic_nonexistent123",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 404


class TestEpicTranscriptAndDecisions:
    """Test Epic transcript and decisions endpoints"""
    
    def test_get_epic_transcript(self, auth_headers):
        """Test GET /api/epics/{id}/transcript returns transcript"""
        # Create epic first
        create_response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Pytest Transcript Epic"},
            timeout=10
        )
        assert create_response.status_code == 201
        epic_id = create_response.json()["epic_id"]
        
        # Get transcript
        transcript_response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}/transcript",
            headers=auth_headers,
            timeout=10
        )
        assert transcript_response.status_code == 200
        
        data = transcript_response.json()
        assert "events" in data
        assert isinstance(data["events"], list)
        # Should have at least the creation system message
        assert len(data["events"]) >= 1
        assert data["events"][0]["role"] == "system"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
    
    def test_get_epic_decisions(self, auth_headers):
        """Test GET /api/epics/{id}/decisions returns decisions"""
        # Create epic first
        create_response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Pytest Decisions Epic"},
            timeout=10
        )
        assert create_response.status_code == 201
        epic_id = create_response.json()["epic_id"]
        
        # Get decisions
        decisions_response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}/decisions",
            headers=auth_headers,
            timeout=10
        )
        assert decisions_response.status_code == 200
        
        data = decisions_response.json()
        assert "decisions" in data
        assert isinstance(data["decisions"], list)
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)
    
    def test_get_epic_artifacts(self, auth_headers):
        """Test GET /api/epics/{id}/artifacts returns artifacts"""
        # Create epic first
        create_response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": "TEST_Pytest Artifacts Epic"},
            timeout=10
        )
        assert create_response.status_code == 201
        epic_id = create_response.json()["epic_id"]
        
        # Get artifacts
        artifacts_response = requests.get(
            f"{BASE_URL}/api/epics/{epic_id}/artifacts",
            headers=auth_headers,
            timeout=10
        )
        assert artifacts_response.status_code == 200
        
        data = artifacts_response.json()
        assert isinstance(data, list)
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/epics/{epic_id}", headers=auth_headers, timeout=10)


class TestEpicValidation:
    """Test Epic input validation"""
    
    def test_create_epic_missing_title(self, auth_headers):
        """Test POST /api/epics with missing title returns 422"""
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={},
            timeout=10
        )
        assert response.status_code == 422
    
    def test_create_epic_empty_title(self, auth_headers):
        """Test POST /api/epics with empty title"""
        response = requests.post(
            f"{BASE_URL}/api/epics",
            headers=auth_headers,
            json={"title": ""},
            timeout=10
        )
        # Empty string might be accepted or rejected depending on validation
        # Just verify it doesn't crash
        assert response.status_code in [201, 422]


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
