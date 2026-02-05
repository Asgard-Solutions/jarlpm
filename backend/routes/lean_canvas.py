"""
Lean Canvas API for JarlPM
Generates Lean Canvas from Epic data using LLM
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from db import get_db
from db.models import Epic, EpicSnapshot, Subscription, SubscriptionStatus, LeanCanvas
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lean-canvas", tags=["lean-canvas"])


class LeanCanvasData(BaseModel):
    """Lean Canvas data structure"""
    problem: str = Field("", description="Top 3 problems being solved")
    solution: str = Field("", description="Top 3 features solving the problems")
    unique_value: str = Field("", description="Single compelling value proposition")
    unfair_advantage: str = Field("", description="Something hard to copy or buy")
    customer_segments: str = Field("", description="Target customers and users")
    key_metrics: str = Field("", description="Key activities to measure")
    channels: str = Field("", description="Path to customers")
    cost_structure: str = Field("", description="Main costs")
    revenue_streams: str = Field("", description="Revenue model")


class GenerateLeanCanvasRequest(BaseModel):
    """Request to generate lean canvas"""
    epic_id: str


class SaveLeanCanvasRequest(BaseModel):
    """Request to save lean canvas"""
    epic_id: str
    canvas: LeanCanvasData
    source: str = "manual"  # manual | ai_generated


class LeanCanvasResponse(BaseModel):
    """Response with generated lean canvas"""
    epic_id: str
    epic_title: str
    canvas: LeanCanvasData
    generated_at: str
    source: Optional[str] = None


async def get_current_user_id(request: Request, session: AsyncSession) -> str:
    """Get current user ID from session cookie"""
    from routes.auth import get_current_user_id as auth_get_user
    return await auth_get_user(request, session)


@router.get("/list")
async def list_lean_canvases(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all Lean Canvases for the current user"""
    user_id = await get_current_user_id(request, session)
    
    # Get all canvases with epic info
    result = await session.execute(
        select(LeanCanvas, Epic)
        .join(Epic, LeanCanvas.epic_id == Epic.epic_id)
        .where(LeanCanvas.user_id == user_id)
        .order_by(LeanCanvas.updated_at.desc())
    )
    rows = result.all()
    
    canvases = []
    for canvas, epic in rows:
        canvases.append({
            "canvas_id": canvas.canvas_id,
            "epic_id": canvas.epic_id,
            "epic_title": epic.title,
            "source": canvas.source,
            "created_at": canvas.created_at.isoformat(),
            "updated_at": canvas.updated_at.isoformat(),
        })
    
    return {"canvases": canvases}


