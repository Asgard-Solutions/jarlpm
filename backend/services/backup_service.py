"""
Database Backup and Retention Service for JarlPM

Provides:
- Manual and scheduled database backup creation
- Backup retention policy enforcement  
- Audit log cleanup for data retention compliance
"""
import os
import asyncio
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import json
import shutil
import gzip

from sqlalchemy import text, delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Configuration from environment
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/app/backups"))
BACKUP_RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))
AUDIT_LOG_RETENTION_DAYS = int(os.environ.get("AUDIT_LOG_RETENTION_DAYS", "90"))
MAX_AUDIT_RECORDS = int(os.environ.get("MAX_AUDIT_RECORDS", "100000"))


class BackupService:
    """Handles database backup operations."""
    
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.environ.get("DATABASE_URL", "")
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_backup_filename(self, prefix: str = "jarlpm") -> str:
        """Generate a timestamped backup filename."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_backup_{timestamp}.sql.gz"
    
    async def create_backup(self, prefix: str = "jarlpm") -> Dict[str, Any]:
        """
        Create a PostgreSQL database backup.
        
        Returns:
            Dict with backup details including path, size, and timestamp
        """
        filename = self._get_backup_filename(prefix)
        backup_path = self.backup_dir / filename
        temp_path = self.backup_dir / f"{filename}.tmp"
        
        # Parse database URL for pg_dump
        # Format: postgresql+asyncpg://user:pass@host:port/dbname
        try:
            from urllib.parse import urlparse
            
            # Remove +asyncpg suffix for pg_dump
            clean_url = self.db_url.replace("+asyncpg", "")
            parsed = urlparse(clean_url)
            
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password
            
            # Build pg_dump command
            cmd = [
                "pg_dump",
                "-h", parsed.hostname or "localhost",
                "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres",
                "-d", parsed.path.lstrip("/"),
                "-F", "p",  # Plain text format
                "--no-owner",
                "--no-acl"
            ]
            
            logger.info(f"Starting database backup: {filename}")
            start_time = datetime.now(timezone.utc)
            
            # Run pg_dump and compress output
            with gzip.open(temp_path, "wt") as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    timeout=600  # 10 minute timeout
                )
            
            if result.returncode != 0:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                logger.error(f"pg_dump failed: {error_msg}")
                if temp_path.exists():
                    temp_path.unlink()
                return {
                    "success": False,
                    "error": f"Backup failed: {error_msg}"
                }
            
            # Move temp file to final location
            shutil.move(str(temp_path), str(backup_path))
            
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            size_bytes = backup_path.stat().st_size
            
            logger.info(f"Backup completed: {filename} ({size_bytes / 1024 / 1024:.2f} MB) in {duration:.1f}s")
            
            return {
                "success": True,
                "filename": filename,
                "path": str(backup_path),
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / 1024 / 1024, 2),
                "created_at": start_time.isoformat(),
                "duration_seconds": round(duration, 1)
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Backup timed out after 10 minutes")
            if temp_path.exists():
                temp_path.unlink()
            return {
                "success": False,
                "error": "Backup timed out"
            }
        except Exception as e:
            logger.error(f"Backup error: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []
        
        for backup_file in self.backup_dir.glob("*.sql.gz"):
            stat = backup_file.stat()
            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / 1024 / 1024, 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            })
        
        # Sort by creation time, newest first
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups
    
    def cleanup_old_backups(self, retention_days: int = BACKUP_RETENTION_DAYS) -> Dict[str, Any]:
        """
        Remove backups older than retention period.
        
        Returns:
            Dict with cleanup summary
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = []
        kept = []
        
        for backup_file in self.backup_dir.glob("*.sql.gz"):
            stat = backup_file.stat()
            file_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            
            if file_time < cutoff_date:
                try:
                    backup_file.unlink()
                    deleted.append(backup_file.name)
                    logger.info(f"Deleted old backup: {backup_file.name}")
                except Exception as e:
                    logger.error(f"Failed to delete {backup_file.name}: {e}")
            else:
                kept.append(backup_file.name)
        
        return {
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "deleted_count": len(deleted),
            "deleted_files": deleted,
            "kept_count": len(kept)
        }
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """Get backup storage statistics."""
        backups = self.list_backups()
        
        if not backups:
            return {
                "backup_count": 0,
                "total_size_mb": 0,
                "oldest_backup": None,
                "newest_backup": None
            }
        
        total_size = sum(b["size_bytes"] for b in backups)
        
        return {
            "backup_count": len(backups),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "oldest_backup": backups[-1]["created_at"] if backups else None,
            "newest_backup": backups[0]["created_at"] if backups else None,
            "retention_days": BACKUP_RETENTION_DAYS
        }


