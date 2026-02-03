"""
Export Service for JarlPM
Handles export to Jira, Azure DevOps, and file formats (CSV, JSON, Markdown)
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import json
import csv
import io
import base64
import httpx
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Epic, EpicSnapshot, Bug
from db.feature_models import Feature
from db.user_story_models import UserStory

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    JIRA_CSV = "jira_csv"
    AZURE_DEVOPS_CSV = "azure_devops_csv"
    JSON = "json"
    MARKDOWN = "markdown"


class ExportPlatform(str, Enum):
    JIRA = "jira"
    AZURE_DEVOPS = "azure_devops"


# Field mappings for JarlPM -> External platforms
JIRA_FIELD_MAPPING = {
    "epic": {
        "issue_type": "Epic",
        "fields": {
            "title": "Summary",
            "problem_statement": "Description",
            "moscow_score": "Priority",  # Will be mapped to Jira priority
            "acceptance_criteria": "Acceptance Criteria",
        }
    },
    "feature": {
        "issue_type": "Story",
        "fields": {
            "title": "Summary",
            "description": "Description",
            "moscow_score": "Priority",
            "acceptance_criteria": "Acceptance Criteria",
            "rice_total": "Story Points",  # Approximate mapping
        }
    },
    "user_story": {
        "issue_type": "Sub-task",
        "fields": {
            "story_text": "Summary",
            "acceptance_criteria": "Acceptance Criteria",
            "story_points": "Story Points",
            "rice_total": "Custom Field (RICE)",
        }
    },
    "bug": {
        "issue_type": "Bug",
        "fields": {
            "title": "Summary",
            "description": "Description",
            "severity": "Priority",
            "steps_to_reproduce": "Steps to Reproduce",
            "expected_behavior": "Expected Result",
            "actual_behavior": "Actual Result",
            "rice_total": "Custom Field (RICE)",
        }
    }
}

AZURE_DEVOPS_FIELD_MAPPING = {
    "epic": {
        "work_item_type": "Epic",
        "fields": {
            "title": "System.Title",
            "problem_statement": "System.Description",
            "moscow_score": "Microsoft.VSTS.Common.Priority",
            "acceptance_criteria": "Microsoft.VSTS.Common.AcceptanceCriteria",
        }
    },
    "feature": {
        "work_item_type": "Feature",
        "fields": {
            "title": "System.Title",
            "description": "System.Description",
            "moscow_score": "Microsoft.VSTS.Common.Priority",
            "acceptance_criteria": "Microsoft.VSTS.Common.AcceptanceCriteria",
            "rice_total": "Microsoft.VSTS.Scheduling.StoryPoints",
        }
    },
    "user_story": {
        "work_item_type": "User Story",
        "fields": {
            "story_text": "System.Title",
            "acceptance_criteria": "Microsoft.VSTS.Common.AcceptanceCriteria",
            "story_points": "Microsoft.VSTS.Scheduling.StoryPoints",
        }
    },
    "bug": {
        "work_item_type": "Bug",
        "fields": {
            "title": "System.Title",
            "description": "System.Description",
            "severity": "Microsoft.VSTS.Common.Severity",
            "steps_to_reproduce": "Microsoft.VSTS.TCM.ReproSteps",
        }
    }
}

# MoSCoW to Priority mapping
MOSCOW_TO_PRIORITY = {
    "must_have": 1,  # Highest/Critical
    "should_have": 2,  # High
    "could_have": 3,  # Medium
    "wont_have": 4,  # Low
}

MOSCOW_TO_JIRA_PRIORITY = {
    "must_have": "Highest",
    "should_have": "High", 
    "could_have": "Medium",
    "wont_have": "Low",
}

SEVERITY_TO_AZURE = {
    "critical": "1 - Critical",
    "major": "2 - High",
    "minor": "3 - Medium",
    "trivial": "4 - Low",
}


class ExportService:
    """Service for exporting JarlPM data to external platforms and file formats"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # ============================================
    # Data Retrieval
    # ============================================
    
    async def get_epic_with_all_children(self, epic_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get an epic with all its features, stories, and bugs for export"""
        result = await self.session.execute(
            select(Epic)
            .options(
                selectinload(Epic.snapshot),
                selectinload(Epic.features).selectinload(Feature.user_stories)
            )
            .where(Epic.epic_id == epic_id, Epic.user_id == user_id)
        )
        epic = result.scalar_one_or_none()
        
        if not epic:
            return None
        
        # Convert to dict for export
        epic_data = {
            "epic_id": epic.epic_id,
            "title": epic.title,
            "current_stage": epic.current_stage,
            "moscow_score": epic.moscow_score,
            "problem_statement": epic.snapshot.problem_statement if epic.snapshot else None,
            "desired_outcome": epic.snapshot.desired_outcome if epic.snapshot else None,
            "acceptance_criteria": epic.snapshot.acceptance_criteria if epic.snapshot else [],
            "created_at": epic.created_at.isoformat() if epic.created_at else None,
            "features": [],
        }
        
        for feature in epic.features:
            feature_data = {
                "feature_id": feature.feature_id,
                "title": feature.title,
                "description": feature.description,
                "current_stage": feature.current_stage,
                "moscow_score": feature.moscow_score,
                "rice_reach": feature.rice_reach,
                "rice_impact": feature.rice_impact,
                "rice_confidence": feature.rice_confidence,
                "rice_effort": feature.rice_effort,
                "rice_total": feature.rice_total,
                "acceptance_criteria": feature.acceptance_criteria or [],
                "user_stories": [],
            }
            
            for story in feature.user_stories:
                story_data = {
                    "story_id": story.story_id,
                    "story_text": story.story_text,
                    "persona": story.persona,
                    "action": story.action,
                    "benefit": story.benefit,
                    "current_stage": story.current_stage,
                    "story_points": story.story_points,
                    "rice_reach": story.rice_reach,
                    "rice_impact": story.rice_impact,
                    "rice_confidence": story.rice_confidence,
                    "rice_effort": story.rice_effort,
                    "rice_total": story.rice_total,
                    "acceptance_criteria": story.acceptance_criteria or [],
                }
                feature_data["user_stories"].append(story_data)
            
            epic_data["features"].append(feature_data)
        
        return epic_data
    
    async def get_bugs_for_export(self, user_id: str, epic_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get bugs for export, optionally filtered by epic"""
        query = select(Bug).where(Bug.user_id == user_id, Bug.is_deleted.is_(False))
        
        result = await self.session.execute(query)
        bugs = result.scalars().all()
        
        bug_list = []
        for bug in bugs:
            bug_data = {
                "bug_id": bug.bug_id,
                "title": bug.title,
                "description": bug.description,
                "severity": bug.severity,
                "status": bug.status,
                "steps_to_reproduce": bug.steps_to_reproduce,
                "expected_behavior": bug.expected_behavior,
                "actual_behavior": bug.actual_behavior,
                "rice_reach": bug.rice_reach,
                "rice_impact": bug.rice_impact,
                "rice_confidence": bug.rice_confidence,
                "rice_effort": bug.rice_effort,
                "rice_total": bug.rice_total,
                "created_at": bug.created_at.isoformat() if bug.created_at else None,
            }
            bug_list.append(bug_data)
        
        return bug_list
    
    # ============================================
    # File Export (CSV, JSON, Markdown)
    # ============================================
    
    def export_to_jira_csv(self, epic_data: Dict[str, Any], bugs: List[Dict[str, Any]]) -> str:
        """Export to Jira-compatible CSV format"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Jira CSV headers
        headers = [
            "Issue Type", "Summary", "Description", "Priority", 
            "Acceptance Criteria", "Story Points", "Parent", "Labels"
        ]
        writer.writerow(headers)
        
        # Export Epic
        epic_row = [
            "Epic",
            epic_data["title"],
            epic_data.get("problem_statement") or "",
            MOSCOW_TO_JIRA_PRIORITY.get(epic_data.get("moscow_score"), "Medium"),
            "\n".join(epic_data.get("acceptance_criteria") or []),
            "",
            "",
            "jarlpm-export"
        ]
        writer.writerow(epic_row)
        
        # Export Features as Stories
        for feature in epic_data.get("features") or []:
            feature_row = [
                "Story",
                feature["title"],
                feature.get("description") or "",
                MOSCOW_TO_JIRA_PRIORITY.get(feature.get("moscow_score"), "Medium"),
                "\n".join(feature.get("acceptance_criteria") or []),
                str(feature.get("rice_total", "")) if feature.get("rice_total") else "",
                epic_data["title"],  # Parent epic
                "jarlpm-export,feature"
            ]
            writer.writerow(feature_row)
            
            # Export User Stories as Sub-tasks
            for story in feature.get("user_stories") or []:
                story_row = [
                    "Sub-task",
                    story["story_text"],
                    f"Persona: {story.get('persona') or ''}\nAction: {story.get('action') or ''}\nBenefit: {story.get('benefit') or ''}",
                    "Medium",
                    "\n".join(story.get("acceptance_criteria") or []),
                    str(story.get("story_points", "")) if story.get("story_points") else "",
                    feature["title"],  # Parent story/feature
                    "jarlpm-export,user-story"
                ]
                writer.writerow(story_row)
        
        # Export Bugs
        for bug in bugs:
            bug_row = [
                "Bug",
                bug["title"],
                f"{bug.get('description', '')}\n\nSteps to Reproduce:\n{bug.get('steps_to_reproduce', '')}\n\nExpected: {bug.get('expected_behavior', '')}\n\nActual: {bug.get('actual_behavior', '')}",
                MOSCOW_TO_JIRA_PRIORITY.get(bug.get("severity", "minor").lower(), "Medium"),
                "",
                "",
                "",
                "jarlpm-export,bug"
            ]
            writer.writerow(bug_row)
        
        return output.getvalue()
    
    def export_to_azure_devops_csv(self, epic_data: Dict[str, Any], bugs: List[Dict[str, Any]]) -> str:
        """Export to Azure DevOps-compatible CSV format"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Azure DevOps CSV headers
        headers = [
            "Work Item Type", "Title", "Description", "Priority", 
            "Acceptance Criteria", "Story Points", "Area Path", "Tags"
        ]
        writer.writerow(headers)
        
        # Export Epic
        epic_row = [
            "Epic",
            epic_data["title"],
            epic_data.get("problem_statement") or "",
            MOSCOW_TO_PRIORITY.get(epic_data.get("moscow_score"), 3),
            "\n".join(epic_data.get("acceptance_criteria") or []),
            "",
            "",
            "jarlpm-export"
        ]
        writer.writerow(epic_row)
        
        # Export Features
        for feature in epic_data.get("features") or []:
            feature_row = [
                "Feature",
                feature["title"],
                feature.get("description") or "",
                MOSCOW_TO_PRIORITY.get(feature.get("moscow_score"), 3),
                "\n".join(feature.get("acceptance_criteria") or []),
                str(feature.get("rice_total", "")) if feature.get("rice_total") else "",
                "",
                "jarlpm-export;feature"
            ]
            writer.writerow(feature_row)
            
            # Export User Stories
            for story in feature.get("user_stories") or []:
                story_row = [
                    "User Story",
                    story["story_text"],
                    f"As a {story.get('persona') or ''}, I want to {story.get('action') or ''} so that {story.get('benefit') or ''}",
                    3,
                    "\n".join(story.get("acceptance_criteria") or []),
                    str(story.get("story_points", "")) if story.get("story_points") else "",
                    "",
                    "jarlpm-export;user-story"
                ]
                writer.writerow(story_row)
        
        # Export Bugs
        for bug in bugs:
            bug_row = [
                "Bug",
                bug["title"],
                f"{bug.get('description') or ''}\n\nSteps to Reproduce:\n{bug.get('steps_to_reproduce') or ''}\n\nExpected: {bug.get('expected_behavior') or ''}\n\nActual: {bug.get('actual_behavior') or ''}",
                MOSCOW_TO_PRIORITY.get(bug.get("severity", "minor").lower(), 3),
                "",
                "",
                "",
                "jarlpm-export;bug"
            ]
            writer.writerow(bug_row)
        
        return output.getvalue()
    
    def export_to_json(self, epic_data: Dict[str, Any], bugs: List[Dict[str, Any]]) -> str:
        """Export to JSON format"""
        export_data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": "JarlPM",
            "epic": epic_data,
            "bugs": bugs,
            "field_mappings": {
                "jira": JIRA_FIELD_MAPPING,
                "azure_devops": AZURE_DEVOPS_FIELD_MAPPING,
            }
        }
        return json.dumps(export_data, indent=2, default=str)
    
    def export_to_markdown(self, epic_data: Dict[str, Any], bugs: List[Dict[str, Any]]) -> str:
        """Export to Markdown format"""
        lines = []
        
        # Epic Header
        lines.append(f"# {epic_data['title']}")
        lines.append("")
        lines.append(f"**Stage:** {epic_data.get('current_stage', 'N/A')}")
        if epic_data.get("moscow_score"):
            lines.append(f"**Priority (MoSCoW):** {epic_data['moscow_score'].replace('_', ' ').title()}")
        lines.append(f"**Created:** {epic_data.get('created_at', 'N/A')}")
        lines.append("")
        
        # Problem Statement
        if epic_data.get("problem_statement"):
            lines.append("## Problem Statement")
            lines.append("")
            lines.append(epic_data["problem_statement"])
            lines.append("")
        
        # Desired Outcome
        if epic_data.get("desired_outcome"):
            lines.append("## Desired Outcome")
            lines.append("")
            lines.append(epic_data["desired_outcome"])
            lines.append("")
        
        # Acceptance Criteria
        if epic_data.get("acceptance_criteria"):
            lines.append("## Acceptance Criteria")
            lines.append("")
            for ac in epic_data["acceptance_criteria"]:
                lines.append(f"- {ac}")
            lines.append("")
        
        # Features
        if epic_data.get("features"):
            lines.append("## Features")
            lines.append("")
            
            for i, feature in enumerate(epic_data["features"], 1):
                lines.append(f"### {i}. {feature['title']}")
                lines.append("")
                lines.append(f"**Stage:** {feature.get('current_stage', 'N/A')}")
                if feature.get("moscow_score"):
                    lines.append(f"**Priority (MoSCoW):** {feature['moscow_score'].replace('_', ' ').title()}")
                if feature.get("rice_total"):
                    lines.append(f"**RICE Score:** {feature['rice_total']:.1f}")
                lines.append("")
                
                if feature.get("description"):
                    lines.append(feature["description"])
                    lines.append("")
                
                if feature.get("acceptance_criteria"):
                    lines.append("**Acceptance Criteria:**")
                    for ac in feature["acceptance_criteria"]:
                        lines.append(f"- {ac}")
                    lines.append("")
                
                # User Stories
                if feature.get("user_stories"):
                    lines.append("**User Stories:**")
                    lines.append("")
                    for j, story in enumerate(feature["user_stories"], 1):
                        lines.append(f"  {j}. {story['story_text']}")
                        if story.get("story_points"):
                            lines.append(f"     - Story Points: {story['story_points']}")
                        if story.get("rice_total"):
                            lines.append(f"     - RICE Score: {story['rice_total']:.1f}")
                        if story.get("acceptance_criteria"):
                            lines.append("     - Acceptance Criteria:")
                            for ac in story["acceptance_criteria"]:
                                lines.append(f"       - {ac}")
                    lines.append("")
        
        # Bugs
        if bugs:
            lines.append("## Bugs")
            lines.append("")
            
            for i, bug in enumerate(bugs, 1):
                lines.append(f"### Bug {i}: {bug['title']}")
                lines.append("")
                lines.append(f"**Severity:** {bug.get('severity', 'N/A')}")
                lines.append(f"**Status:** {bug.get('status', 'N/A')}")
                if bug.get("rice_total"):
                    lines.append(f"**RICE Score:** {bug['rice_total']:.1f}")
                lines.append("")
                
                if bug.get("description"):
                    lines.append(bug["description"])
                    lines.append("")
                
                if bug.get("steps_to_reproduce"):
                    lines.append("**Steps to Reproduce:**")
                    lines.append(bug["steps_to_reproduce"])
                    lines.append("")
                
                if bug.get("expected_behavior"):
                    lines.append(f"**Expected:** {bug['expected_behavior']}")
                
                if bug.get("actual_behavior"):
                    lines.append(f"**Actual:** {bug['actual_behavior']}")
                lines.append("")
        
        return "\n".join(lines)
    
    # ============================================
    # Direct API Integration
    # ============================================
    
    async def export_to_jira_api(
        self,
        epic_data: Dict[str, Any],
        bugs: List[Dict[str, Any]],
        jira_config: Dict[str, str]
    ) -> Dict[str, Any]:
        """Export directly to Jira via REST API"""
        base_url = jira_config["base_url"].rstrip("/")
        email = jira_config["email"]
        api_token = jira_config["api_token"]
        project_key = jira_config["project_key"]
        
        # Create auth header
        credentials = f"{email}:{api_token}"
        auth_header = f"Basic {base64.b64encode(credentials.encode()).decode()}"
        
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        results = {"created": [], "errors": []}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create Epic
            epic_payload = {
                "fields": {
                    "project": {"key": project_key},
                    "issuetype": {"name": "Epic"},
                    "summary": epic_data["title"],
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": epic_data.get("problem_statement", "") or "No description"}]}]
                    }
                }
            }
            
            try:
                response = await client.post(f"{base_url}/rest/api/3/issue", headers=headers, json=epic_payload)
                response.raise_for_status()
                epic_result = response.json()
                epic_key = epic_result["key"]
                results["created"].append({"type": "Epic", "key": epic_key, "title": epic_data["title"]})
                
                # Create Features as Stories linked to Epic
                for feature in epic_data.get("features", []):
                    feature_payload = {
                        "fields": {
                            "project": {"key": project_key},
                            "issuetype": {"name": "Story"},
                            "summary": feature["title"],
                            "description": {
                                "type": "doc",
                                "version": 1,
                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": feature.get("description", "") or "No description"}]}]
                            },
                            "parent": {"key": epic_key}  # Link to epic
                        }
                    }
                    
                    try:
                        resp = await client.post(f"{base_url}/rest/api/3/issue", headers=headers, json=feature_payload)
                        resp.raise_for_status()
                        feature_result = resp.json()
                        feature_key = feature_result["key"]
                        results["created"].append({"type": "Story", "key": feature_key, "title": feature["title"]})
                        
                        # Create User Stories as Sub-tasks
                        for story in feature.get("user_stories", []):
                            story_payload = {
                                "fields": {
                                    "project": {"key": project_key},
                                    "issuetype": {"name": "Sub-task"},
                                    "summary": story["story_text"][:255],
                                    "parent": {"key": feature_key}
                                }
                            }
                            
                            try:
                                sresp = await client.post(f"{base_url}/rest/api/3/issue", headers=headers, json=story_payload)
                                sresp.raise_for_status()
                                story_result = sresp.json()
                                results["created"].append({"type": "Sub-task", "key": story_result["key"], "title": story["story_text"][:50]})
                            except Exception as e:
                                results["errors"].append({"type": "Sub-task", "title": story["story_text"][:50], "error": str(e)})
                    
                    except Exception as e:
                        results["errors"].append({"type": "Story", "title": feature["title"], "error": str(e)})
                
                # Create Bugs
                for bug in bugs:
                    bug_payload = {
                        "fields": {
                            "project": {"key": project_key},
                            "issuetype": {"name": "Bug"},
                            "summary": bug["title"],
                            "description": {
                                "type": "doc",
                                "version": 1,
                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": bug.get("description", "") or "No description"}]}]
                            }
                        }
                    }
                    
                    try:
                        bresp = await client.post(f"{base_url}/rest/api/3/issue", headers=headers, json=bug_payload)
                        bresp.raise_for_status()
                        bug_result = bresp.json()
                        results["created"].append({"type": "Bug", "key": bug_result["key"], "title": bug["title"]})
                    except Exception as e:
                        results["errors"].append({"type": "Bug", "title": bug["title"], "error": str(e)})
            
            except Exception as e:
                results["errors"].append({"type": "Epic", "title": epic_data["title"], "error": str(e)})
        
        return results
    
    async def export_to_azure_devops_api(
        self,
        epic_data: Dict[str, Any],
        bugs: List[Dict[str, Any]],
        azure_config: Dict[str, str]
    ) -> Dict[str, Any]:
        """Export directly to Azure DevOps via REST API"""
        organization = azure_config["organization"]
        project = azure_config["project"]
        pat = azure_config["pat"]
        
        base_url = f"https://dev.azure.com/{organization}/{project}/_apis"
        
        # Create auth header
        credentials = f":{pat}"
        auth_header = f"Basic {base64.b64encode(credentials.encode()).decode()}"
        
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json-patch+json",
            "Accept": "application/json"
        }
        
        results = {"created": [], "errors": []}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create Epic
            epic_patch = [
                {"op": "add", "path": "/fields/System.Title", "value": epic_data["title"]},
                {"op": "add", "path": "/fields/System.Description", "value": epic_data.get("problem_statement", "") or "No description"},
            ]
            if epic_data.get("moscow_score"):
                epic_patch.append({"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": MOSCOW_TO_PRIORITY.get(epic_data["moscow_score"], 3)})
            
            try:
                response = await client.patch(
                    f"{base_url}/wit/workitems/$Epic?api-version=7.1",
                    headers=headers,
                    json=epic_patch
                )
                response.raise_for_status()
                epic_result = response.json()
                epic_id = epic_result["id"]
                results["created"].append({"type": "Epic", "id": epic_id, "title": epic_data["title"]})
                
                # Create Features linked to Epic
                for feature in epic_data.get("features", []):
                    feature_patch = [
                        {"op": "add", "path": "/fields/System.Title", "value": feature["title"]},
                        {"op": "add", "path": "/fields/System.Description", "value": feature.get("description", "") or "No description"},
                    ]
                    if feature.get("moscow_score"):
                        feature_patch.append({"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": MOSCOW_TO_PRIORITY.get(feature["moscow_score"], 3)})
                    if feature.get("rice_total"):
                        feature_patch.append({"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.StoryPoints", "value": feature["rice_total"]})
                    
                    # Link to parent Epic
                    feature_patch.append({
                        "op": "add",
                        "path": "/relations/-",
                        "value": {
                            "rel": "System.LinkTypes.Hierarchy-Reverse",
                            "url": f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{epic_id}"
                        }
                    })
                    
                    try:
                        fresp = await client.patch(
                            f"{base_url}/wit/workitems/$Feature?api-version=7.1",
                            headers=headers,
                            json=feature_patch
                        )
                        fresp.raise_for_status()
                        feature_result = fresp.json()
                        feature_id = feature_result["id"]
                        results["created"].append({"type": "Feature", "id": feature_id, "title": feature["title"]})
                        
                        # Create User Stories linked to Feature
                        for story in feature.get("user_stories", []):
                            story_patch = [
                                {"op": "add", "path": "/fields/System.Title", "value": story["story_text"][:255]},
                            ]
                            if story.get("story_points"):
                                story_patch.append({"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.StoryPoints", "value": story["story_points"]})
                            
                            story_patch.append({
                                "op": "add",
                                "path": "/relations/-",
                                "value": {
                                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                                    "url": f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{feature_id}"
                                }
                            })
                            
                            try:
                                sresp = await client.patch(
                                    f"{base_url}/wit/workitems/$User Story?api-version=7.1",
                                    headers=headers,
                                    json=story_patch
                                )
                                sresp.raise_for_status()
                                story_result = sresp.json()
                                results["created"].append({"type": "User Story", "id": story_result["id"], "title": story["story_text"][:50]})
                            except Exception as e:
                                results["errors"].append({"type": "User Story", "title": story["story_text"][:50], "error": str(e)})
                    
                    except Exception as e:
                        results["errors"].append({"type": "Feature", "title": feature["title"], "error": str(e)})
                
                # Create Bugs
                for bug in bugs:
                    bug_patch = [
                        {"op": "add", "path": "/fields/System.Title", "value": bug["title"]},
                        {"op": "add", "path": "/fields/System.Description", "value": bug.get("description", "") or "No description"},
                    ]
                    if bug.get("severity"):
                        bug_patch.append({"op": "add", "path": "/fields/Microsoft.VSTS.Common.Severity", "value": SEVERITY_TO_AZURE.get(bug["severity"].lower(), "3 - Medium")})
                    
                    try:
                        bresp = await client.patch(
                            f"{base_url}/wit/workitems/$Bug?api-version=7.1",
                            headers=headers,
                            json=bug_patch
                        )
                        bresp.raise_for_status()
                        bug_result = bresp.json()
                        results["created"].append({"type": "Bug", "id": bug_result["id"], "title": bug["title"]})
                    except Exception as e:
                        results["errors"].append({"type": "Bug", "title": bug["title"], "error": str(e)})
            
            except Exception as e:
                results["errors"].append({"type": "Epic", "title": epic_data["title"], "error": str(e)})
        
        return results
