"""
Health and diagnostics router

Provides health check and system diagnostics endpoints for monitoring.
"""
from fastapi import APIRouter
from typing import Dict
import logging
import sys
import subprocess

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> Dict:
    """Basic health check - returns 200 if service is running"""
    return {
        "status": "healthy",
        "service": "pdf-ocr-backend",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    }


@router.get("/dependencies")
async def check_dependencies() -> Dict:
    """Check system and Python dependencies"""
    dependencies = {
        "system": {},
        "python": {},
        "status": "healthy"
    }
    
    # Check Ghostscript
    try:
        result = subprocess.run(
            ["gs", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        dependencies["system"]["ghostscript"] = {
            "installed": True,
            "version": result.stdout.strip()
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        dependencies["system"]["ghostscript"] = {
            "installed": False,
            "error": "Not found in PATH",
            "install_instructions": "brew install ghostscript (macOS) or apt-get install ghostscript (Ubuntu)"
        }
        dependencies["status"] = "degraded"
    
    # Check Poppler (pdftoppm)
    try:
        result = subprocess.run(
            ["pdftoppm", "-v"],
            capture_output=True,
            text=True
        )
        dependencies["system"]["poppler"] = {
            "installed": True,
            "version": result.stderr.strip().split('\n')[0] if result.stderr else "unknown"
        }
    except FileNotFoundError:
        dependencies["system"]["poppler"] = {
            "installed": False,
            "error": "Not found in PATH",
            "install_instructions": "brew install poppler (macOS) or apt-get install poppler-utils (Ubuntu)"
        }
        dependencies["status"] = "degraded"
    
    # Check Python packages
    packages = [
        ("camelot", "camelot-py[cv]"),
        ("google.cloud.storage", "google-cloud-storage"),
        ("google.cloud.documentai", "google-cloud-documentai"),
        ("fastapi", "fastapi"),
    ]
    
    for import_name, package_name in packages:
        try:
            module = __import__(import_name)
            version = getattr(module, "__version__", "unknown")
            dependencies["python"][package_name] = {
                "installed": True,
                "version": version
            }
        except ImportError as e:
            dependencies["python"][package_name] = {
                "installed": False,
                "error": str(e)
            }
            dependencies["status"] = "unhealthy"
    
    return dependencies


@router.get("/diagnostics")
async def diagnostics() -> Dict:
    """Detailed system diagnostics"""
    from app.config import get_settings
    
    settings = get_settings()
    
    # Check service availability
    services = {}
    
    # Check Table Extractor
    try:
        from app.services.table_extractor import TableExtractor
        services["camelot_table_extraction"] = {
            "available": TableExtractor.is_available(),
            "notes": "Requires Ghostscript"
        }
    except Exception as e:
        services["camelot_table_extraction"] = {
            "available": False,
            "error": str(e)
        }
    
    # Check GCS
    try:
        from app.services.storage import storage_service
        services["gcs_storage"] = {
            "available": True,
            "bucket": settings.gcs_bucket_name
        }
    except Exception as e:
        services["gcs_storage"] = {
            "available": False,
            "error": str(e)
        }
    
    # Check Document AI
    try:
        from app.services.documentai import documentai_service
        services["document_ai"] = {
            "available": True,
            "processor_id": settings.gcp_processor_id
        }
    except Exception as e:
        services["document_ai"] = {
            "available": False,
            "error": str(e)
        }
    
    return {
        "services": services,
        "config": {
            "gcp_project": settings.gcp_project_id,
            "gcp_location": settings.gcp_location,
            "debug_mode": settings.debug,
            "llm_enabled": settings.enable_llm_agents
        }
    }
