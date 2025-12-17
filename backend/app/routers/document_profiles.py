"""
Document Profiles API Router

Endpoints for retrieving document quality and structure metadata.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.bigquery_service import BigQueryService
from app.services.document_profile_service import DocumentProfileService
from app.dependencies import get_bigquery_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/document-profiles", tags=["Document Profiles"])


class DocumentProfileResponse(BaseModel):
    """Document profile with quality and structure metadata."""
    
    id: str
    document_version_id: str
    page_count: int
    file_size_bytes: int
    is_born_digital: Optional[bool] = None
    quality_score: Optional[float] = None
    has_tables: bool
    table_count: int
    skew_detected: bool
    max_skew_angle_degrees: float
    document_role: str
    profile_artifact_gcs_uri: Optional[str] = None
    created_at: str


class ProfileRoleQueryResponse(BaseModel):
    """Response for role-based profile queries."""
    
    profiles: list[DocumentProfileResponse]
    total_count: int
    document_role: str


@router.get("/{profile_id}", response_model=DocumentProfileResponse)
async def get_profile_by_id(
    profile_id: str,
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """Retrieve a document profile by its unique ID."""
    
    service = DocumentProfileService(bq_service)
    profile = service.get_profile_by_id(profile_id)
    
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    
    return DocumentProfileResponse(**profile)


@router.get("/document-versions/{document_version_id}", response_model=DocumentProfileResponse)
async def get_profile_for_document_version(
    document_version_id: str,
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Retrieve the document profile for a specific DocumentVersion.
    
    Returns the most recent profile if multiple exist (e.g., re-profiling after corrections).
    """
    
    service = DocumentProfileService(bq_service)
    profile = service.get_profile_for_document_version(document_version_id)
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"No profile found for document_version {document_version_id}"
        )
    
    return DocumentProfileResponse(**profile)


@router.get("/roles/{document_role}", response_model=ProfileRoleQueryResponse)
async def get_profiles_by_role(
    document_role: str,
    quality_min: Optional[float] = None,
    limit: int = 100,
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Query document profiles by role with optional quality filtering.
    
    Example roles:
    - primary_claim_form
    - medical_evidence
    - billing_statement
    - policy_document
    - supporting_document
    - unknown
    
    Quality score ranges from 0.0 to 1.0 (Document AI quality metric).
    """
    
    service = DocumentProfileService(bq_service)
    profiles = service.get_profiles_by_role(
        document_role=document_role,
        quality_min=quality_min,
        limit=limit
    )
    
    return ProfileRoleQueryResponse(
        profiles=[DocumentProfileResponse(**p) for p in profiles],
        total_count=len(profiles),
        document_role=document_role
    )


@router.get("/skewed-documents", response_model=list[DocumentProfileResponse])
async def get_skewed_documents(
    min_skew_degrees: float = 5.0,
    limit: int = 100,
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Find documents with skew issues requiring correction.
    
    Returns profiles ordered by severity (highest skew first).
    Useful for identifying poor-quality scans that may need preprocessing.
    """
    
    service = DocumentProfileService(bq_service)
    profiles = service.get_skewed_documents(
        min_skew_degrees=min_skew_degrees,
        limit=limit
    )
    
    return [DocumentProfileResponse(**p) for p in profiles]
