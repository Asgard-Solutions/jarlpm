"""
Linear Integration Routes
Handles OAuth flow, team/project management, and push operations for Linear.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime, timezone, timedelta
import secrets
import logging

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import Epic, EpicSnapshot
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

from .shared import (
    check_subscription_required,
    get_user_integration,
    get_linear_service,
    ConnectLinearRequest,
    ConfigureLinearRequest,
    LinearPushRequest,
    PushPreviewRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linear", tags=["linear"])


# ============================================
# OAuth Endpoints
# ============================================

@router.post("/connect")
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
    
    state = f"{user_id}|{body.frontend_callback_url}|{secrets.token_urlsafe(16)}"
    authorization_url = oauth_service.generate_authorization_url(state)
    
    return {"authorization_url": authorization_url}


@router.get("/callback")
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
    
    try:
        parts = state.split("|")
        user_id = parts[0]
        frontend_callback_url = parts[1]
    except (IndexError, ValueError):
        return JSONResponse(status_code=400, content={"error": "Invalid state parameter"})
    
    try:
        oauth_service = LinearOAuthService()
        encryption = get_encryption_service()
        
        token_response = await oauth_service.exchange_code_for_tokens(code)
        
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 86400)
        scope = token_response.get("scope", "read write")
        
        graphql = LinearGraphQLService(access_token)
        org_info = await graphql.get_organization()
        
        encrypted_access = encryption.encrypt(access_token)
        encrypted_refresh = encryption.encrypt(refresh_token) if refresh_token else None
        
        integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
        
        now = datetime.now(timezone.utc)
        
        if integration:
            integration.status = IntegrationStatus.CONNECTED.value
            integration.external_account_id = org_info.get("id")
            integration.external_account_name = org_info.get("name")
            integration.access_token_encrypted = encrypted_access
            integration.refresh_token_encrypted = encrypted_refresh
            integration.token_expires_at = now + timedelta(seconds=expires_in)
            integration.scopes = {"scope": scope}
            integration.updated_at = now
        else:
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


@router.post("/disconnect")
async def disconnect_linear(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Disconnect Linear integration"""
    user_id = await get_current_user_id(request, session)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    
    if not integration:
        return {"status": "not_connected"}
    
    if integration.access_token_encrypted:
        try:
            encryption = get_encryption_service()
            access_token = encryption.decrypt(integration.access_token_encrypted)
            oauth = LinearOAuthService()
            await oauth.revoke_token(access_token)
        except Exception as e:
            logger.warning(f"Failed to revoke Linear token: {e}")
    
    integration.status = IntegrationStatus.DISCONNECTED.value
    integration.access_token_encrypted = None
    integration.refresh_token_encrypted = None
    integration.token_expires_at = None
    integration.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {"status": "disconnected"}


# ============================================
# Configuration
# ============================================

