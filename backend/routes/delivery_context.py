from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, date
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import ProductDeliveryContext, DeliveryMethodology, DeliveryPlatform
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delivery-context", tags=["delivery-context"])


class DeliveryContextCreate(BaseModel):
    industry: Optional[str] = Field(None, description="Comma-separated industry tags")
    delivery_methodology: Optional[str] = Field(None, description="waterfall, agile, scrum, kanban, hybrid")
    sprint_cycle_length: Optional[int] = Field(None, ge=1, le=365, description="Sprint cycle length in days")
    sprint_start_date: Optional[date] = Field(None, description="Sprint start date")
    num_developers: Optional[int] = Field(None, ge=0, description="Number of developers")
    num_qa: Optional[int] = Field(None, ge=0, description="Number of QA engineers")
    delivery_platform: Optional[str] = Field(None, description="jira, azure_devops, none, other")
    points_per_dev_per_sprint: Optional[int] = Field(8, ge=1, le=50, description="Story points per developer per sprint (default 8)")
    quality_mode: Optional[str] = Field("standard", description="standard or quality (2-pass with critique)")


class DeliveryContextResponse(BaseModel):
    context_id: str
    industry: Optional[str] = None
    delivery_methodology: Optional[str] = None
    sprint_cycle_length: Optional[int] = None
    sprint_start_date: Optional[date] = None
    num_developers: Optional[int] = None
    num_qa: Optional[int] = None
    delivery_platform: Optional[str] = None
    points_per_dev_per_sprint: Optional[int] = 8
    quality_mode: Optional[str] = "standard"
    created_at: datetime
    updated_at: datetime


def validate_methodology(value: Optional[str]) -> Optional[str]:
    """Validate delivery methodology value"""
    if value is None:
        return None
    valid_values = [e.value for e in DeliveryMethodology]
    if value.lower() not in valid_values:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid delivery_methodology. Must be one of: {', '.join(valid_values)}"
        )
    return value.lower()


def validate_platform(value: Optional[str]) -> Optional[str]:
    """Validate delivery platform value"""
    if value is None:
        return None
    valid_values = [e.value for e in DeliveryPlatform]
    if value.lower() not in valid_values:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid delivery_platform. Must be one of: {', '.join(valid_values)}"
        )
    return value.lower()


@router.get("", response_model=DeliveryContextResponse)
async def get_delivery_context(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get the user's Product Delivery Context"""
    user_id = await get_current_user_id(request, session)
    
    result = await session.execute(
        select(ProductDeliveryContext).where(ProductDeliveryContext.user_id == user_id)
    )
    context = result.scalar_one_or_none()
    
    if not context:
        # Create empty context for new users
        context = ProductDeliveryContext(user_id=user_id)
        session.add(context)
        await session.commit()
        await session.refresh(context)
    
    return DeliveryContextResponse(
        context_id=context.context_id,
        industry=context.industry,
        delivery_methodology=context.delivery_methodology,
        sprint_cycle_length=context.sprint_cycle_length,
        sprint_start_date=context.sprint_start_date.date() if context.sprint_start_date else None,
        num_developers=context.num_developers,
        num_qa=context.num_qa,
        delivery_platform=context.delivery_platform,
        points_per_dev_per_sprint=context.points_per_dev_per_sprint or 8,
        quality_mode=context.quality_mode or "standard",
        created_at=context.created_at,
        updated_at=context.updated_at
    )


@router.put("", response_model=DeliveryContextResponse)
async def update_delivery_context(
    request: Request,
    body: DeliveryContextCreate,
    session: AsyncSession = Depends(get_db)
):
    """Update the user's Product Delivery Context"""
    user_id = await get_current_user_id(request, session)
    
    # Validate enum values
    methodology = validate_methodology(body.delivery_methodology)
    platform = validate_platform(body.delivery_platform)
    
    result = await session.execute(
        select(ProductDeliveryContext).where(ProductDeliveryContext.user_id == user_id)
    )
    context = result.scalar_one_or_none()
    
    if not context:
        # Create new context
        context = ProductDeliveryContext(
            user_id=user_id,
            industry=body.industry,
            delivery_methodology=methodology,
            sprint_cycle_length=body.sprint_cycle_length,
            sprint_start_date=datetime.combine(body.sprint_start_date, datetime.min.time()).replace(tzinfo=timezone.utc) if body.sprint_start_date else None,
            num_developers=body.num_developers,
            num_qa=body.num_qa,
            delivery_platform=platform,
            points_per_dev_per_sprint=body.points_per_dev_per_sprint or 8,
            quality_mode=body.quality_mode or "standard"
        )
        session.add(context)
    else:
        # Update existing context
        context.industry = body.industry
        context.delivery_methodology = methodology
        context.sprint_cycle_length = body.sprint_cycle_length
        context.sprint_start_date = datetime.combine(body.sprint_start_date, datetime.min.time()).replace(tzinfo=timezone.utc) if body.sprint_start_date else None
        context.num_developers = body.num_developers
        context.num_qa = body.num_qa
        context.delivery_platform = platform
        context.points_per_dev_per_sprint = body.points_per_dev_per_sprint or 8
        context.quality_mode = body.quality_mode or "standard"
        context.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    await session.refresh(context)
    
    return DeliveryContextResponse(
        context_id=context.context_id,
        industry=context.industry,
        delivery_methodology=context.delivery_methodology,
        sprint_cycle_length=context.sprint_cycle_length,
        sprint_start_date=context.sprint_start_date.date() if context.sprint_start_date else None,
        num_developers=context.num_developers,
        num_qa=context.num_qa,
        delivery_platform=context.delivery_platform,
        points_per_dev_per_sprint=context.points_per_dev_per_sprint or 8,
        quality_mode=context.quality_mode or "standard",
        created_at=context.created_at,
        updated_at=context.updated_at
    )


def format_context_for_prompt(context: Optional[ProductDeliveryContext]) -> str:
    """Format delivery context as read-only text for LLM prompts"""
    if not context:
        return """
PRODUCT DELIVERY CONTEXT (Read-Only):
- Industry: Not specified
- Delivery Methodology: Not specified
- Sprint Cycle Length: Not specified
- Sprint Start Date: Not specified
- Team Size: Not specified
- Delivery Platform: Not specified
"""
    
    # Format each field, handling None values
    industry = context.industry if context.industry else "Not specified"
    methodology = context.delivery_methodology.replace("_", " ").title() if context.delivery_methodology else "Not specified"
    sprint_length = f"{context.sprint_cycle_length} days" if context.sprint_cycle_length else "Not specified"
    sprint_start = context.sprint_start_date.strftime("%Y-%m-%d") if context.sprint_start_date else "Not specified"
    
    # Team size
    devs = context.num_developers if context.num_developers is not None else None
    qas = context.num_qa if context.num_qa is not None else None
    if devs is not None or qas is not None:
        team_parts = []
        if devs is not None:
            team_parts.append(f"{devs} developer{'s' if devs != 1 else ''}")
        if qas is not None:
            team_parts.append(f"{qas} QA")
        team_size = ", ".join(team_parts)
    else:
        team_size = "Not specified"
    
    platform = context.delivery_platform.replace("_", " ").title() if context.delivery_platform else "Not specified"
    
    return f"""
PRODUCT DELIVERY CONTEXT (Read-Only):
- Industry: {industry}
- Delivery Methodology: {methodology}
- Sprint Cycle Length: {sprint_length}
- Sprint Start Date: {sprint_start}
- Team Size: {team_size}
- Delivery Platform: {platform}
"""
