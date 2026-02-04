"""
Stripe Subscription Management for JarlPM
Uses real Stripe subscriptions with recurring billing
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
import os
import logging
import stripe

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import Subscription, SubscriptionStatus, PaymentTransaction, User
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["subscription"])

# Subscription configuration
SUBSCRIPTION_PRICE = 45.00
SUBSCRIPTION_CURRENCY = "usd"

# Stripe Price ID - set in .env or create dynamically
# This should be a recurring price created in Stripe Dashboard
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")


class CreateCheckoutRequest(BaseModel):
    origin_url: str


class SubscriptionStatusResponse(BaseModel):
    status: str
    stripe_subscription_id: str | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class CancelSubscriptionRequest(BaseModel):
    cancel_at_period_end: bool = True  # Default: cancel at end of billing period


def get_stripe_client():
    """Get configured Stripe client"""
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key or api_key == "your-stripe-api-key-here":
        raise HTTPException(
            status_code=500, 
            detail="Payment system not configured. Please add your STRIPE_API_KEY to .env"
        )
    stripe.api_key = api_key
    return stripe


async def get_or_create_stripe_customer(
    stripe_client, 
    user_id: str, 
    user_email: str,
    session: AsyncSession
) -> str:
    """Get existing Stripe customer or create a new one"""
    # Check if user already has a Stripe customer ID
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()
    
    if subscription and subscription.stripe_customer_id:
        # Verify customer still exists in Stripe
        try:
            stripe_client.Customer.retrieve(subscription.stripe_customer_id)
            return subscription.stripe_customer_id
        except stripe.error.InvalidRequestError:
            # Customer was deleted, create new one
            pass
    
    # Create new Stripe customer
    customer = stripe_client.Customer.create(
        email=user_email,
        metadata={"user_id": user_id}
    )
    
    # Save customer ID to subscription record
    if subscription:
        subscription.stripe_customer_id = customer.id
    else:
        subscription = Subscription(
            user_id=user_id,
            status=SubscriptionStatus.INACTIVE.value,
            stripe_customer_id=customer.id
        )
        session.add(subscription)
    
    await session.commit()
    return customer.id


async def get_or_create_price(stripe_client) -> str:
    """Get existing price or create a new one"""
    # If price ID is configured, use it
    if STRIPE_PRICE_ID:
        return STRIPE_PRICE_ID
    
    # Check for existing JarlPM product
    products = stripe_client.Product.list(limit=10)
    jarlpm_product = None
    
    for product in products.data:
        if product.metadata.get("app") == "jarlpm":
            jarlpm_product = product
            break
    
    # Create product if not exists
    if not jarlpm_product:
        jarlpm_product = stripe_client.Product.create(
            name="JarlPM Pro",
            description="AI-agnostic Product Management subscription - $45/month",
            metadata={"app": "jarlpm"}
        )
        logger.info(f"Created Stripe product: {jarlpm_product.id}")
    
    # Check for existing price on this product
    prices = stripe_client.Price.list(product=jarlpm_product.id, active=True, limit=10)
    
    for price in prices.data:
        if (price.recurring and 
            price.recurring.interval == "month" and 
            price.unit_amount == int(SUBSCRIPTION_PRICE * 100)):
            return price.id
    
    # Create new recurring price
    price = stripe_client.Price.create(
        product=jarlpm_product.id,
        unit_amount=int(SUBSCRIPTION_PRICE * 100),
        currency=SUBSCRIPTION_CURRENCY,
        recurring={"interval": "month"},
        metadata={"app": "jarlpm"}
    )
    logger.info(f"Created Stripe price: {price.id}")
    
    return price.id


@router.post("/create-checkout")
async def create_checkout_session(
    request: Request, 
    body: CreateCheckoutRequest,
    session: AsyncSession = Depends(get_db)
):
    """Create a Stripe checkout session for subscription"""
    user_id = await get_current_user_id(request, session)
    
    # Get user email for Stripe customer
    user_result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    stripe_client = get_stripe_client()
    
    # Get or create Stripe customer
    customer_id = await get_or_create_stripe_customer(
        stripe_client, user_id, user.email, session
    )
    
    # Get or create price
    price_id = await get_or_create_price(stripe_client)
    
    # Build URLs from frontend origin
    success_url = f"{body.origin_url}/settings?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{body.origin_url}/settings?payment=cancelled"
    
    try:
        # Create subscription checkout session
        checkout_session = stripe_client.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",  # SUBSCRIPTION mode, not payment
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                "metadata": {
                    "user_id": user_id,
                    "app": "jarlpm"
                }
            },
            metadata={
                "user_id": user_id,
                "type": "subscription"
            }
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")
    
    # Create payment transaction record
    transaction = PaymentTransaction(
        user_id=user_id,
        stripe_session_id=checkout_session.id,
        amount=SUBSCRIPTION_PRICE,
        currency=SUBSCRIPTION_CURRENCY,
        payment_status="pending",
        transaction_type="subscription",
        payment_metadata={"type": "subscription", "mode": "subscription"}
    )
    session.add(transaction)
    await session.commit()
    
    return {"checkout_url": checkout_session.url, "session_id": checkout_session.id}


@router.get("/checkout-status/{session_id}")
async def get_checkout_status(
    request: Request, 
    session_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get the status of a checkout session"""
    user_id = await get_current_user_id(request, session)
    
    stripe_client = get_stripe_client()
    
    try:
        checkout_session = stripe_client.checkout.Session.retrieve(
            session_id,
            expand=["subscription"]
        )
    except stripe.error.StripeError as e:
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
    
    payment_status = checkout_session.payment_status
    
    if transaction:
        transaction.payment_status = payment_status
        transaction.updated_at = datetime.now(timezone.utc)
    
    # If subscription created, update our records
    if checkout_session.subscription:
        stripe_sub = checkout_session.subscription
        if isinstance(stripe_sub, str):
            # Need to fetch the subscription object
            stripe_sub = stripe_client.Subscription.retrieve(stripe_sub)
        
        # Update local subscription record
        sub_result = await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        subscription = sub_result.scalar_one_or_none()
        
        if subscription:
            subscription.stripe_subscription_id = stripe_sub.id
            subscription.status = _map_stripe_status(stripe_sub.status)
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_sub.current_period_start, tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_sub.current_period_end, tz=timezone.utc
            )
            subscription.updated_at = datetime.now(timezone.utc)
            
            if transaction:
                transaction.payment_status = "processed"
    
    await session.commit()
    
    return {
        "status": checkout_session.status,
        "payment_status": payment_status,
        "subscription_status": checkout_session.subscription.status if checkout_session.subscription and hasattr(checkout_session.subscription, 'status') else None,
        "amount_total": checkout_session.amount_total,
        "currency": checkout_session.currency
    }


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Get current subscription status.
    Acts as fallback sync - if webhook was missed, this syncs from Stripe.
    """
    user_id = await get_current_user_id(request, session)
    
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        return SubscriptionStatusResponse(status="inactive")
    
    # If we have a Stripe subscription, sync ALL fields from Stripe (fallback for missed webhooks)
    if subscription.stripe_subscription_id:
        try:
            stripe_client = get_stripe_client()
            stripe_sub = stripe_client.Subscription.retrieve(subscription.stripe_subscription_id)
            
            # Always sync from Stripe - this is our fallback if webhooks missed
            new_status = _map_stripe_status(stripe_sub.status)
            new_period_start = datetime.fromtimestamp(stripe_sub.current_period_start, tz=timezone.utc)
            new_period_end = datetime.fromtimestamp(stripe_sub.current_period_end, tz=timezone.utc)
            new_cancel_at_period_end = stripe_sub.cancel_at_period_end
            
            # Check if anything changed
            if (subscription.status != new_status or
                subscription.current_period_start != new_period_start or
                subscription.current_period_end != new_period_end or
                subscription.cancel_at_period_end != new_cancel_at_period_end):
                
                subscription.status = new_status
                subscription.current_period_start = new_period_start
                subscription.current_period_end = new_period_end
                subscription.cancel_at_period_end = new_cancel_at_period_end
                subscription.updated_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info(f"Synced subscription {subscription.stripe_subscription_id} from Stripe (fallback)")
            
            return SubscriptionStatusResponse(
                status=new_status,
                stripe_subscription_id=subscription.stripe_subscription_id,
                current_period_end=new_period_end,
                cancel_at_period_end=new_cancel_at_period_end
            )
        except stripe.error.StripeError as e:
            logger.warning(f"Failed to sync from Stripe, using local data: {e}")
            # Fall through to return local data
    
    # Return local data (no Stripe sub or Stripe API failed)
    status_value = subscription.status if isinstance(subscription.status, str) else subscription.status.value
    
    # Check if subscription is expired (for legacy records without Stripe)
    if subscription.current_period_end and subscription.current_period_end < datetime.now(timezone.utc):
        status_value = "expired"
    
    return SubscriptionStatusResponse(
        status=status_value,
        stripe_subscription_id=subscription.stripe_subscription_id,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end
    )


@router.post("/cancel")
async def cancel_subscription(
    request: Request,
    body: CancelSubscriptionRequest,
    session: AsyncSession = Depends(get_db)
):
    """Cancel subscription"""
    user_id = await get_current_user_id(request, session)
    
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    stripe_client = get_stripe_client()
    
    try:
        if body.cancel_at_period_end:
            # Cancel at end of billing period
            stripe_sub = stripe_client.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            subscription.status = SubscriptionStatus.ACTIVE.value  # Still active until period end
        else:
            # Cancel immediately
            stripe_sub = stripe_client.Subscription.cancel(subscription.stripe_subscription_id)
            subscription.status = SubscriptionStatus.CANCELED.value
        
        subscription.updated_at = datetime.now(timezone.utc)
        await session.commit()
        
        return {
            "status": "canceled" if not body.cancel_at_period_end else "cancel_scheduled",
            "cancel_at_period_end": stripe_sub.cancel_at_period_end,
            "current_period_end": datetime.fromtimestamp(
                stripe_sub.current_period_end, tz=timezone.utc
            ).isoformat()
        }
    except stripe.error.StripeError as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel subscription: {str(e)}")


@router.post("/reactivate")
async def reactivate_subscription(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Reactivate a subscription scheduled for cancellation"""
    user_id = await get_current_user_id(request, session)
    
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No subscription found")
    
    stripe_client = get_stripe_client()
    
    try:
        stripe_sub = stripe_client.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False
        )
        
        subscription.status = _map_stripe_status(stripe_sub.status)
        subscription.updated_at = datetime.now(timezone.utc)
        await session.commit()
        
        return {
            "status": "reactivated",
            "subscription_status": stripe_sub.status
        }
    except stripe.error.StripeError as e:
        logger.error(f"Failed to reactivate subscription: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reactivate: {str(e)}")


