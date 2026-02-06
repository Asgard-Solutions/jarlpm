"""
Azure DevOps Integration Routes
Handles PAT-based authentication and push operations for Azure DevOps.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from datetime import datetime, timezone
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
from services.azure_devops_service import (
    AzureDevOpsRESTService, AzureDevOpsPushService,
    AzureDevOpsAPIError, AuthenticationError as ADOAuthError
)

from .shared import (
    check_subscription_required,
    get_user_integration,
    get_azure_devops_service,
    ConnectAzureDevOpsRequest,
    ConfigureAzureDevOpsRequest,
    AzureDevOpsPushRequest,
    PushPreviewRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/azure-devops", tags=["azure-devops"])


# ============================================
# Connection Endpoints
# ============================================

@router.post("/connect")
async def connect_azure_devops(
    request: Request,
    body: ConnectAzureDevOpsRequest,
    session: AsyncSession = Depends(get_db)
):
    """Connect Azure DevOps using Personal Access Token (PAT)"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    encryption = get_encryption_service()
    
    try:
        ado_service = AzureDevOpsRESTService(body.organization_url, body.pat)
        connection_test = await ado_service.verify_connection()
        
        if not connection_test.get("valid"):
            raise HTTPException(status_code=400, detail="Failed to verify Azure DevOps connection")
        
    except AzureDevOpsAPIError as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to Azure DevOps: {str(e)}")
    except Exception as e:
        logger.error(f"Azure DevOps connection error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid organization URL or PAT: {str(e)}")
    
    encrypted_pat = encryption.encrypt(body.pat)
    org_name = body.organization_url.rstrip('/').split('/')[-1]
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.AZURE_DEVOPS.value)
    
    now = datetime.now(timezone.utc)
    
    if integration:
        integration.status = IntegrationStatus.CONNECTED.value
        integration.org_url = body.organization_url
        integration.external_account_name = org_name
        integration.pat_encrypted = encrypted_pat
        integration.updated_at = now
    else:
        integration = ExternalIntegration(
            user_id=user_id,
            provider=IntegrationProvider.AZURE_DEVOPS.value,
            status=IntegrationStatus.CONNECTED.value,
            org_url=body.organization_url,
            external_account_name=org_name,
            pat_encrypted=encrypted_pat
        )
        session.add(integration)
    
    await session.commit()
    logger.info(f"Azure DevOps integration connected for user {user_id}, org: {org_name}")
    
    return {
        "status": "connected",
        "organization": org_name,
        "project_count": connection_test.get("project_count", 0)
    }


@router.post("/disconnect")
async def disconnect_azure_devops(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Disconnect Azure DevOps integration"""
    user_id = await get_current_user_id(request, session)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.AZURE_DEVOPS.value)
    
    if not integration:
        return {"status": "not_connected"}
    
    integration.status = IntegrationStatus.DISCONNECTED.value
    integration.pat_encrypted = None
    integration.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {"status": "disconnected"}


# ============================================
# Configuration
# ============================================

@router.put("/configure")
async def configure_azure_devops_integration(
    request: Request,
    body: ConfigureAzureDevOpsRequest,
    session: AsyncSession = Depends(get_db)
):
    """Configure Azure DevOps integration defaults"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.AZURE_DEVOPS.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Azure DevOps not connected")
    
    integration.org_url = body.organization_url
    integration.default_project_id = body.project_id
    integration.default_project_name = body.project_name
    
    field_mappings = integration.field_mappings or {}
    
    if body.default_area_path:
        field_mappings["default_area_path"] = body.default_area_path
    if body.default_iteration_path:
        field_mappings["default_iteration_path"] = body.default_iteration_path
    if body.story_points_field:
        field_mappings["story_points_field"] = body.story_points_field
    if body.description_format:
        field_mappings["description_format"] = body.description_format
    if body.tag_policy:
        field_mappings["tag_policy"] = body.tag_policy
    if body.work_item_types:
        field_mappings["work_item_types"] = body.work_item_types
    
    integration.field_mappings = field_mappings
    integration.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {
        "status": "configured",
        "organization_url": body.organization_url,
        "default_project": body.project_name,
        "field_mappings": field_mappings
    }


