"""
PRD Document API for JarlPM
Save and retrieve Product Requirements Documents
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from db import get_db
from db.models import Epic, PRDDocument
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prd", tags=["prd"])


class SavePRDRequest(BaseModel):
    """Request to save PRD"""
    epic_id: str
    content: str  # Frontend sends as 'content', we'll store in 'sections'
    title: Optional[str] = None
    version: str = "1.0"
    status: str = "draft"


@router.get("/list")
async def list_prds(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all PRDs for the current user"""
    user_id = await get_current_user_id(request, session)
    
    # Get all PRDs with epic info
    result = await session.execute(
        select(PRDDocument, Epic)
        .join(Epic, PRDDocument.epic_id == Epic.epic_id)
        .where(PRDDocument.user_id == user_id)
        .order_by(PRDDocument.updated_at.desc())
    )
    rows = result.all()
    
    prds = []
    for prd, epic in rows:
        prds.append({
            "prd_id": prd.prd_id,
            "epic_id": prd.epic_id,
            "epic_title": epic.title,
            "title": prd.title or epic.title,
            "version": prd.version,
            "status": prd.status,
            "created_at": prd.created_at.isoformat(),
            "updated_at": prd.updated_at.isoformat(),
        })
    
    return {"prds": prds}


@router.get("/epics-without-prd")
async def get_epics_without_prd(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all epics that don't have a PRD yet"""
    user_id = await get_current_user_id(request, session)
    
    # Get epics that don't have a PRD
    result = await session.execute(
        select(Epic)
        .outerjoin(PRDDocument, Epic.epic_id == PRDDocument.epic_id)
        .where(
            Epic.user_id == user_id,
            PRDDocument.id == None
        )
        .order_by(Epic.updated_at.desc())
    )
    epics = result.scalars().all()
    
    return {
        "epics": [
            {
                "epic_id": e.epic_id,
                "title": e.title,
                "stage": e.stage,
            }
            for e in epics
        ]
    }


@router.get("/{epic_id}")
async def get_prd(
    epic_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get saved PRD for an Epic"""
    user_id = await get_current_user_id(request, session)
    
    # Get epic to verify ownership
    epic_result = await session.execute(
        select(Epic).where(
            Epic.epic_id == epic_id,
            Epic.user_id == user_id
        )
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get saved PRD
    prd_result = await session.execute(
        select(PRDDocument).where(PRDDocument.epic_id == epic_id)
    )
    prd = prd_result.scalar_one_or_none()
    
    if not prd:
        return {
            "epic_id": epic_id,
            "epic_title": epic.title,
            "prd": None,
            "exists": False
        }
    
    return {
        "epic_id": epic_id,
        "epic_title": epic.title,
        "prd": {
            "prd_id": prd.prd_id,
            "content": prd.content,
            "title": prd.title,
            "version": prd.version,
            "status": prd.status,
        },
        "updated_at": prd.updated_at.isoformat(),
        "exists": True
    }


@router.post("/save")
async def save_prd(
    request: Request,
    body: SavePRDRequest,
    session: AsyncSession = Depends(get_db)
):
    """Save or update PRD for an Epic"""
    user_id = await get_current_user_id(request, session)
    
    # Verify epic ownership
    epic_result = await session.execute(
        select(Epic).where(
            Epic.epic_id == body.epic_id,
            Epic.user_id == user_id
        )
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Check if PRD already exists
    existing_result = await session.execute(
        select(PRDDocument).where(PRDDocument.epic_id == body.epic_id)
    )
    existing_prd = existing_result.scalar_one_or_none()
    
    if existing_prd:
        # Update existing PRD
        existing_prd.content = body.content
        existing_prd.title = body.title or epic.title
        existing_prd.version = body.version
        existing_prd.status = body.status
        existing_prd.updated_at = datetime.now(timezone.utc)
    else:
        # Create new PRD
        new_prd = PRDDocument(
            epic_id=body.epic_id,
            user_id=user_id,
            content=body.content,
            title=body.title or epic.title,
            version=body.version,
            status=body.status
        )
        session.add(new_prd)
    
    await session.commit()
    
    return {
        "success": True,
        "epic_id": body.epic_id,
        "message": "PRD saved successfully"
    }


@router.delete("/{epic_id}")
async def delete_prd(
    epic_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Delete PRD for an Epic"""
    user_id = await get_current_user_id(request, session)
    
    # Get PRD
    prd_result = await session.execute(
        select(PRDDocument).where(
            PRDDocument.epic_id == epic_id,
            PRDDocument.user_id == user_id
        )
    )
    prd = prd_result.scalar_one_or_none()
    
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    
    await session.delete(prd)
    await session.commit()
    
    return {"success": True, "message": "PRD deleted"}
