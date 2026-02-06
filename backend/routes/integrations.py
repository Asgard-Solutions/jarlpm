"""
External Integrations Routes for JarlPM
Handles Linear, Jira, and Azure DevOps integrations.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query, Body
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timezone, timedelta
import os
import secrets
import logging

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db import get_db
from db.models import Subscription, SubscriptionStatus, Epic, EpicSnapshot
from db.feature_models import Feature
from db.user_story_models import UserStory
from db.integration_models import (
    ExternalIntegration, ExternalPushMapping, ExternalPushRun,
    IntegrationProvider, IntegrationStatus, PushStatus, EntityType
)
from routes.auth import get_current_user_id
from services.encryption import get_encryption_service
from services.linear_service import (
    LinearOAuthService, LinearGraphQLService, LinearPushService,
    LinearAPIError, AuthenticationError as LinearAuthError, compute_payload_hash
)
from services.jira_service import (
    JiraOAuthService, JiraRESTService, JiraPushService,
    JiraAPIError, AuthenticationError as JiraAuthError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])

# Pydantic Models
class IntegrationStatusResponse(BaseModel):
    provider: str
    status: str
    account_name: Optional[str] = None
    default_team: Optional[dict] = None
    default_project: Optional[dict] = None
    connected_at: Optional[datetime] = None

class ConnectLinearRequest(BaseModel):
    frontend_callback_url: str  # Where to redirect after OAuth completes

class ConfigureIntegrationRequest(BaseModel):
    team_id: str
    team_name: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    field_mappings: Optional[dict] = None

class PushPreviewRequest(BaseModel):
    epic_id: str
    push_scope: Literal["epic_only", "epic_features", "epic_features_stories"] = "epic_features_stories"
    include_bugs: bool = False

class PushRequest(BaseModel):
    epic_id: str
    team_id: str
    project_id: Optional[str] = None
    push_scope: Literal["epic_only", "epic_features", "epic_features_stories"] = "epic_features_stories"
    include_bugs: bool = False
    dry_run: bool = False


# Jira-specific models
class ConnectJiraRequest(BaseModel):
    frontend_callback_url: str

class ConfigureJiraRequest(BaseModel):
    cloud_id: str
    site_name: str
    project_key: str
    project_name: str
    issue_type_mapping: Optional[dict] = None  # e.g., {"feature": "Task", "story": "Story", "bug": "Bug"}
    story_points_field: Optional[str] = None   # e.g., "customfield_10016"
    epic_link_field: Optional[str] = None      # e.g., "customfield_10014"
    label_prefix: Optional[str] = None         # e.g., "jarlpm-"

class JiraPushRequest(BaseModel):
    epic_id: str
    project_key: str
    push_scope: Literal["epic_only", "epic_features", "epic_features_stories", "full"] = "epic_features_stories"
    include_bugs: bool = False
    dry_run: bool = False


# Helper functions
async def check_subscription_required(session: AsyncSession, user_id: str):
    """Check if user has an active subscription. Raise 402 if not."""
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()
    if not sub or sub.status != SubscriptionStatus.ACTIVE.value:
        raise HTTPException(status_code=402, detail="Active subscription required for integrations")


async def get_user_integration(
    session: AsyncSession, 
    user_id: str, 
    provider: str
) -> Optional[ExternalIntegration]:
    """Get user's integration for a specific provider"""
    result = await session.execute(
        select(ExternalIntegration).where(
            and_(
                ExternalIntegration.user_id == user_id,
                ExternalIntegration.provider == provider
            )
        )
    )
    return result.scalar_one_or_none()


async def get_linear_service(session: AsyncSession, user_id: str) -> LinearGraphQLService:
    """Get authenticated Linear GraphQL service for user"""
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Linear integration not connected")
    
    if not integration.access_token_encrypted:
        raise HTTPException(status_code=400, detail="Linear tokens not found")
    
    # Check token expiration
    if integration.token_expires_at and integration.token_expires_at < datetime.now(timezone.utc):
        # Try to refresh
        if integration.refresh_token_encrypted:
            try:
                encryption = get_encryption_service()
                refresh_token = encryption.decrypt(integration.refresh_token_encrypted)
                
                oauth = LinearOAuthService()
                new_tokens = await oauth.refresh_access_token(refresh_token)
                
                # Update tokens
                integration.access_token_encrypted = encryption.encrypt(new_tokens["access_token"])
                if new_tokens.get("refresh_token"):
                    integration.refresh_token_encrypted = encryption.encrypt(new_tokens["refresh_token"])
                integration.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=new_tokens.get("expires_in", 86400)
                )
                await session.commit()
                
                return LinearGraphQLService(new_tokens["access_token"])
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                integration.status = IntegrationStatus.ERROR.value
                await session.commit()
                raise HTTPException(status_code=401, detail="Linear token expired. Please reconnect.")
        else:
            raise HTTPException(status_code=401, detail="Linear token expired. Please reconnect.")
    
    # Decrypt and return service
    encryption = get_encryption_service()
    access_token = encryption.decrypt(integration.access_token_encrypted)
    return LinearGraphQLService(access_token)


async def get_jira_service(session: AsyncSession, user_id: str) -> JiraRESTService:
    """Get authenticated Jira REST service for user"""
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Jira integration not connected")
    
    if not integration.access_token_encrypted:
        raise HTTPException(status_code=400, detail="Jira tokens not found")
    
    if not integration.external_account_id:
        raise HTTPException(status_code=400, detail="Jira cloud ID not found")
    
    # Check token expiration
    if integration.token_expires_at and integration.token_expires_at < datetime.now(timezone.utc):
        # Try to refresh
        if integration.refresh_token_encrypted:
            try:
                encryption = get_encryption_service()
                refresh_token = encryption.decrypt(integration.refresh_token_encrypted)
                
                oauth = JiraOAuthService()
                new_tokens = await oauth.refresh_access_token(refresh_token)
                
                # Update tokens
                integration.access_token_encrypted = encryption.encrypt(new_tokens["access_token"])
                if new_tokens.get("refresh_token"):
                    integration.refresh_token_encrypted = encryption.encrypt(new_tokens["refresh_token"])
                integration.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=new_tokens.get("expires_in", 3600)
                )
                await session.commit()
                
                return JiraRESTService(new_tokens["access_token"], integration.external_account_id)
            except Exception as e:
                logger.error(f"Jira token refresh failed: {e}")
                integration.status = IntegrationStatus.ERROR.value
                await session.commit()
                raise HTTPException(status_code=401, detail="Jira token expired. Please reconnect.")
        else:
            raise HTTPException(status_code=401, detail="Jira token expired. Please reconnect.")
    
    # Decrypt and return service
    encryption = get_encryption_service()
    access_token = encryption.decrypt(integration.access_token_encrypted)
    return JiraRESTService(access_token, integration.external_account_id)


