from typing import AsyncGenerator, Optional
import httpx
import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LLMProvider, LLMProviderConfig, EpicStage
from services.encryption import get_encryption_service


class LLMService:
    """LLM-agnostic service for text generation"""
    
    def __init__(self, session: AsyncSession = None):
        self.session = session
        self.encryption = get_encryption_service()
    
    async def get_user_llm_config(self, user_id: str) -> Optional[LLMProviderConfig]:
        """Get the active LLM configuration for a user"""
        if not self.session:
            raise ValueError("Session required to fetch LLM config")
        result = await self.session.execute(
            select(LLMProviderConfig)
            .where(LLMProviderConfig.user_id == user_id, LLMProviderConfig.is_active.is_(True))
        )
        return result.scalar_one_or_none()
    
    def _decrypt_api_key(self, config: LLMProviderConfig) -> str:
        """Decrypt the API key for use"""
        return self.encryption.decrypt(config.encrypted_api_key)
    
    def prepare_for_streaming(self, config: LLMProviderConfig) -> dict:
        """
        Prepare all data needed for streaming WITHOUT holding the session.
        Call this before releasing the DB session, then use stream_with_config().
        
        Returns a dict with provider, model, api_key, base_url that can be used
        after the session is closed.
        """
        return {
            "provider": config.provider,
            "model_name": config.model_name,
            "api_key": self._decrypt_api_key(config),
            "base_url": config.base_url
        }
    
    async def stream_with_config(
        self,
        config_data: dict,
        system_prompt: str,
        user_prompt: str,
        conversation_history: list[dict] = None,
        temperature: float = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream using pre-fetched config data. Does NOT require a DB session.
        Use this for long-running streams to avoid holding DB connections.
        
        config_data should come from prepare_for_streaming()
        """
        provider = config_data["provider"]
        model = config_data["model_name"]
        api_key = config_data["api_key"]
        base_url = config_data.get("base_url")
        
        if provider == LLMProvider.OPENAI.value:
            async for chunk in self._openai_stream(api_key, model, system_prompt, user_prompt, conversation_history, temperature):
                yield chunk
        elif provider == LLMProvider.ANTHROPIC.value:
            async for chunk in self._anthropic_stream(api_key, model, system_prompt, user_prompt, conversation_history, temperature):
                yield chunk
        elif provider == LLMProvider.GOOGLE.value:
            async for chunk in self._google_stream(api_key, model, system_prompt, user_prompt, conversation_history, temperature):
                yield chunk
        elif provider == LLMProvider.LOCAL.value:
            async for chunk in self._local_stream(api_key, base_url, model, system_prompt, user_prompt, conversation_history, temperature):
                yield chunk
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    async def generate_stream(
        self,
        user_id: str,
        system_prompt: str,
        user_prompt: str,
        conversation_history: list[dict] = None,
        temperature: float = None  # None = use model default
    ) -> AsyncGenerator[str, None]:
        """
        Generate text using the user's configured LLM provider (streaming).
        
        NOTE: This method holds the session reference during streaming.
        For long-running streams in HTTP handlers, prefer:
        1. config = await llm_service.get_user_llm_config(user_id)
        2. config_data = llm_service.prepare_for_streaming(config)
        3. Release session
        4. async for chunk in llm_service.stream_with_config(config_data, ...):
        """
        
        config = await self.get_user_llm_config(user_id)
        if not config:
            raise ValueError("No LLM provider configured. Please add your API key in settings.")
        
        api_key = self._decrypt_api_key(config)
        
        # Compare with string values since provider is now stored as string
        if config.provider == LLMProvider.OPENAI.value:
            async for chunk in self._openai_stream(api_key, config.model_name, system_prompt, user_prompt, conversation_history, temperature):
                yield chunk
        elif config.provider == LLMProvider.ANTHROPIC.value:
            async for chunk in self._anthropic_stream(api_key, config.model_name, system_prompt, user_prompt, conversation_history, temperature):
                yield chunk
        elif config.provider == LLMProvider.GOOGLE.value:
            async for chunk in self._google_stream(api_key, config.model_name, system_prompt, user_prompt, conversation_history, temperature):
                yield chunk
        elif config.provider == LLMProvider.LOCAL.value:
            async for chunk in self._local_stream(api_key, config.base_url, config.model_name, system_prompt, user_prompt, conversation_history, temperature):
                yield chunk
        else:
            raise ValueError(f"Unsupported LLM provider: {config.provider}")
    
    async def _openai_stream(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        conversation_history: list[dict] = None,
        temperature: float = None
    ) -> AsyncGenerator[str, None]:
        """Stream from OpenAI API"""
        model = model or "gpt-4o"
        
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_prompt})
        
        request_body = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": 4096  # Match Anthropic's budget for complete responses
        }
        if temperature is not None:
            request_body["temperature"] = temperature
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=request_body,
                timeout=120.0
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise ValueError(f"OpenAI API error: {error_text.decode()}")
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
    
    async def _anthropic_stream(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        conversation_history: list[dict] = None,
        temperature: float = None
    ) -> AsyncGenerator[str, None]:
        """Stream from Anthropic API"""
        model = model or "claude-sonnet-4-20250514"
        
        messages = []
        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        messages.append({"role": "user", "content": user_prompt})
        
        request_body = {
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": messages,
            "stream": True
        }
        if temperature is not None:
            request_body["temperature"] = temperature
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json=request_body,
                timeout=120.0
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise ValueError(f"Anthropic API error: {error_text.decode()}")
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            chunk = json.loads(data)
                            if chunk.get("type") == "content_block_delta":
                                content = chunk.get("delta", {}).get("text", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
    
    async def _local_stream(
        self,
        api_key: str,
        base_url: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        conversation_history: list[dict] = None,
        temperature: float = None
    ) -> AsyncGenerator[str, None]:
        """Stream from local/custom HTTP endpoint (OpenAI-compatible)"""
        if not base_url:
            raise ValueError("Local provider requires base_url to be configured")
        
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_prompt})
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        request_body = {
            "model": model or "default",
            "messages": messages,
            "stream": True,
            "max_tokens": 4096  # Ensure complete responses from local models
        }
        if temperature is not None:
            request_body["temperature"] = temperature
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/v1/chat/completions",
                headers=headers,
                json=request_body,
                timeout=120.0
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise ValueError(f"Local API error: {error_text.decode()}")
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
    
    def extract_proposal(self, content: str) -> Optional[dict]:
        """Extract proposal from LLM response if present"""
        # Match [PROPOSAL: TYPE]...[/PROPOSAL] pattern
        pattern = r'\[PROPOSAL:\s*(\w+)\]\s*(.+?)\s*\[/PROPOSAL\]'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            proposal_type = match.group(1).upper()
            proposal_content = match.group(2).strip()
            return {
                "type": proposal_type,
                "content": proposal_content
            }
        return None
    
    async def validate_api_key(self, provider, api_key: str, base_url: str = None, model: str = None) -> bool:
        """Validate that an API key works with the provider"""
        # Handle both enum and string provider values
        provider_value = provider.value if isinstance(provider, LLMProvider) else provider
        
        try:
            if provider_value == LLMProvider.OPENAI.value:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=10.0
                    )
                    return response.status_code == 200
            
            elif provider_value == LLMProvider.ANTHROPIC.value:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model or "claude-sonnet-4-20250514",
                            "max_tokens": 10,
                            "messages": [{"role": "user", "content": "Hi"}]
                        },
                        timeout=10.0
                    )
                    return response.status_code == 200
            
            elif provider_value == LLMProvider.LOCAL.value:
                if not base_url:
                    return False
                async with httpx.AsyncClient() as client:
                    headers = {"Content-Type": "application/json"}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    response = await client.get(
                        f"{base_url.rstrip('/')}/v1/models",
                        headers=headers,
                        timeout=10.0
                    )
                    return response.status_code == 200
            
            return False
        except Exception:
            return False
