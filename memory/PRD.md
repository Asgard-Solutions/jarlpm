# JarlPM - Product Requirements Document

## Overview
JarlPM is an AI-agnostic, conversation-driven Product Management system for Product Managers. It helps teams create and improve Epics, Features, User Stories, and Bugs so that developers can implement without missing acceptance criteria.

## Core Architecture

### Tech Stack
- **Frontend**: React 19 with Tailwind CSS, shadcn/ui components
- **Backend**: FastAPI (Python) 
- **Database**: PostgreSQL (Neon) with SQLAlchemy ORM
- **Authentication**: Emergent Google OAuth
- **Payments**: Stripe ($20/month subscription)

### Key Architectural Decisions

1. **LLM Agnosticism**: Users bring their own API keys (OpenAI, Anthropic, Local HTTP). JarlPM never bundles model access.

2. **Prompt Registry Pattern**: All AI interactions use versioned, provider-neutral prompt templates stored in the database. No provider-native agents are used.

3. **Epic as Irreducible Unit**: All workflows, state, persistence, and UX orbit the Epic entity.

4. **Product Delivery Context**: Per-user configuration automatically injected into all LLM prompts.

5. **Feature Lifecycle Pattern**: Features have their own stages (draft → refining → approved) with mini-conversation support for refinement.

## Data Models

### User
- user_id (UUID)
- email
- name
- picture
- created_at, updated_at

### ProductDeliveryContext
- context_id (UUID)
- user_id (FK to User, unique)
- industry (comma-separated string)
- delivery_methodology: waterfall | agile | scrum | kanban | hybrid
- sprint_cycle_length (integer, days)
- sprint_start_date (date)
- num_developers (integer)
- num_qa (integer)
- delivery_platform: jira | azure_devops | none | other
- created_at, updated_at

### Subscription
- subscription_id (UUID)
- user_id
- status: active | inactive | canceled | past_due
- stripe_subscription_id
- current_period_start, current_period_end

### LLMProviderConfig
- config_id (UUID)
- user_id
- provider: openai | anthropic | local
- encrypted_api_key (Fernet encrypted)
- base_url (for local providers)
- model_name
- is_active

### Epic
- epic_id (UUID)
- user_id
- title
- current_stage (monotonic state machine)
- snapshot (canonical content)
- pending_proposal (requires explicit confirmation)
- created_at, updated_at

### Feature (NEW - 2026-01-13)
- feature_id (UUID)
- epic_id (FK to Epic)
- title
- description
- acceptance_criteria (array)
- current_stage: draft | refining | approved
- source: ai_generated | manual
- priority (optional)
- created_at, updated_at, approved_at

### FeatureConversationEvent (Append-Only) (NEW)
- event_id (UUID)
- feature_id (FK to Feature)
- role: user | assistant | system
- content
- event_metadata
- created_at

### EpicTranscriptEvent (Append-Only)
- event_id (UUID)
- epic_id
- role: user | assistant | system
- content
- stage
- event_metadata
- created_at

### EpicDecision (Append-Only)
- decision_id (UUID)
- epic_id
- decision_type: confirm_proposal | reject_proposal | stage_advance
- from_stage, to_stage
- proposal_id
- content_snapshot
- user_id
- created_at

## Epic Lifecycle (Monotonic State Machine)

Stages (no regression allowed):
1. **problem_capture** - Define the problem
2. **problem_confirmed** - LOCKED - Problem statement is immutable
3. **outcome_capture** - Define success metrics
4. **outcome_confirmed** - LOCKED - Desired outcomes are immutable
5. **epic_drafted** - Draft epic with acceptance criteria
6. **epic_locked** - LOCKED - Epic is implementation-ready → Feature Planning Mode

## Feature Lifecycle (NEW)

When an Epic is locked, users enter Feature Planning Mode:
1. **draft** - Initial feature created (AI-generated or manual)
2. **refining** - Feature is being refined through AI conversation
3. **approved** - LOCKED - Feature is finalized and immutable

### Feature Creation Flow
1. User clicks "Generate Features" → AI analyzes locked epic and suggests 3-5 features
2. Each suggestion appears as a draft that user can:
   - **Save as Draft** → Adds to feature list
   - **Discard** → Removes suggestion
3. For saved drafts, user can:
   - **Approve & Lock** → Finalizes feature immediately
   - **Refine with AI** → Opens mini-conversation for refinement
   - **Delete** → Removes feature
4. Refinement conversation allows iterative improvement
5. Once approved, feature is immutable

## API Endpoints

### Authentication
- POST /api/auth/session - Exchange Emergent session_id for session_token
- GET /api/auth/me - Get current user
- POST /api/auth/logout - Logout
- POST /api/auth/test-login - One-click test user login (development)

### Subscription
- GET /api/subscription/status - Get subscription status
- POST /api/subscription/create-checkout - Create Stripe checkout
- GET /api/subscription/checkout-status/{session_id} - Poll payment status

