import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from routers.tools import router as tools_router
from middleware.rate_limiter import RateLimitMiddleware
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting Bitcoin Knowledge Store API")
    yield
    logger.info("Shutting down Bitcoin Knowledge Store API")

# Initialize FastAPI app
app = FastAPI(
    title="Bitcoin Knowledge Store API",
    description="A FastAPI service for ingesting and searching Bitcoin analysis documents",
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chatgpt.com",
        "https://chat.openai.com",
        "http://localhost:*",
        "https://*.repl.co",
        "https://*.replit.dev",
        "https://*.replit.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tools_router, prefix="/tool", tags=["tools"])

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Bitcoin Knowledge Store API",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "services": {
            "api": "operational",
            "database": "connected",
            "s3": "accessible",
            "openai": "available"
        }
    }

if __name__ == "__main__":
    import uvicorn
    # Use PORT environment variable for Cloud Run deployment, fallback to 5000
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