# ============================================
# Data Endpoints
# ============================================

@router.get("/projects")
async def get_azure_devops_projects(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get Azure DevOps projects for the connected organization"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    ado = await get_azure_devops_service(session, user_id)
    projects = await ado.get_projects()
    
    return {
        "projects": [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "description": p.get("description"),
                "state": p.get("state")
            }
            for p in projects
        ]
    }


@router.get("/projects/{project_name}/teams")
async def get_azure_devops_teams(
    project_name: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get teams for an Azure DevOps project"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    ado = await get_azure_devops_service(session, user_id)
    teams = await ado.get_teams(project_name)
    
    return {
        "teams": [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "description": t.get("description")
            }
            for t in teams
        ]
    }


@router.get("/projects/{project_name}/iterations")
async def get_azure_devops_iterations(
    project_name: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get iterations/sprints for an Azure DevOps project"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    ado = await get_azure_devops_service(session, user_id)
    iterations = await ado.get_iterations(project_name)
    
    return {
        "iterations": [
            {
                "id": i.get("id"),
                "name": i.get("name"),
                "path": i.get("path"),
                "attributes": i.get("attributes", {})
            }
            for i in iterations
        ]
    }


@router.get("/projects/{project_name}/areas")
async def get_azure_devops_area_paths(
    project_name: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get area paths for an Azure DevOps project"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    ado = await get_azure_devops_service(session, user_id)
    areas = await ado.get_area_paths(project_name)
    
    return {
        "areas": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "path": a.get("path"),
                "has_children": a.get("hasChildren", False)
            }
            for a in areas
        ]
    }


