"""
Admin Routes for JarlPM

Provides administrative endpoints for:
- Database backup management
- System health monitoring
- Maintenance task execution

Security: Admin access requires either:
1. Valid X-Admin-Token header (for automation/scripts)
2. Authenticated user whose email is in ADMIN_EMAIL_ALLOWLIST
"""
from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks
from datetime import datetime, timezone
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db import get_db
from db.models import User
from routes.auth import get_current_user_id
from services.backup_service import (
    BackupService, 
    AuditLogRetentionService,
    run_maintenance_tasks
)
from services.logging_service import metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Admin token for protected operations (set in environment)
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

# Email allowlist for admin access (comma-separated)
# Example: ADMIN_EMAIL_ALLOWLIST=admin@example.com,owner@company.com
ADMIN_EMAIL_ALLOWLIST = [
    email.strip().lower() 
    for email in os.environ.get("ADMIN_EMAIL_ALLOWLIST", "").split(",") 
    if email.strip()
]


async def verify_admin_access(request: Request, session: AsyncSession) -> bool:
    """Verify caller has admin access.

    Access is granted if EITHER:
    1) X-Admin-Token header matches ADMIN_TOKEN (recommended for ops/scripts), OR
    2) Authenticated user's email is in ADMIN_EMAIL_ALLOWLIST

    Security posture: fail-closed.
    - If neither ADMIN_TOKEN nor ADMIN_EMAIL_ALLOWLIST is configured, deny access.
    """

    # 1) Token-based access (preferred)
    admin_token = request.headers.get("X-Admin-Token")
    if admin_token and ADMIN_TOKEN and admin_token == ADMIN_TOKEN:
        logger.info("Admin access granted via X-Admin-Token")
        return True

    # 2) Allowlist-based access
    if not ADMIN_EMAIL_ALLOWLIST:
        # No allowlist configured - deny all non-token access
        raise HTTPException(
            status_code=403,
            detail="Admin access denied"
        )

    # Require authenticated user for allowlist check
    user_id = await get_current_user_id(request, session)
    if not user_id:
        raise HTTPException(status_code=403, detail="Admin access denied")

    result = await session.execute(select(User.email).where(User.user_id == user_id))
    user_email = result.scalar_one_or_none()
    if not user_email:
        raise HTTPException(status_code=403, detail="Admin access denied")

    if user_email.lower() in ADMIN_EMAIL_ALLOWLIST:
        logger.info(f"Admin access granted for {user_email}")
        return True

    logger.warning(f"Admin access denied for {user_email}: Not in allowlist")
    raise HTTPException(status_code=403, detail="Admin access denied")


# ============================================
# Backup Management
# ============================================

@router.get("/backups")
async def list_backups(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """List all available database backups."""
    await verify_admin_access(request, session)
    
    backup_service = BackupService()
    backups = backup_service.list_backups()
    stats = backup_service.get_backup_stats()
    
    return {
        "backups": backups,
        "stats": stats
    }


@router.post("/backups/create")
async def create_backup(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new database backup.
    
    Note: This runs in the background for large databases.
    """
    await verify_admin_access(request, session)
    
    backup_service = BackupService()
    
    # For smaller databases, run synchronously
    # For larger ones, would use background_tasks
    result = await backup_service.create_backup()
    
    return result


@router.post("/backups/cleanup")
async def cleanup_backups(
    request: Request,
    retention_days: int = None,
    session: AsyncSession = Depends(get_db)
):
    """
    Clean up old backups based on retention policy.
    
    Args:
        retention_days: Optional override for retention period (default from env)
    """
    await verify_admin_access(request, session)
    
    backup_service = BackupService()
    
    if retention_days:
        result = backup_service.cleanup_old_backups(retention_days)
    else:
        result = backup_service.cleanup_old_backups()
    
    return result


# ============================================
# Audit Log Management  
# ============================================

@router.get("/audit-logs/stats")
async def get_audit_stats(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """Get audit log statistics."""
    await verify_admin_access(request, session)
    
    audit_service = AuditLogRetentionService(session)
    stats = await audit_service.get_audit_stats()
    
    return stats


@router.post("/audit-logs/cleanup")
async def cleanup_audit_logs(
    request: Request,
    retention_days: int = None,
    session: AsyncSession = Depends(get_db)
):
    """
    Clean up old audit logs based on retention policy.
    
    Args:
        retention_days: Optional override for retention period (default from env)
    """
    await verify_admin_access(request, session)
    
    audit_service = AuditLogRetentionService(session)
    
    if retention_days:
        result = await audit_service.cleanup_old_audit_logs(retention_days)
    else:
        result = await audit_service.cleanup_old_audit_logs()
    
    return result


# ============================================
# Maintenance Tasks
# ============================================

@router.post("/maintenance/run")
async def run_maintenance(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Run all scheduled maintenance tasks:
    - Backup cleanup
    - Audit log retention
    - Max records enforcement
    """
    await verify_admin_access(request, session)
    
    result = await run_maintenance_tasks(session)
    
    return result


# ============================================
# System Health
# ============================================

@router.get("/health/detailed")
async def detailed_health_check(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed system health information.
    """
    await verify_admin_access(request, session)
    
    from sqlalchemy import text
    
    health = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy",
        "checks": {}
    }
    
    # Database check
    try:
        await session.execute(text("SELECT 1"))
        health["checks"]["database"] = {"status": "healthy"}
    except Exception as e:
        health["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"
    
    # Backup service check
    try:
        backup_service = BackupService()
        stats = backup_service.get_backup_stats()
        health["checks"]["backups"] = {
            "status": "healthy",
            "backup_count": stats["backup_count"],
            "newest_backup": stats["newest_backup"]
        }
    except Exception as e:
        health["checks"]["backups"] = {"status": "unhealthy", "error": str(e)}
    
    # Audit log check
    try:
        audit_service = AuditLogRetentionService(session)
        audit_stats = await audit_service.get_audit_stats()
        health["checks"]["audit_logs"] = {
            "status": "healthy",
            "total_records": audit_stats["total_records"]
        }
    except Exception as e:
        health["checks"]["audit_logs"] = {"status": "unhealthy", "error": str(e)}
    
    return health


@router.get("/metrics")
async def get_metrics(
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Get application metrics for monitoring.
    """
    await verify_admin_access(request, session)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics.get_metrics()
    }
