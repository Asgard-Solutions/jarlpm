#!/bin/bash
# JarlPM Production Startup Script
# This script ensures migrations are run before starting the server

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

cd "$BACKEND_DIR"

echo "=========================================="
echo "JarlPM Server Startup"
echo "=========================================="

# Check required environment variables
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set"
    exit 1
fi

# Run Alembic migrations
echo ""
echo "[1/3] Running database migrations..."
echo "----------------------------------------"
alembic upgrade head

if [ $? -ne 0 ]; then
    echo "ERROR: Database migration failed!"
    exit 1
fi
echo "✓ Migrations complete"

# Verify database connection
echo ""
echo "[2/3] Verifying database connection..."
echo "----------------------------------------"
python3 -c "
import asyncio
from db.database import engine
from sqlalchemy import text

async def verify():
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT 1'))
        print('✓ Database connection verified')

asyncio.run(verify())
"

if [ $? -ne 0 ]; then
    echo "ERROR: Database connection verification failed!"
    exit 1
fi

# Start the server
echo ""
echo "[3/3] Starting JarlPM API server..."
echo "----------------------------------------"
echo "Pool config: DB_POOL_SIZE=${DB_POOL_SIZE:-5}, DB_MAX_OVERFLOW=${DB_MAX_OVERFLOW:-10}"
echo ""

exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8001} --workers ${WORKERS:-1}
