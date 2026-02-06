# JarlPM - Product Requirements Document

## Overview
JarlPM is an AI-agnostic, conversation-driven Product Management system for Product Managers. It helps teams create and improve Epics, Features, User Stories, and Bugs so that developers can implement without missing acceptance criteria.

## Core Architecture

### Tech Stack
- **Frontend**: React 19 with Tailwind CSS, shadcn/ui components
- **Backend**: FastAPI (Python) 
- **Database**: PostgreSQL (Neon) with SQLAlchemy ORM
- **Authentication**: Email/Password with bcrypt hashing and JWT tokens
- **Payments**: Stripe ($45/month subscription)
- **Email**: Microsoft Graph API (sender: support@asgardsolution.io)

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
- password_hash (bcrypt hashed password)
- email_verified (boolean)
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
- quality_mode: standard | quality (NEW - 2-pass with critique)
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
- POST /api/auth/signup - Register new user with email/password
- POST /api/auth/login - Login with email/password
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

- Price: $45/month
- Covers: Database storage, persistence, system infrastructure
- Does NOT cover: Tokens, models, AI usage (user-provided keys)
- Inactive subscription blocks AI execution but preserves data

---

## Changelog

### 2026-01-13: Completed Epic Review Page (COMPLETE)
- New `/epic/:epicId/review` route for completed epic review
- Expandable tree view: Epic → Features → User Stories
- Stats display: total features, stories, story points
- Expand All / Collapse All buttons
- Auto-redirect from Epic page when fully complete (all features & stories approved)
- Dashboard navigates locked epics directly to review page
- "Epic Complete!" celebration message with Trophy badge
- Feature and story cards show locked/approved status with badges

### 2026-01-13: User Story Planning Feature (COMPLETE)
- Added `UserStory` model with standard format: "As a [persona], I want to [action] so that [benefit]"
- Added `UserStoryConversationEvent` model for append-only refinement conversations
- User Story lifecycle stages: draft → refining → approved (mirrors Feature pattern)
- Acceptance criteria use Given/When/Then format
- Story points support (1, 2, 3, 5, 8) for sprint planning
- New API endpoints:
  - GET/POST /api/stories/feature/{feature_id}
  - POST /api/stories/feature/{feature_id}/generate (AI streaming)
  - GET/PUT/DELETE /api/stories/{story_id}
  - POST /api/stories/{story_id}/approve
  - POST /api/stories/{story_id}/chat (AI streaming refinement)
- New StoryPlanning.jsx page at /feature/:featureId/stories
- "Create User Stories" button on approved features in Epic page
- Feature Reference sidebar shows locked feature content
- Fixed LLM provider state management for direct navigation

### 2026-01-13: Logo and Favicon Update (COMPLETE)
- Added Viking helmet logo images (light/dark variants) for theme support
- Created favicon.ico, logo192.png, logo512.png, apple-touch-icon.png
- Updated index.html with proper favicon, meta description, and title
- Updated Landing.jsx, Dashboard.jsx, Settings.jsx to use theme-aware logo
- Logo switches between light/dark versions based on current theme

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

### 2026-01-13: State-Driven Locking Model (COMPLETE)
- Implemented `LockPolicyService` as the central policy module for all mutation permissions
- Added `GET /api/epics/{epic_id}/permissions` endpoint to expose field-level permissions to frontend
- Integrated lock policy checks into feature and user story routes (update/delete operations)
- Updated frontend API client with `epicAPI.getPermissions()` method
- Fixed cascade delete bug for append-only conversation tables in feature/story deletion
- **Policy Rules:**
  - Epic anchors (Problem + Outcome) become immutable after confirmation
  - Features/Stories can be created and edited during Feature Planning Mode (epic_locked stage)
  - Features become immutable when individually approved
  - User Stories become immutable when individually approved
  - Only ARCHIVED epics prevent all mutations
- Comprehensive backend tests: 22/22 passed (100%)

### 2026-01-13: Feature → User Story UX Improvements (COMPLETE)
- **Feature Planning Page (Epic.jsx):**
  - Added story count badges on approved feature cards showing status:
    - "No Stories" (amber) - feature needs stories created
    - "X/Y Stories" (blue) - stories in progress
    - "X Stories Done" (green) - all stories approved
  - Dynamic button text based on story status:
    - "Create User Stories" when no stories
    - "Continue Stories (X/Y)" when stories in progress
    - "View Stories" when all stories complete
  - Added overall progress indicator: "Story Progress: X/Y complete"
- **Story Planning Page (StoryPlanning.jsx):**
  - Enhanced feature reference sidebar with prominent feature context box
  - Added progress bar showing Drafts/Refining/Done counts
  - Added completion banner with 🎉 when all stories approved
  - "Return to Feature Planning" button for easy navigation
  - "Back to Feature Planning" button always visible in sidebar
- Frontend tests: 15/15 passed (100%)

### 2026-01-13: Visual Workflow Stepper (COMPLETE)
- Added workflow stepper component showing the full journey:
  - **Epic Definition** (Problem & Outcome) → **Features** (Break down epic) → **User Stories** (Sprint-sized tasks) → **Complete** (Ready for development)
- Stepper displays on all epic-related pages:
  - Epic Creation page: "Epic Definition" as current step
  - Feature Planning page: "Features" as current (or "User Stories" when all approved)
  - Story Planning page: "User Stories" as current
- Visual styling:
  - Completed steps: Green checkmarks with success color
  - Current step: Ring highlight with primary color
  - Upcoming steps: Muted/disabled appearance
  - Connection lines change color based on completion
- Dynamic content: Shows feature count on Features step, stories ready count on User Stories step
- Frontend tests: 9/9 passed (100%)

### 2026-01-13: Bug Tracking System (COMPLETE)
- **Full lifecycle management:** Draft → Confirmed → In Progress → Resolved → Closed
  - Server-enforced transitions (no skipping states)
  - Status history with timestamps preserved
- **Data Model:**
  - Bug entity with title, description, severity, status, and optional fields
  - BugLink polymorphic join table for linking to Epics/Features/Stories
  - BugStatusHistory for tracking status changes
  - BugConversationEvent for AI assistance (optional)
- **Standalone support:** Bugs can exist with zero links (standalone is valid)
- **Optional linking:** Bugs can link to multiple Epics, Features, or User Stories
- **API Endpoints:**
  - CRUD: POST/GET/PATCH/DELETE /api/bugs
  - Transitions: POST /api/bugs/{id}/transition
  - History: GET /api/bugs/{id}/history
  - Links: POST/DELETE/GET /api/bugs/{id}/links
  - Entity queries: GET /api/bugs/by-entity/{type}/{id}
  - AI assistance: POST /api/bugs/{id}/ai/refine-description, /ai/suggest-severity
- **Frontend (/bugs page):**
  - List view with badges (status, severity, priority, link count)
  - Filters: status, severity, linked/standalone
  - Create Bug dialog with all fields
  - Bug Detail dialog with tabs (Details, Links, History)
  - Status transition control
  - "Bugs" button in Dashboard header
- **Tests:** Backend 27/27 passed (100%), Frontend all flows working

### 2026-01-13: AI-Assisted Bug Creation (COMPLETE)
- **Conversational AI flow** for creating comprehensive bug reports
- **AI guides users through questions:**
  1. What is the problem?
  2. How do you reproduce it (steps)?
  3. What is the expected behavior?
  4. What is the actual behavior?
  5. What environment (browser, OS, device)?
- **Streaming SSE response** for real-time AI chat
- **AI generates proposal** with all bug fields when enough info gathered
- **User approval flow:** Review proposal → Click "Create Bug" → Bug created
- **API Endpoints:**
  - POST /api/bugs/ai/chat - Conversational AI endpoint (streaming)
  - POST /api/bugs/ai/create-from-proposal - Create bug from AI proposal
