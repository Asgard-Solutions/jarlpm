#!/usr/bin/env python3
"""
JarlPM Test Data Seeder for PostgreSQL
Creates test user, session, and subscription for authenticated API testing
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
import uuid

# Add backend to path
sys.path.insert(0, '/app/backend')

from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

from sqlalchemy import select, delete
from db.database import AsyncSessionLocal, engine
from db.models import User, UserSession, Subscription, SubscriptionStatus


async def create_test_data():
    """Create test user, session, and subscription"""
    
    if not AsyncSessionLocal:
        print("ERROR: Database not configured")
        return None
    
    async with AsyncSessionLocal() as session:
        # Generate unique test identifiers
        timestamp = int(datetime.now().timestamp())
        user_id = f"test_user_{timestamp}"
        session_token = f"test_session_{timestamp}"
        email = f"test.user.{timestamp}@example.com"
        
        # Clean up any existing test data first
        await session.execute(
            delete(UserSession).where(UserSession.session_token.like("test_session_%"))
        )
        await session.execute(
            delete(Subscription).where(Subscription.user_id.like("test_user_%"))
        )
        await session.execute(
            delete(User).where(User.user_id.like("test_user_%"))
        )
        await session.commit()
        
        # Create test user
        user = User(
            user_id=user_id,
            email=email,
            name="Test User",
            picture="https://via.placeholder.com/150"
        )
        session.add(user)
        await session.flush()
        
        # Create session (expires in 7 days)
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
        
        print(f"Created test data:")
        print(f"  User ID: {user_id}")
        print(f"  Email: {email}")
        print(f"  Session Token: {session_token}")
        print(f"  Subscription: ACTIVE")
        
        return {
            "user_id": user_id,
            "email": email,
            "session_token": session_token
        }


async def cleanup_test_data():
    """Clean up test data"""
    if not AsyncSessionLocal:
        print("ERROR: Database not configured")
        return
    
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(UserSession).where(UserSession.session_token.like("test_session_%"))
        )
        await session.execute(
            delete(Subscription).where(Subscription.user_id.like("test_user_%"))
        )
        await session.execute(
            delete(User).where(User.user_id.like("test_user_%"))
        )
        await session.commit()
        print("Test data cleaned up")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        asyncio.run(cleanup_test_data())
    else:
        result = asyncio.run(create_test_data())
        if result:
            # Output just the session token for easy capture
            print(f"\nSESSION_TOKEN={result['session_token']}")