# ============================================
# Integration Status Endpoints
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
    
    # Build status for all providers
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
# Linear OAuth Endpoints
# ============================================

@router.post("/linear/connect")
async def initiate_linear_oauth(
    request: Request,
    body: ConnectLinearRequest,
    session: AsyncSession = Depends(get_db)
):
    """Initiate Linear OAuth flow"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    oauth_service = LinearOAuthService()
    if not oauth_service.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Linear integration is not configured. Please add LINEAR_OAUTH_CLIENT_ID, LINEAR_OAUTH_CLIENT_SECRET, and LINEAR_OAUTH_REDIRECT_URI to environment."
        )
    
    # Generate state with user_id and callback URL embedded
    state = f"{user_id}|{body.frontend_callback_url}|{secrets.token_urlsafe(16)}"
    
    authorization_url = oauth_service.generate_authorization_url(state)
    
    return {"authorization_url": authorization_url}


@router.get("/linear/callback")
async def linear_oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
    session: AsyncSession = Depends(get_db)
):
    """Handle Linear OAuth callback"""
    if error:
        logger.error(f"Linear OAuth error: {error} - {error_description}")
        # Parse state to get callback URL
        if state:
            parts = state.split("|")
            if len(parts) >= 2:
                callback_url = parts[1]
                return RedirectResponse(url=f"{callback_url}?error={error}&provider=linear")
        return JSONResponse(
            status_code=400, 
            content={"error": error, "description": error_description}
        )
    
    if not code or not state:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing code or state parameter"}
        )
    
    # Parse state
    try:
        parts = state.split("|")
        user_id = parts[0]
        frontend_callback_url = parts[1]
    except (IndexError, ValueError):
        return JSONResponse(status_code=400, content={"error": "Invalid state parameter"})
    
    try:
        oauth_service = LinearOAuthService()
        encryption = get_encryption_service()
        
        # Exchange code for tokens
        token_response = await oauth_service.exchange_code_for_tokens(code)
        
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 86400)
        scope = token_response.get("scope", "read write")
        
        # Get organization info using the access token
        graphql = LinearGraphQLService(access_token)
        org_info = await graphql.get_organization()
        
        # Encrypt tokens
        encrypted_access = encryption.encrypt(access_token)
        encrypted_refresh = encryption.encrypt(refresh_token) if refresh_token else None
        
        # Create or update integration record
        integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
        
        now = datetime.now(timezone.utc)
        
        if integration:
            # Update existing
            integration.status = IntegrationStatus.CONNECTED.value
            integration.external_account_id = org_info.get("id")
            integration.external_account_name = org_info.get("name")
            integration.access_token_encrypted = encrypted_access
            integration.refresh_token_encrypted = encrypted_refresh
            integration.token_expires_at = now + timedelta(seconds=expires_in)
            integration.scopes = {"scope": scope}
            integration.updated_at = now
        else:
            # Create new
            integration = ExternalIntegration(
                user_id=user_id,
                provider=IntegrationProvider.LINEAR.value,
                status=IntegrationStatus.CONNECTED.value,
                external_account_id=org_info.get("id"),
                external_account_name=org_info.get("name"),
                access_token_encrypted=encrypted_access,
                refresh_token_encrypted=encrypted_refresh,
                token_expires_at=now + timedelta(seconds=expires_in),
                scopes={"scope": scope}
            )
            session.add(integration)
        
        await session.commit()
        logger.info(f"Linear integration connected for user {user_id}")
        
        return RedirectResponse(url=f"{frontend_callback_url}?success=true&provider=linear")
    
    except Exception as e:
        logger.error(f"Linear OAuth callback error: {e}")
        if frontend_callback_url:
            return RedirectResponse(url=f"{frontend_callback_url}?error={str(e)}&provider=linear")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/linear/disconnect")
async def disconnect_linear(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Disconnect Linear integration"""
    user_id = await get_current_user_id(request, session)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    
    if not integration:
        return {"status": "not_connected"}
    
    # Try to revoke the token
    if integration.access_token_encrypted:
        try:
            encryption = get_encryption_service()
            access_token = encryption.decrypt(integration.access_token_encrypted)
            oauth = LinearOAuthService()
            await oauth.revoke_token(access_token)
        except Exception as e:
            logger.warning(f"Failed to revoke Linear token: {e}")
    
    # Update integration status
    integration.status = IntegrationStatus.DISCONNECTED.value
    integration.access_token_encrypted = None
    integration.refresh_token_encrypted = None
    integration.token_expires_at = None
    integration.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {"status": "disconnected"}


