"""
Jira Integration Routes
Handles OAuth 3LO flow, project management, and push operations for Jira Cloud.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime, timezone, timedelta
import secrets
import logging

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db import get_db
from db.models import Epic
from db.feature_models import Feature
from db.user_story_models import UserStory
from db.integration_models import (
    ExternalIntegration, ExternalPushMapping, ExternalPushRun,
    IntegrationProvider, IntegrationStatus, PushStatus, EntityType
)
from routes.auth import get_current_user_id
from services.encryption import get_encryption_service
from services.rate_limit import limiter, RATE_LIMITS
from services.jira_service import (
    JiraOAuthService, JiraRESTService, JiraPushService,
    JiraAPIError, AuthenticationError as JiraAuthError
)

from .shared import (
    check_subscription_required,
    get_user_integration,
    get_jira_service,
    ConnectJiraRequest,
    ConfigureJiraRequest,
    JiraPushRequest,
    PushPreviewRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira", tags=["jira"])


# ============================================
# OAuth Endpoints
# ============================================

@router.post("/connect")
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
    
    state = f"{user_id}|{body.frontend_callback_url}|{secrets.token_urlsafe(16)}"
    authorization_url = oauth_service.generate_authorization_url(state)
    
    return {"authorization_url": authorization_url}


@router.get("/callback")
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
    
    try:
        parts = state.split("|")
        user_id = parts[0]
        frontend_callback_url = parts[1]
    except (IndexError, ValueError):
        return JSONResponse(status_code=400, content={"error": "Invalid state parameter"})
    
    try:
        oauth_service = JiraOAuthService()
        encryption = get_encryption_service()
        
        token_response = await oauth_service.exchange_code_for_tokens(code)
        
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 3600)
        scope = token_response.get("scope", "")
        
        resources = await oauth_service.get_accessible_resources(access_token)
        
        if not resources:
            raise HTTPException(status_code=400, detail="No accessible Jira sites found")
        
        primary_resource = resources[0]
        cloud_id = primary_resource.get("id")
        site_name = primary_resource.get("name")
        site_url = primary_resource.get("url")
        
        encrypted_access = encryption.encrypt(access_token)
        encrypted_refresh = encryption.encrypt(refresh_token) if refresh_token else None
        
        integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
        
        now = datetime.now(timezone.utc)
        
        if integration:
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


@router.post("/disconnect")
async def disconnect_jira(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Disconnect Jira integration"""
    user_id = await get_current_user_id(request, session)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    
    if not integration:
        return {"status": "not_connected"}
    
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
    
    integration.external_account_id = body.cloud_id
    integration.external_account_name = body.site_name
    integration.default_project_id = body.project_key
    integration.default_project_name = body.project_name
    
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
# Data Endpoints
# ============================================

@router.get("/sites")
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


@router.get("/projects")
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


@router.get("/projects/{project_key}/issue-types")
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


@router.get("/fields")
async def get_jira_fields(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all fields including custom fields (for field mapping)"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    jira = await get_jira_service(session, user_id)
    fields = await jira.get_fields()
    
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


@router.get("/test")
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
# Push Preview & Execution
# ============================================

@router.post("/preview")
@limiter.limit(RATE_LIMITS["integration_preview"])
async def preview_jira_push(
    request: Request,
    body: PushPreviewRequest,
    session: AsyncSession = Depends(get_db)
):
    """Preview what will be pushed to Jira without actually pushing"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Jira not connected")
    
    epic_result = await session.execute(
        select(Epic)
        .options(selectinload(Epic.snapshot))
        .where(and_(Epic.epic_id == body.epic_id, Epic.user_id == user_id))
    )
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
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
    
    epic_action = "update" if epic.epic_id in existing_mappings else "create"
    epic_mapping = existing_mappings.get(epic.epic_id)
    preview["epic"] = {
        "entity_id": epic.epic_id,
        "title": epic.title,
        "action": epic_action,
        "existing_key": epic_mapping.external_key if epic_mapping else None
    }
    preview["totals"][epic_action] += 1
    
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


@router.post("/push")
async def push_to_jira(
    request: Request,
    body: JiraPushRequest,
    session: AsyncSession = Depends(get_db)
):
    """Push epic (and optionally features/stories) to Jira"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Jira not connected")
    
    jira = await get_jira_service(session, user_id)
    push_service = JiraPushService(jira)
    
    field_mappings = integration.field_mappings or {}
    issue_type_mapping = field_mappings.get("issue_types", {})
    
    epic_result = await session.execute(
        select(Epic)
        .options(selectinload(Epic.snapshot))
        .where(and_(Epic.epic_id == body.epic_id, Epic.user_id == user_id))
    )
    epic = epic_result.scalar_one_or_none()
    
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
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
        mappings_result = await session.execute(
            select(ExternalPushMapping).where(
                and_(
                    ExternalPushMapping.user_id == user_id,
                    ExternalPushMapping.provider == IntegrationProvider.JIRA.value
                )
            )
        )
        existing_mappings = {m.entity_id: m for m in mappings_result.scalars().all()}
        
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
                        continue
                
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
