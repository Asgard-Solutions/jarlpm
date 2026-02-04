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
- None! All critical items completed.

### P1 - Upcoming
- Configure Stripe webhook in Stripe Dashboard (endpoint: /api/webhook/stripe)
- Test full subscription flow with real Stripe test keys
- Sprint Planning (Kanban board) implementation

### P2 - Future
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
  - `GET /api/initiatives` - List with pagination, filtering by status, search
  - `GET /api/initiatives/stats/summary` - Summary counts (total, draft, active, completed)
  - `GET /api/initiatives/{epic_id}` - Full initiative details
  - `POST /api/initiatives/{epic_id}/duplicate` - Clone an initiative
  - `PATCH /api/initiatives/{epic_id}/archive` - Soft-delete (reversible)
  - `PATCH /api/initiatives/{epic_id}/unarchive` - Restore from archive
  - `DELETE /api/initiatives/{epic_id}` - Permanent delete
- **Status Mapping:**
  - `draft` = Early epic stages (problem_capture, problem_confirmed, outcome_capture, outcome_confirmed)
  - `active` = epic_drafted stage
  - `completed` = epic_locked stage
  - `archived` = Tracked separately (reversible soft-delete)
- **Frontend Page (`/app/frontend/src/pages/Initiatives.jsx`):**
  - Table view with columns: Name, Status, Updated, Stories/Points, Actions
  - Summary cards: Total, Draft, Active, Completed counts
  - Search input: Filters by title, tagline, or problem statement
  - Status filter dropdown
  - Actions menu: View, Duplicate, Archive, Delete
  - Delete confirmation dialog with archive tip
  - Pagination for large lists
- **Navigation:**
  - Route `/initiatives` added to App.jsx
  - "Initiatives" link added to Sidebar under Planning section
- **Bug Fix:** DELETE endpoint now sets `jarlpm.allow_cascade_delete` session variable to bypass append-only constraints on transcript tables
- **Tests:** 22/22 backend tests passed (after bug fix)