def _map_stripe_status(stripe_status: str) -> str:
    """Map Stripe subscription status to our status enum"""
    status_map = {
        "active": SubscriptionStatus.ACTIVE.value,
        "past_due": SubscriptionStatus.PAST_DUE.value,
        "canceled": SubscriptionStatus.CANCELED.value,
        "unpaid": SubscriptionStatus.PAST_DUE.value,
        "incomplete": SubscriptionStatus.INACTIVE.value,
        "incomplete_expired": SubscriptionStatus.INACTIVE.value,
        "trialing": SubscriptionStatus.TRIAL.value,
        "paused": SubscriptionStatus.INACTIVE.value,
    }
    return status_map.get(stripe_status, SubscriptionStatus.INACTIVE.value)


# ============================================
# Webhook Handler
# ============================================

async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events for subscription lifecycle
    
    Key events:
    - customer.subscription.created: New subscription
    - customer.subscription.updated: Status change, renewal, etc.
    - customer.subscription.deleted: Subscription canceled
    - invoice.paid: Successful payment
    - invoice.payment_failed: Failed payment
    """
    from db.database import AsyncSessionLocal
    
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key or api_key == "your-stripe-api-key-here":
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    stripe.api_key = api_key
    
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    
    try:
        # Verify webhook signature
        if webhook_secret:
            event = stripe.Webhook.construct_event(body, signature, webhook_secret)
        else:
            import json
            event = stripe.Event.construct_from(json.loads(body), stripe.api_key)
        
        logger.info(f"Received Stripe webhook: {event.type}")
        
        # Handle subscription events
        if event.type == "customer.subscription.created":
            await _handle_subscription_created(event.data.object)
        
        elif event.type == "customer.subscription.updated":
            await _handle_subscription_updated(event.data.object)
        
        elif event.type == "customer.subscription.deleted":
            await _handle_subscription_deleted(event.data.object)
        
        elif event.type == "invoice.paid":
            await _handle_invoice_paid(event.data.object)
        
        elif event.type == "invoice.payment_failed":
            await _handle_payment_failed(event.data.object)
        
        elif event.type == "checkout.session.completed":
            await _handle_checkout_completed(event.data.object)
        
        return {"received": True, "type": event.type}
        
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook handling failed: {e}")
        raise HTTPException(status_code=400, detail=f"Webhook processing failed: {str(e)}")


async def _handle_subscription_created(subscription_obj):
    """Handle new subscription creation"""
    from db.database import AsyncSessionLocal
    
    user_id = subscription_obj.metadata.get("user_id")
    if not user_id:
        logger.warning("Subscription created without user_id metadata")
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        subscription = result.scalar_one_or_none()
        
        now = datetime.now(timezone.utc)
        
        if subscription:
            subscription.stripe_subscription_id = subscription_obj.id
            subscription.stripe_customer_id = subscription_obj.customer
            subscription.status = _map_stripe_status(subscription_obj.status)
            subscription.current_period_start = datetime.fromtimestamp(
                subscription_obj.current_period_start, tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                subscription_obj.current_period_end, tz=timezone.utc
            )
            subscription.cancel_at_period_end = subscription_obj.cancel_at_period_end
            subscription.updated_at = now
        else:
            subscription = Subscription(
                user_id=user_id,
                stripe_subscription_id=subscription_obj.id,
                stripe_customer_id=subscription_obj.customer,
                status=_map_stripe_status(subscription_obj.status),
                current_period_start=datetime.fromtimestamp(
                    subscription_obj.current_period_start, tz=timezone.utc
                ),
                current_period_end=datetime.fromtimestamp(
                    subscription_obj.current_period_end, tz=timezone.utc
                ),
                cancel_at_period_end=subscription_obj.cancel_at_period_end
            )
            session.add(subscription)
        
        await session.commit()
        logger.info(f"Subscription created for user {user_id}: {subscription_obj.id}")


async def _handle_subscription_updated(subscription_obj):
    """
    Handle subscription updates (renewals, status changes, cancellation scheduling, etc.)
    THIS IS THE SOURCE OF TRUTH - webhooks set the canonical state
    """
    from db.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_obj.id
            )
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            logger.warning(f"Subscription not found for update: {subscription_obj.id}")
            return
        
        # Update ALL fields from Stripe - webhook is source of truth
        subscription.status = _map_stripe_status(subscription_obj.status)
        subscription.current_period_start = datetime.fromtimestamp(
            subscription_obj.current_period_start, tz=timezone.utc
        )
        subscription.current_period_end = datetime.fromtimestamp(
            subscription_obj.current_period_end, tz=timezone.utc
        )
        subscription.cancel_at_period_end = subscription_obj.cancel_at_period_end
        subscription.updated_at = datetime.now(timezone.utc)
        
        await session.commit()
        logger.info(f"Subscription updated via webhook: {subscription_obj.id} -> status={subscription_obj.status}, cancel_at_period_end={subscription_obj.cancel_at_period_end}")


async def _handle_subscription_deleted(subscription_obj):
    """
    Handle subscription cancellation/deletion
    THIS IS THE SOURCE OF TRUTH - webhook sets final canceled state
    """
    from db.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_obj.id
            )
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.status = SubscriptionStatus.CANCELED.value
            subscription.cancel_at_period_end = False  # No longer pending, actually canceled
            subscription.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Subscription deleted via webhook: {subscription_obj.id}")


async def _handle_invoice_paid(invoice_obj):
    """Handle successful invoice payment (subscription renewal)"""
    from db.database import AsyncSessionLocal
    
    subscription_id = invoice_obj.subscription
    if not subscription_id:
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            # Ensure subscription is active after successful payment
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Invoice paid for subscription: {subscription_id}")


async def _handle_payment_failed(invoice_obj):
    """Handle failed invoice payment"""
    from db.database import AsyncSessionLocal
    
    subscription_id = invoice_obj.subscription
    if not subscription_id:
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
        )
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.status = SubscriptionStatus.PAST_DUE.value
            subscription.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.warning(f"Payment failed for subscription: {subscription_id}")


async def _handle_checkout_completed(checkout_obj):
    """Handle checkout session completion"""
    from db.database import AsyncSessionLocal
    
    user_id = checkout_obj.metadata.get("user_id")
    if not user_id:
        return
    
    # For subscription mode, the subscription.created event handles the rest
    # This is just for logging/tracking
    logger.info(f"Checkout completed for user {user_id}, subscription: {checkout_obj.subscription}")