class AuditLogRetentionService:
    """Handles audit log retention and cleanup."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_audit_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        from db.integration_models import ExternalPushRun
        
        # Count total push runs
        count_result = await self.session.execute(
            select(func.count(ExternalPushRun.run_id))
        )
        total_count = count_result.scalar() or 0
        
        # Get oldest record
        oldest_result = await self.session.execute(
            select(func.min(ExternalPushRun.started_at))
        )
        oldest_date = oldest_result.scalar()
        
        # Get newest record
        newest_result = await self.session.execute(
            select(func.max(ExternalPushRun.started_at))
        )
        newest_date = newest_result.scalar()
        
        return {
            "total_records": total_count,
            "oldest_record": oldest_date.isoformat() if oldest_date else None,
            "newest_record": newest_date.isoformat() if newest_date else None,
            "retention_days": AUDIT_LOG_RETENTION_DAYS,
            "max_records": MAX_AUDIT_RECORDS
        }
    
    async def cleanup_old_audit_logs(
        self,
        retention_days: int = AUDIT_LOG_RETENTION_DAYS
    ) -> Dict[str, Any]:
        """
        Remove audit logs older than retention period.
        
        Returns:
            Dict with cleanup summary
        """
        from db.integration_models import ExternalPushRun
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        # Count records to delete
        count_result = await self.session.execute(
            select(func.count(ExternalPushRun.run_id)).where(
                ExternalPushRun.started_at < cutoff_date
            )
        )
        delete_count = count_result.scalar() or 0
        
        if delete_count > 0:
            # Delete old records
            await self.session.execute(
                delete(ExternalPushRun).where(
                    ExternalPushRun.started_at < cutoff_date
                )
            )
            await self.session.commit()
            logger.info(f"Deleted {delete_count} audit log records older than {retention_days} days")
        
        return {
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "deleted_count": delete_count
        }
    
    async def enforce_max_records(
        self,
        max_records: int = MAX_AUDIT_RECORDS
    ) -> Dict[str, Any]:
        """
        Enforce maximum number of audit log records.
        Deletes oldest records if limit is exceeded.
        
        Returns:
            Dict with cleanup summary
        """
        from db.integration_models import ExternalPushRun
        
        # Count total records
        count_result = await self.session.execute(
            select(func.count(ExternalPushRun.run_id))
        )
        total_count = count_result.scalar() or 0
        
        if total_count <= max_records:
            return {
                "max_records": max_records,
                "current_count": total_count,
                "deleted_count": 0,
                "action": "no_cleanup_needed"
            }
        
        # Calculate how many to delete
        delete_count = total_count - max_records
        
        # Find the cutoff run_id
        cutoff_result = await self.session.execute(
            select(ExternalPushRun.run_id)
            .order_by(ExternalPushRun.started_at.asc())
            .offset(delete_count - 1)
            .limit(1)
        )
        cutoff_id = cutoff_result.scalar()
        
        if cutoff_id:
            # Delete records up to the cutoff
            await self.session.execute(
                delete(ExternalPushRun).where(
                    ExternalPushRun.run_id <= cutoff_id
                )
            )
            await self.session.commit()
            logger.info(f"Deleted {delete_count} oldest audit log records to enforce limit of {max_records}")
        
        return {
            "max_records": max_records,
            "previous_count": total_count,
            "deleted_count": delete_count,
            "current_count": total_count - delete_count
        }


async def run_maintenance_tasks(session: AsyncSession):
    """Run all scheduled maintenance tasks."""
    logger.info("Starting scheduled maintenance tasks...")
    
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tasks": {}
    }
    
    # 1. Backup cleanup
    try:
        backup_service = BackupService()
        backup_cleanup = backup_service.cleanup_old_backups()
        results["tasks"]["backup_cleanup"] = {
            "status": "success",
            **backup_cleanup
        }
    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}")
        results["tasks"]["backup_cleanup"] = {
            "status": "error",
            "error": str(e)
        }
    
    # 2. Audit log retention
    try:
        audit_service = AuditLogRetentionService(session)
        audit_cleanup = await audit_service.cleanup_old_audit_logs()
        results["tasks"]["audit_log_cleanup"] = {
            "status": "success",
            **audit_cleanup
        }
    except Exception as e:
        logger.error(f"Audit log cleanup failed: {e}")
        results["tasks"]["audit_log_cleanup"] = {
            "status": "error",
            "error": str(e)
        }
    
    # 3. Enforce max audit records
    try:
        audit_service = AuditLogRetentionService(session)
        max_cleanup = await audit_service.enforce_max_records()
        results["tasks"]["audit_max_records"] = {
            "status": "success",
            **max_cleanup
        }
    except Exception as e:
        logger.error(f"Max records enforcement failed: {e}")
        results["tasks"]["audit_max_records"] = {
            "status": "error",
            "error": str(e)
        }
    
    logger.info(f"Maintenance tasks completed: {json.dumps(results, indent=2)}")
    return results
