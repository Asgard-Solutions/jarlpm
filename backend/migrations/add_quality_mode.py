"""
Migration: Add quality_mode to product_delivery_contexts table
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
        # Add quality_mode column
        await conn.execute(text("""
            ALTER TABLE product_delivery_contexts 
            ADD COLUMN IF NOT EXISTS quality_mode VARCHAR(20) DEFAULT 'standard'
        """))
        
        print("Migration completed: Added quality_mode to product_delivery_contexts")

if __name__ == "__main__":
    asyncio.run(run_migration())
