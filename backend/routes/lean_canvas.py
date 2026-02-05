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
from db.models import Epic, EpicSnapshot, Subscription, SubscriptionStatus
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


class LeanCanvasResponse(BaseModel):
    """Response with generated lean canvas"""
    epic_id: str
    epic_title: str
    canvas: LeanCanvasData
    generated_at: str


async def get_current_user_id(request: Request, session: AsyncSession) -> str:
    """Get current user ID from session cookie"""
    from routes.auth import get_current_user_id as auth_get_user
    return await auth_get_user(request, session)


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
    
    # Get LLM provider config
    llm_result = await session.execute(
        select(LLMProviderConfig).where(
            LLMProviderConfig.user_id == user_id,
            LLMProviderConfig.is_active.is_(True)
        )
    )
    llm_config = llm_result.scalar_one_or_none()
    if not llm_config:
        raise HTTPException(status_code=400, detail="Please configure an LLM provider in Settings first")
    
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
