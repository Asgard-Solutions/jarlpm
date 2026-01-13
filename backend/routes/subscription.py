from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone
import os
import logging

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse, CheckoutStatusResponse
)
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
async def create_checkout_session(request: Request, body: CreateCheckoutRequest):
    """Create a Stripe checkout session for subscription"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
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
        session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
    except Exception as e:
        logger.error(f"Stripe checkout creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")
    
    # Create payment transaction record
    import uuid
    transaction_doc = {
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "session_id": session.session_id,
        "amount": SUBSCRIPTION_PRICE,
        "currency": SUBSCRIPTION_CURRENCY,
        "payment_status": "initiated",
        "metadata": {"type": "subscription"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    await db.payment_transactions.insert_one(transaction_doc)
    
    return {"checkout_url": session.url, "session_id": session.session_id}


@router.get("/checkout-status/{session_id}")
async def get_checkout_status(request: Request, session_id: str):
    """Get the status of a checkout session and update subscription if paid"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
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
    await db.payment_transactions.update_one(
        {"session_id": session_id, "user_id": user_id},
        {
            "$set": {
                "payment_status": status.payment_status,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    # If paid, activate subscription (only once)
    if status.payment_status == "paid":
        # Check if already processed
        existing = await db.payment_transactions.find_one(
            {"session_id": session_id, "processed": True},
            {"_id": 0}
        )
        
        if not existing:
            # Mark as processed
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"processed": True}}
            )
            
            # Activate subscription
            await db.subscriptions.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "status": "active",
                        "stripe_session_id": session_id,
                        "current_period_start": datetime.now(timezone.utc),
                        "current_period_end": datetime.now(timezone.utc).replace(
                            month=datetime.now(timezone.utc).month + 1 if datetime.now(timezone.utc).month < 12 else 1,
                            year=datetime.now(timezone.utc).year if datetime.now(timezone.utc).month < 12 else datetime.now(timezone.utc).year + 1
                        ),
                        "updated_at": datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )
    
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency
    }


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(request: Request):
    """Get current subscription status"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    sub_doc = await db.subscriptions.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not sub_doc:
        return SubscriptionStatusResponse(status="inactive")
    
    return SubscriptionStatusResponse(
        status=sub_doc.get("status", "inactive"),
        stripe_subscription_id=sub_doc.get("stripe_subscription_id"),
        current_period_end=sub_doc.get("current_period_end")
    )


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    db = request.app.state.db
    
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
            if user_id:
                await db.subscriptions.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "status": "active",
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
        
        return {"received": True}
    except Exception as e:
        logger.error(f"Webhook handling failed: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")