@router.put("/linear/configure")
async def configure_linear_integration(
    request: Request,
    body: ConfigureIntegrationRequest,
    session: AsyncSession = Depends(get_db)
):
    """Configure Linear integration defaults"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Linear not connected")
    
    integration.default_team_id = body.team_id
    integration.default_team_name = body.team_name
    integration.default_project_id = body.project_id
    integration.default_project_name = body.project_name
    if body.field_mappings:
        integration.field_mappings = body.field_mappings
    integration.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {
        "status": "configured",
        "default_team": {"id": body.team_id, "name": body.team_name},
        "default_project": {"id": body.project_id, "name": body.project_name} if body.project_id else None
    }


# ============================================
# Linear Data Endpoints
# ============================================

@router.get("/linear/teams")
async def get_linear_teams(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get Linear teams/workspaces"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    graphql = await get_linear_service(session, user_id)
    teams = await graphql.get_teams()
    
    return {"teams": teams}


@router.get("/linear/teams/{team_id}/projects")
async def get_linear_team_projects(
    team_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get projects for a Linear team"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    graphql = await get_linear_service(session, user_id)
    projects = await graphql.get_team_projects(team_id)
    
    return {"projects": projects}


@router.get("/linear/teams/{team_id}/labels")
async def get_linear_team_labels(
    team_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get labels for a Linear team"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    graphql = await get_linear_service(session, user_id)
    labels = await graphql.get_team_labels(team_id)
    
    return {"labels": labels}


@router.get("/linear/test")
async def test_linear_connection(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Test Linear connection by fetching viewer info"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    try:
        graphql = await get_linear_service(session, user_id)
        viewer = await graphql.get_viewer()
        org = await graphql.get_organization()
        
        return {
            "status": "connected",
            "viewer": viewer,
            "organization": org
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================
# Push Preview & Execution
# ============================================

@router.post("/linear/preview")
async def preview_linear_push(
    request: Request,
    body: PushPreviewRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Preview what will be pushed to Linear without actually pushing.
    Shows items that would be created vs updated.
    """
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    # Get integration
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Linear not connected")
    
    # Get epic with related data
    epic_result = await session.execute(
        select(Epic)
        .options(selectinload(Epic.snapshot))
        .where(and_(Epic.epic_id == body.epic_id, Epic.user_id == user_id))
    )
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get existing mappings
    mappings_result = await session.execute(
        select(ExternalPushMapping).where(
            and_(
                ExternalPushMapping.user_id == user_id,
                ExternalPushMapping.provider == IntegrationProvider.LINEAR.value
            )
        )
    )
    existing_mappings = {m.entity_id: m for m in mappings_result.scalars().all()}
    
    preview = {
        "epic": None,
        "features": [],
        "stories": [],
        "bugs": [],
        "totals": {
            "create": 0,
            "update": 0,
            "skip": 0
        }
    }
    
    # Preview epic
    epic_action = "update" if epic.epic_id in existing_mappings else "create"
    preview["epic"] = {
        "entity_id": epic.epic_id,
        "title": epic.title,
        "action": epic_action,
        "existing_key": existing_mappings.get(epic.epic_id, {}).external_key if epic.epic_id in existing_mappings else None
    }
    preview["totals"][epic_action] += 1
    
    # Preview features if scope includes them
    if body.push_scope in ["epic_features", "epic_features_stories"]:
        features_result = await session.execute(
            select(Feature).where(Feature.epic_id == body.epic_id)
        )
        features = features_result.scalars().all()
        
        for feature in features:
            feature_action = "update" if feature.feature_id in existing_mappings else "create"
            preview["features"].append({
                "entity_id": feature.feature_id,
                "title": feature.title,
                "action": feature_action,
                "existing_key": existing_mappings.get(feature.feature_id, {}).external_key if feature.feature_id in existing_mappings else None
            })
            preview["totals"][feature_action] += 1
            
            # Preview stories if scope includes them
            if body.push_scope == "epic_features_stories":
                stories_result = await session.execute(
                    select(UserStory).where(UserStory.feature_id == feature.feature_id)
                )
                stories = stories_result.scalars().all()
                
                for story in stories:
                    story_action = "update" if story.story_id in existing_mappings else "create"
                    preview["stories"].append({
                        "entity_id": story.story_id,
                        "title": story.story_text[:100] + "..." if len(story.story_text) > 100 else story.story_text,
                        "parent_feature_id": feature.feature_id,
                        "action": story_action,
                        "existing_key": existing_mappings.get(story.story_id, {}).external_key if story.story_id in existing_mappings else None
                    })
                    preview["totals"][story_action] += 1
    
    return preview


