"""
Bug Routes for JarlPM
Handles bug CRUD, lifecycle transitions, and linking operations
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import (
    Bug, BugLink, BugStatusHistory,
    BugStatus, BugSeverity, BugPriority, BugLinkEntityType,
    BUG_STATUS_TRANSITIONS
)
from services.bug_service import BugService
from services.llm_service import LLMService
from routes.auth import get_current_user_id

router = APIRouter(prefix="/bugs", tags=["bugs"])
logger = logging.getLogger(__name__)


# ============================================
# PYDANTIC MODELS
# ============================================

class LinkCreate(BaseModel):
    entity_type: str  # epic, feature, story
    entity_id: str

class BugCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    severity: str = Field(default="medium")
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    environment: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    links: Optional[List[LinkCreate]] = None

class BugUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    severity: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    environment: Optional[str] = None
    assignee_id: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None

class StatusTransition(BaseModel):
    new_status: str
    notes: Optional[str] = None

class LinksAdd(BaseModel):
    links: List[LinkCreate]

class LinkResponse(BaseModel):
    link_id: str
    entity_type: str
    entity_id: str
    created_at: datetime

class StatusHistoryResponse(BaseModel):
    history_id: str
    from_status: Optional[str]
    to_status: str
    changed_by: str
    notes: Optional[str]
    created_at: datetime

class BugResponse(BaseModel):
    bug_id: str
    title: str
    description: str
    severity: str
    status: str
    steps_to_reproduce: Optional[str]
    expected_behavior: Optional[str]
    actual_behavior: Optional[str]
    environment: Optional[str]
    assignee_id: Optional[str]
    priority: Optional[str]
    due_date: Optional[datetime]
    links: List[LinkResponse]
    link_count: int
    created_at: datetime
    updated_at: datetime
    allowed_transitions: List[str]


def bug_to_response(bug: Bug) -> BugResponse:
    """Convert Bug model to response"""
    current_status = BugStatus(bug.status)
    allowed = BUG_STATUS_TRANSITIONS.get(current_status, [])
    
    return BugResponse(
        bug_id=bug.bug_id,
        title=bug.title,
        description=bug.description,
        severity=bug.severity,
        status=bug.status,
        steps_to_reproduce=bug.steps_to_reproduce,
        expected_behavior=bug.expected_behavior,
        actual_behavior=bug.actual_behavior,
        environment=bug.environment,
        assignee_id=bug.assignee_id,
        priority=bug.priority,
        due_date=bug.due_date,
        links=[
            LinkResponse(
                link_id=link.link_id,
                entity_type=link.entity_type,
                entity_id=link.entity_id,
                created_at=link.created_at
            )
            for link in (bug.links or [])
        ],
        link_count=len(bug.links or []),
        created_at=bug.created_at,
        updated_at=bug.updated_at,
        allowed_transitions=[s.value for s in allowed]
    )


# ============================================
# CRUD ENDPOINTS
# ============================================

@router.post("", response_model=BugResponse)
async def create_bug(
    request: Request,
    body: BugCreate,
    session: AsyncSession = Depends(get_db)
):
    """Create a new bug (standalone or with links)"""
    user_id = await get_current_user_id(request, session)
    
    # Validate severity
    if body.severity not in [s.value for s in BugSeverity]:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {body.severity}")
    
    # Validate priority if provided
    if body.priority and body.priority not in [p.value for p in BugPriority]:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {body.priority}")
    
    # Validate links if provided
    links_data = None
    if body.links:
        links_data = []
        for link in body.links:
            if link.entity_type not in [e.value for e in BugLinkEntityType]:
                raise HTTPException(status_code=400, detail=f"Invalid entity type: {link.entity_type}")
            links_data.append({"entity_type": link.entity_type, "entity_id": link.entity_id})
    
    bug_service = BugService(session)
    bug = await bug_service.create_bug(
        user_id=user_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        steps_to_reproduce=body.steps_to_reproduce,
        expected_behavior=body.expected_behavior,
        actual_behavior=body.actual_behavior,
        environment=body.environment,
        priority=body.priority,
        due_date=body.due_date,
        links=links_data
    )
    
    logger.info(f"Created bug {bug.bug_id} for user {user_id}")
    return bug_to_response(bug)


@router.get("", response_model=List[BugResponse])
async def list_bugs(
    request: Request,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    assignee_id: Optional[str] = None,
    linked: Optional[str] = None,  # "true", "false", or None for all
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db)
):
    """List bugs with filters and sorting"""
    user_id = await get_current_user_id(request, session)
    
    # Parse linked filter
    linked_only = None
    if linked == "true":
        linked_only = True
    elif linked == "false":
        linked_only = False
    
    bug_service = BugService(session)
    bugs = await bug_service.list_bugs(
        user_id=user_id,
        status=status,
        severity=severity,
        assignee_id=assignee_id,
        linked_only=linked_only,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )
    
    return [bug_to_response(bug) for bug in bugs]


@router.get("/{bug_id}", response_model=BugResponse)
async def get_bug(
    request: Request,
    bug_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get a bug by ID"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    bug = await bug_service.get_bug_for_user(bug_id, user_id)
    
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    return bug_to_response(bug)


@router.patch("/{bug_id}", response_model=BugResponse)
async def update_bug(
    request: Request,
    bug_id: str,
    body: BugUpdate,
    session: AsyncSession = Depends(get_db)
):
    """Update bug fields (only in Draft status)"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    bug = await bug_service.get_bug_for_user(bug_id, user_id)
    
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    # Validate severity if provided
    if body.severity and body.severity not in [s.value for s in BugSeverity]:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {body.severity}")
    
    # Validate priority if provided
    if body.priority and body.priority not in [p.value for p in BugPriority]:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {body.priority}")
    
    try:
        updated = await bug_service.update_bug(
            bug_id=bug_id,
            title=body.title,
            description=body.description,
            severity=body.severity,
            steps_to_reproduce=body.steps_to_reproduce,
            expected_behavior=body.expected_behavior,
            actual_behavior=body.actual_behavior,
            environment=body.environment,
            assignee_id=body.assignee_id,
            priority=body.priority,
            due_date=body.due_date
        )
        return bug_to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{bug_id}")
