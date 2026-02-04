"""
Migration: Add export-ready fields to user_stories table
- labels: Array of text for story categorization
- story_priority: Priority level (must-have, should-have, nice-to-have)
- dependencies: Array of dependencies
- risks: Array of risks
"""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def run_migration():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not set")
    
    # Convert to async URL if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url)
    
    async with engine.begin() as conn:
        # Add labels column
        await conn.execute(text("""
            ALTER TABLE user_stories 
            ADD COLUMN IF NOT EXISTS labels TEXT[] DEFAULT '{}'
        """))
        
        # Add story_priority column
        await conn.execute(text("""
            ALTER TABLE user_stories 
            ADD COLUMN IF NOT EXISTS story_priority VARCHAR(50)
        """))
        
        # Add dependencies column
        await conn.execute(text("""
            ALTER TABLE user_stories 
            ADD COLUMN IF NOT EXISTS dependencies TEXT[] DEFAULT '{}'
        """))
        
        # Add risks column
        await conn.execute(text("""
            ALTER TABLE user_stories 
            ADD COLUMN IF NOT EXISTS risks TEXT[] DEFAULT '{}'
        """))
        
        print("Migration completed: Added export-ready fields to user_stories")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_migration())
