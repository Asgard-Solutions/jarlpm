"""
Migration: Create model_health_metrics table for persistent weak model detection
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
        # Create model_health_metrics table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_health_metrics (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                provider VARCHAR(50) NOT NULL,
                model_name VARCHAR(100),
                
                total_calls INTEGER DEFAULT 0,
                validation_failures INTEGER DEFAULT 0,
                repair_successes INTEGER DEFAULT 0,
                
                warning_shown BOOLEAN DEFAULT FALSE,
                warning_dismissed BOOLEAN DEFAULT FALSE,
                
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        
        # Create indexes
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_model_health_user_provider 
            ON model_health_metrics(user_id, provider)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_model_health_user 
            ON model_health_metrics(user_id)
        """))
        
        print("Migration completed: Created model_health_metrics table")

if __name__ == "__main__":
    asyncio.run(run_migration())