@router.get("/epics-without-canvas")
async def get_epics_without_canvas(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get all epics that don't have a Lean Canvas yet"""
    user_id = await get_current_user_id(request, session)
    
    # Get epics that don't have a canvas
    result = await session.execute(
        select(Epic)
        .outerjoin(LeanCanvas, Epic.epic_id == LeanCanvas.epic_id)
        .where(
            Epic.user_id == user_id,
            LeanCanvas.id == None
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


LEAN_CANVAS_SYSTEM_PROMPT = """You are JarlPM, an expert business strategist and product manager.
Your task is to generate a comprehensive Lean Canvas based on the provided epic/product information.

A Lean Canvas has 9 sections:
1. Problem: Top 3 problems your product solves
2. Solution: Top 3 features that address the problems
3. Unique Value Proposition: A single, clear message about why you're different
4. Unfair Advantage: Something that can't be easily copied (team expertise, network effects, etc.)
5. Customer Segments: Who are your target customers and early adopters
6. Key Metrics: What numbers will you track to measure success
7. Channels: How will you reach your customers
8. Cost Structure: What are your main costs (development, marketing, operations)
9. Revenue Streams: How will you make money

IMPORTANT OUTPUT RULES:
- Return ONLY valid JSON, no markdown fences
- Each section should be 2-4 bullet points or a clear paragraph
- Be specific and actionable, not generic
- Base your answers on the provided epic context

Output format (return exactly this JSON structure):
{
  "problem": "• Problem 1\\n• Problem 2\\n• Problem 3",
  "solution": "• Solution 1\\n• Solution 2\\n• Solution 3",
  "unique_value": "Clear value proposition statement",
  "unfair_advantage": "What makes this hard to copy",
  "customer_segments": "• Segment 1\\n• Segment 2",
  "key_metrics": "• Metric 1\\n• Metric 2\\n• Metric 3",
  "channels": "• Channel 1\\n• Channel 2",
  "cost_structure": "• Cost 1\\n• Cost 2\\n• Cost 3",
  "revenue_streams": "• Revenue stream 1\\n• Revenue stream 2"
}"""


@router.post("/generate", response_model=LeanCanvasResponse)
async def generate_lean_canvas(
    request: Request,
    body: GenerateLeanCanvasRequest,
    session: AsyncSession = Depends(get_db)
):
    """Generate a Lean Canvas from an Epic using LLM"""
    user_id = await get_current_user_id(request, session)
    
    # Check subscription
    sub_result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE.value
        )
    )
    if not sub_result.scalar_one_or_none():
        raise HTTPException(status_code=402, detail="Active subscription required")
    
    # Get epic data
    epic_result = await session.execute(
        select(Epic).where(
            Epic.epic_id == body.epic_id,
            Epic.user_id == user_id
        )
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get epic snapshot for additional context
    snapshot_result = await session.execute(
        select(EpicSnapshot).where(EpicSnapshot.epic_id == body.epic_id)
        .order_by(EpicSnapshot.id.desc())
        .limit(1)
    )
    snapshot = snapshot_result.scalar_one_or_none()
    
    # Build context from epic
    context_parts = [
        f"Product/Epic Title: {epic.title}",
    ]
    
    if snapshot:
        if snapshot.problem_statement:
            context_parts.append(f"Problem Statement: {snapshot.problem_statement}")
        if snapshot.desired_outcome:
            context_parts.append(f"Desired Outcome: {snapshot.desired_outcome}")
        if snapshot.epic_summary:
            context_parts.append(f"Epic Summary: {snapshot.epic_summary}")
        if snapshot.acceptance_criteria:
            context_parts.append(f"Acceptance Criteria: {', '.join(snapshot.acceptance_criteria)}")
    
    epic_context = "\n".join(context_parts)
    
    user_prompt = f"""Generate a Lean Canvas for the following product/epic:

{epic_context}

Return a complete Lean Canvas in JSON format with all 9 sections filled out based on this context.
Be specific and actionable - don't use generic placeholders."""

    # Call LLM using the standard service
    llm_service = LLMService(session)
    
    try:
        response_text = ""
        async for chunk in llm_service.generate_stream(
            user_id=user_id,
            system_prompt=LEAN_CANVAS_SYSTEM_PROMPT,
            user_prompt=user_prompt
        ):
            response_text += chunk
        
        # Parse JSON response
        import json
        
        # Clean up response - remove markdown fences if present
        clean_response = response_text.strip()
        if clean_response.startswith("```"):
            lines = clean_response.split("\n")
            clean_response = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        canvas_data = json.loads(clean_response)
        
        return LeanCanvasResponse(
            epic_id=body.epic_id,
            epic_title=epic.title,
            canvas=LeanCanvasData(**canvas_data),
            generated_at=datetime.now(timezone.utc).isoformat()
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Lean Canvas JSON: {e}")
        logger.error(f"Response was: {response_text[:500]}")
        raise HTTPException(status_code=500, detail="Failed to generate valid Lean Canvas. Please try again.")
    except Exception as e:
        logger.error(f"Lean Canvas generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")



@router.get("/{epic_id}")
async def get_lean_canvas(
    epic_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get saved Lean Canvas for an Epic"""
    user_id = await get_current_user_id(request, session)
    
    # Get epic to verify ownership and get title
    epic_result = await session.execute(
        select(Epic).where(
            Epic.epic_id == epic_id,
            Epic.user_id == user_id
        )
    )
    epic = epic_result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Get saved canvas
    canvas_result = await session.execute(
        select(LeanCanvas).where(LeanCanvas.epic_id == epic_id)
    )
    canvas = canvas_result.scalar_one_or_none()
    
    if not canvas:
        return {
            "epic_id": epic_id,
            "epic_title": epic.title,
            "canvas": None,
            "exists": False
        }
    
    return {
        "epic_id": epic_id,
        "epic_title": epic.title,
        "canvas": {
            "problem": canvas.problem or "",
            "solution": canvas.solution or "",
            "unique_value": canvas.unique_value or "",
            "unfair_advantage": canvas.unfair_advantage or "",
            "customer_segments": canvas.customer_segments or "",
            "key_metrics": canvas.key_metrics or "",
            "channels": canvas.channels or "",
            "cost_structure": canvas.cost_structure or "",
            "revenue_streams": canvas.revenue_streams or "",
        },
        "source": canvas.source,
        "updated_at": canvas.updated_at.isoformat(),
        "exists": True
    }


@router.post("/save")
async def save_lean_canvas(
    request: Request,
    body: SaveLeanCanvasRequest,
    session: AsyncSession = Depends(get_db)
):
    """Save or update Lean Canvas for an Epic"""
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
    
    # Check if canvas already exists
    existing_result = await session.execute(
        select(LeanCanvas).where(LeanCanvas.epic_id == body.epic_id)
    )
    existing_canvas = existing_result.scalar_one_or_none()
    
    if existing_canvas:
        # Update existing canvas
        existing_canvas.problem = body.canvas.problem
        existing_canvas.solution = body.canvas.solution
        existing_canvas.unique_value = body.canvas.unique_value
        existing_canvas.unfair_advantage = body.canvas.unfair_advantage
        existing_canvas.customer_segments = body.canvas.customer_segments
        existing_canvas.key_metrics = body.canvas.key_metrics
        existing_canvas.channels = body.canvas.channels
        existing_canvas.cost_structure = body.canvas.cost_structure
        existing_canvas.revenue_streams = body.canvas.revenue_streams
        existing_canvas.source = body.source
        existing_canvas.updated_at = datetime.now(timezone.utc)
    else:
        # Create new canvas
        new_canvas = LeanCanvas(
            epic_id=body.epic_id,
            user_id=user_id,
            problem=body.canvas.problem,
            solution=body.canvas.solution,
            unique_value=body.canvas.unique_value,
            unfair_advantage=body.canvas.unfair_advantage,
            customer_segments=body.canvas.customer_segments,
            key_metrics=body.canvas.key_metrics,
            channels=body.canvas.channels,
            cost_structure=body.canvas.cost_structure,
            revenue_streams=body.canvas.revenue_streams,
            source=body.source
        )
        session.add(new_canvas)
    
    await session.commit()
    
    return {
        "success": True,
        "epic_id": body.epic_id,
        "message": "Lean Canvas saved successfully"
    }