@router.post("/linear/push")
async def push_to_linear(
    request: Request,
    body: PushRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Push epic (and optionally features/stories) to Linear.
    Creates new issues or updates existing ones based on mappings.
    """
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    # Get integration
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Linear not connected")
    
    # Get Linear service
    graphql = await get_linear_service(session, user_id)
    push_service = LinearPushService(graphql)
    
    # Get epic with related data
    epic_result = await session.execute(
        select(Epic)
        .options(selectinload(Epic.snapshot))
        .where(and_(Epic.epic_id == body.epic_id, Epic.user_id == user_id))
    )
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Create push run record
    push_run = ExternalPushRun(
        user_id=user_id,
        integration_id=integration.integration_id,
        provider=IntegrationProvider.LINEAR.value,
        epic_id=body.epic_id,
        push_scope=body.push_scope,
        include_bugs=body.include_bugs,
        is_dry_run=body.dry_run
    )
    session.add(push_run)
    
    results = {
        "run_id": push_run.run_id,
        "created": [],
        "updated": [],
        "errors": [],
        "links": []
    }
    
    try:
        # Get existing mappings
        mappings_result = await session.execute(
            select(ExternalPushMapping).where(
                and_(
                    ExternalPushMapping.user_id == user_id,
                    ExternalPushMapping.provider == IntegrationProvider.LINEAR.value
                )
            )
        )
        existing_mappings = {m.entity_id: m for m in mappings_result.scalars().all()}
        
        # Push epic
        epic_title = f"[Epic] {epic.title}"
        snapshot = epic.snapshot
        epic_description = push_service.format_epic_description(
            {"epic_id": epic.epic_id, "title": epic.title},
            {
                "problem_statement": snapshot.problem_statement if snapshot else None,
                "desired_outcome": snapshot.desired_outcome if snapshot else None,
                "epic_summary": snapshot.epic_summary if snapshot else None,
                "acceptance_criteria": snapshot.acceptance_criteria if snapshot else None
            }
        )
        
        existing_epic_mapping = existing_mappings.get(epic.epic_id)
        
        if not body.dry_run:
            epic_result = await push_service.push_item(
                team_id=body.team_id,
                title=epic_title,
                description=epic_description,
                entity_type=EntityType.EPIC.value,
                entity_id=epic.epic_id,
                existing_external_id=existing_epic_mapping.external_id if existing_epic_mapping else None,
                project_id=body.project_id
            )
            
            # Create or update mapping
            if existing_epic_mapping:
                existing_epic_mapping.external_key = epic_result["external_key"]
                existing_epic_mapping.external_url = epic_result["external_url"]
                existing_epic_mapping.last_pushed_at = datetime.now(timezone.utc)
                existing_epic_mapping.last_push_hash = epic_result["payload_hash"]
                results["updated"].append({
                    "type": "epic",
                    "entity_id": epic.epic_id,
                    "external_key": epic_result["external_key"],
                    "url": epic_result["external_url"]
                })
            else:
                new_mapping = ExternalPushMapping(
                    user_id=user_id,
                    integration_id=integration.integration_id,
                    provider=IntegrationProvider.LINEAR.value,
                    entity_type=EntityType.EPIC.value,
                    entity_id=epic.epic_id,
                    external_type="Linear Issue",
                    external_id=epic_result["external_id"],
                    external_key=epic_result["external_key"],
                    external_url=epic_result["external_url"],
                    team_id=body.team_id,
                    project_id=body.project_id,
                    last_push_hash=epic_result["payload_hash"]
                )
                session.add(new_mapping)
                existing_mappings[epic.epic_id] = new_mapping
                results["created"].append({
                    "type": "epic",
                    "entity_id": epic.epic_id,
                    "external_key": epic_result["external_key"],
                    "url": epic_result["external_url"]
                })
            
            results["links"].append(epic_result["external_url"])
            parent_epic_external_id = epic_result["external_id"]
        else:
            parent_epic_external_id = None
        
        # Push features if scope includes them
        if body.push_scope in ["epic_features", "epic_features_stories"]:
            features_result = await session.execute(
                select(Feature).where(Feature.epic_id == body.epic_id)
            )
            features = features_result.scalars().all()
            
            for feature in features:
                feature_title = f"[Feature] {feature.title}"
                feature_description = push_service.format_feature_description({
                    "feature_id": feature.feature_id,
                    "description": feature.description,
                    "acceptance_criteria": feature.acceptance_criteria
                })
                
                existing_feature_mapping = existing_mappings.get(feature.feature_id)
                
                if not body.dry_run:
                    try:
                        feature_result = await push_service.push_item(
                            team_id=body.team_id,
                            title=feature_title,
                            description=feature_description,
                            entity_type=EntityType.FEATURE.value,
                            entity_id=feature.feature_id,
                            existing_external_id=existing_feature_mapping.external_id if existing_feature_mapping else None,
                            parent_external_id=parent_epic_external_id,
                            project_id=body.project_id
                        )
                        
                        if existing_feature_mapping:
                            existing_feature_mapping.external_key = feature_result["external_key"]
                            existing_feature_mapping.external_url = feature_result["external_url"]
                            existing_feature_mapping.last_pushed_at = datetime.now(timezone.utc)
                            existing_feature_mapping.last_push_hash = feature_result["payload_hash"]
                            results["updated"].append({
                                "type": "feature",
                                "entity_id": feature.feature_id,
                                "external_key": feature_result["external_key"],
                                "url": feature_result["external_url"]
                            })
                        else:
                            new_mapping = ExternalPushMapping(
                                user_id=user_id,
                                integration_id=integration.integration_id,
                                provider=IntegrationProvider.LINEAR.value,
                                entity_type=EntityType.FEATURE.value,
                                entity_id=feature.feature_id,
                                external_type="Linear Issue",
                                external_id=feature_result["external_id"],
                                external_key=feature_result["external_key"],
                                external_url=feature_result["external_url"],
                                team_id=body.team_id,
                                project_id=body.project_id,
                                last_push_hash=feature_result["payload_hash"]
                            )
                            session.add(new_mapping)
                            existing_mappings[feature.feature_id] = new_mapping
                            results["created"].append({
                                "type": "feature",
                                "entity_id": feature.feature_id,
                                "external_key": feature_result["external_key"],
                                "url": feature_result["external_url"]
                            })
                        
                        results["links"].append(feature_result["external_url"])
                        parent_feature_external_id = feature_result["external_id"]
                    except Exception as e:
                        logger.error(f"Error pushing feature {feature.feature_id}: {e}")
                        results["errors"].append({
                            "type": "feature",
                            "entity_id": feature.feature_id,
                            "error": str(e)
                        })
                        parent_feature_external_id = None
                        continue
                else:
                    parent_feature_external_id = None
                
                # Push stories if scope includes them
                if body.push_scope == "epic_features_stories":
                    stories_result = await session.execute(
                        select(UserStory).where(UserStory.feature_id == feature.feature_id)
                    )
                    stories = stories_result.scalars().all()
                    
                    for story in stories:
                        story_title = story.title if story.title else story.story_text[:80]
                        story_description = push_service.format_story_description({
                            "story_id": story.story_id,
                            "persona": story.persona,
                            "action": story.action,
                            "benefit": story.benefit,
                            "acceptance_criteria": story.acceptance_criteria,
                            "story_points": story.story_points
                        })
                        
                        existing_story_mapping = existing_mappings.get(story.story_id)
                        
                        if not body.dry_run:
                            try:
                                story_result = await push_service.push_item(
                                    team_id=body.team_id,
                                    title=story_title,
                                    description=story_description,
                                    entity_type=EntityType.STORY.value,
                                    entity_id=story.story_id,
                                    existing_external_id=existing_story_mapping.external_id if existing_story_mapping else None,
                                    parent_external_id=parent_feature_external_id,
                                    estimate=story.story_points,
                                    project_id=body.project_id
                                )
                                
                                if existing_story_mapping:
                                    existing_story_mapping.external_key = story_result["external_key"]
                                    existing_story_mapping.external_url = story_result["external_url"]
                                    existing_story_mapping.last_pushed_at = datetime.now(timezone.utc)
                                    existing_story_mapping.last_push_hash = story_result["payload_hash"]
                                    results["updated"].append({
                                        "type": "story",
                                        "entity_id": story.story_id,
                                        "external_key": story_result["external_key"],
                                        "url": story_result["external_url"]
                                    })
                                else:
                                    new_mapping = ExternalPushMapping(
                                        user_id=user_id,
                                        integration_id=integration.integration_id,
                                        provider=IntegrationProvider.LINEAR.value,
                                        entity_type=EntityType.STORY.value,
                                        entity_id=story.story_id,
                                        external_type="Linear Issue",
                                        external_id=story_result["external_id"],
                                        external_key=story_result["external_key"],
                                        external_url=story_result["external_url"],
                                        team_id=body.team_id,
                                        project_id=body.project_id,
                                        last_push_hash=story_result["payload_hash"]
                                    )
                                    session.add(new_mapping)
                                    results["created"].append({
                                        "type": "story",
                                        "entity_id": story.story_id,
                                        "external_key": story_result["external_key"],
                                        "url": story_result["external_url"]
                                    })
                                
                                results["links"].append(story_result["external_url"])
                            except Exception as e:
                                logger.error(f"Error pushing story {story.story_id}: {e}")
                                results["errors"].append({
                                    "type": "story",
                                    "entity_id": story.story_id,
                                    "error": str(e)
                                })
        
        # Update push run with results
        push_run.ended_at = datetime.now(timezone.utc)
        push_run.status = PushStatus.PARTIAL.value if results["errors"] else PushStatus.SUCCESS.value
        push_run.summary_json = {
            "created": len(results["created"]),
            "updated": len(results["updated"]),
            "errors": len(results["errors"]),
            "links": results["links"][:10]  # Limit stored links
        }
        if results["errors"]:
            push_run.error_json = {"errors": results["errors"]}
        
        await session.commit()
        
        return results
    
    except Exception as e:
        logger.error(f"Push to Linear failed: {e}")
        push_run.ended_at = datetime.now(timezone.utc)
        push_run.status = PushStatus.FAILED.value
        push_run.error_json = {"error": str(e)}
        await session.commit()
        raise HTTPException(status_code=500, detail=str(e))


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
# Jira OAuth Endpoints
# ============================================

@router.post("/jira/connect")
async def initiate_jira_oauth(
    request: Request,
    body: ConnectJiraRequest,
    session: AsyncSession = Depends(get_db)
):
    """Initiate Jira Cloud OAuth 2.0 (3LO) flow"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    oauth_service = JiraOAuthService()
    if not oauth_service.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Jira integration is not configured. Please add JIRA_OAUTH_CLIENT_ID, JIRA_OAUTH_CLIENT_SECRET, and JIRA_OAUTH_REDIRECT_URI to environment."
        )
    
    # Generate state with user_id and callback URL embedded
    state = f"{user_id}|{body.frontend_callback_url}|{secrets.token_urlsafe(16)}"
    
    authorization_url = oauth_service.generate_authorization_url(state)
    
    return {"authorization_url": authorization_url}


