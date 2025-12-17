from fastapi import APIRouter, HTTPException, Depends, Path
from app.services.bigquery_service import BigQueryService
from app.dependencies import get_bigquery_service
from app.models.api import DocumentUploadResponse
from pydantic import BaseModel, Field
import logging
from typing import Optional, List
from datetime import datetime

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)


class DocumentResponse(BaseModel):
    """Response for document retrieval"""
    id: str
    name: str
    description: Optional[str]
    uploaded_by_user_id: str
    created_at: str
    updated_at: Optional[str]
    status: str
    metadata: dict


class DocumentVersionResponse(BaseModel):
    """Response for document version retrieval"""
    id: str  # SHA-256 hash
    document_id: str
    file_size_bytes: int
    gcs_uri: str
    mime_type: str
    original_filename: str
    created_at: str


class DocumentUpdateRequest(BaseModel):
    """Request to update document metadata"""
    name: Optional[str] = Field(None, description="Update display name")
    description: Optional[str] = Field(None, description="Update description")
    metadata: Optional[dict] = Field(None, description="Update metadata")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str = Path(..., description="Document ID"),
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Get document by ID
    
    Returns user-facing document entity with mutable metadata.
    """
    try:
        document = bq_service.get_by_id(
            table_name="documents",
            id_field="id",
            id_value=document_id
        )
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
        return DocumentResponse(**document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/versions", response_model=List[DocumentVersionResponse])
async def get_document_versions(
    document_id: str = Path(..., description="Document ID"),
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Get all versions for a document
    
    Returns list of DocumentVersions linked to this Document.
    """
    try:
        versions = bq_service.query(
            table_name="document_versions",
            filters=[{"field": "document_id", "op": "=", "value": document_id}],
            order_by=[{"field": "created_at", "direction": "DESC"}]
        )
        
        return [DocumentVersionResponse(**v) for v in versions]
        
    except Exception as e:
        logger.error(f"Error retrieving versions for document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{version_id}", response_model=DocumentVersionResponse)
async def get_document_version(
    version_id: str = Path(..., description="DocumentVersion ID (SHA-256 hash)"),
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Get document version by ID (SHA-256 hash)
    
    Returns immutable content reference.
    """
    try:
        version = bq_service.get_by_id(
            table_name="document_versions",
            id_field="id",
            id_value=version_id
        )
        
        if not version:
            raise HTTPException(status_code=404, detail=f"DocumentVersion {version_id} not found")
        
        return DocumentVersionResponse(**version)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document version {version_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str = Path(..., description="Document ID"),
    update: DocumentUpdateRequest = ...,
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Update document metadata
    
    Updates mutable fields (name, description, metadata).
    Does not affect immutable DocumentVersion content.
    """
    try:
        # Check document exists
        document = bq_service.get_by_id(
            table_name="documents",
            id_field="id",
            id_value=document_id
        )
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
        # Build updates dict (only non-None fields)
        updates = {}
        if update.name is not None:
            updates["name"] = update.name
        if update.description is not None:
            updates["description"] = update.description
        if update.metadata is not None:
            updates["metadata"] = update.metadata
        
        if not updates:
            # No updates provided, return existing
            return DocumentResponse(**document)
        
        # Perform update
        bq_service.update_row(
            table_name="documents",
            id_field="id",
            id_value=document_id,
            updates=updates
        )
        
        # Fetch updated document
        updated_document = bq_service.get_by_id(
            table_name="documents",
            id_field="id",
            id_value=document_id
        )
        
        return DocumentResponse(**updated_document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
