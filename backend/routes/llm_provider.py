from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import logging

from models.llm_provider import LLMProvider, LLMProviderConfig, LLMProviderConfigCreate, LLMProviderConfigResponse
from services.encryption import get_encryption_service
from services.llm_service import LLMService
from routes.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])


class ValidateKeyRequest(BaseModel):
    provider: LLMProvider
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None


@router.get("", response_model=List[LLMProviderConfigResponse])
async def list_llm_providers(request: Request):
    """List all LLM provider configurations for the current user"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    cursor = db.llm_provider_configs.find(
        {"user_id": user_id},
        {"_id": 0, "encrypted_api_key": 0}  # Never return encrypted key
    )
    configs = await cursor.to_list(100)
    
    return [LLMProviderConfigResponse(**c) for c in configs]


@router.post("", response_model=LLMProviderConfigResponse)
async def create_llm_provider(request: Request, body: LLMProviderConfigCreate):
    """Create or update an LLM provider configuration"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    encryption = get_encryption_service()
    llm_service = LLMService(db)
    
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
            detail=f"Invalid API key for {body.provider.value}. Please check your key and try again."
        )
    
    # Encrypt the API key
    encrypted_key = encryption.encrypt(body.api_key)
    
    # Check if config exists for this provider
    existing = await db.llm_provider_configs.find_one(
        {"user_id": user_id, "provider": body.provider.value},
        {"_id": 0}
    )
    
    import uuid
    
    if existing:
        # Update existing config
        await db.llm_provider_configs.update_one(
            {"user_id": user_id, "provider": body.provider.value},
            {
                "$set": {
                    "encrypted_api_key": encrypted_key,
                    "base_url": body.base_url,
                    "model_name": body.model_name,
                    "is_active": True,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        config_id = existing["config_id"]
    else:
        # Create new config
        config_id = f"llm_{uuid.uuid4().hex[:12]}"
        config_doc = {
            "config_id": config_id,
            "user_id": user_id,
            "provider": body.provider.value,
            "encrypted_api_key": encrypted_key,
            "base_url": body.base_url,
            "model_name": body.model_name,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await db.llm_provider_configs.insert_one(config_doc)
    
    # Deactivate other providers (only one active at a time)
    await db.llm_provider_configs.update_many(
        {"user_id": user_id, "provider": {"$ne": body.provider.value}},
        {"$set": {"is_active": False}}
    )
    
    return LLMProviderConfigResponse(
        config_id=config_id,
        provider=body.provider,
        base_url=body.base_url,
        model_name=body.model_name,
        is_active=True,
        created_at=existing["created_at"] if existing else datetime.now(timezone.utc)
    )


@router.post("/validate")
async def validate_api_key(request: Request, body: ValidateKeyRequest):
    """Validate an API key without saving it"""
    db = request.app.state.db
    await get_current_user_id(request)  # Ensure authenticated
    
    llm_service = LLMService(db)
    is_valid = await llm_service.validate_api_key(
        body.provider,
        body.api_key,
        body.base_url,
        body.model_name
    )
    
    return {"valid": is_valid}


@router.delete("/{config_id}")
async def delete_llm_provider(request: Request, config_id: str):
    """Delete an LLM provider configuration"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    result = await db.llm_provider_configs.delete_one(
        {"config_id": config_id, "user_id": user_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return {"message": "Configuration deleted"}


@router.put("/{config_id}/activate")
async def activate_llm_provider(request: Request, config_id: str):
    """Activate an LLM provider (and deactivate others)"""
    db = request.app.state.db
    user_id = await get_current_user_id(request)
    
    # Check if config exists
    config = await db.llm_provider_configs.find_one(
        {"config_id": config_id, "user_id": user_id},
        {"_id": 0}
    )
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Deactivate all
    await db.llm_provider_configs.update_many(
        {"user_id": user_id},
        {"$set": {"is_active": False}}
    )
    
    # Activate this one
    await db.llm_provider_configs.update_one(
        {"config_id": config_id},
        {"$set": {"is_active": True, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Configuration activated"}
