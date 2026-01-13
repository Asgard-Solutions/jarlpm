from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
import httpx
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

class SessionExchangeRequest(BaseModel):
    session_id: str

class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    picture: str | None = None


@router.post("/session")
async def exchange_session(request: Request, body: SessionExchangeRequest, response: Response):
    """Exchange Emergent session_id for session_token and user data"""
    db = request.app.state.db
    
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
    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    
    if user_doc:
        # Update existing user
        user_id = user_doc["user_id"]
        await db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "name": auth_data.get("name", user_doc.get("name")),
                    "picture": auth_data.get("picture"),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
    else:
        # Create new user
        import uuid
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user_doc = {
            "user_id": user_id,
            "email": email,
            "name": auth_data.get("name", email.split("@")[0]),
            "picture": auth_data.get("picture"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.users.insert_one(user_doc)
        
        # Create inactive subscription for new user
        sub_doc = {
            "subscription_id": f"sub_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "status": "inactive",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.subscriptions.insert_one(sub_doc)
    
    # Store session
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    session_doc = {
        "session_id": f"sess_{uuid.uuid4().hex}" if 'uuid' not in dir() else f"sess_{__import__('uuid').uuid4().hex}",
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc)
    }
    
    # Remove old sessions for this user
    await db.user_sessions.delete_many({"user_id": user_id})
    await db.user_sessions.insert_one(session_doc)
    
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
async def get_current_user(request: Request):
    """Get current user from session token"""
    db = request.app.state.db
    
    # Get session token from cookie or header
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Find session
    session_doc = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Check expiry
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    # Get user
    user_doc = await db.users.find_one(
        {"user_id": session_doc["user_id"]},
        {"_id": 0}
    )
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    return UserResponse(
        user_id=user_doc["user_id"],
        email=user_doc["email"],
        name=user_doc["name"],
        picture=user_doc.get("picture")
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout and clear session"""
    db = request.app.state.db
    
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_many({"session_token": session_token})
    
    response.delete_cookie(
        key="session_token",
        path="/",
        secure=True,
        samesite="none"
    )
    
    return {"message": "Logged out successfully"}


# Helper function to get current user (for use in other routes)
async def get_current_user_id(request: Request) -> str:
    """Extract and validate current user ID from request"""
    db = request.app.state.db
    
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_doc = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    return session_doc["user_id"]