@router.get("/jira/callback")
async def jira_oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
    session: AsyncSession = Depends(get_db)
):
    """Handle Jira OAuth callback"""
    if error:
        logger.error(f"Jira OAuth error: {error} - {error_description}")
        if state:
            parts = state.split("|")
            if len(parts) >= 2:
                callback_url = parts[1]
                return RedirectResponse(url=f"{callback_url}?error={error}&provider=jira")
        return JSONResponse(
            status_code=400, 
            content={"error": error, "description": error_description}
        )
    
    if not code or not state:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing code or state parameter"}
        )
    
    # Parse state
    try:
        parts = state.split("|")
        user_id = parts[0]
        frontend_callback_url = parts[1]
    except (IndexError, ValueError):
        return JSONResponse(status_code=400, content={"error": "Invalid state parameter"})
    
    try:
        oauth_service = JiraOAuthService()
        encryption = get_encryption_service()
        
        # Exchange code for tokens
        token_response = await oauth_service.exchange_code_for_tokens(code)
        
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 3600)
        scope = token_response.get("scope", "")
        
        # Get accessible resources (cloud IDs)
        resources = await oauth_service.get_accessible_resources(access_token)
        
        if not resources:
            raise HTTPException(status_code=400, detail="No accessible Jira sites found")
        
        # Use the first accessible resource (user can change later)
        primary_resource = resources[0]
        cloud_id = primary_resource.get("id")
        site_name = primary_resource.get("name")
        site_url = primary_resource.get("url")
        
        # Encrypt tokens
        encrypted_access = encryption.encrypt(access_token)
        encrypted_refresh = encryption.encrypt(refresh_token) if refresh_token else None
        
        # Create or update integration record
        integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
        
        now = datetime.now(timezone.utc)
        
        if integration:
            # Update existing
            integration.status = IntegrationStatus.CONNECTED.value
            integration.external_account_id = cloud_id
            integration.external_account_name = site_name
            integration.org_url = site_url
            integration.access_token_encrypted = encrypted_access
            integration.refresh_token_encrypted = encrypted_refresh
            integration.token_expires_at = now + timedelta(seconds=expires_in)
            integration.scopes = {"scope": scope, "accessible_resources": resources}
            integration.updated_at = now
        else:
            # Create new
            integration = ExternalIntegration(
                user_id=user_id,
                provider=IntegrationProvider.JIRA.value,
                status=IntegrationStatus.CONNECTED.value,
                external_account_id=cloud_id,
                external_account_name=site_name,
                org_url=site_url,
                access_token_encrypted=encrypted_access,
                refresh_token_encrypted=encrypted_refresh,
                token_expires_at=now + timedelta(seconds=expires_in),
                scopes={"scope": scope, "accessible_resources": resources}
            )
            session.add(integration)
        
        await session.commit()
        logger.info(f"Jira integration connected for user {user_id}, cloud_id: {cloud_id}")
        
        return RedirectResponse(url=f"{frontend_callback_url}?success=true&provider=jira")
    
    except Exception as e:
        logger.error(f"Jira OAuth callback error: {e}")
        if frontend_callback_url:
            return RedirectResponse(url=f"{frontend_callback_url}?error={str(e)}&provider=jira")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jira/disconnect")
