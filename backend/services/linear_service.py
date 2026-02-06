"""
Linear Integration Service for JarlPM
Handles OAuth flow and GraphQL API operations for Linear.
"""
import httpx
import os
import secrets
import hashlib
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
import logging

from services.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class LinearAPIError(Exception):
    """Base exception for Linear API errors"""
    pass


class RateLimitError(LinearAPIError):
    """Raised when API rate limit is exceeded"""
    pass


class GraphQLError(LinearAPIError):
    """Raised when GraphQL query returns errors"""
    pass


class AuthenticationError(LinearAPIError):
    """Raised when OAuth token is invalid or expired"""
    pass


class LinearOAuthService:
    """Handles Linear OAuth 2.0 flow"""
    
    def __init__(self):
        self.client_id = os.environ.get("LINEAR_OAUTH_CLIENT_ID", "")
        self.client_secret = os.environ.get("LINEAR_OAUTH_CLIENT_SECRET", "")
        self.redirect_uri = os.environ.get("LINEAR_OAUTH_REDIRECT_URI", "")
        self.authorize_url = "https://linear.app/oauth/authorize"
        self.token_url = "https://api.linear.app/oauth/token"
        self.revoke_url = "https://api.linear.app/oauth/revoke"
    
    def is_configured(self) -> bool:
        """Check if OAuth credentials are configured"""
        return bool(self.client_id and self.client_secret and self.redirect_uri)
    
    def generate_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate the Linear OAuth authorization URL"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "read write",
            "state": state,
            "prompt": "consent"
        }
        return f"{self.authorize_url}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise AuthenticationError(f"Failed to exchange code for tokens: {response.text}")
            
            return response.json()
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh the access token using the refresh token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                raise AuthenticationError(f"Failed to refresh token: {response.text}")
            
            return response.json()
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke an access token"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.revoke_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    timeout=30.0
                )
                return response.status_code == 200
            except Exception as e:
                logger.warning(f"Token revocation failed: {e}")
                return False