async def delete_bug(
    request: Request,
    bug_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Soft delete a bug"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    success = await bug_service.soft_delete_bug(bug_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    return {"message": "Bug deleted"}


# ============================================
# STATUS TRANSITIONS
# ============================================

@router.post("/{bug_id}/transition", response_model=BugResponse)
async def transition_status(
    request: Request,
    bug_id: str,
    body: StatusTransition,
    session: AsyncSession = Depends(get_db)
):
    """Transition bug to a new status"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    bug = await bug_service.get_bug_for_user(bug_id, user_id)
    
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    # Validate new status
    if body.new_status not in [s.value for s in BugStatus]:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.new_status}")
    
    try:
        updated = await bug_service.transition_status(
            bug_id=bug_id,
            user_id=user_id,
            new_status=body.new_status,
            notes=body.notes
        )
        return bug_to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{bug_id}/history", response_model=List[StatusHistoryResponse])
async def get_status_history(
    request: Request,
    bug_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get status history for a bug"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    bug = await bug_service.get_bug_for_user(bug_id, user_id)
    
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    history = await bug_service.get_status_history(bug_id)
    
    return [
        StatusHistoryResponse(
            history_id=h.history_id,
            from_status=h.from_status,
            to_status=h.to_status,
            changed_by=h.changed_by,
            notes=h.notes,
            created_at=h.created_at
        )
        for h in history
    ]


# ============================================
# LINKING OPERATIONS
# ============================================

@router.post("/{bug_id}/links", response_model=List[LinkResponse])
async def add_links(
    request: Request,
    bug_id: str,
    body: LinksAdd,
    session: AsyncSession = Depends(get_db)
):
    """Add one or more links to a bug"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    bug = await bug_service.get_bug_for_user(bug_id, user_id)
    
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    # Validate entity types
    for link in body.links:
        if link.entity_type not in [e.value for e in BugLinkEntityType]:
            raise HTTPException(status_code=400, detail=f"Invalid entity type: {link.entity_type}")
    
    links_data = [{"entity_type": link.entity_type, "entity_id": link.entity_id} for link in body.links]
    created_links = await bug_service.add_links(bug_id, links_data)
    
    return [
        LinkResponse(
            link_id=link.link_id,
            entity_type=link.entity_type,
            entity_id=link.entity_id,
            created_at=link.created_at
        )
        for link in created_links
    ]


@router.delete("/{bug_id}/links/{link_id}")
async def remove_link(
    request: Request,
    bug_id: str,
    link_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Remove a link from a bug"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    bug = await bug_service.get_bug_for_user(bug_id, user_id)
    
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    success = await bug_service.remove_link(bug_id, link_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Link not found")
    
    return {"message": "Link removed"}


@router.get("/{bug_id}/links", response_model=List[LinkResponse])
async def get_links(
    request: Request,
    bug_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get all links for a bug"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    bug = await bug_service.get_bug_for_user(bug_id, user_id)
    
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    links = await bug_service.get_links(bug_id)
    
    return [
        LinkResponse(
            link_id=link.link_id,
            entity_type=link.entity_type,
            entity_id=link.entity_id,
            created_at=link.created_at
        )
        for link in links
    ]


# ============================================
# ENTITY-BASED QUERIES
# ============================================

@router.get("/by-entity/{entity_type}/{entity_id}", response_model=List[BugResponse])
async def get_bugs_for_entity(
    request: Request,
    entity_type: str,
    entity_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get all bugs linked to a specific entity"""
    user_id = await get_current_user_id(request, session)
    
    if entity_type not in [e.value for e in BugLinkEntityType]:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")
    
    bug_service = BugService(session)
    bugs = await bug_service.get_bugs_for_entity(entity_type, entity_id, user_id)
    
    return [bug_to_response(bug) for bug in bugs]


# ============================================
# AI ASSISTANCE (Optional)
# ============================================

@router.post("/{bug_id}/ai/refine-description")
async def ai_refine_description(
    request: Request,
    bug_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get AI suggestions for refining bug description (streaming)"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    bug = await bug_service.get_bug_for_user(bug_id, user_id)
    
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    llm_service = LLMService(session)
    
    # Get user's active LLM config
    config = await llm_service.get_active_config(user_id)
    if not config:
        raise HTTPException(status_code=400, detail="No LLM provider configured")
    
    # Build context
    context = f"""Bug Title: {bug.title}
Current Description: {bug.description}
Severity: {bug.severity}
Steps to Reproduce: {bug.steps_to_reproduce or 'Not provided'}
Expected Behavior: {bug.expected_behavior or 'Not provided'}
Actual Behavior: {bug.actual_behavior or 'Not provided'}
Environment: {bug.environment or 'Not provided'}"""

    system_prompt = """You are a helpful product management assistant. 
Your task is to help improve bug descriptions to be clearer, more actionable, and better structured.
Suggest improvements while keeping the core issue intact.
Format your response as a refined description that could replace the current one."""

    async def generate():
        async for chunk in llm_service.stream_completion(
            config=config,
            system_prompt=system_prompt,
            user_prompt=f"Please refine this bug description:\n\n{context}",
            context=None
        ):
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/{bug_id}/ai/suggest-severity")
async def ai_suggest_severity(
    request: Request,
    bug_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get AI suggestions for severity and priority"""
    user_id = await get_current_user_id(request, session)
    
    bug_service = BugService(session)
    bug = await bug_service.get_bug_for_user(bug_id, user_id)
    
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    llm_service = LLMService(session)
    
    # Get user's active LLM config
    config = await llm_service.get_active_config(user_id)
    if not config:
        raise HTTPException(status_code=400, detail="No LLM provider configured")
    
    # Build context
    context = f"""Bug Title: {bug.title}
Description: {bug.description}
Steps to Reproduce: {bug.steps_to_reproduce or 'Not provided'}
Expected Behavior: {bug.expected_behavior or 'Not provided'}
Actual Behavior: {bug.actual_behavior or 'Not provided'}
Environment: {bug.environment or 'Not provided'}"""

    system_prompt = """You are a helpful product management assistant.
Analyze this bug and suggest appropriate severity (critical, high, medium, low) and priority (p0, p1, p2, p3).
Provide a brief justification for each suggestion.
Return ONLY valid JSON in this format: {"severity": "...", "priority": "...", "severity_reason": "...", "priority_reason": "..."}"""

    try:
        response = await llm_service.get_completion(
            config=config,
            system_prompt=system_prompt,
            user_prompt=f"Analyze this bug and suggest severity/priority:\n\n{context}",
            context=None
        )
        
        # Try to parse JSON from response
        import re
        json_match = re.search(r'\{[^}]+\}', response)
        if json_match:
            suggestion = json.loads(json_match.group())
            return suggestion
        else:
            return {"error": "Could not parse AI response", "raw": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI suggestion failed: {str(e)}")



# ============================================
# AI-ASSISTED BUG CREATION
# ============================================

class BugChatMessage(BaseModel):
    content: str
    conversation_history: Optional[List[dict]] = []  # Previous messages for context

class BugProposal(BaseModel):
    title: str
    description: str
    severity: str
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    environment: Optional[str] = None
    priority: Optional[str] = None

class BugChatResponse(BaseModel):
    message: str
    proposal: Optional[BugProposal] = None
    is_complete: bool = False


@router.post("/ai/chat")
async def ai_bug_chat(
    request: Request,
    body: BugChatMessage,
    session: AsyncSession = Depends(get_db)
):
    """AI-assisted bug creation via conversation (streaming)"""
    user_id = await get_current_user_id(request, session)
    
    llm_service = LLMService(session)
    
    # Get user's active LLM config
    config = await llm_service.get_active_config(user_id)
    if not config:
        raise HTTPException(status_code=400, detail="No LLM provider configured")
    
    # Build conversation context
    conversation = body.conversation_history or []
    
    system_prompt = """You are an expert QA engineer and bug reporter assistant for JarlPM, a product management tool.
Your goal is to help users create comprehensive, well-structured bug reports through a friendly conversation.

CONVERSATION FLOW:
1. First, ask about the PROBLEM - what went wrong?
2. Then ask for STEPS TO REPRODUCE - how can someone else see this bug?
3. Ask about EXPECTED BEHAVIOR - what should have happened?
4. Ask about ACTUAL BEHAVIOR - what actually happened instead?
5. Optionally ask about ENVIRONMENT (browser, OS, device) if relevant

IMPORTANT RULES:
- Ask ONE question at a time to keep the conversation focused
- Be conversational and helpful, not robotic
- If the user provides multiple pieces of information, acknowledge them
- Once you have enough information (problem, steps, expected, actual), propose a complete bug report

WHEN READY TO PROPOSE:
After gathering sufficient information, respond with a JSON block containing the proposed bug:
```json
{
  "proposal": {
    "title": "Brief, clear title describing the bug",
    "description": "Detailed description of the issue",
    "severity": "critical|high|medium|low",
    "steps_to_reproduce": "Numbered steps",
    "expected_behavior": "What should happen",
    "actual_behavior": "What actually happens",
    "environment": "Browser/OS/Device if mentioned",
    "priority": "p0|p1|p2|p3"
  }
}
```

Severity guide:
- critical: System crash, data loss, security vulnerability
- high: Major feature broken, no workaround
- medium: Feature partially broken, workaround exists
- low: Minor issue, cosmetic, edge case

Priority guide:
- p0: Fix immediately (blocking users)
- p1: Fix this sprint
- p2: Fix soon
- p3: Fix when possible

Start the conversation by asking about the problem they encountered."""

    # Format conversation for LLM
    formatted_history = []
    for msg in conversation:
        formatted_history.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })
    
    async def generate():
        full_response = ""
        async for chunk in llm_service.stream_completion(
            config=config,
            system_prompt=system_prompt,
            user_prompt=body.content,
            context=formatted_history if formatted_history else None
        ):
            full_response += chunk
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        
        # Check if response contains a proposal
        proposal = None
        is_complete = False
        
        # Try to extract JSON proposal from response
        try:
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', full_response, re.DOTALL)
            if json_match:
                proposal_data = json.loads(json_match.group(1))
                if "proposal" in proposal_data:
                    proposal = proposal_data["proposal"]
                    is_complete = True
        except (json.JSONDecodeError, KeyError):
            pass
        
        yield f"data: {json.dumps({'type': 'done', 'proposal': proposal, 'is_complete': is_complete})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/ai/create-from-proposal", response_model=BugResponse)
async def create_bug_from_proposal(
    request: Request,
    body: BugProposal,
    session: AsyncSession = Depends(get_db)
):
    """Create a bug from an AI-generated proposal"""
    user_id = await get_current_user_id(request, session)
    
    # Validate severity
    if body.severity not in [s.value for s in BugSeverity]:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {body.severity}")
    
    # Validate priority if provided
    if body.priority and body.priority not in [p.value for p in BugPriority]:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {body.priority}")
    
    bug_service = BugService(session)
    bug = await bug_service.create_bug(
        user_id=user_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        steps_to_reproduce=body.steps_to_reproduce,
        expected_behavior=body.expected_behavior,
        actual_behavior=body.actual_behavior,
        environment=body.environment,
        priority=body.priority
    )
    
    logger.info(f"Created bug from AI proposal: {bug.bug_id} for user {user_id}")
    return bug_to_response(bug)