@router.get("/projects/{project_name}/work-item-types")
async def get_azure_devops_work_item_types(
    project_name: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get work item types for an Azure DevOps project"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    ado = await get_azure_devops_service(session, user_id)
    work_item_types = await ado.get_work_item_types(project_name)
    
    return {
        "work_item_types": [
            {
                "name": wit.get("name"),
                "description": wit.get("description"),
                "color": wit.get("color"),
                "icon": wit.get("icon", {}).get("url")
            }
            for wit in work_item_types
        ]
    }


@router.get("/projects/{project_name}/fields")
async def get_azure_devops_fields(
    project_name: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get fields for work items in an Azure DevOps project"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    ado = await get_azure_devops_service(session, user_id)
    fields = await ado.get_fields(project_name)
    
    relevant_fields = [
        f for f in fields
        if f.get("referenceName", "").startswith(("System.", "Microsoft."))
        or "story" in f.get("name", "").lower()
        or "point" in f.get("name", "").lower()
    ]
    
    return {
        "fields": [
            {
                "name": f.get("name"),
                "referenceName": f.get("referenceName"),
                "type": f.get("type"),
                "readOnly": f.get("readOnly", False)
            }
            for f in relevant_fields[:50]
        ]
    }


@router.get("/test")
async def test_azure_devops_connection(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Test Azure DevOps connection"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    try:
        ado = await get_azure_devops_service(session, user_id)
        connection_test = await ado.verify_connection()
        
        return {
            "status": "connected" if connection_test.get("valid") else "error",
            "organization": connection_test.get("organization"),
            "project_count": connection_test.get("project_count", 0)
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
async def preview_azure_devops_push(
    request: Request,
    body: PushPreviewRequest,
    session: AsyncSession = Depends(get_db)
):
    """Preview what will be pushed to Azure DevOps without actually pushing"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.AZURE_DEVOPS.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Azure DevOps integration not connected")
    
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
                ExternalPushMapping.provider == IntegrationProvider.AZURE_DEVOPS.value
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
        "existing_id": epic_mapping.external_id if epic_mapping else None
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
                "existing_id": feature_mapping.external_id if feature_mapping else None
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
                        "title": story.title[:100] + "..." if len(story.title or "") > 100 else story.title,
                        "parent_feature_id": feature.feature_id,
                        "action": story_action,
                        "existing_id": story_mapping.external_id if story_mapping else None
                    })
                    preview["totals"][story_action] += 1
    
    return preview


@router.post("/push")
async def push_to_azure_devops(
    request: Request,
    body: AzureDevOpsPushRequest,
    session: AsyncSession = Depends(get_db)
):
    """Push epic (and optionally features/stories) to Azure DevOps"""
    user_id = await get_current_user_id(request, session)
    await check_subscription_required(session, user_id)
    
    integration = await get_user_integration(session, user_id, IntegrationProvider.AZURE_DEVOPS.value)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Azure DevOps not connected")
    
    ado = await get_azure_devops_service(session, user_id)
    push_service = AzureDevOpsPushService(ado)
    
    field_mappings = integration.field_mappings or {}
    work_item_types = field_mappings.get("work_item_types", {
        "epic": "Epic",
        "feature": "Feature",
        "story": "User Story",
        "bug": "Bug"
    })
    
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
        provider=IntegrationProvider.AZURE_DEVOPS.value,
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
                    ExternalPushMapping.provider == IntegrationProvider.AZURE_DEVOPS.value
                )
            )
        )
        existing_mappings = {m.entity_id: m for m in mappings_result.scalars().all()}
        
        snapshot = epic.snapshot
        epic_description = push_service.format_description(
            snapshot.problem_statement if snapshot else epic.title,
            snapshot.desired_outcome if snapshot else None,
            snapshot.acceptance_criteria if snapshot else None
        )
        
        existing_epic_mapping = existing_mappings.get(epic.epic_id)
        
        if not body.dry_run:
            try:
                epic_result = await push_service.push_work_item(
                    project=body.project_name,
                    work_item_type=work_item_types.get("epic", "Epic"),
                    title=epic.title,
                    description=epic_description,
                    area_path=body.area_path,
                    iteration_path=body.iteration_path,
                    existing_id=existing_epic_mapping.external_id if existing_epic_mapping else None,
                    tags=["jarlpm", "epic"]
                )
                
                if existing_epic_mapping:
                    existing_epic_mapping.external_id = str(epic_result["id"])
                    existing_epic_mapping.external_url = epic_result["url"]
                    existing_epic_mapping.last_pushed_at = datetime.now(timezone.utc)
                    results["updated"].append({
                        "type": "epic",
                        "entity_id": epic.epic_id,
                        "external_id": epic_result["id"],
                        "url": epic_result["url"]
                    })
                else:
                    new_mapping = ExternalPushMapping(
                        user_id=user_id,
                        integration_id=integration.integration_id,
                        provider=IntegrationProvider.AZURE_DEVOPS.value,
                        entity_type=EntityType.EPIC.value,
                        entity_id=epic.epic_id,
                        external_type="Work Item",
                        external_id=str(epic_result["id"]),
                        external_url=epic_result["url"],
                        project_id=body.project_name
                    )
                    session.add(new_mapping)
                    existing_mappings[epic.epic_id] = new_mapping
                    results["created"].append({
                        "type": "epic",
                        "entity_id": epic.epic_id,
                        "external_id": epic_result["id"],
                        "url": epic_result["url"]
                    })
                
                results["links"].append(epic_result["url"])
                parent_epic_id = epic_result["id"]
            except Exception as e:
                logger.error(f"Error pushing epic: {e}")
                results["errors"].append({
                    "type": "epic",
                    "entity_id": epic.epic_id,
                    "error": str(e)
                })
                parent_epic_id = None
        else:
            parent_epic_id = None
        
        if body.push_scope in ["epic_features", "epic_features_stories", "full"]:
            features_result = await session.execute(
                select(Feature).where(Feature.epic_id == body.epic_id)
            )
            features = features_result.scalars().all()
            
            for feature in features:
                feature_description = push_service.format_description(
                    feature.description,
                    None,
                    feature.acceptance_criteria
                )
                
                existing_feature_mapping = existing_mappings.get(feature.feature_id)
                
                if not body.dry_run:
                    try:
                        feature_result = await push_service.push_work_item(
                            project=body.project_name,
                            work_item_type=work_item_types.get("feature", "Feature"),
                            title=feature.title,
                            description=feature_description,
                            area_path=body.area_path,
                            iteration_path=body.iteration_path,
                            existing_id=existing_feature_mapping.external_id if existing_feature_mapping else None,
                            parent_id=parent_epic_id,
                            tags=["jarlpm", "feature"]
                        )
                        
                        if existing_feature_mapping:
                            existing_feature_mapping.external_id = str(feature_result["id"])
                            existing_feature_mapping.external_url = feature_result["url"]
                            existing_feature_mapping.last_pushed_at = datetime.now(timezone.utc)
                            results["updated"].append({
                                "type": "feature",
                                "entity_id": feature.feature_id,
                                "external_id": feature_result["id"],
                                "url": feature_result["url"]
                            })
                        else:
                            new_mapping = ExternalPushMapping(
                                user_id=user_id,
                                integration_id=integration.integration_id,
                                provider=IntegrationProvider.AZURE_DEVOPS.value,
                                entity_type=EntityType.FEATURE.value,
                                entity_id=feature.feature_id,
                                external_type="Work Item",
                                external_id=str(feature_result["id"]),
                                external_url=feature_result["url"],
                                project_id=body.project_name
                            )
                            session.add(new_mapping)
                            existing_mappings[feature.feature_id] = new_mapping
                            results["created"].append({
                                "type": "feature",
                                "entity_id": feature.feature_id,
                                "external_id": feature_result["id"],
                                "url": feature_result["url"]
                            })
                        
                        results["links"].append(feature_result["url"])
                        parent_feature_id = feature_result["id"]
                    except Exception as e:
                        logger.error(f"Error pushing feature {feature.feature_id}: {e}")
                        results["errors"].append({
                            "type": "feature",
                            "entity_id": feature.feature_id,
                            "error": str(e)
                        })
                        parent_feature_id = None
                        continue
                else:
                    parent_feature_id = None
                
                if body.push_scope in ["epic_features_stories", "full"] and parent_feature_id:
                    stories_result = await session.execute(
                        select(UserStory).where(UserStory.feature_id == feature.feature_id)
                    )
                    stories = stories_result.scalars().all()
                    
                    for story in stories:
                        story_title = story.title or story.story_text[:80]
                        story_description = push_service.format_description(
                            story.description or story.story_text,
                            None,
                            story.acceptance_criteria
                        )
                        
                        existing_story_mapping = existing_mappings.get(story.story_id)
                        
                        if not body.dry_run:
                            try:
                                story_result = await push_service.push_work_item(
                                    project=body.project_name,
                                    work_item_type=work_item_types.get("story", "User Story"),
                                    title=story_title,
                                    description=story_description,
                                    area_path=body.area_path,
                                    iteration_path=body.iteration_path,
                                    existing_id=existing_story_mapping.external_id if existing_story_mapping else None,
                                    parent_id=parent_feature_id,
                                    story_points=story.story_points,
                                    tags=["jarlpm", "story"]
                                )
                                
                                if existing_story_mapping:
                                    existing_story_mapping.external_id = str(story_result["id"])
                                    existing_story_mapping.external_url = story_result["url"]
                                    existing_story_mapping.last_pushed_at = datetime.now(timezone.utc)
                                    results["updated"].append({
                                        "type": "story",
                                        "entity_id": story.story_id,
                                        "external_id": story_result["id"],
                                        "url": story_result["url"]
                                    })
                                else:
                                    new_mapping = ExternalPushMapping(
                                        user_id=user_id,
                                        integration_id=integration.integration_id,
                                        provider=IntegrationProvider.AZURE_DEVOPS.value,
                                        entity_type=EntityType.STORY.value,
                                        entity_id=story.story_id,
                                        external_type="Work Item",
                                        external_id=str(story_result["id"]),
                                        external_url=story_result["url"],
                                        project_id=body.project_name
                                    )
                                    session.add(new_mapping)
                                    results["created"].append({
                                        "type": "story",
                                        "entity_id": story.story_id,
                                        "external_id": story_result["id"],
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
        logger.error(f"Push to Azure DevOps failed: {e}")
        push_run.ended_at = datetime.now(timezone.utc)
        push_run.status = PushStatus.FAILED.value
        push_run.error_json = {"error": str(e)}
        await session.commit()
        raise HTTPException(status_code=500, detail=str(e))
