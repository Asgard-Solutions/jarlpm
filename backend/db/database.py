"""
JarlPM Database Configuration
PostgreSQL via Neon - SQLAlchemy 2.0 Async
"""
import os
import ssl
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, text
import logging

logger = logging.getLogger(__name__)

# Get DATABASE_URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL', '')

def convert_url_for_asyncpg(url: str) -> str:
    """Convert standard PostgreSQL URL to asyncpg-compatible format"""
    if not url:
        return url
    
    # Parse the URL
    parsed = urlparse(url)
    
    # Change scheme to asyncpg
    scheme = 'postgresql+asyncpg'
    
    # Parse query params and remove sslmode/channel_binding (asyncpg doesn't support them)
    query_params = parse_qs(parsed.query)
    query_params.pop('sslmode', None)
    query_params.pop('channel_binding', None)
    
    # Rebuild query string
    new_query = urlencode({k: v[0] for k, v in query_params.items()})
    
    # Rebuild URL
    new_url = urlunparse((
        scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    
    return new_url

# Convert URL for asyncpg
if DATABASE_URL:
    DATABASE_URL = convert_url_for_asyncpg(DATABASE_URL)

# Create SSL context for Neon (requires SSL)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Create async engine with SSL
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"ssl": ssl_context}
) if DATABASE_URL else None

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
) if engine else None


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency for getting async database sessions"""
    if not AsyncSessionLocal:
        raise RuntimeError("Database not configured. Set DATABASE_URL environment variable.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database - create all tables"""
    if not engine:
        logger.error("Database engine not initialized. Check DATABASE_URL.")
        return
    
    from .models import Base
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Create append-only trigger function
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION prevent_update_delete()
            RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    RAISE EXCEPTION 'UPDATE operations are not allowed on append-only table %', TG_TABLE_NAME;
                ELSIF TG_OP = 'DELETE' THEN
                    -- Allow cascade deletes from epic deletion
                    IF current_setting('jarlpm.allow_cascade_delete', true) = 'true' THEN
                        RETURN OLD;
                    END IF;
                    RAISE EXCEPTION 'DELETE operations are not allowed on append-only table %', TG_TABLE_NAME;
                END IF;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Apply append-only triggers to transcript events
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS enforce_append_only_transcript ON epic_transcript_events;
            CREATE TRIGGER enforce_append_only_transcript
            BEFORE UPDATE OR DELETE ON epic_transcript_events
            FOR EACH ROW EXECUTE FUNCTION prevent_update_delete();
        """))
        
        # Apply append-only triggers to decisions
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS enforce_append_only_decisions ON epic_decisions;
            CREATE TRIGGER enforce_append_only_decisions
            BEFORE UPDATE OR DELETE ON epic_decisions
            FOR EACH ROW EXECUTE FUNCTION prevent_update_delete();
        """))
        
        # Create monotonic stage check function
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION check_monotonic_stage()
            RETURNS TRIGGER AS $$
            DECLARE
                old_order INTEGER;
                new_order INTEGER;
                stage_order INTEGER[] := ARRAY[
                    1,  -- problem_capture
                    2,  -- problem_confirmed
                    3,  -- outcome_capture
                    4,  -- outcome_confirmed
                    5,  -- epic_drafted
                    6   -- epic_locked
                ];
            BEGIN
                -- Get ordinal positions
                old_order := CASE OLD.current_stage
                    WHEN 'problem_capture' THEN 1
                    WHEN 'problem_confirmed' THEN 2
                    WHEN 'outcome_capture' THEN 3
                    WHEN 'outcome_confirmed' THEN 4
                    WHEN 'epic_drafted' THEN 5
                    WHEN 'epic_locked' THEN 6
                END;
                
                new_order := CASE NEW.current_stage
                    WHEN 'problem_capture' THEN 1
                    WHEN 'problem_confirmed' THEN 2
                    WHEN 'outcome_capture' THEN 3
                    WHEN 'outcome_confirmed' THEN 4
                    WHEN 'epic_drafted' THEN 5
                    WHEN 'epic_locked' THEN 6
                END;
                
                -- Enforce monotonic progression (can only move forward)
                IF new_order < old_order THEN
                    RAISE EXCEPTION 'Stage regression not allowed: cannot move from % to %', OLD.current_stage, NEW.current_stage;
                END IF;
                
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Apply monotonic stage trigger
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS enforce_monotonic_stage ON epics;
            CREATE TRIGGER enforce_monotonic_stage
            BEFORE UPDATE OF current_stage ON epics
            FOR EACH ROW EXECUTE FUNCTION check_monotonic_stage();
        """))
        
        # Create locked content check function
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION check_locked_content()
            RETURNS TRIGGER AS $$
            BEGIN
                -- If problem is confirmed, prevent modification
                IF OLD.problem_confirmed_at IS NOT NULL AND 
                   NEW.problem_statement IS DISTINCT FROM OLD.problem_statement THEN
                    RAISE EXCEPTION 'Cannot modify locked problem_statement';
                END IF;
                
                -- If outcome is confirmed, prevent modification
                IF OLD.outcome_confirmed_at IS NOT NULL AND 
                   NEW.desired_outcome IS DISTINCT FROM OLD.desired_outcome THEN
                    RAISE EXCEPTION 'Cannot modify locked desired_outcome';
                END IF;
                
                -- If epic is locked, prevent modification of summary/criteria
                IF OLD.epic_locked_at IS NOT NULL THEN
                    IF NEW.epic_summary IS DISTINCT FROM OLD.epic_summary THEN
                        RAISE EXCEPTION 'Cannot modify locked epic_summary';
                    END IF;
                    IF NEW.acceptance_criteria IS DISTINCT FROM OLD.acceptance_criteria THEN
                        RAISE EXCEPTION 'Cannot modify locked acceptance_criteria';
                    END IF;
                END IF;
                
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Apply locked content trigger
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS enforce_locked_content ON epic_snapshots;
            CREATE TRIGGER enforce_locked_content
            BEFORE UPDATE ON epic_snapshots
            FOR EACH ROW EXECUTE FUNCTION check_locked_content();
        """))
        
    logger.info("Database initialized with tables and constraints")