@router.put("/configure")
async def configure_linear_integration(
    request: Request,
    body: ConfigureLinearRequest,
    session: AsyncSession = Depends(get_db)
):
    """Configure Linear integration defaults including priority and label settings"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Linear not connected")
    
    integration.default_team_id = body.team_id
    integration.default_team_name = body.team_name
    integration.default_project_id = body.project_id
    integration.default_project_name = body.project_name
    
    field_mappings = integration.field_mappings or {}
    
    if body.priority_mapping:
        field_mappings["priority_mapping"] = body.priority_mapping
    if body.label_policy:
        field_mappings["label_policy"] = body.label_policy
    if body.epic_mapping:
        field_mappings["epic_mapping"] = body.epic_mapping
    if body.field_mappings:
        field_mappings.update(body.field_mappings)
    
    integration.field_mappings = field_mappings
    integration.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {
        "status": "configured",
        "default_team": {"id": body.team_id, "name": body.team_name},
        "default_project": {"id": body.project_id, "name": body.project_name} if body.project_id else None,
        "priority_mapping": field_mappings.get("priority_mapping"),
        "label_policy": field_mappings.get("label_policy", "create-missing"),
        "epic_mapping": field_mappings.get("epic_mapping", "issue")
    }


# ============================================
# Data Endpoints
# ============================================

@router.get("/teams")
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


@router.get("/teams/{team_id}/projects")
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


@router.get("/teams/{team_id}/labels")
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


@router.get("/labels")
async def get_linear_organization_labels(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all labels in the Linear organization"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    graphql = await get_linear_service(session, user_id)
    labels = await graphql.get_organization_labels()
    
    return {"labels": labels}


@router.get("/test")
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

@router.post("/preview")
async def preview_linear_push(
    request: Request,
    body: PushPreviewRequest,
    session: AsyncSession = Depends(get_db)
):
    """Preview what will be pushed to Linear without actually pushing."""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    # Verify Linear connection
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Linear integration not connected")
    
    # Fetch Epic and related data
    epic_result = await session.execute(
        select(Epic).where(and_(Epic.epic_id == body.epic_id, Epic.user_id == user_id))
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Build preview response
    preview = {
        "epic": {
            "id": epic.epic_id,
            "title": epic.title,
            "action": "create"
        },
        "features": [],
        "stories": [],
        "totals": {"create": 1, "update": 0}
    }
    
    # Check if epic already pushed
    epic_mapping = await session.execute(
        select(ExternalPushMapping).where(
            and_(
                ExternalPushMapping.user_id == user_id,
                ExternalPushMapping.provider == IntegrationProvider.LINEAR.value,
                ExternalPushMapping.entity_id == epic.epic_id
            )
        )
    )
    if epic_mapping.scalar_one_or_none():
        preview["epic"]["action"] = "update"
        preview["totals"]["create"] -= 1
        preview["totals"]["update"] += 1
    
    # Include features if scope allows
    if body.push_scope in ["epic_features", "epic_features_stories"]:
        features_result = await session.execute(
            select(Feature).where(Feature.epic_id == body.epic_id)
        )
        features = features_result.scalars().all()
        
        for feature in features:
            feature_preview = {
                "id": feature.feature_id,
                "title": feature.title,
                "action": "create"
            }
            
            # Check if feature already pushed
            feature_mapping = await session.execute(
                select(ExternalPushMapping).where(
                    and_(
                        ExternalPushMapping.user_id == user_id,
                        ExternalPushMapping.provider == IntegrationProvider.LINEAR.value,
                        ExternalPushMapping.entity_id == feature.feature_id
                    )
                )
            )
            if feature_mapping.scalar_one_or_none():
                feature_preview["action"] = "update"
                preview["totals"]["update"] += 1
            else:
                preview["totals"]["create"] += 1
            
            preview["features"].append(feature_preview)
            
            # Include stories if full scope
            if body.push_scope == "epic_features_stories":
                stories_result = await session.execute(
                    select(UserStory).where(UserStory.feature_id == feature.feature_id)
                )
                stories = stories_result.scalars().all()
                
                for story in stories:
                    story_preview = {
                        "id": story.story_id,
                        "title": story.title,
                        "feature_id": feature.feature_id,
                        "action": "create"
                    }
                    
                    story_mapping = await session.execute(
                        select(ExternalPushMapping).where(
                            and_(
                                ExternalPushMapping.user_id == user_id,
                                ExternalPushMapping.provider == IntegrationProvider.LINEAR.value,
                                ExternalPushMapping.entity_id == story.story_id
                            )
                        )
                    )
                    if story_mapping.scalar_one_or_none():
                        story_preview["action"] = "update"
                        preview["totals"]["update"] += 1
                    else:
                        preview["totals"]["create"] += 1
                    
                    preview["stories"].append(story_preview)
    
    return preview


@router.post("/push")
async def push_to_linear(
    request: Request,
    body: LinearPushRequest,
    session: AsyncSession = Depends(get_db)
):
    """Push Epic (and optionally Features/Stories) to Linear."""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    # Verify Linear connection
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Linear integration not connected")
    
    # Fetch Epic
    epic_result = await session.execute(
        select(Epic).where(and_(Epic.epic_id == body.epic_id, Epic.user_id == user_id))
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Fetch snapshot for description
    snapshot_result = await session.execute(
        select(EpicSnapshot)
        .where(EpicSnapshot.epic_id == body.epic_id)
        .order_by(EpicSnapshot.created_at.desc())
        .limit(1)
    )
    snapshot = snapshot_result.scalar_one_or_none()
    
    # Create push run record
    now = datetime.now(timezone.utc)
    push_run = ExternalPushRun(
        user_id=user_id,
        integration_id=integration.integration_id,
        provider=IntegrationProvider.LINEAR.value,
        epic_id=body.epic_id,
        push_scope=body.push_scope,
        is_dry_run=body.dry_run,
        status=PushStatus.PENDING.value,
        started_at=now
    )
    session.add(push_run)
    await session.flush()
    
    results = {
        "run_id": push_run.run_id,
        "created": [],
        "updated": [],
        "errors": []
    }
    
    try:
        graphql = await get_linear_service(session, user_id)
        
        # Get field mappings for priority, labels, etc.
        field_mappings = integration.field_mappings or {}
        priority_mapping = body.priority_mapping or field_mappings.get("priority_mapping", {
            "must": 2, "should": 3, "could": 4, "wont": 0
        })
        label_policy = body.label_policy or field_mappings.get("label_policy", "create-missing")
        epic_mapping_strategy = body.epic_mapping or field_mappings.get("epic_mapping", "issue")
        
        # Initialize push service with enhanced options
        push_service = LinearPushService(graphql)
        
        # Push Epic
        epic_data = {
            "id": epic.epic_id,
            "title": epic.title,
            "description": snapshot.problem_statement if snapshot else epic.title,
            "type": "epic"
        }
        
        # Check existing mapping
        existing_epic = await session.execute(
            select(ExternalPushMapping).where(
                and_(
                    ExternalPushMapping.user_id == user_id,
                    ExternalPushMapping.provider == IntegrationProvider.LINEAR.value,
                    ExternalPushMapping.entity_id == epic.epic_id
                )
            )
        )
        existing_epic_mapping = existing_epic.scalar_one_or_none()
        
        if not body.dry_run:
            try:
                if existing_epic_mapping:
                    # Update existing
                    result = await push_service.update_issue(
                        existing_epic_mapping.external_id,
                        epic_data,
                        body.team_id
                    )
                    results["updated"].append({
                        "type": "epic",
                        "id": epic.epic_id,
                        "external_id": existing_epic_mapping.external_id,
                        "external_key": existing_epic_mapping.external_key,
                        "url": existing_epic_mapping.external_url
                    })
                    existing_epic_mapping.last_pushed_at = now
                    existing_epic_mapping.last_push_hash = compute_payload_hash(epic_data)
                else:
                    # Create new with labels
                    labels = ["epic"]
                    result = await push_service.create_issue(
                        epic_data, 
                        body.team_id, 
                        body.project_id,
                        labels=labels,
                        priority=priority_mapping.get("must", 2),
                        label_policy=label_policy
                    )
                    
                    # Create mapping
                    mapping = ExternalPushMapping(
                        user_id=user_id,
                        provider=IntegrationProvider.LINEAR.value,
                        entity_type=EntityType.EPIC.value,
                        entity_id=epic.epic_id,
                        external_id=result["id"],
                        external_key=result.get("identifier"),
                        external_url=result.get("url"),
                        last_pushed_at=now,
                        last_push_hash=compute_payload_hash(epic_data)
                    )
                    session.add(mapping)
                    
                    results["created"].append({
                        "type": "epic",
                        "id": epic.epic_id,
                        "external_id": result["id"],
                        "external_key": result.get("identifier"),
                        "url": result.get("url")
                    })
                    
                    existing_epic_mapping = mapping
            except Exception as e:
                logger.error(f"Failed to push epic: {e}")
                results["errors"].append({
                    "type": "epic",
                    "id": epic.epic_id,
                    "error": str(e)
                })
        
        # Push Features
        if body.push_scope in ["epic_features", "epic_features_stories"]:
            features_result = await session.execute(
                select(Feature).where(Feature.epic_id == body.epic_id)
            )
            features = features_result.scalars().all()
            
            for feature in features:
                feature_data = {
                    "id": feature.feature_id,
                    "title": feature.title,
                    "description": feature.description or "",
                    "type": "feature",
                    "parent_id": existing_epic_mapping.external_id if existing_epic_mapping else None
                }
                
                # Determine priority based on MoSCoW
                moscow = getattr(feature, 'moscow_score', None)
                feature_priority = priority_mapping.get(moscow.lower() if moscow else "should", 3)
                
                existing_feature = await session.execute(
                    select(ExternalPushMapping).where(
                        and_(
                            ExternalPushMapping.user_id == user_id,
                            ExternalPushMapping.provider == IntegrationProvider.LINEAR.value,
                            ExternalPushMapping.entity_id == feature.feature_id
                        )
                    )
                )
                existing_feature_mapping = existing_feature.scalar_one_or_none()
                
                if not body.dry_run:
                    try:
                        if existing_feature_mapping:
                            result = await push_service.update_issue(
                                existing_feature_mapping.external_id,
                                feature_data,
                                body.team_id
                            )
                            results["updated"].append({
                                "type": "feature",
                                "id": feature.feature_id,
                                "external_id": existing_feature_mapping.external_id,
                                "external_key": existing_feature_mapping.external_key,
                                "url": existing_feature_mapping.external_url
                            })
                            existing_feature_mapping.last_pushed_at = now
                            existing_feature_mapping.last_push_hash = compute_payload_hash(feature_data)
                        else:
                            labels = ["feature"]
                            result = await push_service.create_issue(
                                feature_data, 
                                body.team_id, 
                                body.project_id,
                                parent_id=feature_data.get("parent_id"),
                                labels=labels,
                                priority=feature_priority,
                                label_policy=label_policy
                            )
                            
                            mapping = ExternalPushMapping(
                                user_id=user_id,
                                provider=IntegrationProvider.LINEAR.value,
                                entity_type=EntityType.FEATURE.value,
                                entity_id=feature.feature_id,
                                external_id=result["id"],
                                external_key=result.get("identifier"),
                                external_url=result.get("url"),
                                last_pushed_at=now,
                                last_push_hash=compute_payload_hash(feature_data)
                            )
                            session.add(mapping)
                            
                            results["created"].append({
                                "type": "feature",
                                "id": feature.feature_id,
                                "external_id": result["id"],
                                "external_key": result.get("identifier"),
                                "url": result.get("url")
                            })
                            
                            existing_feature_mapping = mapping
                    except Exception as e:
                        logger.error(f"Failed to push feature {feature.feature_id}: {e}")
                        results["errors"].append({
                            "type": "feature",
                            "id": feature.feature_id,
                            "error": str(e)
                        })
                
                # Push Stories
                if body.push_scope == "epic_features_stories" and existing_feature_mapping:
                    stories_result = await session.execute(
                        select(UserStory).where(UserStory.feature_id == feature.feature_id)
                    )
                    stories = stories_result.scalars().all()
                    
                    for story in stories:
                        story_data = {
                            "id": story.story_id,
                            "title": story.title,
                            "description": f"{story.description or ''}\n\n**Acceptance Criteria:**\n{story.acceptance_criteria or ''}".strip(),
                            "type": "story",
                            "parent_id": existing_feature_mapping.external_id if existing_feature_mapping else None,
                            "estimate": story.story_points
                        }
                        
                        existing_story = await session.execute(
                            select(ExternalPushMapping).where(
                                and_(
                                    ExternalPushMapping.user_id == user_id,
                                    ExternalPushMapping.provider == IntegrationProvider.LINEAR.value,
                                    ExternalPushMapping.entity_id == story.story_id
                                )
                            )
                        )
                        existing_story_mapping = existing_story.scalar_one_or_none()
                        
                        if not body.dry_run:
                            try:
                                if existing_story_mapping:
                                    result = await push_service.update_issue(
                                        existing_story_mapping.external_id,
                                        story_data,
                                        body.team_id
                                    )
                                    results["updated"].append({
                                        "type": "story",
                                        "id": story.story_id,
                                        "external_id": existing_story_mapping.external_id,
                                        "external_key": existing_story_mapping.external_key,
                                        "url": existing_story_mapping.external_url
                                    })
                                    existing_story_mapping.last_pushed_at = now
                                    existing_story_mapping.last_push_hash = compute_payload_hash(story_data)
                                else:
                                    labels = ["story"]
                                    result = await push_service.create_issue(
                                        story_data, 
                                        body.team_id, 
                                        body.project_id,
                                        parent_id=story_data.get("parent_id"),
                                        labels=labels,
                                        priority=priority_mapping.get("should", 3),
                                        label_policy=label_policy,
                                        estimate=story.story_points
                                    )
                                    
                                    mapping = ExternalPushMapping(
                                        user_id=user_id,
                                        provider=IntegrationProvider.LINEAR.value,
                                        entity_type=EntityType.STORY.value,
                                        entity_id=story.story_id,
                                        external_id=result["id"],
                                        external_key=result.get("identifier"),
                                        external_url=result.get("url"),
                                        last_pushed_at=now,
                                        last_push_hash=compute_payload_hash(story_data)
                                    )
                                    session.add(mapping)
                                    
                                    results["created"].append({
                                        "type": "story",
                                        "id": story.story_id,
                                        "external_id": result["id"],
                                        "external_key": result.get("identifier"),
                                        "url": result.get("url")
                                    })
                            except Exception as e:
                                logger.error(f"Failed to push story {story.story_id}: {e}")
                                results["errors"].append({
                                    "type": "story",
                                    "id": story.story_id,
                                    "error": str(e)
                                })
        
        # Update push run status
        push_run.status = PushStatus.SUCCESS.value if not results["errors"] else PushStatus.PARTIAL.value
        push_run.ended_at = datetime.now(timezone.utc)
        push_run.summary_json = {
            "created": len(results["created"]),
            "updated": len(results["updated"]),
            "errors": len(results["errors"])
        }
        if results["errors"]:
            push_run.error_json = results["errors"]
        
        await session.commit()
        
    except Exception as e:
        logger.error(f"Push to Linear failed: {e}")
        push_run.status = PushStatus.FAILED.value
        push_run.ended_at = datetime.now(timezone.utc)
        push_run.error_json = [{"error": str(e)}]
        await session.commit()
        raise HTTPException(status_code=500, detail=str(e))
    
    return results
