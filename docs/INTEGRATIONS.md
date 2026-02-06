# JarlPM External Integrations Guide

This document covers the setup, configuration, and troubleshooting for JarlPM's external project management integrations.

---

## Table of Contents

1. [Overview](#overview)
2. [Linear Integration](#linear-integration)
3. [Jira Cloud Integration](#jira-cloud-integration)
4. [Azure DevOps Integration](#azure-devops-integration)
5. [Common Troubleshooting](#common-troubleshooting)
6. [API Reference](#api-reference)

---

## Overview

JarlPM supports pushing Epics, Features, and User Stories to three external project management platforms:

| Provider | Auth Method | Status |
|----------|-------------|--------|
| **Linear** | OAuth 2.0 | Ready (requires OAuth credentials) |
| **Jira Cloud** | OAuth 2.0 (3LO) | Ready (requires OAuth credentials) |
| **Azure DevOps** | Personal Access Token (PAT) | Fully Functional |

### Key Features

- **Idempotent Push**: Re-pushing the same items updates rather than duplicates
- **Preview Mode**: See what will be created/updated before pushing
- **Hierarchical Mapping**: Maintains Epic → Feature → Story relationships
- **Field Mapping**: Configurable mapping for story points, priorities, etc.

---

## Linear Integration

### How to Connect

1. Navigate to **Settings → Integrations**
2. Find the **Linear** card
3. Click **"Connect Linear"**
4. You'll be redirected to Linear to authorize JarlPM
5. After authorization, you'll return to JarlPM with the connection active

### Required OAuth Scopes

When creating your Linear OAuth app, request these scopes:

| Scope | Purpose |
|-------|---------|
| `read` | Read teams, projects, labels, issues |
| `write` | Create/update issues, labels |
| `issues:create` | Create new issues |

### Environment Variables (Server Admin)

```bash
LINEAR_OAUTH_CLIENT_ID=your_client_id
LINEAR_OAUTH_CLIENT_SECRET=your_client_secret
LINEAR_OAUTH_REDIRECT_URI=https://your-domain.com/api/integrations/linear/callback
```

### How to Push to Linear

1. Open a **locked Epic** (Feature Planning Mode)
2. Click **"Push to Linear"** button in the header
3. Select target **Team** (required)
4. Optionally select a **Project**
5. Choose **Push Scope**:
   - Epic Only
   - Epic + Features
   - Full Hierarchy (Epic + Features + Stories)
6. Review the **Preview** showing create/update counts
7. Click **"Push to Linear"**

### Mapping Rules

| JarlPM Entity | Linear Entity | Notes |
|---------------|---------------|-------|
| Epic | Issue (labeled "epic") or Project | Configurable via `epic_mapping` |
| Feature | Issue (labeled "feature") | Child of Epic |
| User Story | Issue (labeled "story") | Child of Feature |
| MoSCoW Score | Priority | Configurable mapping |

### Priority Mapping (Default)

| MoSCoW | Linear Priority |
|--------|-----------------|
| Must Have | High (2) |
| Should Have | Medium (3) |
| Could Have | Low (4) |
| Won't Have | No Priority (0) |

### Troubleshooting Linear

| Error | Cause | Solution |
|-------|-------|----------|
| "OAuth credentials not configured" | Server missing env vars | Admin must set LINEAR_OAUTH_* variables |
| "Invalid or expired token" | OAuth token expired | Disconnect and reconnect Linear |
| "Team not found" | Team was deleted or renamed | Refresh teams list or select different team |
| "Rate limit exceeded" | Too many API calls | Wait and retry in a few minutes |

---

## Jira Cloud Integration

### How to Connect

1. Navigate to **Settings → Integrations**
2. Find the **Jira** card
3. Click **"Connect Jira"**
4. You'll be redirected to Atlassian to authorize JarlPM
5. Select which Jira sites to grant access to
6. After authorization, return to JarlPM and select your default project

### Required OAuth Scopes

| Scope | Purpose |
|-------|---------|
| `read:jira-work` | Read projects, issues, fields |
| `write:jira-work` | Create/update issues |
| `read:jira-user` | Read user info for assignment |
| `offline_access` | Token refresh capability |

### Environment Variables (Server Admin)

```bash
JIRA_OAUTH_CLIENT_ID=your_client_id
JIRA_OAUTH_CLIENT_SECRET=your_client_secret
JIRA_OAUTH_REDIRECT_URI=https://your-domain.com/api/integrations/jira/callback
```

### How to Push to Jira

1. Open a **locked Epic** (Feature Planning Mode)
2. Click **"Push to Jira"** button in the header
3. Select target **Project** (required)
4. Choose **Push Scope**:
   - Epic Only
   - Epic + Features
   - Full Hierarchy (Epic + Features + Stories)
5. Review the **Preview** showing create/update counts
6. Click **"Push to Jira"**

### Mapping Rules

| JarlPM Entity | Jira Issue Type | Notes |
|---------------|-----------------|-------|
| Epic | Epic | Uses Jira's native Epic type |
| Feature | Task | Configurable (Task, Story, etc.) |
| User Story | Story | Or Sub-task if linked to Feature |
| Bug | Bug | Native Jira Bug type |

### Field Mapping

| JarlPM Field | Jira Field | Configuration |
|--------------|------------|---------------|
| Title | Summary | Automatic |
| Description | Description | Automatic |
| Story Points | Story Points (custom field) | Configurable field ID |
| Epic Link | Epic Link (custom field) | Configurable field ID |
| Acceptance Criteria | Description (appended) | Automatic |

### Troubleshooting Jira

| Error | Cause | Solution |
|-------|-------|----------|
| "OAuth credentials not configured" | Server missing env vars | Admin must set JIRA_OAUTH_* variables |
| "No accessible sites" | User hasn't granted site access | Re-authorize and select Jira sites |
| "Project not found" | Project key invalid or no access | Check project permissions |
| "Issue type not found" | Project doesn't have required issue types | Use project with Epic, Story, Task types |
| "Epic Link field not found" | Custom field ID incorrect | Reconfigure epic_link_field in settings |
| "Cannot create issue" | Missing required fields | Check project's required field configuration |

---

## Azure DevOps Integration

### How to Connect

1. Navigate to **Settings → Integrations**
2. Find the **Azure DevOps** card
3. Enter your **Organization URL** (e.g., `https://dev.azure.com/yourorg`)
4. Enter your **Personal Access Token (PAT)**
5. Click **"Connect to Azure DevOps"**

### Creating a Personal Access Token (PAT)

1. Go to Azure DevOps → **User Settings** (top right) → **Personal Access Tokens**
2. Click **"+ New Token"**
3. Configure:
   - **Name**: JarlPM Integration
   - **Organization**: Select your organization
   - **Expiration**: Choose appropriate duration
   - **Scopes**: Select the required scopes below
4. Click **"Create"** and copy the token immediately

### Required PAT Scopes

| Scope | Access Level | Purpose |
|-------|--------------|---------|
| **Work Items** | Read & Write | Create/update work items |
| **Project and Team** | Read | List projects, teams, iterations |

**Minimum scope selection:**
- Work Items: Read & write
- Project and Team: Read

### How to Push to Azure DevOps

1. Open a **locked Epic** (Feature Planning Mode)
2. Click **"Push to Azure DevOps"** button in the header
3. Select target **Project** (required)
4. Optionally select:
   - **Area Path** - for categorization
   - **Iteration/Sprint** - for sprint assignment
5. Choose **Push Scope**:
   - Epic Only
   - Epic + Features
   - Full Hierarchy (Epic + Features + Stories)
6. Review the **Preview** showing create/update counts
7. Click **"Push to Azure DevOps"**

### Mapping Rules

| JarlPM Entity | Azure DevOps Work Item Type | Notes |
|---------------|----------------------------|-------|
| Epic | Epic | Configurable |
| Feature | Feature | Configurable |
| User Story | User Story | Configurable |
| Bug | Bug | Native type |

### Field Mapping

| JarlPM Field | Azure DevOps Field | Reference Name |
|--------------|-------------------|----------------|
| Title | Title | System.Title |
| Description | Description | System.Description |
| Story Points | Story Points | Microsoft.VSTS.Scheduling.StoryPoints |
| Area Path | Area Path | System.AreaPath |
| Iteration Path | Iteration Path | System.IterationPath |
| Tags | Tags | System.Tags |

### Parent-Child Hierarchy

JarlPM creates proper parent-child relationships using Azure DevOps link types:
- Epic → Feature: `System.LinkTypes.Hierarchy-Forward`
- Feature → User Story: `System.LinkTypes.Hierarchy-Forward`

### Troubleshooting Azure DevOps

| Error | Cause | Solution |
|-------|-------|----------|
| "Authentication failed" | Invalid or expired PAT | Generate a new PAT with correct scopes |
| "Organization not found" | Incorrect URL format | Use `https://dev.azure.com/orgname` format |
| "Project not found" | No access to project | Check PAT scope includes the project |
| "Work item type not found" | Process template mismatch | Use process with Epic/Feature/User Story types |
| "Field not found" | Custom process without standard fields | Configure custom field mappings |
| "Rate limit exceeded" | Too many API calls | Wait 60 seconds and retry |
| "TF401027: No permission" | PAT lacks write permission | Generate PAT with Read & Write for Work Items |

### PAT Expiration

- PATs can expire (max 1 year)
- When expired, you'll see authentication errors
- Solution: Generate a new PAT and reconnect in Settings

---

## Common Troubleshooting

### "Active subscription required"

**Cause**: Your JarlPM subscription is not active.

**Solution**: 
1. Go to **Settings → Subscription**
2. Ensure you have an active Pro subscription
3. If expired, renew your subscription

### "Integration not connected"

**Cause**: The integration was disconnected or never connected.

**Solution**:
1. Go to **Settings → Integrations**
2. Find the provider card
3. Click Connect and complete the authorization flow

### Push Results: Items Not Appearing

**Possible causes**:
1. **Permission issues**: Check your token/OAuth has write access
2. **Project configuration**: Ensure the target project accepts the work item types
3. **Field validation**: Some fields may have validation rules blocking creation

**Debug steps**:
1. Check the push results for error messages
2. Verify field mappings in integration configuration
3. Try pushing "Epic Only" first to isolate the issue

### Duplicate Items Created

**Cause**: Mapping table was cleared or corrupted.

**Solution**: JarlPM uses `external_push_mappings` table to track created items. If this data is lost:
1. Manually update or delete duplicates in the external system
2. Future pushes will create new mappings

---

## API Reference

### Status Endpoints

```
GET /api/integrations/status
GET /api/integrations/status/{provider}  # linear, jira, azure_devops
```

### Linear Endpoints

```
POST /api/integrations/linear/connect
GET  /api/integrations/linear/callback
POST /api/integrations/linear/disconnect
PUT  /api/integrations/linear/configure
GET  /api/integrations/linear/teams
GET  /api/integrations/linear/teams/{team_id}/projects
GET  /api/integrations/linear/teams/{team_id}/labels
GET  /api/integrations/linear/labels
POST /api/integrations/linear/preview
POST /api/integrations/linear/push
```

### Jira Endpoints

```
POST /api/integrations/jira/connect
GET  /api/integrations/jira/callback
POST /api/integrations/jira/disconnect
PUT  /api/integrations/jira/configure
GET  /api/integrations/jira/sites
GET  /api/integrations/jira/projects
GET  /api/integrations/jira/projects/{key}/issue-types
GET  /api/integrations/jira/fields
POST /api/integrations/jira/preview
POST /api/integrations/jira/push
```

### Azure DevOps Endpoints

```
POST /api/integrations/azure-devops/connect
POST /api/integrations/azure-devops/disconnect
PUT  /api/integrations/azure-devops/configure
GET  /api/integrations/azure-devops/projects
GET  /api/integrations/azure-devops/projects/{name}/teams
GET  /api/integrations/azure-devops/projects/{name}/iterations
GET  /api/integrations/azure-devops/projects/{name}/areas
GET  /api/integrations/azure-devops/projects/{name}/work-item-types
GET  /api/integrations/azure-devops/projects/{name}/fields
POST /api/integrations/azure-devops/preview
POST /api/integrations/azure-devops/push
```

### Common Push Request Body

```json
{
  "epic_id": "epic_xxxxx",
  "push_scope": "epic_features_stories",  // epic_only | epic_features | epic_features_stories
  "include_bugs": false,
  "dry_run": false
}
```

### Push Response

```json
{
  "run_id": "run_xxxxx",
  "created": [
    { "type": "epic", "external_id": "123", "external_key": "PROJ-123", "url": "..." }
  ],
  "updated": [],
  "errors": []
}
```

---

## Database Schema

### ExternalIntegration

Stores user connections to providers.

| Column | Type | Description |
|--------|------|-------------|
| integration_id | UUID | Primary key |
| user_id | UUID | Foreign key to users |
| provider | String | linear, jira, azure_devops |
| status | String | connected, disconnected, error |
| account_name | String | Display name (org/site name) |
| encrypted_access_token | String | Encrypted OAuth/PAT token |
| encrypted_refresh_token | String | Encrypted refresh token (OAuth) |
| org_url | String | Organization URL (ADO) |
| cloud_id | String | Cloud ID (Jira) |
| default_team | JSON | Default team selection |
| default_project | JSON | Default project selection |
| field_mappings | JSON | Custom field configurations |
| connected_at | DateTime | Connection timestamp |

### ExternalPushMapping

Tracks which JarlPM entities map to which external entities.

| Column | Type | Description |
|--------|------|-------------|
| mapping_id | UUID | Primary key |
| user_id | UUID | Foreign key to users |
| provider | String | linear, jira, azure_devops |
| entity_type | String | epic, feature, story, bug |
| entity_id | String | JarlPM entity ID |
| external_id | String | External system ID |
| external_key | String | External key (e.g., PROJ-123) |
| external_url | String | Link to external item |
| last_pushed_at | DateTime | Last push timestamp |
| last_push_hash | String | Hash for change detection |

### ExternalPushRun

Audit log for push operations.

| Column | Type | Description |
|--------|------|-------------|
| run_id | UUID | Primary key |
| user_id | UUID | Foreign key to users |
| integration_id | UUID | Foreign key to integration |
| provider | String | linear, jira, azure_devops |
| epic_id | String | Epic being pushed |
| push_scope | String | Scope of push |
| is_dry_run | Boolean | Preview only |
| status | String | pending, success, partial, failed |
| summary | JSON | Results summary |
| started_at | DateTime | Start timestamp |
| completed_at | DateTime | End timestamp |

---

*Last updated: 2026-02-06*