- **Frontend:**
  - "Report Bug with AI" button opens chat dialog
  - Auto-starts conversation with greeting
  - Shows streaming AI responses in real-time
  - Proposal preview card with "Create Bug" button
  - "Continue Refining" option if user wants more changes
- **Tests:** Backend 10/10 passed (100%), Frontend all flows working

### 2026-01-13: Standalone User Stories with AI Assistance (COMPLETE)
- **Standalone stories:** User stories not linked to any feature (feature_id = null)
- **Data Model Updates:**
  - `UserStory.feature_id` made nullable for standalone stories
  - `UserStory.user_id` added for ownership tracking
  - `UserStory.is_standalone` boolean flag
  - `UserStory.title` field for story identification
- **API Endpoints:**
  - GET /api/stories/standalone - List all standalone stories for user
  - POST /api/stories/standalone - Create standalone story manually
  - GET /api/stories/standalone/{story_id} - Get specific standalone story
  - PUT /api/stories/standalone/{story_id} - Update standalone story
  - DELETE /api/stories/standalone/{story_id} - Delete standalone story
  - POST /api/stories/standalone/{story_id}/approve - Approve and lock
  - POST /api/stories/standalone/{story_id}/chat - Refine with AI (streaming)
  - POST /api/stories/ai/chat - AI-assisted story creation conversation
  - POST /api/stories/ai/create-from-proposal - Create from AI proposal
- **AI-Assisted Creation:**
  - Conversational flow asks about persona, action, benefit, acceptance criteria
  - AI asks ONE question at a time for focused conversation
  - Streaming SSE response for real-time chat
  - AI generates proposal in JSON format when ready
  - User can accept proposal or continue refining
- **Frontend (/stories page):**
  - "Stories" button in Dashboard header
  - List view with badges (stage, story points, standalone)
  - Filters: stage (draft, refining, approved)
  - Search: title, story text, persona
  - Sort: created_at, updated_at
  - "Create with AI" button opens AI chat dialog
  - "Manual" button opens manual create dialog
  - Story cards with Refine/Approve actions
  - Story detail dialog with full information
  - Refine dialog with AI chat and story preview sidebar
- **Tests:** Backend 22/22 passed (100%), Frontend all flows working

### 2026-01-13: AI-Assisted User Personas for Completed Epics (COMPLETE)
- **User Personas from completed Epics:** AI analyzes Epic, Features, and User Stories to generate actionable personas
- **Persona Structure:**
  - Name & Role (e.g., "Sarah, Product Manager")
  - Demographics (age range, location, tech proficiency)
  - Goals & Motivations
  - Pain Points & Frustrations
  - Key Behaviors/Patterns
  - Jobs-to-Be-Done
  - Product Interaction Context
  - Representative Quote
  - AI-generated Portrait Image (OpenAI gpt-image-1)
- **Data Model:**
  - `Persona` table with all persona fields
  - `PersonaGenerationSettings` for user preferences (image provider, default count)
  - `source` field tracks "ai_generated" vs "human_modified"
  - Soft delete via `is_active` flag
- **API Endpoints:**
  - GET/PUT /api/personas/settings - Manage image provider (openai/gemini), model, default count (1-5)
  - POST /api/personas/epic/{epic_id}/generate - Generate personas (streaming SSE with progress)
  - GET /api/personas - List all personas with search & epic filter
  - GET /api/personas/epic/{epic_id} - List personas for specific epic
  - GET/PUT/DELETE /api/personas/{persona_id} - CRUD operations
  - POST /api/personas/{persona_id}/regenerate-portrait - Regenerate portrait image
- **Frontend (/personas page):**
  - "Personas" button (violet) in Dashboard header
  - Grid view with persona cards (portrait, name, role, quote, source badge)
  - Search and Epic filter
  - Persona detail dialog with all fields
  - Edit dialog for updating persona (marks as human_modified)
  - Delete functionality (soft delete)
  - Regenerate portrait hover button
- **Frontend (CompletedEpic page):**
  - "Generate Personas" button opens dialog
  - Count selector (1-5) with default 3 and warning for >3
  - Real-time progress updates during generation
  - Personas displayed in grid after generation
  - "View All" navigates to /personas page filtered by epic
- **Tests:** Backend 17/17 passed (100%), Frontend all flows working
- **Bug Fix:** Fixed streaming generator database session issue (greenlet_spawn error)
- **UX Improvement:** Added clear messaging when epic isn't completed yet, with disabled Generate button and "Continue Epic Workflow" CTA

### 2026-02-02: RICE & MoSCoW Scoring with AI Assistance (COMPLETE)
- **MoSCoW Scoring for Epics:** Must Have, Should Have, Could Have, Won't Have prioritization
- **MoSCoW + RICE Scoring for Features:** Combined prioritization framework
- **RICE Scoring for User Stories:** Reach × Impact × Confidence / Effort calculation
- **RICE Scoring for Bugs:** Prioritize bug fixes based on impact and effort
- **Database Schema Updates:**
  - `Epic.moscow_score` field
  - `Feature.moscow_score`, `rice_reach`, `rice_impact`, `rice_confidence`, `rice_effort`, `rice_total` fields
  - `UserStory.rice_reach`, `rice_impact`, `rice_confidence`, `rice_effort`, `rice_total` fields
  - `Bug.rice_reach`, `rice_impact`, `rice_confidence`, `rice_effort`, `rice_total` fields
- **Backend API Endpoints:**
  - GET /api/scoring/options - Scoring options for UI dropdowns
  - GET/PUT /api/scoring/epic/{id}/moscow - Epic MoSCoW CRUD
  - POST /api/scoring/epic/{id}/moscow/suggest - AI suggestion for Epic MoSCoW
  - GET /api/scoring/feature/{id} - Feature scores (MoSCoW + RICE)
  - PUT /api/scoring/feature/{id}/moscow - Feature MoSCoW update
  - PUT /api/scoring/feature/{id}/rice - Feature RICE update
  - POST /api/scoring/feature/{id}/suggest - AI suggestion for Feature scores
  - GET/PUT /api/scoring/story/{id}/rice - User Story RICE CRUD
  - POST /api/scoring/story/{id}/suggest - AI suggestion for Story RICE
  - GET/PUT /api/scoring/bug/{id}/rice - Bug RICE CRUD
  - POST /api/scoring/bug/{id}/suggest - AI suggestion for Bug RICE
- **Frontend Components:**
  - `ScoringComponents.jsx` with: MoSCoWBadge, RICEBadge, ScoringDisplay, MoSCoWEditor, RICEEditor
  - `FeatureScoringDialog` - Full MoSCoW + RICE editor with AI suggestion
  - `RICEScoringDialog` - RICE-only editor for Stories and Bugs
  - `EpicMoSCoWDialog` - MoSCoW-only editor for Epics
- **FeatureCard Updates:** TrendingUp prioritize button opens scoring dialog
- **Scoring Badges:** Display MoSCoW and RICE scores on cards
- **Tests:** 34/34 backend tests passed, 100% frontend coverage

### 2026-02-03: Stripe Subscription Implementation (COMPLETE)
- **Checkout Flow:** Users can subscribe for $45/month via Stripe Checkout
- **Payment Transaction Tracking:** All payments tracked in `payment_transactions` table
- **Status Polling:** Frontend polls for payment completion and activates subscription
- **Webhook Support:** Backend handles Stripe webhook events
- **API Endpoints:**
  - POST /api/subscription/create-checkout - Creates Stripe checkout session
  - GET /api/subscription/checkout-status/{session_id} - Polls payment status
  - GET /api/subscription/status - Returns user subscription status
- **Tests:** 30/30 backend tests passed, 100% frontend coverage

### 2026-02-03: User Persona Generation Bug Fix (COMPLETE)
- **Fixed:** Field name mismatch in `persona_service.py` (`desired_outcomes` → `desired_outcome`)
- **Status:** Service code corrected, ready for testing with completed epic

