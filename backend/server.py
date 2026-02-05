from fastapi import FastAPI, APIRouter, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
import sys

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app
app = FastAPI(
    title="JarlPM API",
    description="AI-agnostic Product Management System",
    version="1.0.0"
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Import and include route modules
from routes.auth import router as auth_router
from routes.subscription import router as subscription_router
from routes.llm_provider import router as llm_provider_router
from routes.epic import router as epic_router
from routes.delivery_context import router as delivery_context_router
from routes.feature import router as feature_router
from routes.user_story import router as user_story_router
from routes.bug import router as bug_router
from routes.persona import router as persona_router
from routes.scoring import router as scoring_router
from routes.export import router as export_router
from routes.poker import router as poker_router
from routes.initiative import router as initiative_router
from routes.initiatives import router as initiatives_router
from routes.delivery_reality import router as delivery_reality_router
from routes.dashboard import router as dashboard_router
from routes.lean_canvas import router as lean_canvas_router
from routes.prd import router as prd_router

api_router.include_router(auth_router)
api_router.include_router(subscription_router)
api_router.include_router(llm_provider_router)
api_router.include_router(epic_router)
api_router.include_router(delivery_context_router)
api_router.include_router(feature_router)
api_router.include_router(user_story_router)
api_router.include_router(bug_router)
api_router.include_router(persona_router)
api_router.include_router(scoring_router)
api_router.include_router(export_router)
api_router.include_router(poker_router)
api_router.include_router(initiative_router)
api_router.include_router(initiatives_router)
api_router.include_router(delivery_reality_router)
api_router.include_router(dashboard_router)
api_router.include_router(lean_canvas_router)
api_router.include_router(prd_router)

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
    """Initialize database and default data"""
    logger.info("Starting JarlPM API...")
    
    # Initialize PostgreSQL database
    from db.database import init_db, AsyncSessionLocal
    await init_db()
    
    # Initialize default prompt templates
    if AsyncSessionLocal:
        from services.prompt_service import PromptService
        async with AsyncSessionLocal() as session:
            prompt_service = PromptService(session)
            await prompt_service.initialize_default_prompts()
    
    logger.info("JarlPM API started successfully with PostgreSQL")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    from db.database import engine
    if engine:
        await engine.dispose()
    logger.info("JarlPM API shutdown complete")
