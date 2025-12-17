"""
Evidence Bundles API Router

Endpoints for searching claims and creating evidence packages.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.bigquery import BigQuery
from app.services.evidence import Evidence
from app.dependencies import get_bigquery_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/evidence", tags=["Evidence"])


class EvidenceSearchRequest(BaseModel):
    """Request to search for evidence across documents."""
    
    room_id: Optional[str] = None
    document_version_ids: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    claim_types: Optional[List[str]] = None
    confidence_min: float = 0.0
    limit: int = 100


class ClaimEvidenceResponse(BaseModel):
    """Claim with relevance scoring for evidence search."""
    
    id: str
    claim_type: str
    normalized_value: str
    confidence: float
    source_text: Optional[str] = None
    document_version_id: str
    step_run_id: str
    page_number: Optional[int] = None
    bounding_box: Optional[dict] = None
    user_feedback_json: Optional[dict] = None
    created_at: str
    relevance_score: int


class CreateEvidenceBundleRequest(BaseModel):
    """Request to create an evidence bundle."""
    
    name: str = Field(..., min_length=1, max_length=200)
    room_id: Optional[str] = None
    claim_ids: List[str] = Field(..., min_items=1)
    description: Optional[str] = None
    created_by_user_id: Optional[str] = None
    metadata: Optional[dict] = None


class EvidenceBundleResponse(BaseModel):
    """Evidence bundle entity."""
    
    id: str
    name: str
    description: Optional[str] = None
    room_id: Optional[str] = None
    claim_ids: List[str]
    claim_count: int
    created_at: str
    created_by_user_id: Optional[str] = None
    metadata: Optional[dict] = None


class EvidenceBundleWithClaimsResponse(BaseModel):
    """Evidence bundle with full claim details."""
    
    id: str
    name: str
    description: Optional[str] = None
    room_id: Optional[str] = None
    claim_ids: List[str]
    claim_count: int
    created_at: str
    created_by_user_id: Optional[str] = None
    metadata: Optional[dict] = None
    claims: List[dict]


class BundleStatisticsResponse(BaseModel):
    """Statistics for an evidence bundle."""
    
    bundle_id: str
    claim_count: int
    claim_types: dict
    avg_confidence: float
    document_count: int


@router.post("/search", response_model=List[ClaimEvidenceResponse])
async def search_evidence(
    request: EvidenceSearchRequest,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Search for claims matching evidence criteria.
    
    Performs keyword-based text search across claims with relevance ranking.
    Can scope search to a Room or specific DocumentVersions.
    
    Returns claims ordered by relevance score and confidence.
    """
    
    service = Evidence(bq_service)
    
    claims = service.search_evidence(
        room_id=request.room_id,
        document_version_ids=request.document_version_ids,
        keywords=request.keywords,
        claim_types=request.claim_types,
        confidence_min=request.confidence_min,
        limit=request.limit
    )
    
    return [ClaimEvidenceResponse(**claim) for claim in claims]


@router.post("/bundles", response_model=EvidenceBundleResponse, status_code=201)
async def create_evidence_bundle(
    request: CreateEvidenceBundleRequest,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Create an immutable Evidence Bundle from selected claims.
    
    Evidence bundles provide audit trails for decision-making processes
    by capturing a snapshot of relevant claims at a point in time.
    """
    
    service = Evidence(bq_service)
    
    bundle = service.create_evidence_bundle(
        name=request.name,
        room_id=request.room_id,
        claim_ids=request.claim_ids,
        description=request.description,
        created_by_user_id=request.created_by_user_id,
        metadata=request.metadata
    )
    
    return EvidenceBundleResponse(**bundle)


@router.get("/bundles/{bundle_id}", response_model=EvidenceBundleResponse)
async def get_evidence_bundle(
    bundle_id: str,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """Retrieve an evidence bundle by ID."""
    
    service = Evidence(bq_service)
    bundle = service.get_evidence_bundle(bundle_id)
    
    if not bundle:
        raise HTTPException(
            status_code=404,
            detail=f"Evidence bundle {bundle_id} not found"
        )
    
    return EvidenceBundleResponse(**bundle)


@router.get("/bundles/{bundle_id}/full", response_model=EvidenceBundleWithClaimsResponse)
async def get_evidence_bundle_with_claims(
    bundle_id: str,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Retrieve an evidence bundle with full claim details.
    
    Returns the bundle metadata plus all associated claims in a single response.
    Useful for rendering complete evidence packages.
    """
    
    service = Evidence(bq_service)
    bundle = service.get_evidence_bundle_with_claims(bundle_id)
    
    if not bundle:
        raise HTTPException(
            status_code=404,
            detail=f"Evidence bundle {bundle_id} not found"
        )
    
    return EvidenceBundleWithClaimsResponse(**bundle)


@router.get("/bundles", response_model=List[EvidenceBundleResponse])
async def list_evidence_bundles(
    room_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """List evidence bundles with optional Room filtering."""
    
    service = Evidence(bq_service)
    bundles = service.list_evidence_bundles(
        room_id=room_id,
        limit=limit,
        offset=offset
    )
    
    return [EvidenceBundleResponse(**bundle) for bundle in bundles]


@router.get("/bundles/{bundle_id}/statistics", response_model=BundleStatisticsResponse)
async def get_bundle_statistics(
    bundle_id: str,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Calculate statistics for an evidence bundle.
    
    Returns:
    - Claim type distribution
    - Average confidence per type and overall
    - Number of source documents
    """
    
    service = Evidence(bq_service)
    stats = service.get_claim_statistics_for_bundle(bundle_id)
    
    if not stats:
        raise HTTPException(
            status_code=404,
            detail=f"Evidence bundle {bundle_id} not found"
        )
    
    return BundleStatisticsResponse(**stats)