### 2026-02-03: Epic Hard Delete with Cascade (COMPLETE)
- **Full Cascade Delete:** Deleting an Epic removes ALL related entities
- **Cascades:** Epic → Features → User Stories (with conversations, versions)
- **Also Deletes:** Snapshots, Transcript Events, Decisions, Artifacts, Personas
- **Implementation:** Added `back_populates` and `cascade="all, delete-orphan"` to all relationships
- **Tests:** 10/10 backend tests passed

### 2026-02-03: Export to Jira/Azure DevOps (COMPLETE)
- **Direct API Integration:**
  - Jira Cloud: Creates Epics, Stories (Features), Sub-tasks (User Stories), Bugs
  - Azure DevOps: Creates Epics, Features, User Stories, Bugs with proper hierarchy
- **File Export Formats:**
  - Jira CSV (compatible with Jira CSV Import)
  - Azure DevOps CSV (compatible with Azure Boards Import)
  - JSON (universal format with field mappings)
  - Markdown (documentation/README format)
- **Field Mappings:**
  - Epic → Epic (both platforms)
  - Feature → Story (Jira) / Feature (Azure DevOps)
  - User Story → Sub-task (Jira) / User Story (Azure DevOps)
  - Bug → Bug (both platforms)
  - MoSCoW → Priority
  - RICE Score → Story Points
- **Backend API Endpoints:**
  - GET /api/export/field-mappings - Field mapping reference
  - GET /api/export/preview/{epic_id} - Export preview with item counts
  - POST /api/export/file - Download CSV/JSON/Markdown files
  - POST /api/export/jira - Direct push to Jira Cloud
  - POST /api/export/azure-devops - Direct push to Azure DevOps
- **Frontend Export Page:**
  - Epic selector with export preview
  - File export tab with 4 format buttons
  - Jira configuration tab with URL, email, API token, project key
  - Azure DevOps configuration tab with organization, project, PAT
  - Export results dialog showing created items and errors
- **Tests:** 21/21 backend tests passed, 100% frontend coverage

### 2026-02-03: Contextual Bug Linking (COMPLETE)
- **LinkedBugs Component:** Reusable component for viewing and managing linked bugs
- **Placement:** Added to Epic page, StoryPlanning (Feature) page, and Story detail dialog
- **Features:**
  - View bugs linked to the current entity (Epic/Feature/Story)
  - Create new bugs directly linked to the entity
  - Link existing bugs to the entity
  - Unlink bugs from the entity
  - Navigate to bug details from linked bug cards
- **Bug Cards:** Display severity and status badges with color coding
- **API Endpoints Used:**
  - GET /api/bugs/by-entity/{entity_type}/{entity_id}
  - POST /api/bugs (with links array)
  - POST /api/bugs/{bug_id}/links
  - DELETE /api/bugs/{bug_id}/links/{link_id}
- **Tests:** 16/16 backend tests passed, 100% frontend coverage

### 2026-02-03: Email/Password Authentication (COMPLETE)
- **Removed:** Emergent Google OAuth integration
- **Added:** Email/password authentication with bcrypt password hashing
- **User Model Updated:** Added `password_hash` and `email_verified` fields
- **Backend Endpoints:**
  - POST /api/auth/signup - Register new user (validates email format, min 8 char password, duplicate prevention)
  - POST /api/auth/login - Login with email/password (returns JWT session token)
  - POST /api/auth/logout - Logout and invalidate session
  - GET /api/auth/me - Get current authenticated user
- **Frontend Pages:**
  - `/signup` - Registration with password requirements display
  - `/login` - Login form with error handling
  - Landing page updated with "Sign in" and "Get Started" buttons
- **Security:**
  - Passwords hashed with bcrypt
  - Sessions stored as JWT tokens in httpOnly cookies
  - Session tokens stored in database for validation
- **Environment Updates:**
  - Removed EMERGENT_LLM_KEY from .env
  - Added JWT_SECRET placeholder
  - Updated CORS_ORIGINS for specific domains
  - Added OPENAI_API_KEY and STRIPE_API_KEY placeholders
- **Tests:** 14/14 backend tests passed, 100% frontend coverage

