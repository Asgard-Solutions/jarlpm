# JarlPM Deployment Guide

## Database Migration Discipline

**CRITICAL: Always run migrations before starting the server in production.**

### Why This Matters

- Schema changes are managed by Alembic, not auto-created
- Running without migrations can cause:
  - Missing columns/tables → 500 errors
  - Data integrity issues with multi-user data
  - Silent failures that corrupt data

### Deployment Checklist

```bash
# 1. Set environment variables
export DATABASE_URL="postgresql://..."
export DB_POOL_SIZE=10        # Adjust for traffic (default: 5)
export DB_MAX_OVERFLOW=20     # Adjust for bursts (default: 10)

# 2. Run migrations FIRST
cd /app/backend
alembic upgrade head

# 3. Then start the server
uvicorn server:app --host 0.0.0.0 --port 8001
```

### Using the Startup Script (Recommended)

```bash
# This script handles migrations automatically
./scripts/start.sh
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `DB_POOL_SIZE` | 5 | Connection pool size |
| `DB_MAX_OVERFLOW` | 10 | Max overflow connections |
| `DB_POOL_TIMEOUT` | 30 | Seconds to wait for connection |
| `DB_POOL_RECYCLE` | 1800 | Recycle connections after N seconds |
| `DB_RESET_ON_STARTUP` | false | ⚠️ DEV ONLY: Drop all tables on start |

### Railway / Vercel / Docker Deployment

**Railway:**
```toml
# railway.toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "cd backend && alembic upgrade head && uvicorn server:app --host 0.0.0.0 --port $PORT"
```

**Docker:**
```dockerfile
CMD ["sh", "-c", "cd /app/backend && alembic upgrade head && uvicorn server:app --host 0.0.0.0 --port 8001"]
```

**Vercel (serverless):**
- Migrations must run as a separate build step or GitHub Action
- Not recommended for production due to cold starts with DB connections

### Creating New Migrations

```bash
# After modifying models:
cd /app/backend
alembic revision --autogenerate -m "describe your changes"

# Review the generated migration file in alembic/versions/
# Then apply:
alembic upgrade head
```

### Rollback

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# View history
alembic history
```

### Long-Running Streams and Connection Pool

**Problem:** AI streaming endpoints can hold DB connections for 30+ seconds, exhausting the pool.

**Solution Pattern:**
```python
# DO THIS - Release session before streaming
@router.post("/ai/generate")
async def generate(request: Request, session: AsyncSession = Depends(get_db)):
    user_id = await get_current_user_id(request, session)
    
    # 1. Do ALL database reads upfront
    llm_service = LLMService(session)
    config = await llm_service.get_user_llm_config(user_id)
    my_data = await session.execute(select(MyModel).where(...))
    
    # 2. Prepare streaming config (extracts API key, etc.)
    config_data = llm_service.prepare_for_streaming(config)
    
    # 3. Extract all needed data from ORM objects
    context = f"Title: {my_data.title}, ..."
    
    # Session will be released when this function returns
    
    async def generate():
        # 4. Use stream_with_config - NO session needed
        llm = LLMService()  # No session
        async for chunk in llm.stream_with_config(config_data, system, user):
            yield f"data: {chunk}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

# DON'T DO THIS - Holds session during entire stream
async def bad_example(session: AsyncSession = Depends(get_db)):
    llm_service = LLMService(session)  # Session captured in closure
    
    async def generate():
        # This keeps session open for entire stream duration!
        async for chunk in llm_service.generate_stream(user_id, ...):
            yield chunk
    
    return StreamingResponse(generate())
```

### Troubleshooting

**"Table does not exist" errors:**
- Migrations weren't run. Execute `alembic upgrade head`

**"Column does not exist" errors:**
- New migration needed. Check if models changed without migration.

**Connection pool exhausted:**
- Increase `DB_POOL_SIZE` and `DB_MAX_OVERFLOW`
- Check for connection leaks (sessions not closed)

**Slow startup:**
- Migration running on every deploy is normal
- Use connection pooler (PgBouncer) for serverless
