# JarlPM User Manual

**Version 2.0 | Last Updated: February 2026**

> "Lead like a Jarl — calm authority, decisions that stick."

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Dashboard Overview](#3-dashboard-overview)
4. [New Initiative Wizard](#4-new-initiative-wizard)
5. [Epic Lifecycle](#5-epic-lifecycle)
6. [Feature Planning](#6-feature-planning)
7. [User Story Planning](#7-user-story-planning)
8. [Bug Tracking](#8-bug-tracking)
9. [Scoring & Prioritization](#9-scoring--prioritization)
10. [AI Poker Planning](#10-ai-poker-planning)
11. [Sprint Management](#11-sprint-management)
12. [Delivery Reality](#12-delivery-reality)
13. [User Personas](#13-user-personas)
14. [PRD Generator](#14-prd-generator)
15. [Lean Canvas](#15-lean-canvas)
16. [Export & Integration](#16-export--integration)
17. [Settings & Configuration](#17-settings--configuration)
18. [Subscription & Billing](#18-subscription--billing)

---

## 1. Introduction

### What is JarlPM?

JarlPM is an **AI-agnostic, conversation-driven Product Management system** designed for Product Managers who want to create clear, implementation-ready Epics, Features, User Stories, and Bug Reports.

### Key Principles

1. **LLM Agnosticism**: You bring your own API keys (OpenAI, Anthropic, or Local). JarlPM never bundles model access.
2. **Immutable Decisions**: Once you confirm a decision (problem statement, outcome, etc.), it's locked forever. This prevents scope creep.
3. **Monotonic Progress**: You can only move forward through stages—no backtracking allowed.
4. **Separation of Concerns**: Scoring (MoSCoW, RICE, Story Points) is separate from creation. Items are created without scores; scoring happens via dedicated Scoring or Poker features.

### Workflow Overview

```
Idea → PRD → Epic → Features → User Stories → Scoring → Sprints → Export
```

---

## 2. Getting Started

### Creating an Account

1. Navigate to the JarlPM landing page
2. Click **"Get Started"** or **"Sign in"**
3. Enter your email and create a password (minimum 8 characters, including uppercase, lowercase, and a number)
4. Check your email for a verification link
5. Click the link to verify your account

### Logging In

1. Go to `/login`
2. Enter your email and password
3. Click **"Sign In"**

### Forgot Password?

1. Click **"Forgot password?"** on the login page
2. Enter your email address
3. Check your email for a reset link (valid for 1 hour)
4. Set your new password

### First-Time Setup

Before using AI features, you must:

1. **Subscribe** ($45/month) - Go to Settings → Subscription
2. **Configure an LLM Provider** - Go to Settings → LLM Providers

---

## 3. Dashboard Overview

The Dashboard is your home base showing:

### Header Navigation
- **JarlPM Logo** - Click to return to Dashboard
- **New Initiative** - Start a new initiative with AI
- **Initiatives** - View all saved initiatives
- **Bugs** - Manage bug reports
- **Stories** - Manage standalone user stories
- **Personas** - View AI-generated user personas
- **Settings** - Manage your account and preferences

### Main Content
- **Active Epics** - Epics currently in progress
- **Completed Epics** - Locked epics ready for implementation
- **Quick Stats** - Total epics, features, stories, bugs

### Sidebar Navigation
- **Dashboard** - Home
- **New Initiative** - AI-powered initiative creation
- **Initiatives** - All initiatives
- **Scoring** - MoSCoW and RICE prioritization
- **Poker Planning** - AI story point estimation
- **Sprints** - Sprint management
- **Delivery Reality** - Scope planning
- **PRD Generator** - Generate PRD documents
- **Lean Canvas** - Business model canvas
- **Export** - Export to Jira/Azure DevOps

---

## 4. New Initiative Wizard

The **New Initiative** feature is your "magic moment"—turn a messy idea into a complete product plan in minutes.

### How to Use

1. Click **"New Initiative"** in the sidebar
2. Enter your idea in the text box (can be rough, messy, or detailed)
3. Optionally enter a product name
4. Select **Quality Mode**:
   - **Standard** - Faster generation
   - **Quality** - 2-pass generation with critique (slower but higher quality)
5. Click **"Generate Initiative"**

### What Gets Generated

The AI creates a **3-pass output**:

1. **Pass 1 - PRD**
   - Product name and tagline
   - Problem statement
   - Target users
   - Desired outcome
   - Key metrics
   - Risks and assumptions
   - Out of scope items

2. **Pass 2 - Decomposition**
   - Features with descriptions and acceptance criteria
   - User stories in "As a... I want... So that..." format
   - Acceptance criteria in Given/When/Then format
   - Labels and priorities

3. **Pass 3 - PM Reality Check**
   - Quality review of generated content
   - Auto-fixes for common issues
   - Missing NFR (Non-Functional Requirements) detection
   - Confidence assessment

### After Generation

- Review the generated content
- Click **"Save & Start Working"** to create everything in the database
- Navigate to the new epic from the Initiatives page

> **Note**: Story points are NOT assigned during generation. Use Scoring or Poker Planning to add estimates.

---

## 5. Epic Lifecycle

Epics follow a **monotonic state machine**—you can only move forward, never back.

### Stages

| Stage | Description | Actions Allowed |
|-------|-------------|-----------------|
| **problem_capture** | Define the problem | Edit problem statement, chat with AI |
| **problem_confirmed** | Problem is LOCKED | View only (cannot edit) |
| **outcome_capture** | Define success metrics | Edit outcome, chat with AI |
| **outcome_confirmed** | Outcome is LOCKED | View only (cannot edit) |
| **epic_drafted** | Draft epic summary | Edit summary, acceptance criteria |
| **epic_locked** | Epic is LOCKED | Enter Feature Planning Mode |

### Creating an Epic Manually

1. Go to Dashboard
2. Click **"Create Epic"**
3. Enter a title for your epic
4. Chat with the AI to define your problem
5. When satisfied, the AI will propose a problem statement
6. Click **"Confirm"** to lock the problem and move forward

### Chat Commands

The AI understands natural conversation. Examples:
- "The problem is that users can't find their order history"
- "I want to improve the checkout process"
- "Let me rephrase: the real issue is..."

### Confirming Proposals

When the AI proposes something (problem statement, outcome, etc.):
1. Review the proposal in the chat
2. Click **"Confirm"** to accept and lock
3. Or continue chatting to refine before confirming

### Locked Content

Once confirmed, content is **immutable**:
- Shows in a locked sidebar panel
- Cannot be edited or deleted
- Prevents scope creep

---

## 6. Feature Planning

When an Epic is locked, you enter **Feature Planning Mode**.

### Generating Features

1. Navigate to your locked epic
2. Click **"Generate Features"**
3. AI analyzes the epic and suggests 3-5 features
4. For each suggestion:
   - **Save as Draft** - Add to your feature list
   - **Discard** - Remove suggestion

### Feature Stages

| Stage | Description | Actions |
|-------|-------------|---------|
| **Draft** | Initial feature | Edit, Delete, Refine with AI |
| **Refining** | Being improved | Chat with AI, Edit |
| **Approved** | LOCKED | Create User Stories |

### Refining Features

1. Click **"Refine"** on a draft feature
2. Chat with the AI to improve the feature
3. When satisfied, the AI proposes updates
4. Review and accept changes
5. Click **"Approve & Lock"** to finalize

### Manual Feature Creation

1. Click **"Add Feature Manually"**
2. Enter title, description, and acceptance criteria
3. Save as draft or immediately approve

### Feature Cards

Each feature card shows:
- Title and description
- Stage badge (Draft/Refining/Approved)
- Acceptance criteria count
- Story count badge (after stories created)

---

## 7. User Story Planning

Once a Feature is approved, create User Stories.

### Generating Stories

1. Click **"Create User Stories"** on an approved feature
2. AI generates stories based on the feature
3. Review each generated story
4. Save, edit, or discard as needed

### User Story Format

Stories follow the standard format:
```
As a [persona],
I want to [action],
So that [benefit].
```

### Acceptance Criteria

Acceptance criteria use **Given/When/Then** format:
```
Given I am a logged-in user
When I click the "Save" button
Then my changes should be saved
```

### Story Stages

| Stage | Description | Actions |
|-------|-------------|---------|
| **Draft** | Initial story | Edit, Delete, Refine |
| **Refining** | Being improved | Chat with AI |
| **Approved** | LOCKED | Ready for sprint |

### Standalone Stories

Stories can exist without being linked to a feature:

1. Go to **Stories** page
2. Click **"Create with AI"** for AI-assisted creation
3. Or click **"Manual"** for manual entry
4. Standalone stories appear in the Stories list

### Story Points

Story points are **NOT** assigned during creation. Use:
- **Scoring** page for RICE scores
- **Poker Planning** for AI-assisted estimation

---

## 8. Bug Tracking

### Bug Lifecycle

| Status | Description |
|--------|-------------|
| **Draft** | Initial report |
| **Confirmed** | Bug verified |
| **In Progress** | Being worked on |
| **Resolved** | Fix implemented |
| **Closed** | Verified fixed |

### Creating Bugs

#### Manual Creation
1. Go to **Bugs** page
2. Click **"Create Bug"**
3. Fill in details (title, description, severity, etc.)
4. Optionally link to Epic/Feature/Story
5. Save

#### AI-Assisted Creation
1. Click **"Report Bug with AI"**
2. Chat with AI—it asks:
   - What is the problem?
   - How do you reproduce it?
   - What should happen?
   - What actually happens?
   - What environment?
3. AI generates a complete bug report
4. Review and click **"Create Bug"**

### Bug Severity

| Level | Description |
|-------|-------------|
| **Critical** | System unusable, data loss |
| **High** | Major feature broken |
| **Medium** | Feature impaired, workaround exists |
| **Low** | Minor issue, cosmetic |

### Bug Priority

| Level | Description |
|-------|-------------|
| **P0** | Fix immediately |
| **P1** | Fix this sprint |
| **P2** | Fix soon |
| **P3** | Fix when able |

### Linking Bugs

Bugs can be linked to:
- Epics
- Features
- User Stories

Links appear in the **Links** tab of the bug detail dialog.

---

## 9. Scoring & Prioritization

Scoring is **separate** from creation. Items must be scored explicitly.

### MoSCoW Framework

| Category | Description |
|----------|-------------|
| **Must Have** | Critical for success |
| **Should Have** | Important but not critical |
| **Could Have** | Nice to have |
| **Won't Have** | Out of scope for now |

### RICE Framework

| Factor | Description | Values |
|--------|-------------|--------|
| **Reach** | Users affected | 1-10 |
| **Impact** | Impact per user | 0.25, 0.5, 1, 2, 3 |
| **Confidence** | Estimate confidence | 0.5, 0.8, 1.0 |
| **Effort** | Person-months | 0.5-10 |

**RICE Score** = (Reach × Impact × Confidence) / Effort

### Using the Scoring Page

1. Go to **Scoring** in the sidebar
2. Select an Epic to score
3. For each item:
   - Click the scoring icon
   - Set MoSCoW (for Epics/Features)
   - Set RICE scores
   - Optionally get AI suggestions

### AI Suggestions

Click **"Get AI Suggestion"** to have the AI analyze and suggest scores based on:
- Your delivery context
- The item's description
- Industry best practices

---

## 10. AI Poker Planning

Poker Planning uses **5 AI personas** to estimate story points.

### The Personas

| Name | Role | Focus |
|------|------|-------|
| **Sarah** | Sr. Developer | Technical complexity |
| **Alex** | Jr. Developer | Learning curve |
| **Maya** | QA Engineer | Test coverage |
| **Jordan** | DevOps | Deployment & infrastructure |
| **Riley** | UX Designer | User experience |

### How It Works

1. Go to **Poker Planning** in the sidebar
2. Select a user story
3. Click **"Start Estimation"**
4. Watch as each persona "thinks" and provides:
   - Estimate (Fibonacci: 1, 2, 3, 5, 8, 13)
   - Reasoning
   - Confidence level

### Summary

After all personas vote:
- **Average** - Mean of all estimates
- **Suggested** - Rounded to nearest Fibonacci
- **Min/Max** - Range of estimates
- **Consensus** - How much agreement exists

### Custom Story Estimation

Estimate any story text:
1. Click **"Custom Story"** tab
2. Enter or paste story text
3. Run estimation

---

## 11. Sprint Management

### Sprint Overview

The Sprints page shows:
- Current sprint number and dates
- Sprint velocity
- Story status (Todo/In Progress/Done)

### AI Sprint Insights

#### Kickoff Plan
- Sprint goal recommendations
- Top stories to prioritize
- Suggested focus areas

#### Standup Summary
- Yesterday's progress
- Today's priorities
- Blockers and risks

#### WIP Suggestions
- Stories to finish first
- Stories to consider pausing
- Balance recommendations

### Moving Stories

Drag stories between columns:
- **Backlog** → **Todo** → **In Progress** → **Done**

---

## 12. Delivery Reality

Plan your scope against team capacity.

### Features

- **Points Available** - Based on team velocity and sprint length
- **Points Committed** - Stories in current sprint
- **Scope Health** - Visual indicator of overcommitment

### AI Assistance

- **Cut Rationale** - AI explains what to cut if over capacity
- **Alternative Cuts** - Different scope reduction options
- **Risk Review** - Identify delivery risks

### Scope Planning

1. View committed vs. available points
2. Get AI recommendations for scope cuts
3. Accept/reject suggestions
4. Create a scope plan

---

## 13. User Personas

AI generates user personas from completed Epics.

### Generating Personas

1. Complete an Epic (lock all features and stories)
2. Click **"Generate Personas"**
3. Select count (1-5, default 3)
4. AI analyzes Epic, Features, and Stories
5. Generates detailed personas with portraits

### Persona Details

Each persona includes:
- Name and Role
- Demographics
- Goals and Motivations
- Pain Points
- Behaviors
- Jobs-to-Be-Done
- Representative Quote
- AI-generated Portrait

### Managing Personas

- **Edit** - Modify any field (marks as "human_modified")
- **Regenerate Portrait** - Get a new AI image
- **Delete** - Soft delete (can be recovered)

---

## 14. PRD Generator

Generate Product Requirements Documents from Epic data.

### How to Use

1. Go to **PRD Generator** in the sidebar
2. Select an Epic
3. Document generates automatically

### PRD Sections

- Executive Summary
- Problem Statement
- Target Users
- Success Metrics
- Scope (In/Out)
- Features and Stories
- Risks and Assumptions
- Timeline (if available)

### Export Options

- **Copy** - Copy to clipboard
- **Download** - Download as Markdown (.md)

---

## 15. Lean Canvas

A 9-box business model canvas tied to Epics.

### Canvas Sections

| Box | Description |
|-----|-------------|
| **Problem** | Top 3 problems |
| **Solution** | Top 3 features |
| **Unique Value Proposition** | Clear message |
| **Unfair Advantage** | What competitors can't copy |
| **Customer Segments** | Target users |
| **Key Metrics** | Numbers that matter |
| **Channels** | Path to customers |
| **Cost Structure** | Fixed and variable costs |
| **Revenue Streams** | How you make money |

### Features

- Pre-populates from Epic data
- Auto-saves to local storage
- Export as Markdown

---

## 16. Export & Integration

### File Export Formats

| Format | Use Case |
|--------|----------|
| **Jira CSV** | Import into Jira |
| **Azure DevOps CSV** | Import into Azure Boards |
| **JSON** | Universal format |
| **Markdown** | Documentation |

### Direct API Push

#### Jira Cloud
1. Enter Jira URL (e.g., `https://yourcompany.atlassian.net`)
2. Enter email address
3. Enter API token ([Get token](https://id.atlassian.com/manage/api-tokens))
4. Enter project key
5. Click **"Push to Jira"**

#### Azure DevOps
1. Enter organization name
2. Enter project name
3. Enter Personal Access Token
4. Click **"Push to Azure"**

### Field Mappings

| JarlPM | Jira | Azure DevOps |
|--------|------|--------------|
| Epic | Epic | Epic |
| Feature | Story | Feature |
| User Story | Sub-task | User Story |
| Bug | Bug | Bug |
| MoSCoW | Priority | Priority |
| RICE Score | Story Points | Story Points |

---

## 17. Settings & Configuration

### Account Settings

- **Name** - Display name
- **Email** - Login email (read-only)
- **Theme** - Light/Dark mode

### LLM Providers

Configure your AI provider:

#### OpenAI
1. Click **"Add Provider"**
2. Select **OpenAI**
3. Enter API key ([Get key](https://platform.openai.com/api-keys))
4. Select model (gpt-4o, gpt-4-turbo, etc.)
5. Click **"Save & Test"**

#### Anthropic
1. Select **Anthropic**
2. Enter API key
3. Select model (claude-3-opus, claude-3-sonnet, etc.)

#### Local/Custom
1. Select **Local HTTP**
2. Enter base URL
3. Enter model name

### Delivery Context

Customize AI prompts with your team context:

| Setting | Description |
|---------|-------------|
| **Industry** | Your product domain |
| **Methodology** | Agile, Scrum, Kanban, etc. |
| **Sprint Length** | Days per sprint |
| **Sprint Start** | When sprints begin |
| **Team Size** | Developers and QA |
| **Platform** | Jira, Azure DevOps, etc. |
| **Quality Mode** | Standard or Quality (2-pass) |

---

## 18. Subscription & Billing

### Pricing

**$45/month** includes:
- Database storage
- System infrastructure
- All features

**Not included**:
- AI tokens (use your own keys)
- Export integrations (use your own credentials)

### Managing Subscription

1. Go to **Settings**
2. View subscription status
3. **Cancel** - Subscription remains active until period end
4. **Reactivate** - Resume cancelled subscription

### Payment Methods

- Credit/Debit cards via Stripe
- Automatic monthly renewal

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + K` | Quick search |
| `Ctrl/Cmd + N` | New initiative |
| `Escape` | Close dialog |

---

## Troubleshooting

### AI Not Responding

1. Check LLM provider configuration in Settings
2. Verify API key is valid
3. Ensure you have an active subscription

### Cannot Edit Item

- Item may be locked (approved/confirmed)
- Check the stage badge
- Locked items cannot be modified (by design)

### Export Failing

1. Verify credentials are correct
2. Check network connectivity
3. Ensure target project exists

### Session Expired

1. Log out
2. Log back in
3. Clear browser cookies if issues persist

---

## Support

- **Email**: support@asgardsolution.io
- **Documentation**: This manual
- **Built by**: Asgard Solutions LLC

---

*JarlPM — Lead like a Jarl.*
