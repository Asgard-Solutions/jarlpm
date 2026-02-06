"""
Jira Cloud Integration Service for JarlPM
Handles OAuth 2.0 (3LO) flow and REST API operations for Jira Cloud.
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


class JiraAPIError(Exception):
    """Base exception for Jira API errors"""
    pass


class RateLimitError(JiraAPIError):
    """Raised when API rate limit is exceeded"""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(JiraAPIError):
    """Raised when OAuth token is invalid or expired"""
    pass


class JiraOAuthService:
    """Handles Jira Cloud OAuth 2.0 (3LO) flow"""
    
    def __init__(self):
        self.client_id = os.environ.get("JIRA_OAUTH_CLIENT_ID", "")
        self.client_secret = os.environ.get("JIRA_OAUTH_CLIENT_SECRET", "")
        self.redirect_uri = os.environ.get("JIRA_OAUTH_REDIRECT_URI", "")
        self.authorize_url = "https://auth.atlassian.com/authorize"
        self.token_url = "https://auth.atlassian.com/oauth/token"
        self.accessible_resources_url = "https://api.atlassian.com/oauth/token/accessible-resources"
    
    def is_configured(self) -> bool:
        """Check if OAuth credentials are configured"""
        return bool(self.client_id and self.client_secret and self.redirect_uri)
    
    def generate_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate the Jira OAuth authorization URL"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "read:jira-work write:jira-work read:jira-user offline_access",
            "state": state,
            "audience": "api.atlassian.com",
            "prompt": "consent"
        }
        return f"{self.authorize_url}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                json={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri
                },
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Jira token exchange failed: {response.text}")
                raise AuthenticationError(f"Failed to exchange code for tokens: {response.text}")
            
            return response.json()
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh the access token using the refresh token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                json={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token
                },
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Jira token refresh failed: {response.text}")
                raise AuthenticationError(f"Failed to refresh token: {response.text}")
            
            return response.json()
    
    async def get_accessible_resources(self, access_token: str) -> List[Dict[str, Any]]:
        """Get list of accessible Jira sites (cloud IDs)"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.accessible_resources_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get accessible resources: {response.text}")
                raise JiraAPIError(f"Failed to get accessible resources: {response.text}")
            
            return response.json()


