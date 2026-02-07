from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
import uuid


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LOCAL = "local"


class LLMProviderConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    config_id: str = Field(default_factory=lambda: f"llm_{uuid.uuid4().hex[:12]}")
    user_id: str
    provider: LLMProvider
    # Encrypted API key (stored encrypted, never exposed in plain text)
    encrypted_api_key: str
    # For local providers, the base URL
    base_url: Optional[str] = None
    # Model to use (e.g., gpt-4, claude-3-opus)
    model_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMProviderConfigCreate(BaseModel):
    provider: LLMProvider
    api_key: str  # Plain text, will be encrypted before storage
    base_url: Optional[str] = None
    model_name: Optional[str] = None


class LLMProviderConfigResponse(BaseModel):
    config_id: str
    provider: LLMProvider
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    # Note: API key is NEVER returned
