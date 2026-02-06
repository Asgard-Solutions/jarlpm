from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
import logging
import uuid
import bcrypt
import jwt
import os

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import User, UserSession, Subscription, SubscriptionStatus, ProductDeliveryContext, LLMProviderConfig, VerificationToken
from services.encryption import get_encryption_service
from services.email_service import get_email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# JWT Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "jarlpm-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7

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
    "api_key": os.environ.get("OPENAI_API_KEY", ""),
    "model_name": "gpt-4o",
}


# ============================================
# Request/Response Models
# ============================================

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    picture: str | None = None
    email_verified: bool = False


class AuthResponse(BaseModel):
    message: str
    user_id: str
    email: str
    name: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# ============================================
# Password Hashing Utilities
# ============================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def generate_session_token(user_id: str) -> str:
    """Generate a JWT session token"""
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_session_token(token: str) -> str | None:
    """Verify a JWT token and return user_id"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_verification_token() -> str:
    """Generate a random verification token"""
    import secrets
    return secrets.token_urlsafe(32)


# ============================================
# Auth Routes
# ============================================

@router.post("/signup", response_model=AuthResponse)
async def signup(
    body: SignupRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db)
):
    """Register a new user with email and password"""
    # Validate password strength
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Check if email already exists
    result = await session.execute(select(User).where(User.email == body.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(body.password)
    
    user = User(
        user_id=user_id,
        email=body.email,
        name=body.name,
        password_hash=password_hash
    )
    session.add(user)
    await session.flush()
    
    # Create inactive subscription for new user
    subscription = Subscription(
        user_id=user_id,
        status=SubscriptionStatus.INACTIVE.value
    )
    session.add(subscription)
    
    # Create email verification token
    verification_token = generate_verification_token()
    email_token = VerificationToken(
        user_id=user_id,
        token=verification_token,
        token_type="email_verification",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    session.add(email_token)
    
    # Generate session token
    session_token = generate_session_token(user_id)
    
    # Store session
    expires_at = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    user_session = UserSession(
        user_id=user_id,
        session_token=session_token,
        expires_at=expires_at
    )
    session.add(user_session)
    
    await session.commit()
    
    # Send verification email (async, non-blocking)
    email_service = get_email_service()
    # Get base URL from request origin or use a default
    base_url = str(request.headers.get("origin", "https://jarlpm-convtool.preview.emergentagent.com"))
    try:
        await email_service.send_verification_email(
            to_email=body.email,
            user_name=body.name,
            verification_token=verification_token,
            base_url=base_url
        )
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")
        # Don't fail signup if email fails
    
    # Set httpOnly cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60
    )
    
    logger.info(f"New user registered: {user_id} ({body.email})")
    
    return AuthResponse(
        message="Account created successfully",
        user_id=user_id,
        email=body.email,
        name=body.name
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db)
):
    """Login with email and password"""
    # Find user by email
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    if not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Remove old sessions for this user
    await session.execute(
        delete(UserSession).where(UserSession.user_id == user.user_id)
    )
    
    # Generate new session token
    session_token = generate_session_token(user.user_id)
    
    # Store session
    expires_at = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    user_session = UserSession(
        user_id=user.user_id,
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
        max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60
    )
    
    logger.info(f"User logged in: {user.user_id} ({user.email})")
    
    return AuthResponse(
        message="Login successful",
        user_id=user.user_id,
        email=user.email,
        name=user.name
    )


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
        picture=user.picture,
        email_verified=user.email_verified
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
            password_hash=hash_password("testpassword123"),
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
    
    # Set up or update LLM provider config for test user (only if OPENAI_API_KEY is set)
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        llm_result = await session.execute(
            select(LLMProviderConfig).where(
                LLMProviderConfig.user_id == user_id,
                LLMProviderConfig.provider == TEST_USER_LLM_CONFIG["provider"]
            )
        )
        llm_config = llm_result.scalar_one_or_none()
        
        encrypted_key = encryption.encrypt(openai_key)
        
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
        "llm_provider": "openai (gpt-4o)" if openai_key else "not configured"
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



# ============================================
# Email Verification Routes
# ============================================

EMAIL_VERIFICATION_EXPIRY_HOURS = 24
PASSWORD_RESET_EXPIRY_HOURS = 1


async def create_verification_token(
    session: AsyncSession,
    user_id: str,
    token_type: str,
    expiry_hours: int
) -> str:
    """Create a verification token for email verification or password reset"""
    # Invalidate any existing tokens of the same type
    await session.execute(
        delete(VerificationToken).where(
            VerificationToken.user_id == user_id,
            VerificationToken.token_type == token_type,
            VerificationToken.used_at.is_(None)
        )
    )
    
    # Create new token
    token = generate_verification_token()
    verification_token = VerificationToken(
        user_id=user_id,
        token=token,
        token_type=token_type,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
    )
    session.add(verification_token)
    await session.flush()
    
    return token


@router.post("/verify-email")
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db)
):
    """Verify user's email address using token"""
    # Find the token
    result = await session.execute(
        select(VerificationToken).where(
            VerificationToken.token == body.token,
            VerificationToken.token_type == "email_verification",
            VerificationToken.used_at.is_(None)
        )
    )
    verification_token = result.scalar_one_or_none()
    
    if not verification_token:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    
    # Check expiry
    if verification_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification link has expired")
    
    # Find the user
    result = await session.execute(
        select(User).where(User.user_id == verification_token.user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Mark email as verified
    user.email_verified = True
    user.updated_at = datetime.now(timezone.utc)
    
    # Mark token as used
    verification_token.used_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    logger.info(f"Email verified for user: {user.user_id}")
    
    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification_email(
    body: ResendVerificationRequest,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Resend email verification link"""
    # Find the user
    result = await session.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if email exists
        return {"message": "If the email exists, a verification link has been sent"}
    
    if user.email_verified:
        return {"message": "Email is already verified"}
    
    # Create new verification token
    token = await create_verification_token(
        session,
        user.user_id,
        "email_verification",
        EMAIL_VERIFICATION_EXPIRY_HOURS
    )
    
    await session.commit()
    
    # Send verification email
    email_service = get_email_service()
    base_url = str(request.headers.get("origin", "https://jarlpm-convtool.preview.emergentagent.com"))
    
    email_sent = await email_service.send_verification_email(
        to_email=user.email,
        user_name=user.name,
        verification_token=token,
        base_url=base_url
    )
    
    if email_sent:
        logger.info(f"Verification email sent to {user.email}")
    else:
        logger.warning(f"Failed to send verification email to {user.email}")
    
    return {"message": "Verification email sent"}


# ============================================
# Password Reset Routes
# ============================================

@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Request a password reset email"""
    # Find the user
    result = await session.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if email exists - always return success message
        return {"message": "If the email exists, a password reset link has been sent"}
    
    # Create password reset token
    token = await create_verification_token(
        session,
        user.user_id,
        "password_reset",
        PASSWORD_RESET_EXPIRY_HOURS
    )
    
    await session.commit()
    
    # Send password reset email
    email_service = get_email_service()
    base_url = str(request.headers.get("origin", "https://jarlpm-convtool.preview.emergentagent.com"))
    
    email_sent = await email_service.send_password_reset_email(
        to_email=user.email,
        user_name=user.name,
        reset_token=token,
        base_url=base_url
    )
    
    if email_sent:
        logger.info(f"Password reset email sent to {user.email}")
    else:
        logger.warning(f"Failed to send password reset email to {user.email}")
    
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db)
):
    """Reset password using token"""
    # Validate password
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Find the token
    result = await session.execute(
        select(VerificationToken).where(
            VerificationToken.token == body.token,
            VerificationToken.token_type == "password_reset",
            VerificationToken.used_at.is_(None)
        )
    )
    verification_token = result.scalar_one_or_none()
    
    if not verification_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    
    # Check expiry
    if verification_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Password reset link has expired")
    
    # Find the user
    result = await session.execute(
        select(User).where(User.user_id == verification_token.user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update password
    user.password_hash = hash_password(body.new_password)
    user.updated_at = datetime.now(timezone.utc)
    
    # Mark token as used
    verification_token.used_at = datetime.now(timezone.utc)
    
    # Invalidate all existing sessions for this user (force re-login)
    await session.execute(
        delete(UserSession).where(UserSession.user_id == user.user_id)
    )
    
    await session.commit()
    
    logger.info(f"Password reset for user: {user.user_id}")
    
    return {"message": "Password reset successfully. Please login with your new password."}


@router.get("/check-token/{token}")
async def check_token_validity(
    token: str,
    session: AsyncSession = Depends(get_db)
):
    """Check if a verification/reset token is valid"""
    result = await session.execute(
        select(VerificationToken).where(
            VerificationToken.token == token,
            VerificationToken.used_at.is_(None)
        )
    )
    verification_token = result.scalar_one_or_none()
    
    if not verification_token:
        return {"valid": False, "reason": "Token not found or already used"}
    
    if verification_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return {"valid": False, "reason": "Token has expired"}
    
    return {
        "valid": True,
        "token_type": verification_token.token_type,
        "expires_at": verification_token.expires_at.isoformat()
    }
