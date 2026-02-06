"""
Persona Routes for JarlPM
API endpoints for user persona generation and management
"""
import json
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.persona_models import Persona, PersonaGenerationSettings
from services.persona_service import PersonaService
from services.llm_service import LLMService
from services.epic_service import EpicService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/personas", tags=["personas"])


# Request/Response Models
class PersonaResponse(BaseModel):
    persona_id: str
    epic_id: str
    name: str
    role: str
    age_range: Optional[str] = None
    location: Optional[str] = None
    tech_proficiency: Optional[str] = None
    goals_and_motivations: List[str] = []
    pain_points: List[str] = []
    key_behaviors: List[str] = []
    jobs_to_be_done: List[str] = []
    product_interaction_context: Optional[str] = None
    representative_quote: Optional[str] = None
    portrait_image_base64: Optional[str] = None
    portrait_prompt: Optional[str] = None
    source: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    age_range: Optional[str] = None
    location: Optional[str] = None
    tech_proficiency: Optional[str] = None
    goals_and_motivations: Optional[List[str]] = None
    pain_points: Optional[List[str]] = None
    key_behaviors: Optional[List[str]] = None
    jobs_to_be_done: Optional[List[str]] = None
    product_interaction_context: Optional[str] = None
    representative_quote: Optional[str] = None


class GeneratePersonasRequest(BaseModel):
    count: int = 3  # 1-5, default 3


class PersonaSettingsResponse(BaseModel):
    image_provider: str
    image_model: str
    default_persona_count: int


class PersonaSettingsUpdate(BaseModel):
    image_provider: Optional[str] = None
    image_model: Optional[str] = None
    default_persona_count: Optional[int] = None


class RegeneratePortraitRequest(BaseModel):
    prompt: Optional[str] = None


# Helper to get current user
async def get_current_user_id(request: Request, session: AsyncSession) -> str:
    """Extract user_id from session"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    from db.models import UserSession
    from sqlalchemy import select
    
    result = await session.execute(
        select(UserSession).where(UserSession.session_token == session_token)
    )
    session_record = result.scalar_one_or_none()
    
    if not session_record:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    return session_record.user_id


def persona_to_response(persona: Persona) -> PersonaResponse:
    """Convert Persona model to response"""
    return PersonaResponse(
        persona_id=persona.persona_id,
        epic_id=persona.epic_id,
        name=persona.name,
        role=persona.role,
        age_range=persona.age_range,
        location=persona.location,
        tech_proficiency=persona.tech_proficiency,
        goals_and_motivations=persona.goals_and_motivations or [],
        pain_points=persona.pain_points or [],
        key_behaviors=persona.key_behaviors or [],
        jobs_to_be_done=persona.jobs_to_be_done or [],
        product_interaction_context=persona.product_interaction_context,
        representative_quote=persona.representative_quote,
        portrait_image_base64=persona.portrait_image_base64,
        portrait_prompt=persona.portrait_prompt,
        source=persona.source,
        is_active=persona.is_active,
        created_at=persona.created_at,
        updated_at=persona.updated_at
    )


# ============================================
# SETTINGS ENDPOINTS
# ============================================

@router.get("/settings", response_model=PersonaSettingsResponse)
async def get_persona_settings(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get user's persona generation settings"""
    user_id = await get_current_user_id(request, session)
    
    persona_service = PersonaService(session)
    settings = await persona_service.get_user_settings(user_id)
    
    return PersonaSettingsResponse(
        image_provider=settings.image_provider,
        image_model=settings.image_model,
        default_persona_count=settings.default_persona_count
    )


