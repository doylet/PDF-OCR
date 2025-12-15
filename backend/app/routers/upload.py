from fastapi import APIRouter, HTTPException, Header, Request
from app.models import UploadResponse
from app.services.storage import storage_service
from app.config import get_settings
import logging

router = APIRouter(prefix="/api/upload", tags=["upload"])
logger = logging.getLogger(__name__)
settings = get_settings()


def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key"""
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@router.post("/generate-url", response_model=UploadResponse)
async def generate_upload_url(
    file_name: str,
    request: Request,
    api_key: str = Header(None, alias="X-API-Key")
):
    """
    Generate a signed URL for uploading a PDF
    
    - **file_name**: Name of the PDF file to upload
    """
    # Skip API key check for testing
    # TODO: Re-enable with correct key management
    # if api_key:
    #     verify_api_key(api_key)
    
    try:
        pdf_id, upload_url = storage_service.generate_upload_url(file_name)
        
        return UploadResponse(
            pdf_id=pdf_id,
            upload_url=upload_url,
            file_name=file_name
        )
    except Exception as e:
        logger.error(f"Error generating upload URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))