### 2026-02-03: Email Verification & Password Reset (COMPLETE)
- **Database Model:** Added `VerificationToken` table for email verification and password reset tokens
- **Backend Endpoints:**
  - POST /api/auth/forgot-password - Request password reset (doesn't reveal if email exists)
  - POST /api/auth/reset-password - Reset password with token (invalidates all sessions)
  - POST /api/auth/verify-email - Verify email with token
  - POST /api/auth/resend-verification - Resend verification email
  - GET /api/auth/check-token/{token} - Check token validity
- **Frontend Pages:**
  - `/forgot-password` - Request password reset form
  - `/reset-password?token=xxx` - Reset password form with token validation
  - `/verify-email?token=xxx` - Email verification page
- **Security:**
  - Password reset tokens expire after 1 hour
  - Email verification tokens expire after 24 hours
  - Password reset invalidates all existing sessions
  - API doesn't reveal whether email exists (prevents enumeration attacks)
- **Password Requirements:** Min 8 chars, uppercase, lowercase, number
- **Tests:** 21/21 backend tests passed, all frontend pages working

### 2026-02-03: SDK Refactoring - Remove emergentintegrations (COMPLETE)
- **Stripe Integration:** Refactored `/app/backend/routes/subscription.py` to use official `stripe` Python SDK
  - Create checkout sessions with `stripe.checkout.Session.create()`
  - Check session status with `stripe.checkout.Session.retrieve()`
  - Handle webhooks with `stripe.Webhook.construct_event()`
  - Graceful error handling when API key is placeholder
- **OpenAI Integration:** Refactored `/app/backend/services/persona_service.py` to use official `openai` SDK
  - Use `AsyncOpenAI` client for async operations
  - Generate images with `client.images.generate()` using gpt-image-1 model
  - Returns base64 encoded images directly

### 2026-02-03: Microsoft Graph Email Integration (COMPLETE)
- **Email Service:** Created `/app/backend/services/email_service.py` using Microsoft Graph API
  - Uses `msgraph-sdk` and `azure-identity` for authentication
  - ClientSecretCredential with async support
  - Sends emails via `/users/{email}/sendMail` endpoint
- **Sender:** support@asgardsolution.io
- **Email Templates:** Professional HTML templates with responsive design
  - Verification email with 24-hour expiry link
  - Password reset email with 1-hour expiry link
- **Credentials:** Stored in backend/.env
  - MICROSOFT_GRAPH_CLIENT_ID
  - MICROSOFT_GRAPH_CLIENT_SECRET
  - MICROSOFT_GRAPH_TENANT_ID
- **Tests:** 17/17 backend tests passed

### 2026-02-04: PRD Generator, Lean Canvas & AI Poker Planning (COMPLETE)
- **PRD Generator (`/prd`):** Auto-generates Product Requirements Documents from Epic data
  - Epic selector with completed/in-progress grouping
  - Template-based PRD with all epic fields (problem, outcome, features, scope, etc.)
  - Copy to clipboard and download as Markdown
  - Word count and document summary sidebar
- **Lean Canvas (`/lean-canvas`):** 9-box business model canvas tied to Epics
  - Standard Lean Canvas sections: Problem, Solution, UVP, Unfair Advantage, Customer Segments, Key Metrics, Channels, Cost Structure, Revenue Streams
  - Pre-populates from Epic data (problem_statement, vision, desired_outcome, etc.)
  - Local storage persistence per epic
  - Export as Markdown
- **AI Poker Planning (`/poker`):** AI-powered story point estimation
  - 5 AI personas with unique perspectives:
    - Sarah (Sr. Developer) - Technical complexity focus
    - Alex (Jr. Developer) - Learning curve focus
    - Maya (QA Engineer) - Test coverage focus
    - Jordan (DevOps) - Deployment & infrastructure focus
    - Riley (UX Designer) - User experience focus
  - Fibonacci scale (1, 2, 3, 5, 8, 13) with max 13
  - Each persona provides estimate + reasoning + confidence
  - Summary with average, suggested, min/max, and consensus level
  - Streaming SSE for real-time feedback as each persona "thinks"
- **Backend:**
  - New route: `/api/poker` with `/personas` (public) and `/estimate` (authenticated)
  - Integrated into server.py router
- **Frontend:**
  - Routes added to App.jsx: `/prd`, `/lean-canvas`, `/poker`
  - Sidebar already had correct links
- **Tests:** 21/21 tests passed (iteration_21.json)

### 2026-02-04: Real Stripe Subscription Billing (COMPLETE)
- **Migrated from one-time payments to real Stripe subscriptions**
  - Changed `mode="payment"` to `mode="subscription"` in Stripe Checkout
  - Auto-creates Stripe Product + recurring Price if not configured
  - Supports `STRIPE_PRICE_ID` env var for pre-configured price
- **Full subscription lifecycle management via webhooks:**
  - `customer.subscription.created` - New subscription activated
  - `customer.subscription.updated` - Status changes, renewals
  - `customer.subscription.deleted` - Cancellation
  - `invoice.paid` - Successful payment/renewal
  - `invoice.payment_failed` - Failed payment → past_due status
- **New endpoints:**
  - `POST /api/subscription/cancel` - Cancel at period end or immediately
  - `POST /api/subscription/reactivate` - Reactivate canceled subscription
  - Enhanced `GET /api/subscription/status` - Syncs with Stripe, returns `cancel_at_period_end`
- **Frontend updates (Settings.jsx):**
  - Cancel subscription button (appears when active)
  - Reactivate button (appears when scheduled for cancellation)
  - "Cancels at period end" badge
  - Different messaging for renewal vs. cancellation date
- **Benefits:**
  - Automatic renewals handled by Stripe
  - Proper handling of failed payments
  - Proration handled automatically
  - No manual period tracking needed

### 2026-02-04: Magic Moment - New Initiative Wizard (COMPLETE)
- **One-click PRD + Epic + Features + Stories + Sprint Plan generation**
- **New route:** `/new` - Single input box for messy ideas
- **Backend:** `/api/initiative/generate` (streaming) + `/api/initiative/save`
- **What it generates:**
  - Clean PRD (problem, target users, outcome, metrics, risks, out-of-scope)
  - Epic with vision statement
  - Features with priority (must-have/should-have/nice-to-have)
  - User stories with acceptance criteria and story points
  - 2-sprint delivery plan with goals and point totals
- **UX:**
  - Progress indicators while AI generates
  - Beautiful results display with summary stats
  - One-click "Save & Start Working" to create everything in DB
- **Sidebar:** New prominent "New Initiative" button with Sparkles icon

---

## Backlog

### P0 - Critical
- None! All P0 items completed (Initiative Library + Delivery Reality View).

### P1 - Upcoming
- Configure Stripe webhook in Stripe Dashboard (endpoint: /api/webhook/stripe)
- Test full subscription flow with real Stripe test keys
- Sprint Planning (Kanban board) implementation

### P2 - Future
- **Decision & Assumption Tracking:** Persist assumptions and risks from "Confidence & Risks" panel, build workflow to track validation status
- **Collaboration Loop:** Share read-only links to initiatives, basic commenting system
- **Jira/Linear Push Integration:** Deep integration to push plans directly into user's Jira or Linear project
- **points_per_dev_per_sprint field:** Add to ProductDeliveryContext model to allow user override of default 8
- Google OAuth authentication (nice-to-have)
- Team collaboration features

---

## Changelog (Continued)

### 2026-02-04: Export-Ready Story Formatting (COMPLETE)
- **Enhanced User Story Schema:** Stories now include all fields needed for Jira/Azure DevOps export
  - `title` - Short, actionable title (5-10 words)
  - `description` - Structured description from user story format
  - `acceptance_criteria` - Gherkin format (Given/When/Then)
  - `labels` - Array of tags: backend, frontend, api, auth, database, integration, mvp, ui, etc.
  - `priority` - Story-level priority: must-have, should-have, nice-to-have
  - `points` - Fibonacci story points (1, 2, 3, 5, 8, 13)
  - `dependencies` - Array of story IDs or descriptions
  - `risks` - Array of risk descriptions
- **Database Migration:** Added new columns to `user_stories` table:
  - `labels TEXT[] DEFAULT '{}'`
  - `story_priority VARCHAR(50)`
  - `dependencies TEXT[] DEFAULT '{}'`
  - `risks TEXT[] DEFAULT '{}'`
- **AI Prompt Updates:** DECOMP_SYSTEM prompt now generates:
  - Labels from predefined set
  - Story-level priority (inherits from feature unless overridden)
  - Dependencies between stories
  - Risk identification
- **Export Service Updates:**
  - Jira CSV export includes labels, priority, dependencies, risks columns
  - Azure DevOps CSV export includes all export-ready fields
  - Markdown export enhanced with priority tables, checkable AC, risk warnings
  - JSON export includes all story metadata
- **Frontend Updates:** NewInitiative.jsx story cards now display:
  - Story-level priority badge (color-coded)
  - Labels as small badges
  - Dependencies and risks in collapsible section
- **Tests:** Backend compiles, frontend builds successfully

### 2026-02-04: AI Generation Observability (COMPLETE)
- **Generation Analytics:** Private logging of all initiative generation attempts
  - Tracks prompt version, model/provider, token usage
  - Estimates cost based on provider pricing
  - Monitors parse/validation success rates per pass
  - Records timing for each pipeline pass
  - Logs critic findings (issues found, auto-fixed)
- **Database Tables:**
  - `initiative_generation_logs`: Full generation metrics (tokens, retries, duration, success)
  - `initiative_edit_logs`: Tracks what users edit after generation
  - `prompt_version_registry`: Tracks prompt versions and their performance
- **Analytics Service (`services/analytics_service.py`):**
  - `create_metrics()` - Initialize metrics tracker
  - `save_generation_log()` - Persist generation metrics
  - `log_edit()` - Track user edits with change classification
  - `get_generation_stats()` - Aggregated stats (success rate, tokens, cost)
  - `get_edit_patterns()` - Most edited fields, edit types
- **API Endpoints:**
  - `GET /api/initiative/analytics/stats` - Generation statistics (last N days)
  - `GET /api/initiative/analytics/edit-patterns` - User edit patterns
- **Token Pricing:** Estimates based on OpenAI, Anthropic, local models
- **Prompt Versioning:** Current version `v1.1`, tracked in `CURRENT_PROMPT_VERSION`

### 2026-02-04: Strict Output Layer & Quality Mode (COMPLETE)
**1. Strict Output Layer** - Schema validation + auto-repair for every AI call
- Created `services/strict_output_service.py` with:
  - `extract_json()` - Multi-strategy JSON extraction (code blocks, braces, auto-fix)
  - `validate_against_schema()` - Pydantic schema validation
  - `validate_and_repair()` - Auto-repair loop (up to 2 retries)
  - `build_repair_prompt()` - Context-aware repair instructions
- Pass-specific Pydantic schemas: `Pass1PRDOutput`, `Pass2DecompOutput`, `Pass3PlanningOutput`, `Pass4CriticOutput`
- All 4 passes now use `run_llm_pass_with_validation()` with strict output

**2. Quality Mode Toggle** - Optional 2-pass generation
- New field `quality_mode` in `ProductDeliveryContext` (standard | quality)
- Quality mode adds a second AI pass to critique and improve output
- UI toggle in Settings > Delivery Context with visual cards
- Best for smaller models that benefit from critique

**3. Guardrail Defaults per Task Type**
- Task-specific temperature settings in `TASK_TEMPERATURE`:
  - PRD: 0.8 (higher creativity)
  - Decomposition: 0.6 (balanced)
  - Planning: 0.3 (must follow constraints)
  - Critic: 0.2 (analytical)
  - AC/Export: 0.1-0.2 (strict format)
- Temperature passed to all LLM API calls (OpenAI, Anthropic, Local)

**4. Weak Model Detection** - Warns but doesn't block
- `ModelHealthMetrics` tracks: total_calls, validation_failures, repair_successes
- Warning triggered if failure rate > 30% after 3+ calls
- Warning message suggests switching to GPT-4o or Claude Sonnet
- Displayed in SSE stream before generation starts

**5. Delivery Context in Every Prompt**
- Already implemented in previous session
- `build_context_prompt()` injects: industry, methodology, team size, sprint length, velocity, platform
- All 4 passes receive personalized system prompts

### 2026-02-04: Persistent Model Health & Confidence Panel (COMPLETE)
**1. Persistent Model Health Metrics**
- New DB table `model_health_metrics` for tracking per user+provider+model
- Tracks: total_calls, validation_failures, repair_successes
- Warning state persists across server restarts
- Users can dismiss warnings (warning_dismissed flag)
- API: `track_call()`, `get_model_warning()`, `dismiss_warning()` - all async

**2. Quality Mode UX Enhancement**
- Added cost tradeoff info in Settings UI:
  - "Cost tradeoff: Quality mode uses ~2x tokens but produces more reliable output"
  - "Recommended for smaller models (GPT-3.5, Claude Haiku) or complex initiatives"
- Visual alert box with amber warning icon

**3. Confidence & Risks Panel (Premium PM Feature)**
- New `confidence_assessment` in critic pass output:
  - `confidence_score`: 0-100 percentage
  - `top_risks`: Array of top 3 risks
  - `key_assumptions`: Array of critical assumptions
  - `validate_first`: What to validate before heavy development
  - `success_factors`: Critical success factors
- New UI panel in NewInitiative.jsx after quality summary:
  - Confidence score with color coding (green >70%, amber 50-70%, red <50%)
  - Top Risks section with numbered list
  - Key Assumptions section
  - "Validate First" badges (high visibility)
  - Critical Success Factors
- PMs love this - helps prioritize discovery work

### 2026-02-04: Database Safety & Migration Infrastructure (COMPLETE)
**1. DB_RESET_ON_STARTUP Guard**
- New env var `DB_RESET_ON_STARTUP` (default: `false`)
- When `true`: DROPS ALL TABLES on startup (dev only - logs warning)
- When `false`: Safe mode - only creates missing tables via `create_all`
- Documented in `.env.example`

**2. Alembic Migration Flow**
- Installed Alembic 1.18.0
- Configured `alembic/env.py` for async PostgreSQL
- Created initial schema migration
- Usage:
  - `alembic revision --autogenerate -m "description"` - Generate migration
  - `alembic upgrade head` - Apply migrations
  - `alembic downgrade -1` - Rollback one migration

**3. Model Health Keying (user + provider + model)**
- Model health now keyed by `user_id + provider + model_name`
- Granular tracking per model (e.g., gpt-4o vs gpt-3.5-turbo)
- Warning message includes model name for clarity
- Updated index: `idx_model_health_user_provider_model`

**4. Strict Validation Logging**
- All 4 passes now use `run_llm_pass_with_validation()` with `pass_name`
- Consistent logging format:
  - `[Pass1-PRD] Starting with temp=0.8, schema=Pass1PRDOutput`
  - `[Pass1-PRD] ✓ Valid after 1 repair(s)` or `[Pass1-PRD] ✗ Failed validation`
- Repair attempts logged: `[Pass2-Decomp] Attempting repair...`
- Quality pass logged: `[Pass3-Planning] Running quality pass (2-pass mode)`

### 2026-02-05: Initiative Library (COMPLETE)
**Central hub to view, search, and manage all saved initiatives**
- **Backend Routes (`/app/backend/routes/initiatives.py`):**
  - `GET /api/initiatives` - List with pagination, SQL-based search and status filtering
  - `GET /api/initiatives/stats/summary` - Summary counts (total, draft, active, completed, archived)
  - `GET /api/initiatives/{epic_id}` - Full initiative details
  - `POST /api/initiatives/{epic_id}/duplicate` - Clone an initiative
  - `PATCH /api/initiatives/{epic_id}/archive` - Soft-delete (reversible, sets is_archived=true)
  - `PATCH /api/initiatives/{epic_id}/unarchive` - Restore from archive
  - `DELETE /api/initiatives/{epic_id}` - Permanent delete
- **Database Changes:**
  - Added `is_archived` (Boolean, default false) to Epic model
  - Added `archived_at` (DateTime) to Epic model
  - Added `idx_epics_archived` index
- **Status Mapping:**
  - `draft` = Early epic stages (problem_capture, problem_confirmed, outcome_capture, outcome_confirmed)
  - `active` = epic_drafted stage
  - `completed` = epic_locked stage
  - `archived` = is_archived=true (reversible soft-delete)
- **Frontend Page (`/app/frontend/src/pages/Initiatives.jsx`):**
  - Table view with columns: Name, Status, Updated, Stories/Points, Actions
  - 5 Summary cards: Total, Draft, Active, Completed, Archived counts
  - **SQL-based search**: Filters by title or problem statement in database (correct pagination)
  - **Archived filter**: Status dropdown includes Archived option, works correctly
  - Actions menu: View, Duplicate, Archive/Restore (conditional), Delete
  - Delete confirmation dialog with archive tip
  - Pagination for large lists
- **Navigation:**
  - Route `/initiatives` added to App.jsx
  - "Initiatives" link added to Sidebar under Planning section
- **Bug Fixes:**
  - DELETE endpoint sets `jarlpm.allow_cascade_delete` session variable (scoped to transaction)
  - Search is now SQL-based, not client-side (correct pagination/totals)
  - Archived filter actually filters for is_archived=true
- **Tests:** 22/22 backend tests passed

### 2026-02-05: Dashboard Command Center (COMPLETE)
**Answers "what do I do next?" in 10 seconds**
- **Backend Route (`/app/backend/routes/dashboard.py`):**
  - `GET /api/dashboard` - Single endpoint returning all dashboard data
  - Returns: at_risk_initiatives, focus_list, kpis, recent_activity, setup status
- **Components:**
  1. **Setup Alerts**: Warns if LLM or capacity not configured with Configure button
  2. **At Risk / Overloaded Inbox**: Shows initiatives over capacity, sorted by worst delta, with Fix button linking to Delivery Reality
  3. **Quick Start**: "What problem are you solving?" input → Generate button navigates to /new with pre-filled problem
  4. **Focus List**: Top 5 initiatives by must-have points, clickable to epic detail
  5. **Portfolio KPIs**: Active initiatives, Completed (30d), Points in flight, Capacity utilization % with progress bar
  6. **Recent Activity**: Last 10 events (created, locked, scope_plan_saved) with timestamps
- **Frontend Page (`/app/frontend/src/pages/Dashboard.jsx`):**
  - Responsive 3-column grid (2 left + 1 right on desktop)
  - Clean, minimal design without vanity charts
  - Personalized greeting using user's name
- **Tests:** API returns all expected fields
**Senior-PM assistant showing feasibility, capacity, and scope recommendations**
- **Backend Routes (`/app/backend/routes/delivery_reality.py`):**
  - `GET /api/delivery-reality/summary` - Global summary with delivery context, status breakdown, total points
  - `GET /api/delivery-reality/initiatives` - List all initiatives with delivery assessment
  - `GET /api/delivery-reality/initiative/{epic_id}` - Per-initiative detail with recommended deferrals
  - `POST /api/delivery-reality/initiative/{epic_id}/scope-plan` - Save scope plan (reversible)
  - `GET /api/delivery-reality/initiative/{epic_id}/scope-plan` - Get active scope plan
  - `DELETE /api/delivery-reality/initiative/{epic_id}/scope-plan` - Clear scope plan (return to base)
- **Database Changes:**
  - Added `points_per_dev_per_sprint` (Integer, default 8) to ProductDeliveryContext
  - Added `scope_plans` table for reversible deferral planning
- **Capacity Model:**
  - `points_per_dev_per_sprint` = user-configurable (default 8)
  - `sprint_capacity` = num_developers * points_per_dev_per_sprint
  - `two_sprint_capacity` = sprint_capacity * 2
  - `delta` = two_sprint_capacity - total_points
- **Assessment Logic:**
  - `on_track`: delta >= 0
  - `at_risk`: delta < 0 but |delta| <= 25% of sprint_capacity
  - `overloaded`: delta < -25% of sprint_capacity
- **Scope Plan Feature:**
  - Stores deferred story IDs without mutating stories (reversible)
  - Saves total/deferred/remaining points at time of save
  - Supports notes from PM
  - Active plan per epic (old plans deactivated)
- **Frontend Page (`/app/frontend/src/pages/DeliveryReality.jsx`):**
  - Delivery Context card with all metrics including custom velocity
  - Status summary cards: Active Initiatives, On Track, At Risk, Overloaded
  - Initiative table with clickable rows
  - Detail dialog:
    - Capacity meter (progress bar)
    - Points breakdown by priority (Must/Should/Nice to Have)
    - "Recommended Scope Cuts" or "Saved Scope Plan" (labeled correctly)
    - Deferral checkboxes with notes field
    - Save Plan / Update Plan / Reset to Base buttons
- **Settings UI (`/app/frontend/src/pages/Settings.jsx`):**
  - Added "Velocity (Points per Dev per Sprint)" field with helper text
- **Navigation:**
  - Route `/delivery-reality` and `/delivery-reality/:epicId` added
  - "Delivery Reality" link in Sidebar under Delivery section
- **Tests:** All API endpoints verified working


### 2026-02-05: Best-in-Class Prompt Engineering - Bug Fixes (COMPLETE)
**Fixed critical issues in the prompt engineering implementation:**
1. **CRITIC_SYSTEM Syntax Error Fixed:** Removed extraneous JSON content (lines 649-664) that leaked outside the string literal, causing IndentationError and preventing backend startup.
2. **analytics_service.py Date Calculation Fixed:** Changed `from_date.replace(day=from_date.day - days)` to proper `from_date - timedelta(days=days)` to avoid negative day values.
3. **initiative.py Save Endpoint Fixed:** 
   - Changed `status="in_progress"` to `current_stage=EpicStage.EPIC_LOCKED.value`
   - Removed non-existent `description` field from Epic creation (description is stored in EpicSnapshot)
4. **Lint Fixes:** Removed unnecessary f-strings without placeholders
5. **vite.config.js:** Added `pm-assistant-3.preview.emergentagent.com` to allowedHosts

**Prompt Improvements Verified:**
- All 4 pass prompts (PRD, Decomposition, Planning, Critic) have proper structure
- Character limits (400 chars for problem_statement, 100 for tagline)
- Exact item counts (3-5 key_metrics)
- NFR story requirements in decomposition
- Gherkin format enforcement for acceptance criteria
- confidence_assessment with confidence_score, top_risks, key_assumptions, validate_first
- All system prompts forbid markdown code fences

**Tests:** 25/25 backend tests passed, frontend /new page verified working


### 2026-02-05: Dashboard & Save Fixes (COMPLETE)
**User-reported issues fixed:**
1. **Save endpoint was broken** - EpicSnapshot model mismatch (`snapshot_id`, `version`, `vision` fields didn't exist). Fixed to use correct fields.
2. **Feature model mismatch** - Changed `name` → `title`, `status` → `current_stage`, removed `order_index`.
3. **UserStory save** - Added `source="ai_generated"` field.
4. **Missing "Create Epic" button** - Added back to Dashboard header alongside "AI Initiative".

**Dashboard improvements (per user feedback):**
1. **Focus list sorting** - Fixed to sort by must_have_points DESC, then updated_at DESC (most urgent + recent first).
2. **Activity includes archived epics** - Now queries all epics (including archived) for activity events, shows `archived` and `restored` events.

**Both workflows now available:**
- **Create Epic** (outline button) → Traditional 6-stage conversational workflow
- **AI Initiative** (primary button) → AI-powered complete plan generator

**Tests:** Save endpoint verified working via curl, Create Epic flow verified via screenshot


### 2026-02-05: UI Header Cleanup & Logout Fix (COMPLETE)
**Issues fixed:**
1. **Double header removed** - Pages like Epic, Bugs, Stories, Personas, Settings, Export, StoryPlanning, and CompletedEpic had their own `<header>` elements conflicting with AppLayout's header. Removed page-level headers, keeping only the AppLayout header with user menu.
2. **Logout broken** - AppLayout was calling `clearUser()` which didn't exist in auth store. Fixed to use `logout()` (the correct store action).

**Pages updated:**
- Epic.jsx (both modes)
- Bugs.jsx
- Stories.jsx
- Personas.jsx
- Settings.jsx
- Export.jsx
- StoryPlanning.jsx
- CompletedEpic.jsx

**Layout pattern now:**
- AppLayout provides: Sidebar + Top header (theme toggle, user menu with Settings/Logout)
- Pages provide: Page title bar with back button + page-specific actions

**Tests:** Screenshot verified single header, logout flow tested and working


### 2026-02-05: Persist Poker Planning AI Reasoning (COMPLETE)
**Feature:** Save detailed AI persona reasoning during poker planning sessions for later review

**Database Changes:**
- Added `poker_estimate_sessions` table:
  - session_id, story_id, user_id
  - min/max/average/suggested estimates (statistics)
  - accepted_estimate, accepted_at (when user accepts)
  - created_at
- Added `poker_persona_estimates` table:
  - estimate_id, session_id (FK)
  - persona_name, persona_role
  - estimate_points, reasoning, confidence
  - created_at
- Migration: `20260205_1830_add_poker_session_tables.py`

**Backend Updates (`/app/backend/routes/poker.py`):**
- Modified `/estimate` endpoint to save session and persona estimates to database
- Summary now includes `session_id` for frontend reference
- Added `session_id` parameter to `POST /api/poker/save-estimate` to link acceptance
- New `GET /api/poker/sessions/{story_id}` - Get all poker sessions for a story
- New `GET /api/poker/session/{session_id}` - Get specific session with full reasoning

**Frontend Updates:**
- `PokerPlanning.jsx`: Passes `session_id` to save-estimate call when accepting
- `api/index.js`: Updated `saveEstimate()` to accept optional `sessionId`
- Added `getSessions()` and `getSession()` API methods

**Data Flow:**
1. User runs AI estimation → Session + persona estimates saved to DB
2. User accepts estimate → Story points saved + session marked as accepted
3. Later: User can retrieve full reasoning via `/sessions/{story_id}` endpoint

**Tests:** API endpoints verified via curl, backend running without errors

### 2026-02-05: Poker Session History UI Component (COMPLETE)
**Feature:** View past AI estimation sessions with full persona reasoning

**New Component (`/app/frontend/src/components/PokerSessionHistory.jsx`):**
- Dialog-based history viewer triggered by "View History" button
- Collapsible session cards showing:
  - Date/time of estimation
  - Acceptance status badge (if estimate was accepted)
  - Summary stats (suggested, average, min, max)
- Expandable persona reasoning section:
  - Each persona's estimate with avatar
  - Full reasoning text
  - Confidence level indicator
- "Latest" badge on most recent session

**Integration Points:**
- **PokerPlanning.jsx:** Button appears next to story badge when story is selected
- **Stories.jsx (StoryDetailDialog):** Button appears next to story points in header

**User Flow:**
1. User opens story detail or selects story in Poker Planning
2. Clicks "View History" button (History icon)
3. Dialog shows all past estimation sessions
4. Click session to expand and see full persona reasoning
5. Useful for retrospectives, audits, and understanding estimate rationale

**Tests:** Frontend compiles successfully, UI visually verified

### 2026-02-05: Lean Canvas Database Persistence (BUG FIX)
**Issue:** Lean Canvas was saving to localStorage only, not to database. Canvas data was lost when selecting an Epic that already had a canvas created.

**Database Changes:**
- Added `lean_canvases` table:
  - canvas_id, epic_id (unique constraint), user_id
  - 9 canvas sections: problem, solution, unique_value, unfair_advantage, customer_segments, key_metrics, channels, cost_structure, revenue_streams
  - source: manual | ai_generated
  - created_at, updated_at
- Migration: `20260205_1850_add_lean_canvas_table.py`

**Backend Updates (`/app/backend/routes/lean_canvas.py`):**
- Added `GET /api/lean-canvas/{epic_id}` - Get saved canvas for an epic
- Added `POST /api/lean-canvas/save` - Save or update canvas (upsert behavior)
- Response includes `exists: true/false` to indicate if canvas is persisted

**Frontend Updates (`/app/frontend/src/pages/LeanCanvas.jsx`):**
- Replaced localStorage with API calls
- Added `loadingCanvas` state with spinner while fetching
- Shows "Saved" badge when canvas exists in database
- Button changes from "Save" to "Update" when editing existing canvas
- AI-generated canvases marked with `source: ai_generated` when saved

**API Updates (`/app/frontend/src/api/index.js`):**
- Added `leanCanvasAPI.get(epicId)` 
- Added `leanCanvasAPI.save(epicId, canvas, source)`

**Tests:** API verified via curl, UI screenshot confirmed data loads correctly


### 2026-02-05: List-First UX for Lean Canvas & PRD Pages (FEATURE)
**User Request:** Both pages should show a list of existing items first, with a "Create New" option that only shows epics without an existing item.

**Lean Canvas Changes:**
- **List View:** Shows all existing canvases as cards with epic title, source (AI/Manual), and last updated date
- **Editor View:** Opens when clicking a canvas card, with Back button to return to list
- **Create New Dialog:** Shows only epics that don't have a canvas yet
- **New Endpoints:**
  - `GET /api/lean-canvas/list` - List all user's canvases
  - `GET /api/lean-canvas/epics-without-canvas` - Get epics eligible for new canvas

**PRD Changes:**
- **Database Model:** Added `PRDDocument` model to persist PRDs (using `sections` column for content)
- **List View:** Shows all PRDs with epic title, status badge, version, and last updated
- **Editor View:** Markdown editor with Edit/Preview tabs, regenerate from epic data option
- **Create New Dialog:** Shows only epics that don't have a PRD yet
- **New Endpoints:**
  - `GET /api/prd/list` - List all user's PRDs
  - `GET /api/prd/epics-without-prd` - Get epics eligible for new PRD
  - `GET /api/prd/{epic_id}` - Get saved PRD
  - `POST /api/prd/save` - Save or update PRD
  - `DELETE /api/prd/{epic_id}` - Delete PRD

**UI Features (both pages):**
- Click card to view/edit
- "Back" button returns to list
- "Saved" badge shows persistence status
- "Update" vs "Save" button based on existing state
- Loading spinners during data fetch

**Tests:** All APIs verified via curl, UI screenshots confirm list and editor views working


### 2026-02-06: Scoring Page List-First UX (COMPLETE)
**Feature:** Complete refactor of Scoring page with list-first UX pattern showing all scored items

**Backend Changes:**
- **New endpoints in `/app/backend/routes/scoring.py`:**
  - `GET /api/scoring/scored-items` - Returns all scored items (Epics, Standalone Stories, Standalone Bugs) with score details
  - `GET /api/scoring/items-for-scoring` - Returns items available for scoring (locked epics, standalone stories/bugs)
  - `GET /api/scoring/epic/{epic_id}/scores` - Returns detailed epic scores with all features, stories, and bugs
  - `POST /api/scoring/standalone-story/{story_id}/score` - Score standalone story with RICE
  - `POST /api/scoring/standalone-bug/{bug_id}/score` - Score standalone bug with RICE

**Frontend Changes:**
- **Scoring page rewrite (`/app/frontend/src/pages/Scoring.jsx`):**
  - List view with stats cards: Scored Epics, Scored Stories, Scored Bugs, Total Scored
  - Tabs: Epics | Standalone Stories | Standalone Bugs
  - Epic cards show children_scored/children_total count
  - "Initiate Scoring" dialog with:
    - Item type selection (Epic/Standalone Story/Standalone Bug)
    - Item dropdown filtered by type
    - Info card explaining scoring types (Epic=MoSCoW, Features=MoSCoW+RICE, Stories=RICE, Bugs=RICE)
  - Detail view when clicking epic:
    - Epic Priority section with MoSCoW badge
    - Features section with MoSCoW + RICE badges
    - User Stories section with RICE badges
    - Bugs section with RICE badges
    - "AI Score All" button to generate scores
    - "Apply Scores" button to save AI suggestions

- **Epic Review page updates (`/app/frontend/src/pages/CompletedEpic.jsx`):**
  - Added "Scoring" button in Epic Details card
  - Deep-link to `/scoring?epic={epic_id}` pre-opens detail view
  - MoSCoW badges on features (Must Have, Should Have, etc.)
  - RICE badges on features showing score (RICE: 4.0)
  - RICE badges on user stories

**Scoring Rules:**
- Epics → MoSCoW only
- Features → MoSCoW + RICE
- User Stories → RICE only
- Bugs → RICE only
- RICE calculation: (Reach × Impact × Confidence) / Effort

**Tests:** 23/23 backend tests passed, 100% frontend coverage


### 2026-02-06: Bug Fix - RICE Values Normalization & Display (COMPLETE)
**Issues Fixed:**
1. **AI-generated RICE values validation error**: AI was generating continuous values (e.g., confidence=0.9) but validation expected discrete values ([0.5, 0.8, 1.0]). Added `normalize_rice_values()` helper that snaps AI values to nearest allowed discrete values.
2. **User Stories missing RICE badges**: `UserStoryResponse` model didn't include RICE fields. Added `rice_reach`, `rice_impact`, `rice_confidence`, `rice_effort`, `rice_total` to the response model and `story_to_response()` function.

**UI Updates:**
- Epic header now shows MoSCoW badge next to "Epic Locked" badge (when epic has moscow_score)
- User Stories now display RICE badges (e.g., "RICE: 24.0")
- Features continue to show MoSCoW + RICE badges

**Files Modified:**
- `/app/backend/routes/scoring.py` - Added `normalize_rice_values()` function
- `/app/backend/routes/user_story.py` - Added RICE fields to UserStoryResponse
- `/app/frontend/src/pages/CompletedEpic.jsx` - Added MoSCoW badge to epic header


### 2026-02-06: Delivery Reality Enhancement (COMPLETE)
**Feature:** Transform Delivery Reality from calculator to PM tool

**Core UX Features (No LLM):**
1. **"Why these cuts" summary** - Auto-generates human-readable cut explanation
2. **MVP Feasibility Alert** - Red warning if must-haves exceed capacity  
3. **Scope Decision Summary** - Exportable artifact (Sprint 1/2 scope, Deferred, Notes)

**AI Features (Uses User's LLM):**
1. **Scope Cut Rationale** - 3 bullets: rationale, user impact, validate first
2. **Alternative Cut Sets** - 3 strategies: Cut Polish, Cut Integrations, Cut Low Adoption
3. **Risk Review** - Top 3 risks, assumptions, suggested spike story

**Files Created/Modified:**
- `/app/backend/routes/delivery_reality.py` - 4 new endpoints + helper functions
- `/app/frontend/src/pages/DeliveryReality.jsx` - Complete rewrite with AI tabs


### 2026-02-06: Sprints Page Enhancement (COMPLETE)
**Feature:** Transform Sprints from overview to daily driver PM tool

**Database Changes:**
- Added `sprint_number`, `status`, `blocked_reason` columns to user_stories table
- New migration: `20260206_0345_add_sprint_fields_to_stories.py`

**Core UX Features:**
1. **Sprint Scope Selection** - Stories can be committed to Sprint N
2. **Capacity Fit Display** - Shows committed vs capacity with overflow warning
3. **Blocked Lane** - Stories can be marked blocked with reason
4. **Kanban Board** - 4 columns: Ready, In Progress, Blocked, Done

**AI Features (Uses User's LLM):**
1. **Sprint Kickoff Plan** - Sprint goal, top 5 stories, sequencing, 3 risks
2. **Daily Standup Summary** - What changed, blocked, next actions
3. **WIP Optimization** - Finish first vs pause recommendations

**Files Created:**
- `/app/backend/routes/sprints.py` - Complete sprint management API
- `/app/frontend/src/pages/Sprints.jsx` - Complete rewrite with AI insights

**Key Integration:**
- Delivery Reality → Sprints connection via `GET /sprints/from-delivery-reality/{epic_id}`


### 2026-02-06: AI Endpoint Robustness Refactor (COMPLETE)
**Issue:** New AI-powered endpoints in `delivery_reality.py` and `sprints.py` were fragile and didn't follow established architectural patterns.

**Refactoring Applied:**
1. **StrictOutputService Integration** - All 6 AI endpoints now use `validate_and_repair()` for robust JSON parsing with auto-repair (max 2 attempts)
2. **Subscription Gating** - Added `EpicService.check_subscription_active()` check to all AI endpoints (returns 402 if no active subscription)
3. **LLM Config Check** - Returns 400 with clear error message if no LLM provider configured
4. **ID Hallucination Prevention** - Alternative-cuts and sprint AI endpoints validate story IDs against actual IDs
5. **Model Health Tracking** - Added `strict_service.track_call()` to track success/failure rates for weak model detection

**AI Endpoints Refactored:**
- `POST /api/delivery-reality/initiative/{id}/ai/cut-rationale`
- `POST /api/delivery-reality/initiative/{id}/ai/alternative-cuts`
- `POST /api/delivery-reality/initiative/{id}/ai/risk-review`
- `POST /api/sprints/ai/kickoff-plan`
- `POST /api/sprints/ai/standup-summary`
- `POST /api/sprints/ai/wip-suggestions`

**Files Modified:**
- `/app/backend/routes/delivery_reality.py` - Lines 893-1220
- `/app/backend/routes/sprints.py` - Lines 369-715

**Testing:** 24/24 backend tests passed (subscription gating, LLM config check, error handling, StrictOutputService validation)


### 2026-02-06: Sprint Insights Persistence (COMPLETE)
**Feature:** AI-generated sprint insights (kickoff plan, standup summary, WIP suggestions) are now persisted to the database and automatically loaded when users return to the Sprints page.

**Implementation:**
1. **Database Model:** Added `SprintInsight` model with fields for `user_id`, `sprint_number`, `insight_type`, `content` (JSON), and `generated_at`
2. **API Endpoints:**
   - `GET /api/sprints/insights/current` - Get saved insights for current sprint
   - `GET /api/sprints/insights/{sprint_number}` - Get saved insights for specific sprint
3. **Auto-save on Generation:** All 3 AI endpoints (`kickoff-plan`, `standup-summary`, `wip-suggestions`) now save results to DB after generation
4. **Frontend Integration:** Sprints page loads saved insights on mount and displays them automatically

**Files Modified:**
- `/app/backend/db/models.py` - Added `SprintInsight` model
- `/app/backend/alembic/versions/20260206_0530_add_sprint_insights_table.py` - Migration
- `/app/backend/routes/sprints.py` - Added GET endpoints and save logic
- `/app/frontend/src/api/index.js` - Added `getSavedInsights()` function
- `/app/frontend/src/pages/Sprints.jsx` - Load and display saved insights


### 2026-02-06: Senior PM-Quality PRD Schema (COMPLETE)
**Issue:** PRD schema was too shallow with hard character limits, producing "thin" output that wasn't useful for teams without a PM.

**Enhanced PRD Schema:**
- `target_users`: Now array of detailed personas with `persona`, `context`, `pain_points`, `current_workaround`, `jtbd`
- `mvp_scope`: Array with items and rationale for inclusion
- `not_now`: Deferred items with rationale explaining WHY deferred
- `assumptions`: Structured with `assumption`, `risk_if_wrong`, `validation_approach`
- `constraints`: With `constraint`, `rationale`, `impact` (high/medium/low)
- `positioning`: Full positioning statement framework (for/who/unlike/benefit)
- `riskiest_unknown`: Single biggest uncertainty
- `validation_plan`: Concrete de-risking steps
- `problem_evidence`: Data/quotes supporting the problem
- `alternatives`: Competitor/workaround list
- `gtm_notes`: Go-to-market considerations

**Prompt Changes:**
- Removed character limits (400 char max)
- Added quality requirements (specificity, depth)
- Focus on "Senior PM-quality" output for teams without a PM

**Files Modified:**
- `/app/backend/routes/initiative.py` - New PRDSchema with nested models, updated PRD_SYSTEM prompt
- `/app/frontend/src/pages/NewInitiative.jsx` - Enhanced PRD display with all new fields


### 2026-02-06: Security Fix - Story Ownership Checks (COMPLETE)
**Issue:** `update_story_sprint`, `update_story_status`, and `commit_story_to_sprint` endpoints allowed any authenticated user to modify another user's stories if they guessed the ID.

**Fix Applied:**
- Added ownership verification for all 3 endpoints
- For standalone stories: checks `UserStory.user_id == current_user_id`
- For feature-based stories: verifies ownership via `feature→epic→user_id`
- Returns 403 "Not authorized to modify this story" for unauthorized access

**Files Modified:**
- `/app/backend/routes/sprints.py` - Added ownership checks to lines 252-420

### 2026-02-06: Fix - Capacity Default Mismatch (COMPLETE)
**Issue:** `sprints.py` used `or 10` for default velocity while rest of app uses 8.

**Fix Applied:**
- Changed all occurrences of `or 10` to `or 8` in sprints.py
- Now consistent with `DEFAULT_POINTS_PER_DEV_PER_SPRINT = 8` in delivery_reality.py

**Files Modified:**
- `/app/backend/routes/sprints.py` - Lines 106, 498, 995



### 2026-02-06: Critical Fix - DB Pool Exhaustion Prevention (COMPLETE)
**Issue:** All streaming LLM endpoints (initiative generation, sprint AI insights, delivery reality AI, epic/feature/story/bug chat) were holding database sessions open during the entire streaming process. Under concurrent load, this could exhaust the DB connection pool.

**Pattern Applied:**
1. **Prepare config before streaming:** Call `llm_service.prepare_for_streaming(llm_config)` to extract all LLM config data BEFORE entering the async generator
2. **Use sessionless streaming:** Create `LLMService()` without a session and call `stream_with_config(config_data, ...)` instead of `generate_stream(user_id, ...)`
3. **Fresh sessions for DB writes:** Use `async with AsyncSessionLocal() as new_session:` for any database operations inside the generator (e.g., saving conversation events, tracking metrics)

**New Functions/Methods:**
- `LLMService.prepare_for_streaming(llm_config)` - Extracts config data as dict
- `LLMService.stream_with_config(config_data, ...)` - Streams without needing session
- `run_llm_pass_with_validation_sessionless()` - Sessionless version for initiative generation

**Files Modified:**
- `/app/backend/routes/initiative.py` - 4-pass generation now sessionless
- `/app/backend/routes/sprints.py` - kickoff, standup, WIP endpoints
- `/app/backend/routes/delivery_reality.py` - cut rationale, alternatives, risk review
- `/app/backend/routes/scoring.py` - epic/feature/story/bug suggestions
- `/app/backend/routes/feature.py` - feature generation and chat
- `/app/backend/routes/user_story.py` - story generation and chat
- `/app/backend/routes/epic.py` - epic chat
- `/app/backend/routes/bug.py` - bug refine and chat

**Tests:** 23/23 backend tests passed (iteration_27.json)