async def disconnect_jira(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Disconnect Jira integration"""
    user_id = await get_current_user_id(request, session)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    
    if not integration:
        return {"status": "not_connected"}
    
    # Update integration status (Jira doesn't have a revoke endpoint like Linear)
    integration.status = IntegrationStatus.DISCONNECTED.value
    integration.access_token_encrypted = None
    integration.refresh_token_encrypted = None
    integration.token_expires_at = None
    integration.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {"status": "disconnected"}


@router.put("/jira/configure")
async def configure_jira_integration(
    request: Request,
    body: ConfigureJiraRequest,
    session: AsyncSession = Depends(get_db)
):
    """Configure Jira integration defaults and field mappings"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Jira not connected")
    
    # Update configuration
    integration.external_account_id = body.cloud_id
    integration.external_account_name = body.site_name
    integration.default_project_id = body.project_key
    integration.default_project_name = body.project_name
    
    # Store field mappings
    field_mappings = integration.field_mappings or {}
    if body.issue_type_mapping:
        field_mappings["issue_types"] = body.issue_type_mapping
    if body.story_points_field:
        field_mappings["story_points_field"] = body.story_points_field
    if body.epic_link_field:
        field_mappings["epic_link_field"] = body.epic_link_field
    if body.label_prefix:
        field_mappings["label_prefix"] = body.label_prefix
    
    integration.field_mappings = field_mappings
    integration.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {
        "status": "configured",
        "cloud_id": body.cloud_id,
        "site_name": body.site_name,
        "default_project": {"key": body.project_key, "name": body.project_name},
        "field_mappings": field_mappings
    }


# ============================================
# Jira Data Endpoints
# ============================================

@router.get("/jira/sites")
async def get_jira_sites(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get accessible Jira sites (cloud IDs) for the user"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Jira not connected")
    
    # Return cached accessible resources from scopes
    resources = integration.scopes.get("accessible_resources", []) if integration.scopes else []
    
    return {
        "sites": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "url": r.get("url"),
                "scopes": r.get("scopes", [])
            }
            for r in resources
        ],
        "current_site": {
            "id": integration.external_account_id,
            "name": integration.external_account_name
        }
    }


