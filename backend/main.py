"""
FastAPI Application - PDF OCR Backend

This application provides a comprehensive API for document processing, extraction,
and analysis using GCP Document AI and BigQuery.

Architecture:
- Document versioning with SHA-256 deduplication
- ProcessingRuns for tracking pipeline execution
- Claims extraction with HITL feedback
- Document profiling for quality assessment
- Rooms for multi-document analysis
- Evidence bundles for decision support
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    upload,
    documents,
    document_profiles,
    rooms,
    processing_runs,
    step_runs,
    claims,
    evidence,
    extraction,  # Legacy: Direct extraction endpoint
    feedback,  # Legacy: HITL feedback endpoint
    tasks,  # Cloud Tasks handlers
)
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
    description="Document processing API with BigQuery persistence and Document AI integration",
    version="2.0.0",
    debug=settings.debug
)

# Configure CORS
logger.info(f"CORS Origins: {settings.cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Core API routers (BigQuery-backed)
app.include_router(upload.router)
app.include_router(documents.router)
app.include_router(document_profiles.router)
app.include_router(rooms.router)
app.include_router(processing_runs.router)
app.include_router(step_runs.router)
app.include_router(claims.router)
app.include_router(evidence.router)

# Legacy routers (Firestore-backed, for backward compatibility)
app.include_router(extraction.router)
app.include_router(feedback.router)

# Task handlers (Cloud Tasks callbacks)
app.include_router(tasks.router)


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
