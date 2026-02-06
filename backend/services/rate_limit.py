"""
Rate Limiting Configuration for JarlPM

Protects against abuse and controls costs for:
- Authentication endpoints (prevent brute force)
- AI generation endpoints (protect LLM API costs)
- Integration push endpoints (prevent API abuse)
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Custom key functions
def get_user_id_or_ip(request: Request) -> str:
    """
    Get user ID from session if authenticated, otherwise fall back to IP.
    This allows per-user rate limiting for authenticated requests.
    """
    # Try to get user_id from request state (set by auth middleware)
    user_id = getattr(request.state, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    
    # Fall back to IP address
    return f"ip:{get_remote_address(request)}"


def get_ip_only(request: Request) -> str:
    """Get only IP address for auth endpoints."""
    return f"ip:{get_remote_address(request)}"


# Create limiter instance with in-memory storage
# For production with multiple workers, use Redis: "redis://localhost:6379"
limiter = Limiter(
    key_func=get_user_id_or_ip,
    default_limits=["200/minute"],  # Default fallback
    storage_uri="memory://",
    strategy="fixed-window"
)

# Rate limit configurations by endpoint type
RATE_LIMITS = {
    # Authentication - strict to prevent brute force
    "auth_login": "5/minute",           # 5 login attempts per minute per IP
    "auth_signup": "3/minute",          # 3 signups per minute per IP
    "auth_password_reset": "3/minute",  # 3 reset requests per minute per IP
    
    # AI Generation - protect LLM costs
    "ai_generate": "10/minute",         # 10 AI generations per minute per user
    "ai_chat": "30/minute",             # 30 chat messages per minute per user
    
    # Integration push - prevent API abuse
    "integration_push": "5/minute",     # 5 pushes per minute per user
    "integration_preview": "20/minute", # 20 previews per minute per user
    
    # General API
    "api_read": "100/minute",           # 100 reads per minute per user
    "api_write": "30/minute",           # 30 writes per minute per user
}


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom handler for rate limit exceeded errors.
    Returns a user-friendly JSON response with retry information.
    """
    # Extract retry-after from the exception
    retry_after = getattr(exc, 'retry_after', 60)
    
    # Log the rate limit hit
    client_id = get_user_id_or_ip(request)
    logger.warning(
        f"Rate limit exceeded for {client_id} on {request.url.path}",
        extra={
            "client_id": client_id,
            "path": request.url.path,
            "method": request.method,
            "limit": str(exc.detail) if hasattr(exc, 'detail') else "unknown"
        }
    )
    
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please slow down.",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "retry_after_seconds": retry_after,
            "message": f"Too many requests. Please wait {retry_after} seconds before trying again."
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(exc.detail) if hasattr(exc, 'detail') else "unknown",
        }
    )


# Decorator shortcuts for common rate limits
def limit_auth(limit: str = RATE_LIMITS["auth_login"]):
    """Rate limit decorator for auth endpoints."""
    return limiter.limit(limit, key_func=get_ip_only)


def limit_ai(limit: str = RATE_LIMITS["ai_generate"]):
    """Rate limit decorator for AI generation endpoints."""
    return limiter.limit(limit, key_func=get_user_id_or_ip)


def limit_integration(limit: str = RATE_LIMITS["integration_push"]):
    """Rate limit decorator for integration endpoints."""
    return limiter.limit(limit, key_func=get_user_id_or_ip)


def limit_api_read(limit: str = RATE_LIMITS["api_read"]):
    """Rate limit decorator for read endpoints."""
    return limiter.limit(limit, key_func=get_user_id_or_ip)


def limit_api_write(limit: str = RATE_LIMITS["api_write"]):
    """Rate limit decorator for write endpoints."""
    return limiter.limit(limit, key_func=get_user_id_or_ip)
