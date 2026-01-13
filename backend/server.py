from fastapi import FastAPI, APIRouter, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
import sys

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'jarlpm')]

# Create the main app
app = FastAPI(
    title="JarlPM API",
    description="AI-agnostic Product Management System",
    version="1.0.0"
)

# Store db in app state for access in routes
app.state.db = db

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Import and include route modules
from routes.auth import router as auth_router
from routes.subscription import router as subscription_router
from routes.llm_provider import router as llm_provider_router
from routes.epic import router as epic_router

api_router.include_router(auth_router)
api_router.include_router(subscription_router)
api_router.include_router(llm_provider_router)
api_router.include_router(epic_router)

# Health check endpoint
@api_router.get("/")
async def root():
    return {"message": "JarlPM API", "status": "healthy"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "jarlpm"}

# Include the router in the main app
app.include_router(api_router)

# Webhook endpoint (needs to be at root level for Stripe)
from routes.subscription import stripe_webhook
app.add_api_route("/api/webhook/stripe", stripe_webhook, methods=["POST"])

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Initialize database indexes and default data"""
    logger.info("Starting JarlPM API...")
    
    # Create indexes for better query performance
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token")
    await db.user_sessions.create_index("user_id")
    await db.subscriptions.create_index("user_id")
    await db.llm_provider_configs.create_index([("user_id", 1), ("provider", 1)])
    await db.epics.create_index("user_id")
    await db.epics.create_index("epic_id", unique=True)
    await db.epic_transcript_events.create_index([("epic_id", 1), ("created_at", 1)])
    await db.epic_decisions.create_index([("epic_id", 1), ("created_at", 1)])
    await db.epic_artifacts.create_index("epic_id")
    await db.payment_transactions.create_index("session_id")
    await db.prompt_templates.create_index([("stage", 1), ("is_active", 1)])
    
    # Initialize default prompt templates
    from services.prompt_service import PromptService
    prompt_service = PromptService(db)
    await prompt_service.initialize_default_prompts()
    
    logger.info("JarlPM API started successfully")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    logger.info("JarlPM API shutdown complete")
