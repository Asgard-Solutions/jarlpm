"""
Structured Logging Configuration for JarlPM

Provides:
- JSON-formatted structured logging
- Request/Response correlation IDs
- Performance metrics logging
- Error tracking with context
"""
import os
import sys
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variables for request correlation
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


class StructuredJSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    Outputs logs in a format suitable for log aggregation tools.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(""),
            "user_id": user_id_var.get(""),
        }
        
        # Add location info
        log_data["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "request_id", "user_id"
            }:
                try:
                    json.dumps(value)  # Check if serializable
                    extra_fields[key] = value
                except (TypeError, ValueError):
                    extra_fields[key] = str(value)
        
        if extra_fields:
            log_data["extra"] = extra_fields
        
        return json.dumps(log_data)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests with correlation IDs.
    """
    
    def __init__(self, app, logger: logging.Logger = None):
        super().__init__(app)
        self.logger = logger or logging.getLogger("jarlpm.requests")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:12])
        request_id_var.set(request_id)
        
        # Extract user ID from request if available (set by auth middleware)
        user_id = getattr(request.state, "user_id", "")
        if user_id:
            user_id_var.set(user_id)
        
        # Log request start
        start_time = time.time()
        
        self.logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "event_type": "request_start",
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent", ""),
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log request completion
            self.logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "event_type": "request_complete",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )
            
            # Add correlation headers to response
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Log request error
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.error(
                f"Request failed: {request.method} {request.url.path} - {type(e).__name__}",
                extra={
                    "event_type": "request_error",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True
            )
            raise


def log_operation(
    operation_name: str,
    logger: logging.Logger = None
) -> Callable:
    """
    Decorator to log async function execution with timing.
    
    Usage:
        @log_operation("generate_initiative")
        async def generate_initiative(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            op_logger = logger or logging.getLogger(f"jarlpm.operations.{operation_name}")
            start_time = time.time()
            
            op_logger.info(
                f"Operation started: {operation_name}",
                extra={
                    "event_type": "operation_start",
                    "operation": operation_name,
                }
            )
            
            try:
                result = await func(*args, **kwargs)
                
                duration_ms = (time.time() - start_time) * 1000
                op_logger.info(
                    f"Operation completed: {operation_name}",
                    extra={
                        "event_type": "operation_complete",
                        "operation": operation_name,
                        "duration_ms": round(duration_ms, 2),
                    }
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                op_logger.error(
                    f"Operation failed: {operation_name} - {type(e).__name__}",
                    extra={
                        "event_type": "operation_error",
                        "operation": operation_name,
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


def log_integration_push(
    provider: str,
    user_id: str,
    epic_id: str,
    scope: str,
    result: Dict[str, Any],
    duration_ms: float,
    logger: logging.Logger = None
):
    """Log integration push operation result."""
    push_logger = logger or logging.getLogger("jarlpm.integrations.push")
    
    created_count = len(result.get("created", []))
    updated_count = len(result.get("updated", []))
    error_count = len(result.get("errors", []))
    
    level = logging.INFO if error_count == 0 else (
        logging.WARNING if created_count > 0 or updated_count > 0 else logging.ERROR
    )
    
    push_logger.log(
        level,
        f"Integration push to {provider}: created={created_count}, updated={updated_count}, errors={error_count}",
        extra={
            "event_type": "integration_push",
            "provider": provider,
            "user_id": user_id,
            "epic_id": epic_id,
            "scope": scope,
            "created_count": created_count,
            "updated_count": updated_count,
            "error_count": error_count,
            "duration_ms": round(duration_ms, 2),
            "run_id": result.get("run_id"),
        }
    )


def log_ai_generation(
    user_id: str,
    generation_type: str,
    model: str,
    tokens_used: Optional[int] = None,
    duration_ms: Optional[float] = None,
    success: bool = True,
    error: Optional[str] = None,
    logger: logging.Logger = None
):
    """Log AI generation operation."""
    ai_logger = logger or logging.getLogger("jarlpm.ai.generation")
    
    level = logging.INFO if success else logging.ERROR
    
    ai_logger.log(
        level,
        f"AI generation {'completed' if success else 'failed'}: {generation_type}",
        extra={
            "event_type": "ai_generation",
            "generation_type": generation_type,
            "user_id": user_id,
            "model": model,
            "tokens_used": tokens_used,
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
        }
    )


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: Optional[str] = None
):
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON formatting for structured logging
        log_file: Optional file path to write logs
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if json_format and os.environ.get("LOG_FORMAT", "json") == "json":
        console_handler.setFormatter(StructuredJSONFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
    
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredJSONFormatter())
        root_logger.addHandler(file_handler)
    
    # Silence noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    return root_logger


# Metric collection helpers
class MetricsCollector:
    """Simple in-memory metrics collector for monitoring."""
    
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, list] = {}
    
    def increment(self, name: str, value: int = 1):
        """Increment a counter."""
        self.counters[name] = self.counters.get(name, 0) + value
    
    def gauge(self, name: str, value: float):
        """Set a gauge value."""
        self.gauges[name] = value
    
    def histogram(self, name: str, value: float):
        """Record a histogram value."""
        if name not in self.histograms:
            self.histograms[name] = []
        # Keep last 1000 values
        if len(self.histograms[name]) >= 1000:
            self.histograms[name] = self.histograms[name][-999:]
        self.histograms[name].append(value)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        result = {
            "counters": self.counters.copy(),
            "gauges": self.gauges.copy(),
            "histograms": {}
        }
        
        for name, values in self.histograms.items():
            if values:
                sorted_values = sorted(values)
                n = len(sorted_values)
                result["histograms"][name] = {
                    "count": n,
                    "min": sorted_values[0],
                    "max": sorted_values[-1],
                    "mean": sum(sorted_values) / n,
                    "p50": sorted_values[int(n * 0.5)],
                    "p95": sorted_values[int(n * 0.95)],
                    "p99": sorted_values[int(n * 0.99)] if n > 100 else sorted_values[-1],
                }
        
        return result


# Global metrics collector instance
metrics = MetricsCollector()
