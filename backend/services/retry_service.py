"""
Integration Retry Utilities for JarlPM

Provides retry mechanisms and error handling utilities for external integrations.
Handles transient failures, rate limiting, and partial push recovery.
"""
import asyncio
import logging
from functools import wraps
from typing import Any, Callable, TypeVar, Optional, List, Dict
from datetime import datetime, timezone
import traceback

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryableError(Exception):
    """Base class for errors that can be retried."""
    pass


class NonRetryableError(Exception):
    """Base class for errors that should not be retried."""
    pass


class PushResult:
    """Result of a push operation with detailed status."""
    
    def __init__(self):
        self.created: List[Dict[str, Any]] = []
        self.updated: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, Any]] = []
        self.skipped: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.started_at: datetime = datetime.now(timezone.utc)
        self.ended_at: Optional[datetime] = None
    
    def add_created(self, entity_type: str, entity_id: str, external_id: str, 
                    external_key: str = None, url: str = None):
        self.created.append({
            "type": entity_type,
            "entity_id": entity_id,
            "external_id": external_id,
            "external_key": external_key,
            "url": url
        })
    
    def add_updated(self, entity_type: str, entity_id: str, external_id: str,
                    external_key: str = None, url: str = None):
        self.updated.append({
            "type": entity_type,
            "entity_id": entity_id,
            "external_id": external_id,
            "external_key": external_key,
            "url": url
        })
    
    def add_failed(self, entity_type: str, entity_id: str, error: str, 
                   retried: bool = False, retry_count: int = 0):
        self.failed.append({
            "type": entity_type,
            "entity_id": entity_id,
            "error": error,
            "retried": retried,
            "retry_count": retry_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def add_skipped(self, entity_type: str, entity_id: str, reason: str):
        self.skipped.append({
            "type": entity_type,
            "entity_id": entity_id,
            "reason": reason
        })
    
    def add_warning(self, message: str):
        self.warnings.append(message)
    
    def finalize(self):
        self.ended_at = datetime.now(timezone.utc)
    
    @property
    def is_success(self) -> bool:
        return len(self.failed) == 0
    
    @property
    def is_partial(self) -> bool:
        return len(self.failed) > 0 and (len(self.created) > 0 or len(self.updated) > 0)
    
    @property
    def is_failure(self) -> bool:
        return len(self.failed) > 0 and len(self.created) == 0 and len(self.updated) == 0
    
    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "created": len(self.created),
            "updated": len(self.updated),
            "failed": len(self.failed),
            "skipped": len(self.skipped),
            "warnings": len(self.warnings),
            "status": "success" if self.is_success else ("partial" if self.is_partial else "failed"),
            "duration_ms": int((self.ended_at - self.started_at).total_seconds() * 1000) if self.ended_at else None
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "failed": self.failed,
            "skipped": self.skipped,
            "warnings": self.warnings,
            "summary": self.summary
        }


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable."""
    retryable_messages = [
        "timeout",
        "rate limit",
        "too many requests",
        "503",
        "502",
        "504",
        "connection",
        "temporarily unavailable",
        "internal server error"
    ]
    
    error_str = str(error).lower()
    return any(msg in error_str for msg in retryable_messages)


async def retry_async(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    **kwargs
) -> T:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for delay after each retry
        retryable_exceptions: Tuple of exception types to retry
        on_retry: Optional callback when a retry occurs
    
    Returns:
        Result of the function call
    
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e
            
            if not is_retryable_error(e):
                logger.warning(f"Non-retryable error: {e}")
                raise
            
            if attempt < max_retries:
                if on_retry:
                    on_retry(attempt + 1, e)
                
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} after error: {e}. "
                    f"Waiting {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"All {max_retries} retries failed. Last error: {e}")
    
    raise last_exception


class RetryContext:
    """Context manager for tracking retry state in push operations."""
    
    def __init__(self, entity_type: str, entity_id: str, max_retries: int = 2):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.max_retries = max_retries
        self.attempt = 0
        self.errors: List[str] = []
    
    def should_retry(self, error: Exception) -> bool:
        """Check if the operation should be retried."""
        self.attempt += 1
        self.errors.append(str(error))
        
        if self.attempt > self.max_retries:
            return False
        
        return is_retryable_error(error)
    
    @property
    def retry_summary(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "attempts": self.attempt,
            "errors": self.errors
        }


def format_user_friendly_error(error: Exception, provider: str) -> str:
    """Convert technical error into user-friendly message."""
    error_str = str(error).lower()
    
    # Rate limiting
    if "rate limit" in error_str or "too many requests" in error_str:
        return f"{provider} rate limit reached. Please wait a few minutes and try again."
    
    # Authentication
    if "unauthorized" in error_str or "401" in error_str or "authentication" in error_str:
        return f"Your {provider} connection has expired. Please reconnect in Settings."
    
    # Permission
    if "forbidden" in error_str or "403" in error_str or "permission" in error_str:
        return f"You don't have permission to perform this action in {provider}."
    
    # Not found
    if "not found" in error_str or "404" in error_str:
        return f"The {provider} project or resource was not found. Please check your settings."
    
    # Server errors
    if any(x in error_str for x in ["500", "502", "503", "504", "internal server"]):
        return f"{provider} is temporarily unavailable. Please try again in a few minutes."
    
    # Timeout
    if "timeout" in error_str:
        return f"Request to {provider} timed out. Please try again."
    
    # Connection
    if "connection" in error_str:
        return f"Could not connect to {provider}. Please check your internet connection."
    
    # Validation errors
    if "validation" in error_str or "invalid" in error_str:
        return f"The data could not be validated by {provider}. Please check your inputs."
    
    # Field mapping errors
    if "field" in error_str or "required" in error_str:
        return f"A required field is missing or misconfigured. Please check your {provider} settings."
    
    # Default
    return f"An error occurred while syncing with {provider}: {str(error)[:100]}"


def categorize_push_errors(errors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize push errors by type for better UX."""
    categories = {
        "auth_errors": [],
        "permission_errors": [],
        "validation_errors": [],
        "rate_limit_errors": [],
        "server_errors": [],
        "other_errors": []
    }
    
    for error in errors:
        error_str = error.get("error", "").lower()
        
        if any(x in error_str for x in ["unauthorized", "401", "authentication", "token"]):
            categories["auth_errors"].append(error)
        elif any(x in error_str for x in ["forbidden", "403", "permission"]):
            categories["permission_errors"].append(error)
        elif any(x in error_str for x in ["validation", "invalid", "required", "field"]):
            categories["validation_errors"].append(error)
        elif any(x in error_str for x in ["rate limit", "429", "too many"]):
            categories["rate_limit_errors"].append(error)
        elif any(x in error_str for x in ["500", "502", "503", "504", "server"]):
            categories["server_errors"].append(error)
        else:
            categories["other_errors"].append(error)
    
    # Remove empty categories
    return {k: v for k, v in categories.items() if v}


def generate_error_summary(
    errors: List[Dict[str, Any]], 
    provider: str,
    total_items: int
) -> Dict[str, Any]:
    """Generate a user-friendly summary of push errors."""
    categorized = categorize_push_errors(errors)
    
    summary = {
        "total_failed": len(errors),
        "total_items": total_items,
        "success_rate": f"{((total_items - len(errors)) / total_items * 100):.0f}%" if total_items > 0 else "N/A",
        "categories": {},
        "recommendations": []
    }
    
    if "auth_errors" in categorized:
        summary["categories"]["authentication"] = len(categorized["auth_errors"])
        summary["recommendations"].append(
            f"Reconnect your {provider} account in Settings → Integrations"
        )
    
    if "permission_errors" in categorized:
        summary["categories"]["permissions"] = len(categorized["permission_errors"])
        summary["recommendations"].append(
            f"Check that your {provider} account has write access to the project"
        )
    
    if "validation_errors" in categorized:
        summary["categories"]["validation"] = len(categorized["validation_errors"])
        summary["recommendations"].append(
            f"Review your {provider} field mappings in Settings → Integrations"
        )
    
    if "rate_limit_errors" in categorized:
        summary["categories"]["rate_limited"] = len(categorized["rate_limit_errors"])
        summary["recommendations"].append(
            "Wait a few minutes and try again, or push in smaller batches"
        )
    
    if "server_errors" in categorized:
        summary["categories"]["server_issues"] = len(categorized["server_errors"])
        summary["recommendations"].append(
            f"{provider} may be experiencing issues. Try again later."
        )
    
    if "other_errors" in categorized:
        summary["categories"]["other"] = len(categorized["other_errors"])
    
    if not summary["recommendations"]:
        summary["recommendations"].append(
            "Try pushing again. If the issue persists, check your integration settings."
        )
    
    return summary
