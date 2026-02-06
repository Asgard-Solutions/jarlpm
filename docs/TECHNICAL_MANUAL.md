# JarlPM Technical Manual

**Version 2.0 | Last Updated: February 2026**

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Technology Stack](#2-technology-stack)
3. [Database Schema](#3-database-schema)
4. [API Reference](#4-api-reference)
5. [Authentication & Security](#5-authentication--security)
6. [LLM Integration](#6-llm-integration)
7. [Services Layer](#7-services-layer)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Deployment](#9-deployment)
10. [Configuration](#10-configuration)
11. [Development Guide](#11-development-guide)
12. [Testing](#12-testing)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Architecture Overview

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│                    React 19 + Tailwind CSS                       │
│                      (Port 3000)                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (via Ingress)
                              │ /api/* routes
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Backend                                  │
│                    FastAPI (Python)                              │
│                      (Port 8001)                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │PostgreSQL│   │  Stripe  │   │   LLM    │
        │  (Neon)  │   │   API    │   │ Providers│
        └──────────┘   └──────────┘   └──────────┘
```

### Key Architectural Decisions

1. **LLM Agnosticism**: Users provide their own API keys. No bundled model access.
2. **Epic as Irreducible Unit**: All workflows orbit the Epic entity.
3. **Monotonic State Machine**: No stage regression allowed.
4. **Append-Only Conversations**: Transcript events are immutable.
5. **Separation of Scoring**: MoSCoW/RICE/Points assigned separately from creation.
6. **Sessionless Streaming**: LLM streaming endpoints don't hold DB sessions.

### Directory Structure

```
/app
├── backend/
│   ├── alembic/              # Database migrations
│   ├── db/
│   │   ├── database.py       # DB connection & session management
│   │   ├── models.py         # SQLAlchemy ORM models
│   │   ├── feature_models.py # Feature-specific models
│   │   ├── user_story_models.py
│   │   ├── persona_models.py
│   │   ├── scoring_models.py
│   │   └── analytics_models.py
│   ├── routes/
│   │   ├── auth.py           # Authentication endpoints
│   │   ├── epic.py           # Epic CRUD & chat
│   │   ├── feature.py        # Feature management
│   │   ├── user_story.py     # User story management
│   │   ├── bug.py            # Bug tracking
│   │   ├── initiative.py     # Initiative generation
│   │   ├── scoring.py        # MoSCoW/RICE scoring
│   │   ├── poker.py          # AI poker planning
│   │   ├── sprints.py        # Sprint management
│   │   ├── delivery_reality.py
│   │   ├── prd.py            # PRD generation
│   │   ├── lean_canvas.py    # Lean canvas
│   │   ├── persona.py        # User personas
│   │   ├── export.py         # Export to Jira/Azure
│   │   ├── subscription.py   # Stripe billing
│   │   ├── llm_provider.py   # LLM config management
│   │   └── delivery_context.py
│   ├── services/
│   │   ├── llm_service.py    # LLM abstraction layer
│   │   ├── strict_output_service.py  # JSON validation & repair
│   │   ├── epic_service.py
│   │   ├── feature_service.py
│   │   ├── user_story_service.py
│   │   ├── bug_service.py
│   │   ├── scoring_service.py
│   │   ├── persona_service.py
│   │   ├── prompt_service.py
│   │   ├── export_service.py
│   │   ├── email_service.py
│   │   ├── analytics_service.py
│   │   ├── lock_policy_service.py
│   │   └── encryption.py
│   ├── server.py             # FastAPI application entry
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/              # API client
│   │   ├── components/       # Reusable components
│   │   │   └── ui/           # shadcn/ui components
│   │   ├── pages/            # Page components
│   │   └── App.jsx           # Router & layout
│   └── package.json
├── docs/
│   ├── USER_MANUAL.md
│   └── TECHNICAL_MANUAL.md
└── memory/
    └── PRD.md                # Product requirements
```

---

## 2. Technology Stack

### Backend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | FastAPI | 0.100+ |
| Language | Python | 3.11+ |
| ORM | SQLAlchemy | 2.0+ |
| Database | PostgreSQL (Neon) | 15+ |
| Migrations | Alembic | 1.12+ |
| Password Hashing | bcrypt | 4.0+ |
| JWT | python-jose | 3.3+ |
| HTTP Client | httpx | 0.25+ |
| Encryption | cryptography (Fernet) | 41+ |

### Frontend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | React | 19 |
| Styling | Tailwind CSS | 3.4+ |
| Components | shadcn/ui | Latest |
| Icons | Lucide React | Latest |
| HTTP Client | Axios | 1.6+ |
| Routing | React Router | 6+ |

### External Services

| Service | Purpose |
|---------|---------|
| Stripe | Subscription billing |
| Microsoft Graph | Email sending |
| OpenAI | LLM provider (user keys) |
| Anthropic | LLM provider (user keys) |
| Local HTTP | Custom LLM endpoint |

---

## 3. Database Schema

### Core Entities

#### User
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    password_hash VARCHAR(255),
    email_verified BOOLEAN DEFAULT FALSE,
    picture TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### Epic
```sql
CREATE TABLE epics (
    epic_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    title VARCHAR(500) NOT NULL,
    current_stage VARCHAR(50) DEFAULT 'problem_capture',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Epic stages (monotonic progression):
-- problem_capture → problem_confirmed → outcome_capture → 
-- outcome_confirmed → epic_drafted → epic_locked
```

#### EpicSnapshot
```sql
CREATE TABLE epic_snapshots (
    snapshot_id UUID PRIMARY KEY,
    epic_id UUID REFERENCES epics(epic_id) ON DELETE CASCADE,
    problem_statement TEXT,
    desired_outcome TEXT,
    epic_summary TEXT,
    vision_statement TEXT,
    acceptance_criteria TEXT[],
    risks TEXT[],
    out_of_scope TEXT[],
    key_metrics TEXT[],
    target_users TEXT,
    moscow_score VARCHAR(50)
);
```

#### Feature
```sql
CREATE TABLE features (
    feature_id UUID PRIMARY KEY,
    epic_id UUID REFERENCES epics(epic_id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    acceptance_criteria TEXT[],
    current_stage VARCHAR(50) DEFAULT 'draft',
    source VARCHAR(50) DEFAULT 'manual',
    priority INTEGER DEFAULT 0,
    -- MoSCoW & RICE scoring (set via Scoring, not creation)
    moscow_score VARCHAR(50),
    rice_reach INTEGER,
    rice_impact FLOAT,
    rice_confidence FLOAT,
    rice_effort FLOAT,
    rice_total FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    approved_at TIMESTAMP
);

-- Feature stages: draft → refining → approved
```

#### UserStory
```sql
CREATE TABLE user_stories (
    story_id UUID PRIMARY KEY,
    feature_id UUID REFERENCES features(feature_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id),
    title VARCHAR(500),
    persona VARCHAR(255) NOT NULL,
    action TEXT NOT NULL,
    benefit TEXT NOT NULL,
    story_text TEXT,
    acceptance_criteria TEXT[],
    labels TEXT[],
    story_priority VARCHAR(50),
    dependencies TEXT[],
    risks TEXT[],
    current_stage VARCHAR(50) DEFAULT 'draft',
    source VARCHAR(50) DEFAULT 'manual',
    is_standalone BOOLEAN DEFAULT FALSE,
    -- Scoring fields (set via Scoring/Poker, not creation)
    story_points INTEGER,
    rice_reach INTEGER,
    rice_impact FLOAT,
    rice_confidence FLOAT,
    rice_effort FLOAT,
    rice_total FLOAT,
    -- Sprint assignment
    sprint_number INTEGER,
    sprint_status VARCHAR(50),
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    approved_at TIMESTAMP
);

-- Story stages: draft → refining → approved
```

#### Bug
```sql
CREATE TABLE bugs (
    bug_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    severity VARCHAR(50) DEFAULT 'medium',
    priority VARCHAR(10),
    steps_to_reproduce TEXT,
    expected_behavior TEXT,
    actual_behavior TEXT,
    environment TEXT,
    -- RICE scoring
    rice_reach INTEGER,
    rice_impact FLOAT,
    rice_confidence FLOAT,
    rice_effort FLOAT,
    rice_total FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Bug statuses: draft → confirmed → in_progress → resolved → closed
```

### Conversation Events (Append-Only)

```sql
CREATE TABLE epic_transcript_events (
    event_id UUID PRIMARY KEY,
    epic_id UUID REFERENCES epics(epic_id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    stage VARCHAR(50),
    event_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE feature_conversation_events (
    event_id UUID PRIMARY KEY,
    feature_id UUID REFERENCES features(feature_id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    event_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_story_conversation_events (
    event_id UUID PRIMARY KEY,
    story_id UUID REFERENCES user_stories(story_id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    event_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE bug_conversation_events (
    event_id UUID PRIMARY KEY,
    bug_id UUID REFERENCES bugs(bug_id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    event_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Supporting Entities

#### LLMProviderConfig
```sql
CREATE TABLE llm_provider_configs (
    config_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    provider VARCHAR(50) NOT NULL,  -- openai, anthropic, local
    encrypted_api_key TEXT,
    base_url TEXT,
    model_name VARCHAR(255),
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### ProductDeliveryContext
```sql
CREATE TABLE product_delivery_contexts (
    context_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) UNIQUE,
    industry TEXT,
    delivery_methodology VARCHAR(50),
    sprint_cycle_length INTEGER DEFAULT 14,
    sprint_start_date DATE,
    num_developers INTEGER DEFAULT 3,
    num_qa INTEGER DEFAULT 1,
    delivery_platform VARCHAR(50),
    quality_mode VARCHAR(50) DEFAULT 'standard',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### Subscription
```sql
CREATE TABLE subscriptions (
    subscription_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    status VARCHAR(50) DEFAULT 'inactive',
    stripe_subscription_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Database Triggers

#### Append-Only Enforcement
```sql
CREATE OR REPLACE FUNCTION prevent_transcript_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Transcript events are append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER transcript_update_trigger
BEFORE UPDATE OR DELETE ON epic_transcript_events
FOR EACH ROW EXECUTE FUNCTION prevent_transcript_update();
```

#### Monotonic Stage Progression
```sql
CREATE OR REPLACE FUNCTION enforce_stage_progression()
RETURNS TRIGGER AS $$
DECLARE
    stage_order TEXT[] := ARRAY[
        'problem_capture', 'problem_confirmed',
        'outcome_capture', 'outcome_confirmed',
        'epic_drafted', 'epic_locked'
    ];
BEGIN
    IF array_position(stage_order, NEW.current_stage) < 
       array_position(stage_order, OLD.current_stage) THEN
        RAISE EXCEPTION 'Stage regression not allowed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## 4. API Reference

### Authentication

#### POST /api/auth/signup
Create a new user account.

**Request:**
```json
{
    "email": "user@example.com",
    "password": "SecurePass123",
    "name": "John Doe"
}
```

**Response (201):**
```json
{
    "user_id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "email_verified": false
}
```

#### POST /api/auth/login
Authenticate user.

**Request:**
```json
{
    "email": "user@example.com",
    "password": "SecurePass123"
}
```

**Response (200):**
```json
{
    "user_id": "uuid",
    "email": "user@example.com",
    "name": "John Doe"
}
```

Sets `session_token` httpOnly cookie.

#### GET /api/auth/me
Get current authenticated user.

**Response (200):**
```json
{
    "user_id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "email_verified": true
}
```

### Epics

#### GET /api/epics
List user's epics.

**Response (200):**
```json
[
    {
        "epic_id": "uuid",
        "title": "Epic Title",
        "current_stage": "epic_locked",
        "snapshot": { ... },
        "created_at": "2026-02-06T12:00:00Z"
    }
]
```

#### POST /api/epics
Create new epic.

**Request:**
```json
{
    "title": "New Epic"
}
```

**Response (201):**
```json
{
    "epic_id": "uuid",
    "title": "New Epic",
    "current_stage": "problem_capture"
}
```

#### POST /api/epics/{epic_id}/chat
Chat with AI about epic (streaming SSE).

**Request:**
```json
{
    "content": "The problem is users can't find their order history"
}
```

**Response (SSE Stream):**
```
data: {"type": "chunk", "content": "I understand..."}
data: {"type": "chunk", "content": " the problem..."}
data: {"type": "proposal", "proposal_id": "uuid", "content": "...", "target_stage": "problem_confirmed"}
data: {"type": "done"}
```

#### POST /api/epics/{epic_id}/confirm-proposal
Confirm or reject a proposal.

**Request:**
```json
{
    "proposal_id": "uuid",
    "action": "confirm"  // or "reject"
}
```

### Features

#### POST /api/features/epic/{epic_id}/generate
Generate AI feature suggestions (streaming).

**Response (SSE Stream):**
```
data: {"type": "chunk", "content": "["}
data: {"type": "chunk", "content": "{\"title\":..."}
data: {"type": "features", "features": [...]}
data: {"type": "done"}
```

#### POST /api/features/{feature_id}/chat
Refine feature with AI (streaming).

**Request:**
```json
{
    "content": "Can we add error handling to this feature?"
}
```

#### POST /api/features/{feature_id}/approve
Lock and approve feature.

**Response (200):**
```json
{
    "feature_id": "uuid",
    "current_stage": "approved",
    "approved_at": "2026-02-06T12:00:00Z"
}
```

### User Stories

#### POST /api/stories/feature/{feature_id}/generate
Generate stories for a feature (streaming).

#### POST /api/stories/standalone
Create standalone story.

**Request:**
```json
{
    "persona": "logged-in user",
    "action": "view my order history",
    "benefit": "I can track my purchases",
    "acceptance_criteria": [
        "Given I am logged in, When I click Orders, Then I see my order list"
    ]
}
```

> **Note:** `story_points` is NOT accepted. Use Scoring or Poker to set points.

### Initiative Generation

#### POST /api/initiative/generate
Generate complete initiative (streaming).

**Request:**
```json
{
    "idea": "A mobile app for tracking daily water intake",
    "product_name": "HydroTrack",
    "quality_mode": "quality"  // or "standard"
}
```

**Response (SSE Stream):**
```
data: {"type": "pass", "pass": 1, "message": "Defining the problem..."}
data: {"type": "progress", "pass": 1, "message": "PRD complete: HydroTrack"}
data: {"type": "pass", "pass": 2, "message": "Breaking down features..."}
data: {"type": "progress", "pass": 2, "message": "Created 4 features, 12 stories"}
data: {"type": "pass", "pass": 3, "message": "Running PM quality checks..."}
data: {"type": "initiative", "data": {...}}
data: {"type": "done", "message": "Initiative generated!"}
```

#### POST /api/initiative/save
Save generated initiative to database.

**Request:**
```json
{
    "initiative": { ... }  // The initiative object from generate
}
```

### Scoring

#### POST /api/scoring/epic/{epic_id}/moscow/suggest
Get AI MoSCoW suggestion (streaming).

#### PUT /api/scoring/feature/{feature_id}/rice
Update feature RICE scores.

**Request:**
```json
{
    "reach": 8,
    "impact": 2,
    "confidence": 0.8,
    "effort": 3
}
```

### Poker Planning

#### POST /api/poker/estimate
Get AI story point estimates (streaming).

**Request:**
```json
{
    "story_id": "uuid"
}
```

**Response (SSE Stream):**
```
data: {"type": "start", "total_personas": 5}
data: {"type": "persona_start", "persona_id": "sarah", "name": "Sarah"}
data: {"type": "persona_done", "persona_id": "sarah", "estimate": {"estimate": 5, "reasoning": "...", "confidence": "high"}}
data: {"type": "summary", "summary": {"average": 4.2, "suggested": 5, "consensus": "medium"}}
data: {"type": "done"}
```

### Sprints

#### GET /api/sprints/current
Get current sprint info.

#### POST /api/sprints/ai/kickoff-plan
Generate sprint kickoff plan.

#### POST /api/sprints/ai/standup
Generate standup summary.

#### POST /api/sprints/ai/wip-suggestions
Generate WIP suggestions.

### Export

#### POST /api/export/file
Download export file.

**Request:**
```json
{
    "epic_id": "uuid",
    "format": "jira_csv"  // jira_csv, azure_csv, json, markdown
}
```

#### POST /api/export/jira
Push to Jira Cloud.

**Request:**
```json
{
    "epic_id": "uuid",
    "jira_url": "https://company.atlassian.net",
    "email": "user@company.com",
    "api_token": "xxx",
    "project_key": "PROJ"
}
```

### Subscription

#### POST /api/subscription/create-checkout
Create Stripe checkout session.

**Response (200):**
```json
{
    "checkout_url": "https://checkout.stripe.com/...",
    "session_id": "cs_xxx"
}
```

#### GET /api/subscription/status
Get subscription status.

**Response (200):**
```json
{
    "status": "active",
    "current_period_end": "2026-03-06T12:00:00Z",
    "cancel_at_period_end": false
}
```

---

## 5. Authentication & Security

### Password Security

- Passwords hashed with bcrypt (work factor 12)
- Minimum 8 characters, uppercase, lowercase, number required
- Password reset invalidates all existing sessions

### Session Management

```python
# JWT token structure
{
    "sub": "user_id",
    "exp": timestamp,  # 7 days
    "iat": timestamp
}
```

- Tokens stored in `session_tokens` table
- httpOnly cookies prevent XSS
- SameSite=Lax prevents CSRF

### API Key Encryption

```python
from cryptography.fernet import Fernet

# Key derivation
key = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=ENCRYPTION_SALT,
    iterations=100000
).derive(ENCRYPTION_KEY.encode())

cipher = Fernet(base64.urlsafe_b64encode(key))

# Encrypt
encrypted = cipher.encrypt(api_key.encode())

# Decrypt
decrypted = cipher.decrypt(encrypted).decode()
```

### Authorization

All endpoints require authentication except:
- `/api/auth/signup`
- `/api/auth/login`
- `/api/auth/forgot-password`
- `/api/auth/reset-password`
- `/api/auth/verify-email`
- `/api/health`

AI features additionally require:
- Active subscription
- Configured LLM provider

---

## 6. LLM Integration

### Provider Abstraction

```python
# /backend/services/llm_service.py

class LLMService:
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
    
    async def get_user_llm_config(self, user_id: str) -> Optional[LLMProviderConfig]:
        """Get user's active LLM configuration"""
        ...
    
    def prepare_for_streaming(self, config: LLMProviderConfig) -> dict:
        """Extract config data for sessionless streaming"""
        return {
            "provider": config.provider,
            "api_key": decrypt(config.encrypted_api_key),
            "base_url": config.base_url,
            "model_name": config.model_name
        }
    
    async def stream_with_config(
        self,
        config_data: dict,
        system_prompt: str,
        user_prompt: str,
        conversation_history: Optional[List] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response without holding DB session"""
        ...
```

### Supported Providers

#### OpenAI
```python
async with httpx.AsyncClient() as client:
    async with client.stream(
        "POST",
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model_name,
            "messages": messages,
            "stream": True,
            "max_tokens": 4096,
            "temperature": temperature
        }
    ) as response:
        async for line in response.aiter_lines():
            # Parse SSE data
            ...
```

#### Anthropic
```python
async with httpx.AsyncClient() as client:
    async with client.stream(
        "POST",
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        },
        json={
            "model": model_name,
            "messages": messages,
            "stream": True,
            "max_tokens": 4096
        }
    ) as response:
        ...
```

#### Local HTTP
```python
async with httpx.AsyncClient() as client:
    async with client.stream(
        "POST",
        f"{base_url}/v1/chat/completions",
        json={
            "model": model_name,
            "messages": messages,
            "stream": True
        }
    ) as response:
        ...
```

### Strict Output Service

Validates and repairs LLM JSON output:

```python
class StrictOutputService:
    async def validate_and_repair(
        self,
        raw_response: str,
        schema: Type[BaseModel],
        repair_callback: Callable,
        max_repairs: int = 2
    ) -> ValidationResult:
        """
        1. Extract JSON from response
        2. Validate against Pydantic schema
        3. If invalid, call LLM to repair
        4. Repeat up to max_repairs times
        """
        ...
```

### Sessionless Streaming Pattern

To prevent DB connection pool exhaustion:

```python
@router.post("/generate")
async def generate(request: Request, session: AsyncSession = Depends(get_db)):
    # 1. Fetch all needed data BEFORE streaming
    user_id = await get_current_user_id(request, session)
    llm_config = await llm_service.get_user_llm_config(user_id)
    config_data = llm_service.prepare_for_streaming(llm_config)
    
    # 2. Release session before streaming
    async def generate():
        # 3. Use sessionless LLM service
        llm = LLMService()  # No session
        async for chunk in llm.stream_with_config(config_data, ...):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        # 4. Use fresh session for DB writes
        async with AsyncSessionLocal() as new_session:
            await save_to_db(new_session, ...)
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## 7. Services Layer

### EpicService

```python
class EpicService:
    async def create_epic(self, user_id: str, title: str) -> Epic
    async def get_epic(self, epic_id: str, user_id: str) -> Optional[Epic]
    async def get_epics(self, user_id: str) -> List[Epic]
    async def delete_epic(self, epic_id: str, user_id: str) -> bool
    async def advance_stage(self, epic_id: str, target_stage: EpicStage) -> Epic
    async def set_pending_proposal(self, ...) -> dict
    async def confirm_proposal(self, epic_id: str, proposal_id: str, action: str) -> Epic
    async def add_transcript_event(self, ...) -> None
    async def get_conversation_history(self, epic_id: str, limit: int) -> List[dict]
```

### LockPolicyService

Central policy module for mutation permissions:

```python
class LockPolicyService:
    async def can_edit_feature(self, feature: Feature) -> bool:
        return feature.current_stage != "approved"
    
    async def can_delete_story(self, story: UserStory) -> bool:
        return story.current_stage != "approved"
    
    async def get_epic_permissions(self, epic: Epic) -> dict:
        return {
            "can_edit_problem": epic.current_stage == "problem_capture",
            "can_edit_outcome": epic.current_stage == "outcome_capture",
            "can_create_features": epic.current_stage == "epic_locked",
            ...
        }
```

### PromptService

Manages prompt templates with delivery context injection:

```python
class PromptService:
    async def get_prompt_for_stage(self, stage: str) -> PromptTemplate
    async def get_delivery_context(self, user_id: str) -> ProductDeliveryContext
    
    def render_prompt(
        self,
        template: PromptTemplate,
        epic_title: str,
        user_message: str,
        snapshot: EpicSnapshot,
        delivery_context: ProductDeliveryContext
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) with context injected"""
        ...
    
    def format_delivery_context(self, ctx: ProductDeliveryContext) -> str:
        """Format context for prompt injection"""
        return f"""
DELIVERY CONTEXT:
- Industry: {ctx.industry or 'Not specified'}
- Methodology: {ctx.delivery_methodology or 'Agile'}
- Sprint Length: {ctx.sprint_cycle_length or 14} days
- Team: {ctx.num_developers or 3} developers, {ctx.num_qa or 1} QA
"""
```

### ScoringService

```python
class ScoringService:
    async def get_epic_moscow(self, epic_id: str) -> Optional[str]
    async def set_epic_moscow(self, epic_id: str, score: str) -> None
    
    async def get_feature_scores(self, feature_id: str) -> FeatureScores
    async def set_feature_moscow(self, feature_id: str, score: str) -> None
    async def set_feature_rice(self, feature_id: str, rice: RICEScores) -> None
    
    async def get_story_rice(self, story_id: str) -> RICEScores
    async def set_story_rice(self, story_id: str, rice: RICEScores) -> None
    
    def calculate_rice_total(self, reach: int, impact: float, confidence: float, effort: float) -> float:
        return (reach * impact * confidence) / effort
```

### ExportService

```python
class ExportService:
    async def export_to_jira_csv(self, epic_id: str) -> bytes
    async def export_to_azure_csv(self, epic_id: str) -> bytes
    async def export_to_json(self, epic_id: str) -> dict
    async def export_to_markdown(self, epic_id: str) -> str
    
    async def push_to_jira(
        self,
        epic_id: str,
        jira_url: str,
        email: str,
        api_token: str,
        project_key: str
    ) -> ExportResult
    
    async def push_to_azure_devops(
        self,
        epic_id: str,
        organization: str,
        project: str,
        pat: str
    ) -> ExportResult
```

---

## 8. Frontend Architecture

### Routing

```jsx
// App.jsx
<Routes>
    {/* Public routes */}
    <Route path="/" element={<Landing />} />
    <Route path="/login" element={<Login />} />
    <Route path="/signup" element={<Signup />} />
    <Route path="/forgot-password" element={<ForgotPassword />} />
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/verify-email" element={<VerifyEmail />} />
    
    {/* Protected routes */}
    <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
    <Route path="/new" element={<ProtectedRoute><NewInitiative /></ProtectedRoute>} />
    <Route path="/initiatives" element={<ProtectedRoute><Initiatives /></ProtectedRoute>} />
    <Route path="/epic/:epicId" element={<ProtectedRoute><Epic /></ProtectedRoute>} />
    <Route path="/epic/:epicId/review" element={<ProtectedRoute><CompletedEpic /></ProtectedRoute>} />
    <Route path="/feature/:featureId/stories" element={<ProtectedRoute><StoryPlanning /></ProtectedRoute>} />
    <Route path="/bugs" element={<ProtectedRoute><Bugs /></ProtectedRoute>} />
    <Route path="/stories" element={<ProtectedRoute><Stories /></ProtectedRoute>} />
    <Route path="/personas" element={<ProtectedRoute><Personas /></ProtectedRoute>} />
    <Route path="/scoring" element={<ProtectedRoute><Scoring /></ProtectedRoute>} />
    <Route path="/poker" element={<ProtectedRoute><PokerPlanning /></ProtectedRoute>} />
    <Route path="/sprints" element={<ProtectedRoute><Sprints /></ProtectedRoute>} />
    <Route path="/delivery-reality" element={<ProtectedRoute><DeliveryReality /></ProtectedRoute>} />
    <Route path="/prd" element={<ProtectedRoute><PRDGenerator /></ProtectedRoute>} />
    <Route path="/lean-canvas" element={<ProtectedRoute><LeanCanvas /></ProtectedRoute>} />
    <Route path="/export" element={<ProtectedRoute><Export /></ProtectedRoute>} />
    <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
</Routes>
```

### API Client

```javascript
// /frontend/src/api/index.js
import axios from 'axios';

const API = axios.create({
    baseURL: process.env.REACT_APP_BACKEND_URL,
    withCredentials: true  // Include cookies
});

export const authAPI = {
    login: (email, password) => API.post('/api/auth/login', { email, password }),
    signup: (data) => API.post('/api/auth/signup', data),
    logout: () => API.post('/api/auth/logout'),
    me: () => API.get('/api/auth/me'),
};

export const epicAPI = {
    list: () => API.get('/api/epics'),
    create: (title) => API.post('/api/epics', { title }),
    get: (id) => API.get(`/api/epics/${id}`),
    delete: (id) => API.delete(`/api/epics/${id}`),
    confirmProposal: (id, proposalId, action) => 
        API.post(`/api/epics/${id}/confirm-proposal`, { proposal_id: proposalId, action }),
};

// SSE streaming helper
export const streamChat = (url, body, onChunk, onProposal, onDone, onError) => {
    return fetch(`${process.env.REACT_APP_BACKEND_URL}${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body)
    }).then(response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        function read() {
            reader.read().then(({ done, value }) => {
                if (done) { onDone(); return; }
                
                const text = decoder.decode(value);
                const lines = text.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        if (data.type === 'chunk') onChunk(data.content);
                        if (data.type === 'proposal') onProposal(data);
                        if (data.type === 'error') onError(data.message);
                    }
                }
                
                read();
            });
        }
        
        read();
    });
};
```

### Component Structure

```
/components
├── ui/                    # shadcn/ui components
│   ├── button.jsx
│   ├── card.jsx
│   ├── dialog.jsx
│   ├── input.jsx
│   ├── select.jsx
│   ├── tabs.jsx
│   └── ...
├── Sidebar.jsx            # Navigation sidebar
├── WorkflowStepper.jsx    # Progress stepper
├── LinkedBugs.jsx         # Bug linking component
├── ScoringComponents.jsx  # MoSCoW/RICE editors
└── ...
```

### State Management

Uses React hooks and local state:
- `useState` for component state
- `useEffect` for data fetching
- `useNavigate` for routing
- `useParams` for URL parameters

No global state management (Redux, etc.) - data fetched per-page.

---

## 9. Deployment

### Environment Variables

#### Backend (`/app/backend/.env`)

```env
# Database
MONGO_URL=postgresql+asyncpg://user:pass@host/db
DB_NAME=jarlpm

# Security
JWT_SECRET=your-jwt-secret
ENCRYPTION_KEY=your-encryption-key

# Stripe
STRIPE_API_KEY=sk_test_xxx
STRIPE_PRICE_ID=price_xxx  # Optional
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Email (Microsoft Graph)
MICROSOFT_GRAPH_CLIENT_ID=xxx
MICROSOFT_GRAPH_CLIENT_SECRET=xxx
MICROSOFT_GRAPH_TENANT_ID=xxx

# CORS
CORS_ORIGINS=https://yourdomain.com
```

#### Frontend (`/app/frontend/.env`)

```env
REACT_APP_BACKEND_URL=https://yourdomain.com
```

### Supervisor Configuration

```ini
[program:backend]
command=/usr/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8001
directory=/app/backend
autostart=true
autorestart=true
redirect_stderr=true

[program:frontend]
command=/usr/bin/yarn start
directory=/app/frontend
autostart=true
autorestart=true
environment=PORT=3000
```

### Database Migrations

```bash
# Create migration
cd /app/backend
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Startup Script

```bash
#!/bin/bash
# /app/backend/scripts/start.sh

# Run migrations
cd /app/backend
alembic upgrade head

# Start application
exec uvicorn server:app --host 0.0.0.0 --port 8001
```

---

## 10. Configuration

### Database Connection Pool

```python
# /backend/db/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Pool configuration from environment
POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.environ.get("DB_MAX_OVERFLOW", "10"))
POOL_TIMEOUT = int(os.environ.get("DB_POOL_TIMEOUT", "30"))

engine = create_async_engine(
    DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_recycle=3600,
    pool_pre_ping=True
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
```

### LLM Configuration

```python
# Default models per provider
DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-sonnet-20240229",
    "local": "llama-3"
}

# Temperature settings per task type
TASK_TEMPERATURES = {
    "prd_generation": 0.7,
    "decomposition": 0.6,
    "planning": 0.3,
    "critic": 0.2,
    "repair": 0.1
}
```

### Stripe Configuration

```python
# Subscription settings
SUBSCRIPTION_PRICE = 4500  # $45.00 in cents
SUBSCRIPTION_INTERVAL = "month"

# Checkout settings
SUCCESS_URL = f"{FRONTEND_URL}/settings?success=true"
CANCEL_URL = f"{FRONTEND_URL}/settings?canceled=true"
```

---

## 11. Development Guide

### Local Setup

```bash
# Clone repository
git clone <repo-url>
cd jarlpm

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your values

# Run migrations
alembic upgrade head

# Start backend
uvicorn server:app --reload --port 8001

# Frontend setup (new terminal)
cd frontend
yarn install
yarn start
```

### Adding a New Route

1. Create route file in `/backend/routes/`
2. Define Pydantic models for request/response
3. Implement endpoints with proper auth checks
4. Register router in `server.py`
5. Add API client methods in `/frontend/src/api/`
6. Create frontend page in `/frontend/src/pages/`
7. Add route to `App.jsx`

### Adding a New Service

1. Create service file in `/backend/services/`
2. Define class with async methods
3. Use dependency injection for session
4. Follow existing patterns (Epic/Feature/Story services)

### Code Style

- **Python**: Follow PEP 8, use type hints
- **JavaScript**: ES6+, React hooks, functional components
- **SQL**: Uppercase keywords, snake_case identifiers

---

## 12. Testing

### Backend Tests

```bash
cd /app/backend
pytest tests/ -v
```

### Test Structure

```python
# tests/test_epics.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_epic(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/epics",
        json={"title": "Test Epic"},
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Test Epic"
```

### Test Database

Tests use a separate test database:
```python
# conftest.py
@pytest.fixture
async def test_db():
    # Create test database
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

---

## 13. Troubleshooting

### Common Issues

#### "No LLM provider configured"
- User hasn't added API key in Settings → LLM Providers
- Solution: Guide user to add and activate a provider

#### "Active subscription required"
- User doesn't have active subscription
- Solution: Direct to Settings → Subscription

#### Database Connection Pool Exhaustion
- Too many concurrent streaming requests
- Solution: Ensure all streaming endpoints use sessionless pattern

#### "Stage regression not allowed"
- Trying to move backward in epic lifecycle
- Solution: This is by design - stages are monotonic

### Logs

```bash
# Backend logs
tail -f /var/log/supervisor/backend.err.log

# Check for specific errors
grep -i error /var/log/supervisor/backend.err.log

# Database queries (DEBUG mode)
# Set LOG_LEVEL=DEBUG in .env
```

### Health Check

```bash
curl http://localhost:8001/api/health
# {"status":"healthy","service":"jarlpm"}
```

### Database Status

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'jarlpm';

-- Check table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

---

## Appendix A: API Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Not logged in |
| 402 | Payment Required - No active subscription |
| 403 | Forbidden - Not allowed |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Duplicate or invalid state |
| 500 | Server Error - Internal error |

---

## Appendix B: Data Validation

### Email
- RFC 5322 compliant
- Unique per account

### Password
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number

### Story Points (Fibonacci)
- Valid values: 1, 2, 3, 5, 8, 13
- Set only via Scoring or Poker

### MoSCoW Scores
- Valid values: must_have, should_have, could_have, wont_have

### RICE Scores
- Reach: 1-10 (integer)
- Impact: 0.25, 0.5, 1, 2, 3
- Confidence: 0.5, 0.8, 1.0
- Effort: 0.5-10 (float)

---

*JarlPM Technical Manual — Version 2.0*
