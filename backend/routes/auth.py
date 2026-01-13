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
from db.models import User, UserSession, Subscription, SubscriptionStatus, ProductDeliveryContext, LLMProviderConfig
from services.encryption import get_encryption_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Test user credentials
TEST_USER_EMAIL = "testuser@jarlpm.dev"
TEST_USER_NAME = "Test User"
TEST_SESSION_TOKEN = "test_session_jarlpm_full_access_2025"

# Test user default configurations
TEST_USER_DELIVERY_CONTEXT = {
    "industry": "Healthcare, Pharmacy",
    "delivery_methodology": "agile",
    "sprint_cycle_length": 14,
    "sprint_start_date": datetime(2026, 1, 14, tzinfo=timezone.utc),
    "num_developers": 5,
    "num_qa": 3,
    "delivery_platform": "jira",
}

TEST_USER_LLM_CONFIG = {
    "provider": "openai",
    "api_key": "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",
    "model_name": "gpt-4o",
}


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


@router.post("/test-login")
async def test_login(
    response: Response,
    session: AsyncSession = Depends(get_db)
):
    """
    Login as test user with full access (active subscription).
    Automatically sets up delivery context and LLM provider.
    For development/testing purposes only.
    """
    encryption = get_encryption_service()
    
    # Check if test user exists
    result = await session.execute(select(User).where(User.email == TEST_USER_EMAIL))
    user = result.scalar_one_or_none()
    
    if not user:
        # Create test user
        user_id = f"user_test_{uuid.uuid4().hex[:8]}"
        user = User(
            user_id=user_id,
            email=TEST_USER_EMAIL,
            name=TEST_USER_NAME,
            picture=None
        )
        session.add(user)
        await session.flush()
        
        # Create ACTIVE subscription for test user (1 year from now)
        subscription = Subscription(
            user_id=user_id,
            status=SubscriptionStatus.ACTIVE.value,
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + relativedelta(years=1)
        )
        session.add(subscription)
        logger.info(f"Created test user: {user_id} with active subscription")
    else:
        user_id = user.user_id
        # Ensure subscription is active
        sub_result = await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        subscription = sub_result.scalar_one_or_none()
        if subscription:
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.current_period_end = datetime.now(timezone.utc) + relativedelta(years=1)
        else:
            subscription = Subscription(
                user_id=user_id,
                status=SubscriptionStatus.ACTIVE.value,
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + relativedelta(years=1)
            )
            session.add(subscription)
    
    # Set up or update delivery context for test user
    ctx_result = await session.execute(
        select(ProductDeliveryContext).where(ProductDeliveryContext.user_id == user_id)
    )
    delivery_context = ctx_result.scalar_one_or_none()
    
    if delivery_context:
        # Update existing
        delivery_context.industry = TEST_USER_DELIVERY_CONTEXT["industry"]
        delivery_context.delivery_methodology = TEST_USER_DELIVERY_CONTEXT["delivery_methodology"]
        delivery_context.sprint_cycle_length = TEST_USER_DELIVERY_CONTEXT["sprint_cycle_length"]
        delivery_context.sprint_start_date = TEST_USER_DELIVERY_CONTEXT["sprint_start_date"]
        delivery_context.num_developers = TEST_USER_DELIVERY_CONTEXT["num_developers"]
        delivery_context.num_qa = TEST_USER_DELIVERY_CONTEXT["num_qa"]
        delivery_context.delivery_platform = TEST_USER_DELIVERY_CONTEXT["delivery_platform"]
        delivery_context.updated_at = datetime.now(timezone.utc)
    else:
        # Create new
        delivery_context = ProductDeliveryContext(
            user_id=user_id,
            industry=TEST_USER_DELIVERY_CONTEXT["industry"],
            delivery_methodology=TEST_USER_DELIVERY_CONTEXT["delivery_methodology"],
            sprint_cycle_length=TEST_USER_DELIVERY_CONTEXT["sprint_cycle_length"],
            sprint_start_date=TEST_USER_DELIVERY_CONTEXT["sprint_start_date"],
            num_developers=TEST_USER_DELIVERY_CONTEXT["num_developers"],
            num_qa=TEST_USER_DELIVERY_CONTEXT["num_qa"],
            delivery_platform=TEST_USER_DELIVERY_CONTEXT["delivery_platform"],
        )
        session.add(delivery_context)
    logger.info(f"Set up delivery context for test user: {user_id}")
    
    # Set up or update LLM provider config for test user
    llm_result = await session.execute(
        select(LLMProviderConfig).where(
            LLMProviderConfig.user_id == user_id,
            LLMProviderConfig.provider == TEST_USER_LLM_CONFIG["provider"]
        )
    )
    llm_config = llm_result.scalar_one_or_none()
    
    encrypted_key = encryption.encrypt(TEST_USER_LLM_CONFIG["api_key"])
    
    if llm_config:
        # Update existing
        llm_config.encrypted_api_key = encrypted_key
        llm_config.model_name = TEST_USER_LLM_CONFIG["model_name"]
        llm_config.is_active = True
        llm_config.updated_at = datetime.now(timezone.utc)
    else:
        # Create new
        llm_config = LLMProviderConfig(
            user_id=user_id,
            provider=TEST_USER_LLM_CONFIG["provider"],
            encrypted_api_key=encrypted_key,
            model_name=TEST_USER_LLM_CONFIG["model_name"],
            is_active=True
        )
        session.add(llm_config)
    logger.info(f"Set up LLM config (OpenAI) for test user: {user_id}")
    
    # Remove old sessions for this user
    await session.execute(
        delete(UserSession).where(UserSession.user_id == user_id)
    )
    
    # Create new session with long expiry
    expires_at = datetime.now(timezone.utc) + timedelta(days=365)
    user_session = UserSession(
        user_id=user_id,
        session_token=TEST_SESSION_TOKEN,
        expires_at=expires_at
    )
    session.add(user_session)
    
    await session.commit()
    
    # Set httpOnly cookie
    response.set_cookie(
        key="session_token",
        value=TEST_SESSION_TOKEN,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=365 * 24 * 60 * 60  # 1 year
    )
    
    return {
        "message": "Logged in as test user",
        "user_id": user_id,
        "email": TEST_USER_EMAIL,
        "name": TEST_USER_NAME,
        "subscription_status": "active",
        "delivery_context": "configured",
        "llm_provider": "openai (gpt-4o)"
    }


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
