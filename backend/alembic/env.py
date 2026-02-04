"""
Alembic Environment Configuration for JarlPM
Async PostgreSQL migrations with SQLAlchemy 2.0
"""
import asyncio
from logging.config import fileConfig
import os
import sys

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all models to register them with Base.metadata
from db.models import Base
from db.feature_models import Feature, FeatureConversationEvent
from db.user_story_models import UserStory, UserStoryConversationEvent
from db.persona_models import Persona, PersonaGenerationSettings
from db.analytics_models import InitiativeGenerationLog, InitiativeEditLog, PromptVersionRegistry, ModelHealthMetrics

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata

# Get DATABASE_URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL', '')

def get_url():
    """Get database URL, converting to asyncpg format"""
    url = DATABASE_URL
    if not url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Convert to asyncpg format
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # Remove unsupported params for asyncpg
    if "sslmode=" in url:
        url = url.split("sslmode=")[0].rstrip("&?")
    if "channel_binding=" in url:
        url = url.split("channel_binding=")[0].rstrip("&?")
    
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode - generates SQL script."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