@router.put("/settings", response_model=PersonaSettingsResponse)
async def update_persona_settings(
    request: Request,
    body: PersonaSettingsUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update user's persona generation settings"""
    user_id = await get_current_user_id(request, session)
    
    persona_service = PersonaService(session)
    settings = await persona_service.update_user_settings(
        user_id=user_id,
        image_provider=body.image_provider,
        image_model=body.image_model,
        default_persona_count=body.default_persona_count
    )
    
    return PersonaSettingsResponse(
        image_provider=settings.image_provider,
        image_model=settings.image_model,
        default_persona_count=settings.default_persona_count
    )


# ============================================
# GENERATION ENDPOINTS
# ============================================

@router.post("/epic/{epic_id}/generate")
async def generate_personas_for_epic(
    request: Request,
    epic_id: str,
    body: GeneratePersonasRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Generate personas for a completed epic.
    Step 1: Generate text data via LLM
    Step 2: Save personas (images generated separately)
    """
    user_id = await get_current_user_id(request, session)
    
    persona_service = PersonaService(session)
    llm_service = LLMService(session)
    epic_service = EpicService(session)
    
    # Check subscription
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required")
    
    # Check LLM config
    llm_config = await llm_service.get_user_llm_config(user_id)
    if not llm_config:
        raise HTTPException(status_code=400, detail="No LLM provider configured")
    
    # Prepare for streaming - extract config BEFORE releasing session
    config_data = llm_service.prepare_for_streaming(llm_config)
    
    # Validate count (1-5)
    count = max(1, min(5, body.count))
    
    # Get epic data
    epic_data = await persona_service.get_epic_with_children(epic_id, user_id)
    if not epic_data:
        raise HTTPException(status_code=400, detail="Epic not found or not completed")
    
    # Build context for LLM
    context = persona_service.build_context_for_generation(epic_data)
    
    # Build prompts
    system_prompt = """You are an expert UX researcher. Create detailed user personas based on the Epic, Features, and User Stories provided.

OUTPUT FORMAT - Return ONLY a JSON array:
[
  {
    "name": "First name",
    "role": "Job title/user type",
    "age_range": "25-34",
    "location": "Urban, USA",
    "tech_proficiency": "High",
    "goals_and_motivations": ["Goal 1", "Goal 2"],
    "pain_points": ["Pain 1", "Pain 2"],
    "key_behaviors": ["Behavior 1", "Behavior 2"],
    "jobs_to_be_done": ["JTBD 1", "JTBD 2"],
    "product_interaction_context": "When/why they use this product",
    "representative_quote": "Quote in first person",
    "portrait_prompt": "Professional headshot description"
  }
]

Return ONLY the JSON array, no other text."""

    user_prompt = f"""Generate {count} distinct user personas for this product:

{context}

Return as JSON array."""

    try:
        # Call LLM (non-streaming for simplicity)
        full_response = ""
        async for chunk in llm_service.generate_stream(
            user_id=user_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        ):
            full_response += chunk
        
        # Parse JSON
        import re
        json_match = re.search(r'\[[\s\S]*\]', full_response)
        if not json_match:
            raise ValueError("No JSON array in LLM response")
        
        personas_data = json.loads(json_match.group(0))
        
        # Create personas in database (without images)
        created_personas = []
        for persona_data in personas_data:
            persona = await persona_service.create_persona(
                user_id=user_id,
                epic_id=epic_id,
                persona_data=persona_data,
                portrait_image_base64=None  # Images generated separately
            )
            created_personas.append(persona_to_response(persona))
        
        return {
            "success": True,
            "count": len(created_personas),
            "personas": created_personas,
            "message": f"Created {len(created_personas)} personas. Use regenerate-portrait to add images."
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except Exception as e:
        logger.error(f"Persona generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# CRUD ENDPOINTS
# ============================================

@router.get("", response_model=List[PersonaResponse])
async def list_personas(
    request: Request,
    epic_id: Optional[str] = None,
    search: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """List all personas for the current user"""
    user_id = await get_current_user_id(request, session)
    
    persona_service = PersonaService(session)
    personas = await persona_service.get_all_personas_for_user(
        user_id=user_id,
        epic_id=epic_id,
        search=search
    )
    
    return [persona_to_response(p) for p in personas]


@router.get("/epic/{epic_id}", response_model=List[PersonaResponse])
async def list_personas_for_epic(
    request: Request,
    epic_id: str,
    session: AsyncSession = Depends(get_db)
):
    """List all personas for a specific epic"""
    user_id = await get_current_user_id(request, session)
    
    persona_service = PersonaService(session)
    personas = await persona_service.get_personas_for_epic(epic_id, user_id)
    
    return [persona_to_response(p) for p in personas]


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    request: Request,
    persona_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get a specific persona by ID"""
    user_id = await get_current_user_id(request, session)
    
    persona_service = PersonaService(session)
    persona = await persona_service.get_persona(persona_id, user_id)
    
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    return persona_to_response(persona)


@router.put("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    request: Request,
    persona_id: str,
    body: PersonaUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update a persona (marks as human_modified)"""
    user_id = await get_current_user_id(request, session)
    
    persona_service = PersonaService(session)
    
    updates = body.dict(exclude_unset=True)
    persona = await persona_service.update_persona(persona_id, user_id, updates)
    
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    logger.info(f"Updated persona {persona_id} for user {user_id}")
    return persona_to_response(persona)


@router.delete("/{persona_id}")
async def delete_persona(
    request: Request,
    persona_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Delete a persona (soft delete)"""
    user_id = await get_current_user_id(request, session)
    
    persona_service = PersonaService(session)
    success = await persona_service.delete_persona(persona_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    logger.info(f"Deleted persona {persona_id} for user {user_id}")
    return {"message": "Persona deleted"}


@router.post("/{persona_id}/regenerate-portrait", response_model=PersonaResponse)
async def regenerate_portrait(
    request: Request,
    persona_id: str,
    body: RegeneratePortraitRequest,
    session: AsyncSession = Depends(get_db)
):
    """Regenerate the portrait image for a persona"""
    user_id = await get_current_user_id(request, session)
    
    persona_service = PersonaService(session)
    epic_service = EpicService(session)
    
    # Check subscription
    has_subscription = await epic_service.check_subscription_active(user_id)
    if not has_subscription:
        raise HTTPException(status_code=402, detail="Active subscription required")
    
    persona = await persona_service.regenerate_portrait(
        persona_id=persona_id,
        user_id=user_id,
        new_prompt=body.prompt
    )
    
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    logger.info(f"Regenerated portrait for persona {persona_id}")
    return persona_to_response(persona)