class LinearGraphQLService:
    """Handles Linear GraphQL API operations"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.endpoint = "https://api.linear.app/graphql"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against the Linear API"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.endpoint,
                    json={"query": query, "variables": variables or {}},
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 429:
                    logger.warning("Rate limit exceeded on Linear API")
                    raise RateLimitError("Linear API rate limit exceeded. Please try again later.")
                
                if response.status_code == 401:
                    raise AuthenticationError("Linear authentication failed. Please reconnect.")
                
                if response.status_code != 200:
                    logger.error(f"GraphQL error: {response.text}")
                    raise LinearAPIError(f"Linear API error: {response.text}")
                
                result = response.json()
                
                if "errors" in result:
                    error_messages = [error.get("message", "Unknown error") 
                                     for error in result["errors"]]
                    logger.error(f"GraphQL errors: {error_messages}")
                    raise GraphQLError(f"GraphQL errors: {', '.join(error_messages)}")
                
                return result.get("data", {})
            
            except httpx.TimeoutException:
                logger.error("Timeout connecting to Linear API")
                raise LinearAPIError("Linear API request timed out")
    
    async def get_viewer(self) -> Dict[str, Any]:
        """Get the authenticated user info"""
        query = """
        query Viewer {
            viewer {
                id
                name
                email
            }
        }
        """
        result = await self.execute_query(query)
        return result.get("viewer", {})
    
    async def get_organization(self) -> Dict[str, Any]:
        """Get the organization/workspace info"""
        query = """
        query Organization {
            organization {
                id
                name
                urlKey
            }
        }
        """
        result = await self.execute_query(query)
        return result.get("organization", {})
    
    async def get_teams(self) -> List[Dict]:
        """Fetch all teams in the workspace"""
        query = """
        query Teams {
            teams {
                nodes {
                    id
                    name
                    key
                    description
                }
            }
        }
        """
        result = await self.execute_query(query)
        return result.get("teams", {}).get("nodes", [])
    
    async def get_team_projects(self, team_id: str) -> List[Dict]:
        """Fetch projects for a specific team"""
        query = """
        query TeamProjects($teamId: String!) {
            team(id: $teamId) {
                id
                name
                projects {
                    nodes {
                        id
                        name
                        description
                        state
                    }
                }
            }
        }
        """
        result = await self.execute_query(query, {"teamId": team_id})
        team_data = result.get("team", {})
        return team_data.get("projects", {}).get("nodes", [])
    
    async def get_team_labels(self, team_id: str) -> List[Dict]:
        """Fetch all labels defined for a team"""
        query = """
        query TeamLabels($teamId: String!) {
            team(id: $teamId) {
                id
                labels {
                    nodes {
                        id
                        name
                        color
                    }
                }
            }
        }
        """
        result = await self.execute_query(query, {"teamId": team_id})
        return result.get("team", {}).get("labels", {}).get("nodes", [])
    
    async def get_workflow_states(self, team_id: str) -> List[Dict]:
        """Fetch workflow states for a team"""
        query = """
        query WorkflowStates($teamId: String!) {
            team(id: $teamId) {
                id
                states {
                    nodes {
                        id
                        name
                        type
                        position
                        color
                    }
                }
            }
        }
        """
        result = await self.execute_query(query, {"teamId": team_id})
        return result.get("team", {}).get("states", {}).get("nodes", [])
    
    async def create_issue(
        self,
        team_id: str,
        title: str,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        estimate: Optional[int] = None,
        assignee_id: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new issue in Linear"""
        input_data = {
            "title": title,
            "teamId": team_id,
        }
        
        if description:
            input_data["description"] = description
        if priority is not None:
            input_data["priority"] = priority
        if estimate is not None:
            input_data["estimate"] = estimate
        if assignee_id:
            input_data["assigneeId"] = assignee_id
        if label_ids:
            input_data["labelIds"] = label_ids
        if project_id:
            input_data["projectId"] = project_id
        if parent_id:
            input_data["parentId"] = parent_id
        
        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                    number
                }
            }
        }
        """
        
        result = await self.execute_query(mutation, {"input": input_data})
        issue_data = result.get("issueCreate", {})
        
        if not issue_data.get("success"):
            raise LinearAPIError("Failed to create issue in Linear")
        
        return issue_data.get("issue", {})
    
    async def update_issue(
        self,
        issue_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        state_id: Optional[str] = None,
        priority: Optional[int] = None,
        estimate: Optional[int] = None,
        label_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Update an existing issue in Linear"""
        input_data = {}
        
        if title:
            input_data["title"] = title
        if description:
            input_data["description"] = description
        if state_id:
            input_data["stateId"] = state_id
        if priority is not None:
            input_data["priority"] = priority
        if estimate is not None:
            input_data["estimate"] = estimate
        if label_ids:
            input_data["labelIds"] = label_ids
        
        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                    state {
                        id
                        name
                    }
                }
            }
        }
        """
        
        result = await self.execute_query(mutation, {"id": issue_id, "input": input_data})
        issue_data = result.get("issueUpdate", {})
        
        if not issue_data.get("success"):
            raise LinearAPIError("Failed to update issue in Linear")
        
        return issue_data.get("issue", {})
    
    async def get_issue_by_id(self, issue_id: str) -> Dict[str, Any]:
        """Fetch a specific issue from Linear"""
        query = """
        query Issue($id: String!) {
            issue(id: $id) {
                id
                identifier
                title
                description
                priority
                estimate
                url
                state {
                    id
                    name
                }
                assignee {
                    id
                    name
                }
                labels {
                    nodes {
                        id
                        name
                    }
                }
                parent {
                    id
                    identifier
                }
                children {
                    nodes {
                        id
                        identifier
                        title
                    }
                }
            }
        }
        """
        result = await self.execute_query(query, {"id": issue_id})
        return result.get("issue", {})

    async def create_label(
        self,
        team_id: str,
        name: str,
        color: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new label in Linear"""
        input_data = {
            "teamId": team_id,
            "name": name,
        }
        if color:
            input_data["color"] = color
        
        mutation = """
        mutation CreateLabel($input: IssueLabelCreateInput!) {
            issueLabelCreate(input: $input) {
                success
                issueLabel {
                    id
                    name
                    color
                }
            }
        }
        """
        
        result = await self.execute_query(mutation, {"input": input_data})
        label_data = result.get("issueLabelCreate", {})
        
        if not label_data.get("success"):
            raise LinearAPIError(f"Failed to create label '{name}' in Linear")
        
        return label_data.get("issueLabel", {})

    async def create_project(
        self,
        team_ids: List[str],
        name: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new project in Linear"""
        input_data = {
            "teamIds": team_ids,
            "name": name,
        }
        if description:
            input_data["description"] = description
        
        mutation = """
        mutation CreateProject($input: ProjectCreateInput!) {
            projectCreate(input: $input) {
                success
                project {
                    id
                    name
                    url
                }
            }
        }
        """
        
        result = await self.execute_query(mutation, {"input": input_data})
        project_data = result.get("projectCreate", {})
        
        if not project_data.get("success"):
            raise LinearAPIError(f"Failed to create project '{name}' in Linear")
        
        return project_data.get("project", {})

    async def get_organization_labels(self) -> List[Dict]:
        """Fetch all labels in the organization"""
        query = """
        query IssueLabels {
            issueLabels(first: 250) {
                nodes {
                    id
                    name
                    color
                }
            }
        }
        """
        result = await self.execute_query(query)
        return result.get("issueLabels", {}).get("nodes", [])


def compute_payload_hash(payload: Dict) -> str:
    """Compute SHA256 hash of payload for idempotency checking"""
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(payload_str.encode()).hexdigest()


class LinearPushService:
    """
    Service for pushing JarlPM items to Linear.
    Handles idempotent create/update operations.
    """
    
    def __init__(self, graphql_service: LinearGraphQLService):
        self.graphql = graphql_service
    
    def format_epic_description(self, epic: Dict, snapshot: Dict) -> str:
        """Format epic data as Linear issue description"""
        parts = []
        
        if snapshot.get("problem_statement"):
            parts.append(f"## Problem Statement\n{snapshot['problem_statement']}")
        
        if snapshot.get("desired_outcome"):
            parts.append(f"## Desired Outcome\n{snapshot['desired_outcome']}")
        
        if snapshot.get("epic_summary"):
            parts.append(f"## Summary\n{snapshot['epic_summary']}")
        
        if snapshot.get("acceptance_criteria"):
            ac_text = "\n".join([f"- {ac}" for ac in snapshot["acceptance_criteria"]])
            parts.append(f"## Acceptance Criteria\n{ac_text}")
        
        parts.append(f"\n---\n*Synced from JarlPM • Epic ID: {epic.get('epic_id')}*")
        
        return "\n\n".join(parts)
    
    def format_feature_description(self, feature: Dict) -> str:
        """Format feature data as Linear issue description"""
        parts = [feature.get("description", "")]
        
        if feature.get("acceptance_criteria"):
            ac_text = "\n".join([f"- {ac}" for ac in feature["acceptance_criteria"]])
            parts.append(f"\n## Acceptance Criteria\n{ac_text}")
        
        parts.append(f"\n---\n*Synced from JarlPM • Feature ID: {feature.get('feature_id')}*")
        
        return "\n".join(parts)
    
    def format_story_description(self, story: Dict) -> str:
        """Format user story data as Linear issue description"""
        parts = [f"**As a** {story.get('persona', 'user')}"]
        parts.append(f"**I want to** {story.get('action', '')}")
        parts.append(f"**So that** {story.get('benefit', '')}")
        
        if story.get("acceptance_criteria"):
            ac_text = "\n".join([f"- {ac}" for ac in story["acceptance_criteria"]])
            parts.append(f"\n## Acceptance Criteria\n{ac_text}")
        
        if story.get("story_points"):
            parts.append(f"\n**Story Points:** {story['story_points']}")
        
        parts.append(f"\n---\n*Synced from JarlPM • Story ID: {story.get('story_id')}*")
        
        return "\n".join(parts)
    
    async def push_item(
        self,
        team_id: str,
        title: str,
        description: str,
        entity_type: str,
        entity_id: str,
        existing_external_id: Optional[str] = None,
        parent_external_id: Optional[str] = None,
        estimate: Optional[int] = None,
        project_id: Optional[str] = None,
        label_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Push a single item to Linear (create or update).
        Returns the issue data with external_id, external_key, and external_url.
        """
        payload = {
            "title": title,
            "description": description,
            "entity_type": entity_type,
            "entity_id": entity_id
        }
        payload_hash = compute_payload_hash(payload)
        
        if existing_external_id:
            # Update existing issue
            issue = await self.graphql.update_issue(
                issue_id=existing_external_id,
                title=title,
                description=description,
                estimate=estimate,
                label_ids=label_ids
            )
            action = "updated"
        else:
            # Create new issue
            issue = await self.graphql.create_issue(
                team_id=team_id,
                title=title,
                description=description,
                estimate=estimate,
                parent_id=parent_external_id,
                project_id=project_id,
                label_ids=label_ids
            )
            action = "created"
        
        return {
            "action": action,
            "external_id": issue.get("id"),
            "external_key": issue.get("identifier"),
            "external_url": issue.get("url"),
            "payload_hash": payload_hash
        }
