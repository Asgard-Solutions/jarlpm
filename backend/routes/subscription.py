from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import os
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse, CheckoutStatusResponse
)
from db import get_db
from db.models import Subscription, SubscriptionStatus, PaymentTransaction
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["subscription"])

# Subscription price: $20/month
SUBSCRIPTION_PRICE = 20.00
SUBSCRIPTION_CURRENCY = "usd"


class CreateCheckoutRequest(BaseModel):
    origin_url: str


class SubscriptionStatusResponse(BaseModel):
    status: str
    stripe_subscription_id: str | None = None
    current_period_end: datetime | None = None


@router.post("/create-checkout")
async def create_checkout_session(
    request: Request, 
    body: CreateCheckoutRequest,
    session: AsyncSession = Depends(get_db)
):
    """Create a Stripe checkout session for subscription"""
    user_id = await get_current_user_id(request, session)
    
    # Get Stripe API key
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    # Build URLs from frontend origin
    success_url = f"{body.origin_url}/settings?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{body.origin_url}/settings?payment=cancelled"
    
    # Initialize Stripe checkout
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    
    # Create checkout session
    checkout_request = CheckoutSessionRequest(
        amount=SUBSCRIPTION_PRICE,
        currency=SUBSCRIPTION_CURRENCY,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": user_id,
            "type": "subscription"
        }
    )
    
    try:
        checkout_session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
    except Exception as e:
        logger.error(f"Stripe checkout creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")
    
    # Create payment transaction record
    transaction = PaymentTransaction(
        user_id=user_id,
        stripe_session_id=checkout_session.session_id,
        amount=SUBSCRIPTION_PRICE,
        currency=SUBSCRIPTION_CURRENCY,
        payment_status="pending",
        transaction_type="subscription",
        payment_metadata={"type": "subscription"}
    )
    session.add(transaction)
    await session.commit()
    
    return {"checkout_url": checkout_session.url, "session_id": checkout_session.session_id}


@router.get("/checkout-status/{session_id}")
async def get_checkout_status(
    request: Request, 
    session_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get the status of a checkout session and update subscription if paid"""
    user_id = await get_current_user_id(request, session)
    
    # Get Stripe API key
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    # Initialize Stripe checkout
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    
    try:
        status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
    except Exception as e:
        logger.error(f"Stripe status check failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to check payment status")
    
    # Update transaction record
    result = await session.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.stripe_session_id == session_id,
            PaymentTransaction.user_id == user_id
        )
    )
    transaction = result.scalar_one_or_none()
    
    if transaction:
        # Update payment status
        transaction.payment_status = status.payment_status
        transaction.updated_at = datetime.now(timezone.utc)
    
    # If paid, activate subscription (only once - check if already processed)
    if status.payment_status == "paid":
        if transaction and transaction.payment_status != "processed":
            # Mark as processed to prevent duplicate processing
            transaction.payment_status = "processed"
            
            # Get or create subscription
            sub_result = await session.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            )
            subscription = sub_result.scalar_one_or_none()
            
            now = datetime.now(timezone.utc)
            next_month = now + relativedelta(months=1)
            
            if subscription:
                subscription.status = SubscriptionStatus.ACTIVE.value
                subscription.current_period_start = now
                subscription.current_period_end = next_month
                subscription.updated_at = now
            else:
                subscription = Subscription(
                    user_id=user_id,
                    status=SubscriptionStatus.ACTIVE.value,
                    current_period_start=now,
                    current_period_end=next_month
                )
                session.add(subscription)
    
    await session.commit()
    
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency
    }


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get current subscription status"""
    user_id = await get_current_user_id(request, session)
    
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        return SubscriptionStatusResponse(status="inactive")
    
    # Status is stored as string in PostgreSQL
    status_value = subscription.status if isinstance(subscription.status, str) else (subscription.status.value if subscription.status else "inactive")
    
    # Check if subscription is expired
    if subscription.current_period_end and subscription.current_period_end < datetime.now(timezone.utc):
        status_value = "expired"
    
    return SubscriptionStatusResponse(
        status=status_value,
        stripe_subscription_id=subscription.stripe_subscription_id,
        current_period_end=subscription.current_period_end
    )


async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    from db.database import AsyncSessionLocal
    
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    
    try:
        event = await stripe_checkout.handle_webhook(body, signature)
        
        if event.payment_status == "paid":
            user_id = event.metadata.get("user_id")
            if user_id and AsyncSessionLocal:
                async with AsyncSessionLocal() as db_session:
                    # Check if already processed
                    txn_result = await db_session.execute(
                        select(PaymentTransaction).where(
                            PaymentTransaction.stripe_session_id == event.session_id
                        )
                    )
                    transaction = txn_result.scalar_one_or_none()
                    
                    if transaction and transaction.payment_status == "processed":
                        return {"received": True, "status": "already_processed"}
                    
                    # Update transaction
                    if transaction:
                        transaction.payment_status = "processed"
                        transaction.stripe_payment_id = event.event_id
                    
                    # Update subscription
                    result = await db_session.execute(
                        select(Subscription).where(Subscription.user_id == user_id)
                    )
                    subscription = result.scalar_one_or_none()
                    
                    now = datetime.now(timezone.utc)
                    if subscription:
                        subscription.status = SubscriptionStatus.ACTIVE.value
                        subscription.current_period_start = now
                        subscription.current_period_end = now + relativedelta(months=1)
                        subscription.updated_at = now
                    else:
                        subscription = Subscription(
                            user_id=user_id,
                            status=SubscriptionStatus.ACTIVE.value,
                            current_period_start=now,
                            current_period_end=now + relativedelta(months=1)
                        )
                        db_session.add(subscription)
                    
                    await db_session.commit()
        
        return {"received": True}
    except Exception as e:
        logger.error(f"Webhook handling failed: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")
