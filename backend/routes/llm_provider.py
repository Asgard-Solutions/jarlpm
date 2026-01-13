from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import logging
import uuid

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.models import LLMProviderConfig, LLMProvider
from services.encryption import get_encryption_service
from services.llm_service import LLMService
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])


class LLMProviderConfigCreate(BaseModel):
    provider: LLMProvider
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None


class LLMProviderConfigResponse(BaseModel):
    config_id: str
    provider: LLMProvider
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    is_active: bool
    created_at: datetime


class ValidateKeyRequest(BaseModel):
    provider: LLMProvider
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None


@router.get("", response_model=List[LLMProviderConfigResponse])
async def list_llm_providers(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """List all LLM provider configurations for the current user"""
    user_id = await get_current_user_id(request, session)
    
    result = await session.execute(
        select(LLMProviderConfig).where(LLMProviderConfig.user_id == user_id)
    )
    configs = result.scalars().all()
    
    return [LLMProviderConfigResponse(
        config_id=c.config_id,
        provider=c.provider,
        base_url=c.base_url,
        model_name=c.model_name,
        is_active=c.is_active,
        created_at=c.created_at
    ) for c in configs]


@router.post("", response_model=LLMProviderConfigResponse)
async def create_llm_provider(
    request: Request, 
    body: LLMProviderConfigCreate,
    session: AsyncSession = Depends(get_db)
):
    """Create or update an LLM provider configuration"""
    user_id = await get_current_user_id(request, session)
    encryption = get_encryption_service()
    llm_service = LLMService(session)
    
    # Get provider value as string
    provider_value = body.provider.value if isinstance(body.provider, LLMProvider) else body.provider
    
    # Validate the API key first
    is_valid = await llm_service.validate_api_key(
        body.provider,
        body.api_key,
        body.base_url,
        body.model_name
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid API key for {provider_value}. Please check your key and try again."
        )
    
    # Encrypt the API key
    encrypted_key = encryption.encrypt(body.api_key)
    
    # Check if config exists for this provider
    result = await session.execute(
        select(LLMProviderConfig).where(
            LLMProviderConfig.user_id == user_id,
            LLMProviderConfig.provider == provider_value
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing config
        existing.encrypted_api_key = encrypted_key
        existing.base_url = body.base_url
        existing.model_name = body.model_name
        existing.is_active = True
        existing.updated_at = datetime.now(timezone.utc)
        config_id = existing.config_id
        created_at = existing.created_at
    else:
        # Create new config
        new_config = LLMProviderConfig(
            user_id=user_id,
            provider=provider_value,
            encrypted_api_key=encrypted_key,
            base_url=body.base_url,
            model_name=body.model_name,
            is_active=True
        )
        session.add(new_config)
        await session.flush()
        config_id = new_config.config_id
        created_at = new_config.created_at
    
    # Deactivate other providers (only one active at a time)
    await session.execute(
        update(LLMProviderConfig)
        .where(
            LLMProviderConfig.user_id == user_id,
            LLMProviderConfig.provider != provider_value
        )
        .values(is_active=False)
    )
    
    await session.commit()
    
    return LLMProviderConfigResponse(
        config_id=config_id,
        provider=body.provider,
        base_url=body.base_url,
        model_name=body.model_name,
        is_active=True,
        created_at=created_at
    )


@router.post("/validate")
async def validate_api_key(
    request: Request, 
    body: ValidateKeyRequest,
    session: AsyncSession = Depends(get_db)
):
    """Validate an API key without saving it"""
    await get_current_user_id(request, session)  # Ensure authenticated
    
    llm_service = LLMService(session)
    is_valid = await llm_service.validate_api_key(
        body.provider,
        body.api_key,
        body.base_url,
        body.model_name
    )
    
    return {"valid": is_valid}


@router.delete("/{config_id}")
async def delete_llm_provider(
    request: Request, 
    config_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Delete an LLM provider configuration"""
    user_id = await get_current_user_id(request, session)
    
    result = await session.execute(
        delete(LLMProviderConfig)
        .where(LLMProviderConfig.config_id == config_id, LLMProviderConfig.user_id == user_id)
    )
    await session.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return {"message": "Configuration deleted"}


@router.put("/{config_id}/activate")
async def activate_llm_provider(
    request: Request, 
    config_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Activate an LLM provider (and deactivate others)"""
    user_id = await get_current_user_id(request, session)
    
    # Check if config exists
    result = await session.execute(
        select(LLMProviderConfig).where(
            LLMProviderConfig.config_id == config_id,
            LLMProviderConfig.user_id == user_id
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Deactivate all
    await session.execute(
        update(LLMProviderConfig)
        .where(LLMProviderConfig.user_id == user_id)
        .values(is_active=False)
    )
    
    # Activate this one
    config.is_active = True
    config.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return {"message": "Configuration activated"}
