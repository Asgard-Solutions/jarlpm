"""
Shared utilities, models, and helpers for integration routes.
"""
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime, timezone, timedelta
import logging

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Subscription, SubscriptionStatus
from services.subscription_helper import is_subscription_active, get_user_subscription
from db.integration_models import (
    ExternalIntegration, IntegrationProvider, IntegrationStatus
)
from services.encryption import get_encryption_service
from services.linear_service import LinearOAuthService, LinearGraphQLService
from services.jira_service import JiraOAuthService, JiraRESTService
from services.azure_devops_service import AzureDevOpsRESTService

logger = logging.getLogger(__name__)


# ============================================
# Shared Pydantic Models
# ============================================

class IntegrationStatusResponse(BaseModel):
    provider: str
    status: str
    account_name: Optional[str] = None
    default_team: Optional[dict] = None
    default_project: Optional[dict] = None
    connected_at: Optional[datetime] = None


class PushPreviewRequest(BaseModel):
    epic_id: str
    push_scope: Literal["epic_only", "epic_features", "epic_features_stories"] = "epic_features_stories"
    include_bugs: bool = False


# ============================================
# Linear-specific models
# ============================================

class ConnectLinearRequest(BaseModel):
    frontend_callback_url: str


class ConfigureLinearRequest(BaseModel):
    team_id: str
    team_name: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    priority_mapping: Optional[dict] = None
    label_policy: Optional[str] = "create-missing"
    epic_mapping: Optional[str] = "issue"
    field_mappings: Optional[dict] = None


class LinearPushRequest(BaseModel):
    epic_id: str
    team_id: str
    project_id: Optional[str] = None
    push_scope: Literal["epic_only", "epic_features", "epic_features_stories"] = "epic_features_stories"
    include_bugs: bool = False
    dry_run: bool = False
    epic_mapping: Optional[str] = None
    priority_mapping: Optional[dict] = None
    label_policy: Optional[str] = None


# ============================================
# Jira-specific models
# ============================================

class ConnectJiraRequest(BaseModel):
    frontend_callback_url: str


class ConfigureJiraRequest(BaseModel):
    cloud_id: str
    site_name: str
    project_key: str
    project_name: str
    issue_type_mapping: Optional[dict] = None
    story_points_field: Optional[str] = None
    epic_link_field: Optional[str] = None
    label_prefix: Optional[str] = None


class JiraPushRequest(BaseModel):
    epic_id: str
    project_key: str
    push_scope: Literal["epic_only", "epic_features", "epic_features_stories", "full"] = "epic_features_stories"
    include_bugs: bool = False
    dry_run: bool = False


# ============================================
# Azure DevOps-specific models
# ============================================

class ConnectAzureDevOpsRequest(BaseModel):
    organization_url: str
    pat: str


class ConfigureAzureDevOpsRequest(BaseModel):
    organization_url: str
    project_name: str
    project_id: Optional[str] = None
    default_area_path: Optional[str] = None
    default_iteration_path: Optional[str] = None
    story_points_field: Optional[str] = "Microsoft.VSTS.Scheduling.StoryPoints"
    description_format: Optional[str] = "html"
    tag_policy: Optional[str] = "add"
    work_item_types: Optional[dict] = None


class AzureDevOpsPushRequest(BaseModel):
    epic_id: str
    project_name: str
    area_path: Optional[str] = None
    iteration_path: Optional[str] = None
    push_scope: Literal["epic_only", "epic_features", "epic_features_stories", "full"] = "epic_features_stories"
    include_bugs: bool = False
    dry_run: bool = False


# ============================================
# Helper functions
# ============================================

async def check_subscription_required(session: AsyncSession, user_id: str):
    """Check if user has an active subscription. Raise 402 if not."""
    subscription = await get_user_subscription(session, user_id)
    if not is_subscription_active(subscription):
        raise HTTPException(status_code=402, detail="Active subscription required for integrations")


async def get_user_integration(
    session: AsyncSession, 
    user_id: str, 
    provider: str
) -> Optional[ExternalIntegration]:
    """Get user's integration for a specific provider"""
    result = await session.execute(
        select(ExternalIntegration).where(
            and_(
                ExternalIntegration.user_id == user_id,
                ExternalIntegration.provider == provider
            )
        )
    )
    return result.scalar_one_or_none()


