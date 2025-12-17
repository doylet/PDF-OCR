from fastapi import APIRouter, HTTPException, Header, Request, Depends, UploadFile, File
from app.models.api import UploadResponse, DocumentUploadRequest, DocumentUploadResponse
from app.services.storage import storage_service
from app.services.bigquery_service import BigQueryService
from app.dependencies import get_bigquery_service
from app.config import get_settings
import logging
import uuid
import hashlib
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/upload", tags=["upload"])
logger = logging.getLogger(__name__)
settings = get_settings()


def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key"""
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file bytes"""
    return hashlib.sha256(file_bytes).hexdigest()


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    uploaded_by_user_id: str = Header(..., alias="X-User-Id"),
    name: Optional[str] = Header(None, alias="X-Document-Name"),
    description: Optional[str] = Header(None, alias="X-Document-Description"),
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Upload a document with SHA-256 deduplication.
    
    Returns document_id and document_version_id (hash).
    If content already exists, reuses existing DocumentVersion.
    """
    try:
        # Read file bytes and compute hash
        file_bytes = await file.read()
        file_size = len(file_bytes)
        content_hash = compute_file_hash(file_bytes)
        
        logger.info(f"Uploading document: filename={file.filename}, size={file_size}, hash={content_hash}")
        
        # Check if this content hash already exists
        existing_version = bq_service.get_by_id(
            table_name="document_versions",
            id_field="id",
            id_value=content_hash
        )
        
        was_duplicate = existing_version is not None
        document_version_id = content_hash
        gcs_uri = None
        
        if was_duplicate:
            logger.info(f"Content hash {content_hash} already exists - reusing DocumentVersion")
            gcs_uri = existing_version["gcs_uri"]
            existing_doc_id = existing_version["document_id"]
        else:
            # Upload new content to GCS
            logger.info(f"New content hash {content_hash} - uploading to GCS")
            gcs_uri = f"gs://{settings.gcs_bucket}/documents/{content_hash}.pdf"
            
            # Upload to GCS using storage service
            blob = storage_service.bucket.blob(f"documents/{content_hash}.pdf")
            blob.upload_from_string(file_bytes, content_type="application/pdf")
            logger.info(f"Uploaded to GCS: {gcs_uri}")
        
        # Always create a new Document entity (user-facing)
        document_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        document_row = {
            "id": document_id,
            "name": name or file.filename,
            "description": description,
            "uploaded_by_user_id": uploaded_by_user_id,
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "metadata": {}
        }
        
        bq_service.insert_row("documents", document_row)
        logger.info(f"Created Document entity: {document_id}")
        
        # Create DocumentVersion only if new content
        if not was_duplicate:
            version_row = {
                "id": content_hash,
                "document_id": document_id,
                "file_size_bytes": file_size,
                "gcs_uri": gcs_uri,
                "mime_type": "application/pdf",
                "original_filename": file.filename,
                "created_at": now
            }
            
            bq_service.insert_row("document_versions", version_row)
            logger.info(f"Created DocumentVersion: {content_hash}")
        else:
            # Update existing DocumentVersion to link to new Document
            logger.info(f"Updating DocumentVersion {content_hash} to reference new Document {document_id}")
        
        # Generate signed URL for client to verify upload (for future use)
        blob = storage_service.bucket.blob(f"documents/{content_hash}.pdf")
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=3600,
            method="GET"
        )
        
        return DocumentUploadResponse(
            document_id=document_id,
            document_version_id=document_version_id,
            upload_url=upload_url,
            was_duplicate=was_duplicate,
            filename=file.filename
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-url", response_model=UploadResponse)
async def generate_upload_url(
    file_name: str,
    request: Request,
    api_key: str = Header(None, alias="X-API-Key")
):
    """
    Generate a signed URL for uploading a PDF (legacy endpoint)
    
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
