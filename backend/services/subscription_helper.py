"""
Subscription Helper Utilities

Provides consistent subscription status checking across the application.
This module handles the various ways subscription status can be stored/compared.
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from db.models import Subscription, SubscriptionStatus


def is_subscription_active(subscription: Optional[Subscription]) -> bool:
    """
    Check if a subscription is active.
    
    Handles multiple representations of the status:
    - String value: "active"
    - Enum: SubscriptionStatus.ACTIVE
    - Enum value: SubscriptionStatus.ACTIVE.value
    
    Args:
        subscription: The subscription object to check, or None
        
    Returns:
        True if subscription exists and is active, False otherwise
    """
    if subscription is None:
        return False
    
    status = subscription.status
    
    # Handle different representations
    if isinstance(status, str):
        return status.lower() == "active"
    elif isinstance(status, SubscriptionStatus):
        return status == SubscriptionStatus.ACTIVE
    else:
        # Fallback: try string comparison
        return str(status).lower() == "active"


async def get_user_subscription(session: AsyncSession, user_id: str) -> Optional[Subscription]:
    """
    Get subscription for a user.
    
    Args:
        session: Database session
        user_id: User ID to look up
        
    Returns:
        Subscription object or None
    """
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def check_active_subscription(session: AsyncSession, user_id: str) -> Subscription:
    """
    Check if user has an active subscription and return it.
    Raises HTTPException with 402 if not active.
    
    Args:
        session: Database session
        user_id: User ID to check
        
    Returns:
        Active Subscription object
        
    Raises:
        HTTPException: 402 if subscription is not active
    """
    subscription = await get_user_subscription(session, user_id)
    
    if not is_subscription_active(subscription):
        raise HTTPException(
            status_code=402, 
            detail="Active subscription required"
        )
    
    return subscription


async def require_subscription_for_feature(
    session: AsyncSession, 
    user_id: str, 
    feature_name: str = "this feature"
) -> Subscription:
    """
    Require an active subscription for a specific feature.
    Provides a customizable error message.
    
    Args:
        session: Database session
        user_id: User ID to check
        feature_name: Name of the feature for error message
        
    Returns:
        Active Subscription object
        
    Raises:
        HTTPException: 402 if subscription is not active
    """
    subscription = await get_user_subscription(session, user_id)
    
    if not is_subscription_active(subscription):
        raise HTTPException(
            status_code=402, 
            detail=f"Active subscription required for {feature_name}"
        )
    
    return subscription
