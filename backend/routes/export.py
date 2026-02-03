"""
Export Routes for JarlPM
Handles export to Jira, Azure DevOps, and file formats
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import io
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from services.export_service import ExportService, ExportFormat, ExportPlatform
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


# ============================================
# Request/Response Models
# ============================================

class FileExportRequest(BaseModel):
    epic_id: str
    format: ExportFormat
    include_bugs: bool = True


class JiraExportRequest(BaseModel):
    epic_id: str
    include_bugs: bool = True
    jira_base_url: str = Field(..., description="Jira Cloud URL (e.g., https://yourcompany.atlassian.net)")
    jira_email: str = Field(..., description="Jira account email")
    jira_api_token: str = Field(..., description="Jira API token")
    jira_project_key: str = Field(..., description="Jira project key (e.g., PROJ)")


class AzureDevOpsExportRequest(BaseModel):
    epic_id: str
    include_bugs: bool = True
    organization: str = Field(..., description="Azure DevOps organization name")
    project: str = Field(..., description="Azure DevOps project name")
    pat: str = Field(..., description="Personal Access Token")


class ExportPreviewResponse(BaseModel):
    epic_title: str
    feature_count: int
    story_count: int
    bug_count: int
    items: List[dict]


class ExportResultResponse(BaseModel):
    success: bool
    created_count: int
    error_count: int
    created: List[dict]
    errors: List[dict]


# ============================================
# Field Mappings Endpoint
# ============================================

@router.get("/field-mappings")
async def get_field_mappings():
    """Get field mappings for Jira and Azure DevOps"""
    from services.export_service import JIRA_FIELD_MAPPING, AZURE_DEVOPS_FIELD_MAPPING
    
    return {
        "jira": JIRA_FIELD_MAPPING,
        "azure_devops": AZURE_DEVOPS_FIELD_MAPPING,
        "description": {
            "jira": {
                "Epic": "JarlPM Epic → Jira Epic",
                "Feature": "JarlPM Feature → Jira Story (linked to Epic)",
                "User Story": "JarlPM User Story → Jira Sub-task (linked to Story)",
                "Bug": "JarlPM Bug → Jira Bug"
            },
            "azure_devops": {
                "Epic": "JarlPM Epic → Azure DevOps Epic",
                "Feature": "JarlPM Feature → Azure DevOps Feature (linked to Epic)",
                "User Story": "JarlPM User Story → Azure DevOps User Story (linked to Feature)",
                "Bug": "JarlPM Bug → Azure DevOps Bug"
            }
        }
    }


# ============================================
# Export Preview Endpoint
# ============================================

@router.get("/preview/{epic_id}", response_model=ExportPreviewResponse)
async def preview_export(
    request: Request,
    epic_id: str,
    include_bugs: bool = True,
    session: AsyncSession = Depends(get_db)
):
    """Preview what will be exported for an epic"""
    user_id = await get_current_user_id(request, session)
    export_service = ExportService(session)
    
    # Get epic data
    epic_data = await export_service.get_epic_with_all_children(epic_id, user_id)
    if not epic_data:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get bugs if requested
    bugs = []
    if include_bugs:
        bugs = await export_service.get_bugs_for_export(user_id)
    
    # Count items
    story_count = sum(len(f.get("user_stories", [])) for f in epic_data.get("features", []))
    
    # Build preview items
    items = [{"type": "Epic", "title": epic_data["title"], "stage": epic_data.get("current_stage")}]
    
    for feature in epic_data.get("features", []):
        items.append({
            "type": "Feature",
            "title": feature["title"],
            "stage": feature.get("current_stage"),
            "moscow": feature.get("moscow_score"),
            "rice": feature.get("rice_total")
        })
        
        for story in feature.get("user_stories", []):
            items.append({
                "type": "User Story",
                "title": story["story_text"][:80] + ("..." if len(story["story_text"]) > 80 else ""),
                "stage": story.get("current_stage"),
                "points": story.get("story_points"),
                "rice": story.get("rice_total")
            })
    
    for bug in bugs:
        items.append({
            "type": "Bug",
            "title": bug["title"],
            "severity": bug.get("severity"),
            "status": bug.get("status"),
            "rice": bug.get("rice_total")
        })
    
    return ExportPreviewResponse(
        epic_title=epic_data["title"],
        feature_count=len(epic_data.get("features", [])),
        story_count=story_count,
        bug_count=len(bugs),
        items=items
    )


# ============================================
# File Export Endpoints
# ============================================

@router.post("/file")
async def export_to_file(
    request: Request,
    body: FileExportRequest,
    session: AsyncSession = Depends(get_db)
):
    """Export to file (CSV, JSON, or Markdown)"""
    user_id = await get_current_user_id(request, session)
    export_service = ExportService(session)
    
    # Get epic data
    epic_data = await export_service.get_epic_with_all_children(body.epic_id, user_id)
    if not epic_data:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get bugs if requested
    bugs = []
    if body.include_bugs:
        bugs = await export_service.get_bugs_for_export(user_id)
    
    # Generate export based on format
    if body.format == ExportFormat.JIRA_CSV:
        content = export_service.export_to_jira_csv(epic_data, bugs)
        media_type = "text/csv"
        filename = f"{epic_data['title'].replace(' ', '_')}_jira_export.csv"
    
    elif body.format == ExportFormat.AZURE_DEVOPS_CSV:
        content = export_service.export_to_azure_devops_csv(epic_data, bugs)
        media_type = "text/csv"
        filename = f"{epic_data['title'].replace(' ', '_')}_azure_devops_export.csv"
    
    elif body.format == ExportFormat.JSON:
        content = export_service.export_to_json(epic_data, bugs)
        media_type = "application/json"
        filename = f"{epic_data['title'].replace(' ', '_')}_export.json"
    
    elif body.format == ExportFormat.MARKDOWN:
        content = export_service.export_to_markdown(epic_data, bugs)
        media_type = "text/markdown"
        filename = f"{epic_data['title'].replace(' ', '_')}_export.md"
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format")
    
    # Return as downloadable file
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================
# Direct API Export Endpoints
# ============================================

@router.post("/jira", response_model=ExportResultResponse)
async def export_to_jira(
    request: Request,
    body: JiraExportRequest,
    session: AsyncSession = Depends(get_db)
):
    """Export directly to Jira via REST API"""
    user_id = await get_current_user_id(request, session)
    export_service = ExportService(session)
    
    # Get epic data
    epic_data = await export_service.get_epic_with_all_children(body.epic_id, user_id)
    if not epic_data:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get bugs if requested
    bugs = []
    if body.include_bugs:
        bugs = await export_service.get_bugs_for_export(user_id)
    
    # Export to Jira
    jira_config = {
        "base_url": body.jira_base_url,
        "email": body.jira_email,
        "api_token": body.jira_api_token,
        "project_key": body.jira_project_key
    }
    
    try:
        results = await export_service.export_to_jira_api(epic_data, bugs, jira_config)
        
        return ExportResultResponse(
            success=len(results["errors"]) == 0,
            created_count=len(results["created"]),
            error_count=len(results["errors"]),
            created=results["created"],
            errors=results["errors"]
        )
    
    except Exception as e:
        logger.error(f"Jira export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Jira export failed: {str(e)}")


@router.post("/azure-devops", response_model=ExportResultResponse)
async def export_to_azure_devops(
    request: Request,
    body: AzureDevOpsExportRequest,
    session: AsyncSession = Depends(get_db)
):
    """Export directly to Azure DevOps via REST API"""
    user_id = await get_current_user_id(request, session)
    export_service = ExportService(session)
    
    # Get epic data
    epic_data = await export_service.get_epic_with_all_children(body.epic_id, user_id)
    if not epic_data:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get bugs if requested
    bugs = []
    if body.include_bugs:
        bugs = await export_service.get_bugs_for_export(user_id)
    
    # Export to Azure DevOps
    azure_config = {
        "organization": body.organization,
        "project": body.project,
        "pat": body.pat
    }
    
    try:
        results = await export_service.export_to_azure_devops_api(epic_data, bugs, azure_config)
        
        return ExportResultResponse(
            success=len(results["errors"]) == 0,
            created_count=len(results["created"]),
            error_count=len(results["errors"]),
            created=results["created"],
            errors=results["errors"]
        )
    
    except Exception as e:
        logger.error(f"Azure DevOps export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Azure DevOps export failed: {str(e)}")
