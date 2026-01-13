from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
import httpx
import logging
import uuid
import os

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import User, UserSession, Subscription, SubscriptionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Test user credentials
TEST_USER_EMAIL = "testuser@jarlpm.dev"
TEST_USER_NAME = "Test User"
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"


class SessionExchangeRequest(BaseModel):
    session_id: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    picture: str | None = None


@router.post("/session")
async def exchange_session(
    body: SessionExchangeRequest, 
    response: Response,
    session: AsyncSession = Depends(get_db)
):
    """Exchange Emergent session_id for session_token and user data"""
    try:
        # Call Emergent auth API to get user data
        async with httpx.AsyncClient() as client:
            auth_response = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": body.session_id},
                timeout=10.0
            )
            
            if auth_response.status_code != 200:
                logger.error(f"Emergent auth failed: {auth_response.status_code} - {auth_response.text}")
                raise HTTPException(status_code=401, detail="Invalid session")
            
            auth_data = auth_response.json()
    except httpx.RequestError as e:
        logger.error(f"Emergent auth request failed: {e}")
        raise HTTPException(status_code=500, detail="Authentication service unavailable")
    
    email = auth_data.get("email")
    session_token = auth_data.get("session_token")
    
    if not email or not session_token:
        raise HTTPException(status_code=401, detail="Invalid session data")
    
    # Check if user exists
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if user:
        # Update existing user
        user.name = auth_data.get("name", user.name)
        user.picture = auth_data.get("picture")
        user.updated_at = datetime.now(timezone.utc)
        user_id = user.user_id
    else:
        # Create new user
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = User(
            user_id=user_id,
            email=email,
            name=auth_data.get("name", email.split("@")[0]),
            picture=auth_data.get("picture")
        )
        session.add(user)
        await session.flush()
        
        # Create inactive subscription for new user
        subscription = Subscription(
            user_id=user_id,
            status=SubscriptionStatus.INACTIVE
        )
        session.add(subscription)
    
    # Remove old sessions for this user
    await session.execute(
        delete(UserSession).where(UserSession.user_id == user_id)
    )
    
    # Store new session
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    user_session = UserSession(
        user_id=user_id,
        session_token=session_token,
        expires_at=expires_at
    )
    session.add(user_session)
    
    await session.commit()
    
    # Set httpOnly cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    return {
        "user_id": user_id,
        "email": email,
        "name": auth_data.get("name", email.split("@")[0]),
        "picture": auth_data.get("picture")
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get current user from session token"""
    user_id = await get_current_user_id(request, session)
    
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        picture=user.picture
    )


@router.post("/logout")
async def logout(
    request: Request, 
    response: Response,
    session: AsyncSession = Depends(get_db)
):
    """Logout and clear session"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await session.execute(
            delete(UserSession).where(UserSession.session_token == session_token)
        )
        await session.commit()
    
    response.delete_cookie(
        key="session_token",
        path="/",
        secure=True,
        samesite="none"
    )
    
    return {"message": "Logged out successfully"}


# Helper function to get current user (for use in other routes)
async def get_current_user_id(request: Request, session: AsyncSession) -> str:
    """Extract and validate current user ID from request"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    result = await session.execute(
        select(UserSession).where(UserSession.session_token == session_token)
    )
    user_session = result.scalar_one_or_none()
    
    if not user_session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Check expiry
    if user_session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    return user_session.user_id
