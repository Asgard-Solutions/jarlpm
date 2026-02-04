"""
Migration: Create analytics tables for observability
- initiative_generation_logs: Tracks each generation attempt
- initiative_edit_logs: Tracks user edits after generation
- prompt_version_registry: Tracks prompt versions and performance
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
        # Create initiative_generation_logs table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS initiative_generation_logs (
                id SERIAL PRIMARY KEY,
                log_id VARCHAR(50) UNIQUE NOT NULL,
                user_id VARCHAR(50) NOT NULL,
                
                -- Input context
                idea_length INTEGER NOT NULL,
                idea_hash VARCHAR(64) NOT NULL,
                product_name_provided BOOLEAN DEFAULT FALSE,
                
                -- Delivery context
                has_delivery_context BOOLEAN DEFAULT FALSE,
                industry VARCHAR(100),
                methodology VARCHAR(50),
                team_size INTEGER,
                
                -- Model info
                llm_provider VARCHAR(50) NOT NULL,
                model_name VARCHAR(100),
                prompt_version VARCHAR(20) DEFAULT 'v1.0',
                
                -- Token usage
                pass_1_tokens_in INTEGER,
                pass_1_tokens_out INTEGER,
                pass_2_tokens_in INTEGER,
                pass_2_tokens_out INTEGER,
                pass_3_tokens_in INTEGER,
                pass_3_tokens_out INTEGER,
                pass_4_tokens_in INTEGER,
                pass_4_tokens_out INTEGER,
                total_tokens INTEGER,
                estimated_cost_usd FLOAT,
                
                -- Parse/validation
                pass_1_retries INTEGER DEFAULT 0,
                pass_2_retries INTEGER DEFAULT 0,
                pass_3_retries INTEGER DEFAULT 0,
                pass_4_retries INTEGER DEFAULT 0,
                total_retries INTEGER DEFAULT 0,
                validation_errors TEXT[],
                
                -- Output metrics
                success BOOLEAN DEFAULT FALSE,
                error_message TEXT,
                features_generated INTEGER,
                stories_generated INTEGER,
                total_points INTEGER,
                
                -- Quality check
                critic_issues_found INTEGER,
                critic_auto_fixed INTEGER,
                scope_assessment VARCHAR(20),
                
                -- Timing
                duration_ms INTEGER,
                pass_1_duration_ms INTEGER,
                pass_2_duration_ms INTEGER,
                pass_3_duration_ms INTEGER,
                pass_4_duration_ms INTEGER,
                
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        
        # Create indexes
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_gen_logs_user_id ON initiative_generation_logs(user_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_gen_logs_created ON initiative_generation_logs(created_at)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_gen_logs_provider ON initiative_generation_logs(llm_provider)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_gen_logs_success ON initiative_generation_logs(success)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_gen_logs_prompt_version ON initiative_generation_logs(prompt_version)"))
        
        # Create initiative_edit_logs table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS initiative_edit_logs (
                id SERIAL PRIMARY KEY,
                edit_id VARCHAR(50) UNIQUE NOT NULL,
                generation_log_id VARCHAR(50),
                user_id VARCHAR(50) NOT NULL,
                epic_id VARCHAR(50) NOT NULL,
                
                -- What was edited
                entity_type VARCHAR(50) NOT NULL,
                entity_id VARCHAR(50) NOT NULL,
                field_edited VARCHAR(100) NOT NULL,
                
                -- Edit metrics
                original_length INTEGER,
                edited_length INTEGER,
                change_ratio FLOAT,
                edit_type VARCHAR(50) NOT NULL,
                
                time_to_edit_seconds INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_edit_logs_user_id ON initiative_edit_logs(user_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_edit_logs_epic_id ON initiative_edit_logs(epic_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_edit_logs_entity_type ON initiative_edit_logs(entity_type)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_edit_logs_field ON initiative_edit_logs(field_edited)"))
        
        # Create prompt_version_registry table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prompt_version_registry (
                id SERIAL PRIMARY KEY,
                version_id VARCHAR(50) UNIQUE NOT NULL,
                version VARCHAR(20) UNIQUE NOT NULL,
                pass_name VARCHAR(50) NOT NULL,
                
                system_prompt_hash VARCHAR(64) NOT NULL,
                user_prompt_hash VARCHAR(64) NOT NULL,
                
                total_uses INTEGER DEFAULT 0,
                success_rate FLOAT,
                avg_retries FLOAT,
                avg_edit_ratio FLOAT,
                
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_registry_version ON prompt_version_registry(version)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prompt_registry_active ON prompt_version_registry(is_active)"))
        
        print("Migration completed: Created analytics tables")

if __name__ == "__main__":
    asyncio.run(run_migration())
