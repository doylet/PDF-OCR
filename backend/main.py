from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import upload, extraction, feedback, documents, processing_runs, step_runs, claims
from app.config import get_settings
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="API for extracting structured data from PDF regions using GCP Document AI",
    version="1.0.0",
    debug=settings.debug
)

# Configure CORS
logger.info(f"CORS Origins: {settings.cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Temporary: allow all origins for testing
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Include routers
app.include_router(upload.router)
app.include_router(documents.router)
app.include_router(processing_runs.router)
app.include_router(step_runs.router)
app.include_router(claims.router)
app.include_router(extraction.router)
app.include_router(feedback.router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check for Cloud Run"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
