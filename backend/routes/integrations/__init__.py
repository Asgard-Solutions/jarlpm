"""
Integration Routes - Main Router
Combines all provider-specific routes into a single router.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from typing import Optional
import os
import logging

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.integration_models import (
    ExternalIntegration, ExternalPushMapping, ExternalPushRun,
    IntegrationProvider, IntegrationStatus
)
from routes.auth import get_current_user_id
from services.linear_service import LinearOAuthService

from .shared import (
    check_subscription_required,
    get_user_integration,
    IntegrationStatusResponse
)

logger = logging.getLogger(__name__)

# Main router - will include sub-routers
router = APIRouter(prefix="/integrations", tags=["integrations"])


# ============================================
# Status Endpoints (Shared across providers)
# ============================================

@router.get("/status")
async def get_all_integrations_status(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get status of all integrations for current user"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    result = await session.execute(
        select(ExternalIntegration).where(ExternalIntegration.user_id == user_id)
    )
    integrations = result.scalars().all()
    
    providers_status = {}
    
    for provider in IntegrationProvider:
        integration = next((i for i in integrations if i.provider == provider.value), None)
        
        if integration:
            providers_status[provider.value] = {
                "status": integration.status,
                "account_name": integration.external_account_name,
                "default_team": {
                    "id": integration.default_team_id,
                    "name": integration.default_team_name
                } if integration.default_team_id else None,
                "default_project": {
                    "id": integration.default_project_id,
                    "name": integration.default_project_name
                } if integration.default_project_id else None,
                "connected_at": integration.created_at
            }
        else:
            providers_status[provider.value] = {
                "status": IntegrationStatus.DISCONNECTED.value,
                "account_name": None,
                "default_team": None,
                "default_project": None,
                "connected_at": None
            }
    
    # Add configuration status for each provider
    oauth_service = LinearOAuthService()
    providers_status["linear"]["configured"] = oauth_service.is_configured()
    providers_status["jira"]["configured"] = bool(os.environ.get("JIRA_OAUTH_CLIENT_ID"))
    providers_status["azure_devops"]["configured"] = True  # PAT-based, always available
    
    return providers_status


@router.get("/status/{provider}")
async def get_integration_status(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get status of a specific integration"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    if provider not in [p.value for p in IntegrationProvider]:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")
    
    integration = await get_user_integration(session, user_id, provider)
    
    if not integration:
        return {
            "status": IntegrationStatus.DISCONNECTED.value,
            "connected": False
        }
    
    return {
        "status": integration.status,
        "connected": integration.status == IntegrationStatus.CONNECTED.value,
        "account_name": integration.external_account_name,
        "default_team": {
            "id": integration.default_team_id,
            "name": integration.default_team_name
        } if integration.default_team_id else None,
        "default_project": {
            "id": integration.default_project_id,
            "name": integration.default_project_name
        } if integration.default_project_id else None
    }


# ============================================
# Push History & Mappings (Shared)
# ============================================

@router.get("/push-history")
async def get_push_history(
    request: Request,
    provider: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    session: AsyncSession = Depends(get_db)
):
    """Get push history for user"""
    user_id = await get_current_user_id(request, session)
    
    query = select(ExternalPushRun).where(ExternalPushRun.user_id == user_id)
    
    if provider:
        query = query.where(ExternalPushRun.provider == provider)
    
    query = query.order_by(ExternalPushRun.started_at.desc()).limit(limit)
    
    result = await session.execute(query)
    runs = result.scalars().all()
    
    return {
        "runs": [
            {
                "run_id": run.run_id,
                "provider": run.provider,
                "epic_id": run.epic_id,
                "push_scope": run.push_scope,
                "status": run.status,
                "is_dry_run": run.is_dry_run,
                "started_at": run.started_at,
                "ended_at": run.ended_at,
                "summary": run.summary_json,
                "errors": run.error_json
            }
            for run in runs
        ]
    }


@router.get("/mappings/{entity_id}")
async def get_entity_mappings(
    entity_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get external mappings for a specific JarlPM entity"""
    user_id = await get_current_user_id(request, session)
    
    result = await session.execute(
        select(ExternalPushMapping).where(
            and_(
                ExternalPushMapping.user_id == user_id,
                ExternalPushMapping.entity_id == entity_id
            )
        )
    )
    mappings = result.scalars().all()
    
    return {
        "mappings": [
            {
                "provider": m.provider,
                "external_key": m.external_key,
                "external_url": m.external_url,
                "last_pushed_at": m.last_pushed_at
            }
            for m in mappings
        ]
    }


# ============================================
# Include Provider-Specific Routes
# ============================================

from .linear import router as linear_router
from .jira import router as jira_router
from .azure_devops import router as azure_devops_router

router.include_router(linear_router)
router.include_router(jira_router)
router.include_router(azure_devops_router)
