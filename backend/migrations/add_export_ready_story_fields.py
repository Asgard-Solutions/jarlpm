"""
Migration: Add export-ready fields to user_stories table
- labels: Array of text for story categorization
- story_priority: Priority level (must-have, should-have, nice-to-have)
- dependencies: Array of dependencies
- risks: Array of risks
"""
import asyncio
import sys
sys.path.insert(0, '/app/backend')

from sqlalchemy import text
from db.database import engine

async def run_migration():
    if not engine:
        raise ValueError("Database engine not configured")
    
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

if __name__ == "__main__":
    asyncio.run(run_migration())