### LLM Providers
- GET /api/llm-providers - List user's LLM configurations
- POST /api/llm-providers - Add/update LLM configuration (validates key)
- DELETE /api/llm-providers/{config_id} - Delete configuration
- PUT /api/llm-providers/{config_id}/activate - Activate provider

### Product Delivery Context
- GET /api/delivery-context - Get user's delivery context (auto-creates if none)
- PUT /api/delivery-context - Update delivery context

### Epics
- GET /api/epics - List user's epics
- POST /api/epics - Create new epic (status 201)
- GET /api/epics/{id} - Get epic details
- DELETE /api/epics/{id} - Delete epic (hard delete, cascades)
- POST /api/epics/{id}/chat - Chat with AI (streaming SSE)
- POST /api/epics/{id}/confirm-proposal - Confirm/reject pending proposal
- GET /api/epics/{id}/transcript - Get full conversation history
- GET /api/epics/{id}/decisions - Get decision log

### Features (NEW - 2026-01-13)
- GET /api/features/epic/{epic_id} - List features for an epic
- POST /api/features/epic/{epic_id} - Create a feature (manual or AI-generated)
- POST /api/features/epic/{epic_id}/generate - Generate AI feature suggestions (streaming)
- GET /api/features/{feature_id} - Get feature details
- PUT /api/features/{feature_id} - Update feature (only if not approved)
- DELETE /api/features/{feature_id} - Delete feature
- POST /api/features/{feature_id}/approve - Approve and lock feature
- GET /api/features/{feature_id}/conversation - Get refinement conversation history
- POST /api/features/{feature_id}/chat - Chat to refine feature (streaming)

## Sacred Invariants

1. Confirmed decisions are immutable
2. Conversation history is append-only
3. User intent is preserved
4. Agent reasoning context is persisted
5. Stage locks cannot be bypassed
6. **Product Delivery Context is read-only for LLM** (injected but not modifiable by AI)
7. **Approved features are immutable** (NEW)
8. **Feature conversations are append-only** (NEW)

## Security

- API keys encrypted with Fernet (PBKDF2-derived key)
- Session tokens stored in httpOnly cookies
- All state changes enforced server-side
- Client cannot advance stages or lock content
- PostgreSQL constraints enforce append-only tables and monotonic stage progression

## Subscription Model

- Price: $20/month
- Covers: Database storage, persistence, system infrastructure
- Does NOT cover: Tokens, models, AI usage (user-provided keys)
- Inactive subscription blocks AI execution but preserves data

---

## Changelog

### 2026-01-13: Landing Page Copy Update (COMPLETE)
- Updated hero section with new tagline: "Lead like a Jarl — calm authority, decisions that stick."
- New description copy emphasizing clarity and discipline
- Hidden Test Login behind environment flag (dev-only by default)
- Updated "Why JarlPM?" section with philosophical intro and refined card copy
- Updated Epic Lifecycle subheading: "A monotonic decision lifecycle"
- Added footer attribution: "Built by Asgard Solutions LLC"
- CTA changed to "Start Building Epics" with helper text

### 2026-01-13: Feature Planning Mode (COMPLETE)
- Added `Feature` model with lifecycle stages (draft → refining → approved)
- Added `FeatureConversationEvent` model for append-only refinement conversations
- New API endpoints for feature CRUD, approval, and AI chat
- New Feature Planning UI when epic is locked:
  - "Generate Features" button triggers AI to suggest features
  - Features organized by stage (Drafts, Refining, Approved)
  - Mini-conversation dialog for refining individual features
  - Manual feature creation option
  - Epic Reference sidebar shows locked epic content
- Added useEffect to Epic.jsx to fetch subscription/LLM providers on direct navigation
- Database triggers for append-only feature conversations

### 2026-01-13: Product Delivery Context Feature
- Added `ProductDeliveryContext` model for per-user delivery configuration
- New API endpoints: GET/PUT /api/delivery-context
- Context automatically injected into all LLM prompts via `prompt_service.py`
- Fields: industry, delivery_methodology, sprint_cycle_length, sprint_start_date, num_developers, num_qa, delivery_platform
- Missing values treated as "Not specified"
- Context persists across Epics and sessions

### 2026-01-13: MongoDB to PostgreSQL Migration
- Migrated entire database from MongoDB to PostgreSQL (Neon)
- Implemented SQLAlchemy ORM models
- Added database-level constraints:
  - Append-only triggers for transcript_events and decisions
  - Monotonic stage progression trigger for epics
  - Locked content protection trigger for snapshots
- All enum types stored as strings for compatibility

---

## Backlog

### P1 - Upcoming
- Story and Bug creation stages (children of Features)
- Full E2E workflow test

### P2 - Future
- Implement full Stripe subscription flow
- Epic deletion with explicit confirmation
- Export to Jira/Azure DevOps
- Team collaboration features