@router.get("/jira/projects")
async def get_jira_projects(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get projects for the connected Jira site"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    jira = await get_jira_service(session, user_id)
    projects = await jira.get_projects()
    
    return {
        "projects": [
            {
                "id": p.get("id"),
                "key": p.get("key"),
                "name": p.get("name"),
                "projectTypeKey": p.get("projectTypeKey")
            }
            for p in projects
        ]
    }


@router.get("/jira/projects/{project_key}/issue-types")
async def get_jira_issue_types(
    project_key: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get issue types available for a Jira project"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    jira = await get_jira_service(session, user_id)
    issue_types = await jira.get_issue_types_for_project(project_key)
    
    return {
        "issue_types": [
            {
                "id": it.get("id"),
                "name": it.get("name"),
                "description": it.get("description"),
                "subtask": it.get("subtask", False)
            }
            for it in issue_types
        ]
    }


@router.get("/jira/fields")
async def get_jira_fields(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all fields including custom fields (for field mapping)"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    jira = await get_jira_service(session, user_id)
    fields = await jira.get_fields()
    
    # Filter to show relevant custom fields
    custom_fields = [
        {
            "id": f.get("id"),
            "name": f.get("name"),
            "custom": f.get("custom", False),
            "schema": f.get("schema", {}).get("type", "unknown")
        }
        for f in fields
        if f.get("custom") or f.get("name", "").lower() in ["story points", "epic link", "epic name", "labels"]
    ]
    
    return {"fields": custom_fields}


@router.get("/jira/test")
async def test_jira_connection(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Test Jira connection by fetching current user info"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    try:
        jira = await get_jira_service(session, user_id)
        myself = await jira.get_myself()
        server_info = await jira.get_server_info()
        
        return {
            "status": "connected",
            "user": {
                "accountId": myself.get("accountId"),
                "displayName": myself.get("displayName"),
                "emailAddress": myself.get("emailAddress")
            },
            "server": {
                "baseUrl": server_info.get("baseUrl"),
                "serverTitle": server_info.get("serverTitle")
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================
# Jira Push Endpoints
# ============================================

@router.post("/jira/preview")
async def preview_jira_push(
    request: Request,
    body: PushPreviewRequest,
    session: AsyncSession = Depends(get_db)
):
    """Preview what will be pushed to Jira without actually pushing"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    # Get integration
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Jira not connected")
    
    # Get epic with related data
    epic_result = await session.execute(
        select(Epic)
        .options(selectinload(Epic.snapshot))
        .where(and_(Epic.epic_id == body.epic_id, Epic.user_id == user_id))
    )
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get existing mappings
    mappings_result = await session.execute(
        select(ExternalPushMapping).where(
            and_(
                ExternalPushMapping.user_id == user_id,
                ExternalPushMapping.provider == IntegrationProvider.JIRA.value
            )
        )
    )
    existing_mappings = {m.entity_id: m for m in mappings_result.scalars().all()}
    
    preview = {
        "epic": None,
        "features": [],
        "stories": [],
        "bugs": [],
        "totals": {"create": 0, "update": 0, "skip": 0}
    }
    
    # Preview epic
    epic_action = "update" if epic.epic_id in existing_mappings else "create"
    epic_mapping = existing_mappings.get(epic.epic_id)
    preview["epic"] = {
        "entity_id": epic.epic_id,
        "title": epic.title,
        "action": epic_action,
        "existing_key": epic_mapping.external_key if epic_mapping else None
    }
    preview["totals"][epic_action] += 1
    
    # Preview features if scope includes them
    if body.push_scope in ["epic_features", "epic_features_stories", "full"]:
        features_result = await session.execute(
            select(Feature).where(Feature.epic_id == body.epic_id)
        )
        features = features_result.scalars().all()
        
        for feature in features:
            feature_action = "update" if feature.feature_id in existing_mappings else "create"
            feature_mapping = existing_mappings.get(feature.feature_id)
            preview["features"].append({
                "entity_id": feature.feature_id,
                "title": feature.title,
                "action": feature_action,
                "existing_key": feature_mapping.external_key if feature_mapping else None
            })
            preview["totals"][feature_action] += 1
            
            # Preview stories if scope includes them
            if body.push_scope in ["epic_features_stories", "full"]:
                stories_result = await session.execute(
                    select(UserStory).where(UserStory.feature_id == feature.feature_id)
                )
                stories = stories_result.scalars().all()
                
                for story in stories:
                    story_action = "update" if story.story_id in existing_mappings else "create"
                    story_mapping = existing_mappings.get(story.story_id)
                    preview["stories"].append({
                        "entity_id": story.story_id,
                        "title": story.story_text[:100] + "..." if len(story.story_text) > 100 else story.story_text,
                        "parent_feature_id": feature.feature_id,
                        "action": story_action,
                        "existing_key": story_mapping.external_key if story_mapping else None
                    })
                    preview["totals"][story_action] += 1
    
    return preview


@router.post("/jira/push")
async def push_to_jira(
    request: Request,
    body: JiraPushRequest,
    session: AsyncSession = Depends(get_db)
):
    """Push epic (and optionally features/stories) to Jira"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    # Get integration
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Jira not connected")
    
    # Get Jira service
    jira = await get_jira_service(session, user_id)
    push_service = JiraPushService(jira)
    
    # Get field mappings from integration
    field_mappings = integration.field_mappings or {}
    issue_type_mapping = field_mappings.get("issue_types", {})
    
    # Get epic with related data
    epic_result = await session.execute(
        select(Epic)
        .options(selectinload(Epic.snapshot))
        .where(and_(Epic.epic_id == body.epic_id, Epic.user_id == user_id))
    )
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Create push run record
    push_run = ExternalPushRun(
        user_id=user_id,
        integration_id=integration.integration_id,
        provider=IntegrationProvider.JIRA.value,
        epic_id=body.epic_id,
        push_scope=body.push_scope,
        include_bugs=body.include_bugs,
        is_dry_run=body.dry_run
    )
    session.add(push_run)
    
    results = {
        "run_id": push_run.run_id,
        "created": [],
        "updated": [],
        "errors": [],
        "links": []
    }
    
    try:
        # Get existing mappings
        mappings_result = await session.execute(
            select(ExternalPushMapping).where(
                and_(
                    ExternalPushMapping.user_id == user_id,
                    ExternalPushMapping.provider == IntegrationProvider.JIRA.value
                )
            )
        )
        existing_mappings = {m.entity_id: m for m in mappings_result.scalars().all()}
        
        # Push epic
        snapshot = epic.snapshot
        epic_description = push_service.format_epic_description(
            {"epic_id": epic.epic_id, "title": epic.title},
            {
                "problem_statement": snapshot.problem_statement if snapshot else None,
                "desired_outcome": snapshot.desired_outcome if snapshot else None,
                "epic_summary": snapshot.epic_summary if snapshot else None,
                "acceptance_criteria": snapshot.acceptance_criteria if snapshot else None
            }
        )
        
        existing_epic_mapping = existing_mappings.get(epic.epic_id)
        
        if not body.dry_run:
            epic_result = await push_service.push_item(
                project_key=body.project_key,
                issue_type="Epic",
                title=epic.title,
                description=epic_description,
                entity_type=EntityType.EPIC.value,
                entity_id=epic.epic_id,
                existing_issue_key=existing_epic_mapping.external_key if existing_epic_mapping else None,
                field_mappings=field_mappings
            )
            
            # Create or update mapping
            if existing_epic_mapping:
                existing_epic_mapping.external_key = epic_result["key"]
                existing_epic_mapping.external_url = epic_result["url"]
                existing_epic_mapping.last_pushed_at = datetime.now(timezone.utc)
                existing_epic_mapping.last_push_hash = epic_result["payload_hash"]
                results["updated"].append({
                    "type": "epic",
                    "entity_id": epic.epic_id,
                    "external_key": epic_result["key"],
                    "url": epic_result["url"]
                })
            else:
                new_mapping = ExternalPushMapping(
                    user_id=user_id,
                    integration_id=integration.integration_id,
                    provider=IntegrationProvider.JIRA.value,
                    entity_type=EntityType.EPIC.value,
                    entity_id=epic.epic_id,
                    external_type="Jira Issue",
                    external_id=epic_result["id"],
                    external_key=epic_result["key"],
                    external_url=epic_result["url"],
                    project_id=body.project_key,
                    last_push_hash=epic_result["payload_hash"]
                )
                session.add(new_mapping)
                existing_mappings[epic.epic_id] = new_mapping
                results["created"].append({
                    "type": "epic",
                    "entity_id": epic.epic_id,
                    "external_key": epic_result["key"],
                    "url": epic_result["url"]
                })
            
            results["links"].append(epic_result["url"])
            parent_epic_key = epic_result["key"]
        else:
            parent_epic_key = None
        
        # Push features if scope includes them
        if body.push_scope in ["epic_features", "epic_features_stories", "full"]:
            features_result = await session.execute(
                select(Feature).where(Feature.epic_id == body.epic_id)
            )
            features = features_result.scalars().all()
            
            feature_issue_type = issue_type_mapping.get("feature", "Task")
            
            for feature in features:
                feature_description = push_service.format_feature_description({
                    "feature_id": feature.feature_id,
                    "description": feature.description,
                    "acceptance_criteria": feature.acceptance_criteria
                })
                
                existing_feature_mapping = existing_mappings.get(feature.feature_id)
                
                if not body.dry_run:
                    try:
                        feature_result = await push_service.push_item(
                            project_key=body.project_key,
                            issue_type=feature_issue_type,
                            title=feature.title,
                            description=feature_description,
                            entity_type=EntityType.FEATURE.value,
                            entity_id=feature.feature_id,
                            existing_issue_key=existing_feature_mapping.external_key if existing_feature_mapping else None,
                            epic_link_key=parent_epic_key,
                            field_mappings=field_mappings
                        )
                        
                        if existing_feature_mapping:
                            existing_feature_mapping.external_key = feature_result["key"]
                            existing_feature_mapping.external_url = feature_result["url"]
                            existing_feature_mapping.last_pushed_at = datetime.now(timezone.utc)
                            existing_feature_mapping.last_push_hash = feature_result["payload_hash"]
                            results["updated"].append({
                                "type": "feature",
                                "entity_id": feature.feature_id,
                                "external_key": feature_result["key"],
                                "url": feature_result["url"]
                            })
                        else:
                            new_mapping = ExternalPushMapping(
                                user_id=user_id,
                                integration_id=integration.integration_id,
                                provider=IntegrationProvider.JIRA.value,
                                entity_type=EntityType.FEATURE.value,
                                entity_id=feature.feature_id,
                                external_type="Jira Issue",
                                external_id=feature_result["id"],
                                external_key=feature_result["key"],
                                external_url=feature_result["url"],
                                project_id=body.project_key,
                                last_push_hash=feature_result["payload_hash"]
                            )
                            session.add(new_mapping)
                            existing_mappings[feature.feature_id] = new_mapping
                            results["created"].append({
                                "type": "feature",
                                "entity_id": feature.feature_id,
                                "external_key": feature_result["key"],
                                "url": feature_result["url"]
                            })
                        
                        results["links"].append(feature_result["url"])
                        parent_feature_key = feature_result["key"]
                    except Exception as e:
                        logger.error(f"Error pushing feature {feature.feature_id}: {e}")
                        results["errors"].append({
                            "type": "feature",
                            "entity_id": feature.feature_id,
                            "error": str(e)
                        })
                        parent_feature_key = None
                        continue
                else:
                    parent_feature_key = None
                
                # Push stories if scope includes them
                if body.push_scope in ["epic_features_stories", "full"]:
                    stories_result = await session.execute(
                        select(UserStory).where(UserStory.feature_id == feature.feature_id)
                    )
                    stories = stories_result.scalars().all()
                    
                    story_issue_type = issue_type_mapping.get("story", "Story")
                    
                    for story in stories:
                        story_title = story.title if story.title else story.story_text[:80]
                        story_description = push_service.format_story_description({
                            "story_id": story.story_id,
                            "persona": story.persona,
                            "action": story.action,
                            "benefit": story.benefit,
                            "acceptance_criteria": story.acceptance_criteria,
                            "story_points": story.story_points
                        })
                        
                        existing_story_mapping = existing_mappings.get(story.story_id)
                        
                        if not body.dry_run:
                            try:
                                story_result = await push_service.push_item(
                                    project_key=body.project_key,
                                    issue_type=story_issue_type,
                                    title=story_title,
                                    description=story_description,
                                    entity_type=EntityType.STORY.value,
                                    entity_id=story.story_id,
                                    existing_issue_key=existing_story_mapping.external_key if existing_story_mapping else None,
                                    epic_link_key=parent_epic_key,
                                    story_points=story.story_points,
                                    field_mappings=field_mappings
                                )
                                
                                if existing_story_mapping:
                                    existing_story_mapping.external_key = story_result["key"]
                                    existing_story_mapping.external_url = story_result["url"]
                                    existing_story_mapping.last_pushed_at = datetime.now(timezone.utc)
                                    existing_story_mapping.last_push_hash = story_result["payload_hash"]
                                    results["updated"].append({
                                        "type": "story",
                                        "entity_id": story.story_id,
                                        "external_key": story_result["key"],
                                        "url": story_result["url"]
                                    })
                                else:
                                    new_mapping = ExternalPushMapping(
                                        user_id=user_id,
                                        integration_id=integration.integration_id,
                                        provider=IntegrationProvider.JIRA.value,
                                        entity_type=EntityType.STORY.value,
                                        entity_id=story.story_id,
                                        external_type="Jira Issue",
                                        external_id=story_result["id"],
                                        external_key=story_result["key"],
                                        external_url=story_result["url"],
                                        project_id=body.project_key,
                                        last_push_hash=story_result["payload_hash"]
                                    )
                                    session.add(new_mapping)
                                    results["created"].append({
                                        "type": "story",
                                        "entity_id": story.story_id,
                                        "external_key": story_result["key"],
                                        "url": story_result["url"]
                                    })
                                
                                results["links"].append(story_result["url"])
                            except Exception as e:
                                logger.error(f"Error pushing story {story.story_id}: {e}")
                                results["errors"].append({
                                    "type": "story",
                                    "entity_id": story.story_id,
                                    "error": str(e)
                                })
        
        # Update push run with results
        push_run.ended_at = datetime.now(timezone.utc)
        push_run.status = PushStatus.PARTIAL.value if results["errors"] else PushStatus.SUCCESS.value
        push_run.summary_json = {
            "created": len(results["created"]),
            "updated": len(results["updated"]),
            "errors": len(results["errors"]),
            "links": results["links"][:10]
        }
        if results["errors"]:
            push_run.error_json = {"errors": results["errors"]}
        
        await session.commit()
        
        return results
    
    except Exception as e:
        logger.error(f"Push to Jira failed: {e}")
        push_run.ended_at = datetime.now(timezone.utc)
        push_run.status = PushStatus.FAILED.value
        push_run.error_json = {"error": str(e)}
        await session.commit()
        raise HTTPException(status_code=500, detail=str(e))