async def get_linear_service(session: AsyncSession, user_id: str) -> LinearGraphQLService:
    """Get authenticated Linear GraphQL service for user"""
    integration = await get_user_integration(session, user_id, IntegrationProvider.LINEAR.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Linear integration not connected")
    
    if not integration.access_token_encrypted:
        raise HTTPException(status_code=400, detail="Linear tokens not found")
    
    # Check token expiration
    if integration.token_expires_at and integration.token_expires_at < datetime.now(timezone.utc):
        if integration.refresh_token_encrypted:
            try:
                encryption = get_encryption_service()
                refresh_token = encryption.decrypt(integration.refresh_token_encrypted)
                
                oauth = LinearOAuthService()
                new_tokens = await oauth.refresh_access_token(refresh_token)
                
                integration.access_token_encrypted = encryption.encrypt(new_tokens["access_token"])
                if new_tokens.get("refresh_token"):
                    integration.refresh_token_encrypted = encryption.encrypt(new_tokens["refresh_token"])
                integration.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=new_tokens.get("expires_in", 86400)
                )
                await session.commit()
                
                return LinearGraphQLService(new_tokens["access_token"])
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                integration.status = IntegrationStatus.ERROR.value
                await session.commit()
                raise HTTPException(status_code=401, detail="Linear token expired. Please reconnect.")
        else:
            raise HTTPException(status_code=401, detail="Linear token expired. Please reconnect.")
    
    encryption = get_encryption_service()
    access_token = encryption.decrypt(integration.access_token_encrypted)
    return LinearGraphQLService(access_token)


async def get_jira_service(session: AsyncSession, user_id: str) -> JiraRESTService:
    """Get authenticated Jira REST service for user"""
    integration = await get_user_integration(session, user_id, IntegrationProvider.JIRA.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Jira integration not connected")
    
    if not integration.access_token_encrypted:
        raise HTTPException(status_code=400, detail="Jira tokens not found")
    
    if not integration.external_account_id:
        raise HTTPException(status_code=400, detail="Jira cloud ID not found")
    
    if integration.token_expires_at and integration.token_expires_at < datetime.now(timezone.utc):
        if integration.refresh_token_encrypted:
            try:
                encryption = get_encryption_service()
                refresh_token = encryption.decrypt(integration.refresh_token_encrypted)
                
                oauth = JiraOAuthService()
                new_tokens = await oauth.refresh_access_token(refresh_token)
                
                integration.access_token_encrypted = encryption.encrypt(new_tokens["access_token"])
                if new_tokens.get("refresh_token"):
                    integration.refresh_token_encrypted = encryption.encrypt(new_tokens["refresh_token"])
                integration.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=new_tokens.get("expires_in", 3600)
                )
                await session.commit()
                
                return JiraRESTService(new_tokens["access_token"], integration.external_account_id)
            except Exception as e:
                logger.error(f"Jira token refresh failed: {e}")
                integration.status = IntegrationStatus.ERROR.value
                await session.commit()
                raise HTTPException(status_code=401, detail="Jira token expired. Please reconnect.")
        else:
            raise HTTPException(status_code=401, detail="Jira token expired. Please reconnect.")
    
    encryption = get_encryption_service()
    access_token = encryption.decrypt(integration.access_token_encrypted)
    return JiraRESTService(access_token, integration.external_account_id)


async def get_azure_devops_service(session: AsyncSession, user_id: str) -> AzureDevOpsRESTService:
    """Get authenticated Azure DevOps REST service for user"""
    integration = await get_user_integration(session, user_id, IntegrationProvider.AZURE_DEVOPS.value)
    
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise HTTPException(status_code=400, detail="Azure DevOps integration not connected")
    
    if not integration.pat_encrypted:
        raise HTTPException(status_code=400, detail="Azure DevOps PAT not found")
    
    if not integration.org_url:
        raise HTTPException(status_code=400, detail="Azure DevOps organization URL not found")
    
    encryption = get_encryption_service()
    pat = encryption.decrypt(integration.pat_encrypted)
    return AzureDevOpsRESTService(integration.org_url, pat)