class JiraRESTService:
    """Handles Jira Cloud REST API v3 operations"""
    
    def __init__(self, access_token: str, cloud_id: str):
        self.access_token = access_token
        self.cloud_id = cloud_id
        self.base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make authenticated request to Jira REST API"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers=self.headers,
                    timeout=30.0,
                    **kwargs
                )
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    logger.warning(f"Jira rate limit exceeded. Retry after {retry_after}s")
                    raise RateLimitError(
                        "Jira API rate limit exceeded. Please try again later.",
                        retry_after=retry_after
                    )
                
                if response.status_code == 401:
                    raise AuthenticationError("Jira authentication failed. Please reconnect.")
                
                if response.status_code >= 400:
                    logger.error(f"Jira API error: {response.status_code} - {response.text}")
                    raise JiraAPIError(f"Jira API error: {response.text}")
                
                if response.content:
                    return response.json()
                return {}
            
            except httpx.TimeoutException:
                logger.error("Timeout connecting to Jira API")
                raise JiraAPIError("Jira API request timed out")
    
    async def get_myself(self) -> Dict[str, Any]:
        """Get the authenticated user info"""
        return await self._request("GET", "/myself")
    
    async def get_server_info(self) -> Dict[str, Any]:
        """Get Jira server info"""
        return await self._request("GET", "/serverInfo")
    
    async def get_projects(self) -> List[Dict]:
        """Fetch all projects accessible to the user"""
        result = await self._request("GET", "/project/search?maxResults=100")
        return result.get("values", [])
    
    async def get_project(self, project_key: str) -> Dict[str, Any]:
        """Get a specific project by key"""
        return await self._request("GET", f"/project/{project_key}")
    
    async def get_issue_types_for_project(self, project_id_or_key: str) -> List[Dict]:
        """Get issue types available for a project"""
        result = await self._request(
            "GET",
            f"/issue/createmeta/{project_id_or_key}/issuetypes"
        )
        return result.get("values", [])
    
    async def get_fields(self) -> List[Dict]:
        """Get all fields including custom fields"""
        result = await self._request("GET", "/field")
        return result if isinstance(result, list) else []
    
    async def get_labels(self) -> List[str]:
        """Get all labels in the Jira instance"""
        # Note: Jira doesn't have a direct labels endpoint, 
        # labels are created on-the-fly when used
        return []
    
    async def create_issue(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new issue in Jira"""
        return await self._request(
            "POST",
            "/issue",
            json={"fields": fields}
        )
    
    async def update_issue(
        self,
        issue_key: str,
        fields: Dict[str, Any]
    ) -> None:
        """Update an existing issue"""
        await self._request(
            "PUT",
            f"/issue/{issue_key}",
            json={"fields": fields}
        )
    
    async def get_issue(self, issue_key: str, expand: str = "") -> Dict[str, Any]:
        """Get issue details"""
        endpoint = f"/issue/{issue_key}"
        if expand:
            endpoint += f"?expand={expand}"
        return await self._request("GET", endpoint)
    
    async def add_labels(self, issue_key: str, labels: List[str]) -> None:
        """Add labels to an issue"""
        await self._request(
            "PUT",
            f"/issue/{issue_key}",
            json={
                "update": {
                    "labels": [{"add": label} for label in labels]
                }
            }
        )
    
    async def link_issues(
        self,
        link_type: str,
        inward_issue_key: str,
        outward_issue_key: str
    ) -> None:
        """Create a link between two issues"""
        await self._request(
            "POST",
            "/issueLink",
            json={
                "type": {"name": link_type},
                "inwardIssue": {"key": inward_issue_key},
                "outwardIssue": {"key": outward_issue_key}
            }
        )
    
    async def search_issues(
        self,
        jql: str,
        fields: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict]:
        """Search issues using JQL"""
        body = {
            "jql": jql,
            "maxResults": max_results
        }
        if fields:
            body["fields"] = fields
        
        result = await self._request("POST", "/search", json=body)
        return result.get("issues", [])


def compute_payload_hash(payload: Dict) -> str:
    """Compute SHA256 hash of payload for idempotency checking"""
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(payload_str.encode()).hexdigest()


class JiraPushService:
    """
    Service for pushing JarlPM items to Jira.
    Handles idempotent create/update operations with proper field mapping.
    """
    
    def __init__(self, rest_service: JiraRESTService):
        self.jira = rest_service
        self._field_cache: Dict[str, str] = {}
    
    async def discover_custom_fields(self) -> Dict[str, str]:
        """
        Discover custom field IDs for Epic Link, Story Points, etc.
        Returns mapping of field name -> field ID
        """
        if self._field_cache:
            return self._field_cache
        
        fields = await self.jira.get_fields()
        
        field_mapping = {}
        for field in fields:
            field_id = field.get("id", "")
            field_name = field.get("name", "").lower()
            
            # Common field mappings
            if "epic link" in field_name:
                field_mapping["epic_link"] = field_id
            elif "story point" in field_name:
                field_mapping["story_points"] = field_id
            elif field_name == "epic name":
                field_mapping["epic_name"] = field_id
            
            # Store by original name too
            field_mapping[field.get("name", "")] = field_id
        
        self._field_cache = field_mapping
        return field_mapping
    
    def format_epic_description(self, epic: Dict, snapshot: Dict) -> str:
        """Format epic data as Jira issue description (Atlassian Document Format)"""
        parts = []
        
        if snapshot.get("problem_statement"):
            parts.append(f"h2. Problem Statement\n{snapshot['problem_statement']}")
        
        if snapshot.get("desired_outcome"):
            parts.append(f"h2. Desired Outcome\n{snapshot['desired_outcome']}")
        
        if snapshot.get("epic_summary"):
            parts.append(f"h2. Summary\n{snapshot['epic_summary']}")
        
        if snapshot.get("acceptance_criteria"):
            ac_text = "\n".join([f"* {ac}" for ac in snapshot["acceptance_criteria"]])
            parts.append(f"h2. Acceptance Criteria\n{ac_text}")
        
        parts.append(f"\n----\n_Synced from JarlPM • Epic ID: {epic.get('epic_id')}_")
        
        return "\n\n".join(parts)
    
    def format_feature_description(self, feature: Dict) -> str:
        """Format feature data as Jira issue description"""
        parts = [feature.get("description", "")]
        
        if feature.get("acceptance_criteria"):
            ac_text = "\n".join([f"* {ac}" for ac in feature["acceptance_criteria"]])
            parts.append(f"\nh2. Acceptance Criteria\n{ac_text}")
        
        parts.append(f"\n----\n_Synced from JarlPM • Feature ID: {feature.get('feature_id')}_")
        
        return "\n".join(parts)
    
    def format_story_description(self, story: Dict) -> str:
        """Format user story data as Jira issue description"""
        parts = []
        
        # User story format
        parts.append(f"*As a* {story.get('persona', 'user')}")
        parts.append(f"*I want to* {story.get('action', '')}")
        parts.append(f"*So that* {story.get('benefit', '')}")
        
        if story.get("acceptance_criteria"):
            parts.append("\nh2. Acceptance Criteria")
            for ac in story["acceptance_criteria"]:
                parts.append(f"* {ac}")
        
        parts.append(f"\n----\n_Synced from JarlPM • Story ID: {story.get('story_id')}_")
        
        return "\n".join(parts)
    
    async def push_item(
        self,
        project_key: str,
        issue_type: str,
        title: str,
        description: str,
        entity_type: str,
        entity_id: str,
        existing_issue_key: Optional[str] = None,
        epic_link_key: Optional[str] = None,
        story_points: Optional[int] = None,
        labels: Optional[List[str]] = None,
        field_mappings: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Push a single item to Jira (create or update).
        Returns the issue data with key and URL.
        """
        payload = {
            "title": title,
            "description": description,
            "entity_type": entity_type,
            "entity_id": entity_id
        }
        payload_hash = compute_payload_hash(payload)
        
        # Build fields
        fields = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary": title,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            }
        }
        
        # Add labels if provided
        if labels:
            fields["labels"] = labels
        
        # Add story points if provided and field is mapped
        if story_points is not None and field_mappings and field_mappings.get("story_points_field"):
            fields[field_mappings["story_points_field"]] = story_points
        
        # Add epic link if provided and field is mapped
        if epic_link_key and field_mappings and field_mappings.get("epic_link_field"):
            fields[field_mappings["epic_link_field"]] = epic_link_key
        
        if existing_issue_key:
            # Update existing issue
            update_fields = {
                "summary": title,
                "description": fields["description"]
            }
            if labels:
                update_fields["labels"] = labels
            
            await self.jira.update_issue(existing_issue_key, update_fields)
            
            # Get issue URL
            issue = await self.jira.get_issue(existing_issue_key)
            
            return {
                "action": "updated",
                "key": existing_issue_key,
                "id": issue.get("id"),
                "url": f"https://{self.jira.cloud_id}.atlassian.net/browse/{existing_issue_key}",
                "payload_hash": payload_hash
            }
        else:
            # Create new issue
            result = await self.jira.create_issue(fields)
            issue_key = result.get("key")
            issue_id = result.get("id")
            
            return {
                "action": "created",
                "key": issue_key,
                "id": issue_id,
                "url": f"https://{self.jira.cloud_id}.atlassian.net/browse/{issue_key}",
                "payload_hash": payload_hash
            }
