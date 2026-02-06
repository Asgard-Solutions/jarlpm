"""
Azure DevOps Integration Service for JarlPM
Handles PAT-based authentication and REST API operations for Azure DevOps.
"""
import httpx
import os
import base64
import hashlib
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

from services.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class AzureDevOpsAPIError(Exception):
    """Base exception for Azure DevOps API errors"""
    pass


class RateLimitError(AzureDevOpsAPIError):
    """Raised when API rate limit is exceeded"""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(AzureDevOpsAPIError):
    """Raised when PAT is invalid or expired"""
    pass


class AzureDevOpsRESTService:
    """Handles Azure DevOps REST API operations using PAT authentication"""
    
    API_VERSION = "7.1"
    
    def __init__(self, organization_url: str, pat: str):
        """
        Initialize Azure DevOps service.
        
        Args:
            organization_url: e.g., "https://dev.azure.com/myorg" or "https://myorg.visualstudio.com"
            pat: Personal Access Token
        """
        self.organization_url = organization_url.rstrip('/')
        self.pat = pat
        
        # Create Basic Auth header from PAT
        # Format: Base64(":{PAT}")
        auth_string = f":{pat}"
        self.auth_header = base64.b64encode(auth_string.encode()).decode()
        
        self.headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Content-Type": "application/json"
        }
    
    async def _request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make authenticated request to Azure DevOps REST API"""
        async with httpx.AsyncClient() as client:
            try:
                # Add API version to URL
                separator = "&" if "?" in url else "?"
                full_url = f"{url}{separator}api-version={self.API_VERSION}"
                
                response = await client.request(
                    method,
                    full_url,
                    headers=self.headers,
                    timeout=30.0,
                    **kwargs
                )
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    logger.warning(f"Azure DevOps rate limit exceeded. Retry after {retry_after}s")
                    raise RateLimitError(
                        "Azure DevOps API rate limit exceeded. Please try again later.",
                        retry_after=retry_after
                    )
                
                if response.status_code in [401, 403]:
                    raise AuthenticationError("Azure DevOps authentication failed. Please check your PAT.")
                
                if response.status_code >= 400:
                    logger.error(f"Azure DevOps API error: {response.status_code} - {response.text}")
                    raise AzureDevOpsAPIError(f"Azure DevOps API error: {response.text}")
                
                if response.content:
                    return response.json()
                return {}
            
            except httpx.TimeoutException:
                logger.error("Timeout connecting to Azure DevOps API")
                raise AzureDevOpsAPIError("Azure DevOps API request timed out")
    
    async def verify_connection(self) -> Dict[str, Any]:
        """Verify the PAT and organization URL are valid"""
        url = f"{self.organization_url}/_apis/projects"
        result = await self._request("GET", url)
        return {
            "valid": True,
            "project_count": result.get("count", 0)
        }
    
    async def get_projects(self) -> List[Dict]:
        """Get all projects in the organization"""
        url = f"{self.organization_url}/_apis/projects"
        result = await self._request("GET", url)
        return result.get("value", [])
    
    async def get_project(self, project_name: str) -> Dict[str, Any]:
        """Get a specific project"""
        url = f"{self.organization_url}/_apis/projects/{project_name}"
        return await self._request("GET", url)
    
    async def get_teams(self, project_name: str) -> List[Dict]:
        """Get teams for a project"""
        url = f"{self.organization_url}/_apis/projects/{project_name}/teams"
        result = await self._request("GET", url)
        return result.get("value", [])
    
    async def get_iterations(self, project_name: str, team_name: Optional[str] = None) -> List[Dict]:
        """Get iterations (sprints) for a project/team"""
        if team_name:
            url = f"{self.organization_url}/{project_name}/{team_name}/_apis/work/teamsettings/iterations"
        else:
            url = f"{self.organization_url}/{project_name}/_apis/wit/classificationnodes/iterations?$depth=10"
        
        result = await self._request("GET", url)
        
        # Handle different response formats
        if "value" in result:
            return result["value"]
        elif "children" in result:
            return self._flatten_classification_nodes(result)
        return [result] if result.get("id") else []
    
    async def get_area_paths(self, project_name: str) -> List[Dict]:
        """Get area paths for a project"""
        url = f"{self.organization_url}/{project_name}/_apis/wit/classificationnodes/areas?$depth=10"
        result = await self._request("GET", url)
        return self._flatten_classification_nodes(result)
    
    def _flatten_classification_nodes(self, node: Dict, prefix: str = "") -> List[Dict]:
        """Flatten hierarchical classification nodes into a list"""
        results = []
        
        name = node.get("name", "")
        path = f"{prefix}\\{name}" if prefix else name
        
        results.append({
            "id": node.get("id"),
            "name": name,
            "path": path,
            "structureType": node.get("structureType")
        })
        
        for child in node.get("children", []):
            results.extend(self._flatten_classification_nodes(child, path))
        
        return results
    
    async def get_work_item_types(self, project_name: str) -> List[Dict]:
        """Get available work item types for a project"""
        url = f"{self.organization_url}/{project_name}/_apis/wit/workitemtypes"
        result = await self._request("GET", url)
        return result.get("value", [])
    
    async def get_fields(self, project_name: str) -> List[Dict]:
        """Get all fields for a project"""
        url = f"{self.organization_url}/{project_name}/_apis/wit/fields"
        result = await self._request("GET", url)
        return result.get("value", [])
    
    async def create_work_item(
        self,
        project_name: str,
        work_item_type: str,
        title: str,
        description: Optional[str] = None,
        area_path: Optional[str] = None,
        iteration_path: Optional[str] = None,
        state: Optional[str] = None,
        story_points: Optional[int] = None,
        story_points_field: str = "Microsoft.VSTS.Scheduling.StoryPoints",
        tags: Optional[List[str]] = None,
        description_format: str = "html"  # "html" or "markdown"
    ) -> Dict[str, Any]:
        """Create a new work item in Azure DevOps"""
        url = f"{self.organization_url}/{project_name}/_apis/wit/workitems/${work_item_type}"
        
        # Build JSON Patch operations
        operations = [
            {"op": "add", "path": "/fields/System.Title", "value": title}
        ]
        
        if description:
            # Use appropriate field based on format preference
            desc_field = "/fields/System.Description"
            if description_format == "html":
                # Convert basic markdown to HTML
                description = self._markdown_to_html(description)
            operations.append({"op": "add", "path": desc_field, "value": description})
        
        if area_path:
            operations.append({"op": "add", "path": "/fields/System.AreaPath", "value": area_path})
        
        if iteration_path:
            operations.append({"op": "add", "path": "/fields/System.IterationPath", "value": iteration_path})
        
        if state:
            operations.append({"op": "add", "path": "/fields/System.State", "value": state})
        
        if story_points is not None:
            operations.append({"op": "add", "path": f"/fields/{story_points_field}", "value": story_points})
        
        if tags:
            operations.append({"op": "add", "path": "/fields/System.Tags", "value": "; ".join(tags)})
        
        # Use JSON Patch content type
        headers = {**self.headers, "Content-Type": "application/json-patch+json"}
        
        async with httpx.AsyncClient() as client:
            separator = "&" if "?" in url else "?"
            full_url = f"{url}{separator}api-version={self.API_VERSION}"
            
            response = await client.post(
                full_url,
                headers=headers,
                json=operations,
                timeout=30.0
            )
            
            if response.status_code >= 400:
                logger.error(f"Failed to create work item: {response.text}")
                raise AzureDevOpsAPIError(f"Failed to create work item: {response.text}")
            
            return response.json()
    
    async def update_work_item(
        self,
        work_item_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        state: Optional[str] = None,
        story_points: Optional[int] = None,
        story_points_field: str = "Microsoft.VSTS.Scheduling.StoryPoints",
        tags: Optional[List[str]] = None,
        description_format: str = "html"
    ) -> Dict[str, Any]:
        """Update an existing work item"""
        url = f"{self.organization_url}/_apis/wit/workitems/{work_item_id}"
        
        operations = []
        
        if title:
            operations.append({"op": "replace", "path": "/fields/System.Title", "value": title})
        
        if description:
            if description_format == "html":
                description = self._markdown_to_html(description)
            operations.append({"op": "replace", "path": "/fields/System.Description", "value": description})
        
        if state:
            operations.append({"op": "replace", "path": "/fields/System.State", "value": state})
        
        if story_points is not None:
            operations.append({"op": "replace", "path": f"/fields/{story_points_field}", "value": story_points})
        
        if tags is not None:
            operations.append({"op": "replace", "path": "/fields/System.Tags", "value": "; ".join(tags)})
        
        if not operations:
            return await self.get_work_item(work_item_id)
        
        headers = {**self.headers, "Content-Type": "application/json-patch+json"}
        
        async with httpx.AsyncClient() as client:
            separator = "&" if "?" in url else "?"
            full_url = f"{url}{separator}api-version={self.API_VERSION}"
            
            response = await client.patch(
                full_url,
                headers=headers,
                json=operations,
                timeout=30.0
            )
            
            if response.status_code >= 400:
                logger.error(f"Failed to update work item: {response.text}")
                raise AzureDevOpsAPIError(f"Failed to update work item: {response.text}")
            
            return response.json()
    
    async def get_work_item(self, work_item_id: int, expand: str = "all") -> Dict[str, Any]:
        """Get a work item by ID"""
        url = f"{self.organization_url}/_apis/wit/workitems/{work_item_id}?$expand={expand}"
        return await self._request("GET", url)
    
    async def add_work_item_link(
        self,
        work_item_id: int,
        target_work_item_id: int,
        link_type: str = "System.LinkTypes.Hierarchy-Forward"  # Parent-Child
    ) -> Dict[str, Any]:
        """Add a link between work items (e.g., parent-child relationship)"""
        url = f"{self.organization_url}/_apis/wit/workitems/{work_item_id}"
        
        # The relation URL format for Azure DevOps
        target_url = f"{self.organization_url}/_apis/wit/workItems/{target_work_item_id}"
        
        operations = [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": link_type,
                    "url": target_url
                }
            }
        ]
        
        headers = {**self.headers, "Content-Type": "application/json-patch+json"}
        
        async with httpx.AsyncClient() as client:
            separator = "&" if "?" in url else "?"
            full_url = f"{url}{separator}api-version={self.API_VERSION}"
            
            response = await client.patch(
                full_url,
                headers=headers,
                json=operations,
                timeout=30.0
            )
            
            if response.status_code >= 400:
                logger.error(f"Failed to add work item link: {response.text}")
                raise AzureDevOpsAPIError(f"Failed to add work item link: {response.text}")
            
            return response.json()
    
    def _markdown_to_html(self, text: str) -> str:
        """Convert basic markdown to HTML for Azure DevOps description field"""
        import re
        
        # Headers
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        
        # Bold and italic
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        
        # Lists
        text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'^• (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        
        # Line breaks
        text = text.replace('\n\n', '</p><p>')
        text = text.replace('\n', '<br/>')
        
        # Wrap in paragraph
        if not text.startswith('<'):
            text = f"<p>{text}</p>"
        
        return text


def compute_payload_hash(payload: Dict) -> str:
    """Compute SHA256 hash of payload for idempotency checking"""
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(payload_str.encode()).hexdigest()


class AzureDevOpsPushService:
    """
    Service for pushing JarlPM items to Azure DevOps.
    Handles idempotent create/update operations.
    """
    
    def __init__(self, rest_service: AzureDevOpsRESTService):
        self.ado = rest_service
    
    def format_epic_description(self, epic: Dict, snapshot: Dict, format_type: str = "html") -> str:
        """Format epic data as Azure DevOps description"""
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
    
    def format_feature_description(self, feature: Dict, format_type: str = "html") -> str:
        """Format feature data as Azure DevOps description"""
        parts = [feature.get("description", "")]
        
        if feature.get("acceptance_criteria"):
            ac_text = "\n".join([f"- {ac}" for ac in feature["acceptance_criteria"]])
            parts.append(f"\n## Acceptance Criteria\n{ac_text}")
        
        parts.append(f"\n---\n*Synced from JarlPM • Feature ID: {feature.get('feature_id')}*")
        
        return "\n".join(parts)
    
    def format_story_description(self, story: Dict, format_type: str = "html") -> str:
        """Format user story data as Azure DevOps description"""
        parts = []
        
        # User story format
        parts.append(f"**As a** {story.get('persona', 'user')}")
        parts.append(f"**I want to** {story.get('action', '')}")
        parts.append(f"**So that** {story.get('benefit', '')}")
        
        if story.get("acceptance_criteria"):
            parts.append("\n## Acceptance Criteria")
            for ac in story["acceptance_criteria"]:
                parts.append(f"- {ac}")
        
        parts.append(f"\n---\n*Synced from JarlPM • Story ID: {story.get('story_id')}*")
        
        return "\n".join(parts)
    
    async def push_item(
        self,
        project_name: str,
        work_item_type: str,
        title: str,
        description: str,
        entity_type: str,
        entity_id: str,
        existing_work_item_id: Optional[int] = None,
        parent_work_item_id: Optional[int] = None,
        area_path: Optional[str] = None,
        iteration_path: Optional[str] = None,
        story_points: Optional[int] = None,
        story_points_field: str = "Microsoft.VSTS.Scheduling.StoryPoints",
        tags: Optional[List[str]] = None,
        description_format: str = "html"
    ) -> Dict[str, Any]:
        """
        Push a single item to Azure DevOps (create or update).
        Returns the work item data with ID and URL.
        """
        payload = {
            "title": title,
            "description": description,
            "entity_type": entity_type,
            "entity_id": entity_id
        }
        payload_hash = compute_payload_hash(payload)
        
        if existing_work_item_id:
            # Update existing work item
            work_item = await self.ado.update_work_item(
                work_item_id=existing_work_item_id,
                title=title,
                description=description,
                story_points=story_points,
                story_points_field=story_points_field,
                tags=tags,
                description_format=description_format
            )
            action = "updated"
        else:
            # Create new work item
            work_item = await self.ado.create_work_item(
                project_name=project_name,
                work_item_type=work_item_type,
                title=title,
                description=description,
                area_path=area_path,
                iteration_path=iteration_path,
                story_points=story_points,
                story_points_field=story_points_field,
                tags=tags,
                description_format=description_format
            )
            action = "created"
            
            # Add parent-child relationship if parent exists
            if parent_work_item_id:
                try:
                    await self.ado.add_work_item_link(
                        work_item_id=work_item["id"],
                        target_work_item_id=parent_work_item_id,
                        link_type="System.LinkTypes.Hierarchy-Reverse"  # Child points to Parent
                    )
                except Exception as e:
                    logger.warning(f"Failed to link work item to parent: {e}")
        
        work_item_id = work_item.get("id")
        work_item_url = work_item.get("_links", {}).get("html", {}).get("href", "")
        
        # Build URL if not provided
        if not work_item_url:
            work_item_url = f"{self.ado.organization_url}/_workitems/edit/{work_item_id}"
        
        return {
            "action": action,
            "id": work_item_id,
            "url": work_item_url,
            "payload_hash": payload_hash
        }
