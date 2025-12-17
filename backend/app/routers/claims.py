from fastapi import APIRouter, HTTPException, Depends, Path, Query
from app.services.bigquery import BigQuery
from app.container import get_claims
from app.dependencies import get_bigquery_service
from pydantic import BaseModel, Field
import logging
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/api/claims", tags=["claims"])
logger = logging.getLogger(__name__)


class BoundingBox(BaseModel):
    """Bounding box coordinates"""
    x: float = Field(..., description="X coordinate (pixels)")
    y: float = Field(..., description="Y coordinate (pixels)")
    width: float = Field(..., description="Width (pixels)")
    height: float = Field(..., description="Height (pixels)")


class ClaimResponse(BaseModel):
    """Response for claim retrieval"""
    id: str
    document_version_id: str
    room_id: Optional[str]
    step_run_id: str
    claim_type: str
    value: str
    normalized_value: str
    confidence: float
    page_number: int
    bbox_x: float
    bbox_y: float
    bbox_width: float
    bbox_height: float
    source_text: Optional[str]
    user_feedback_json: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    created_at: str


class ClaimFeedbackRequest(BaseModel):
    """Request to provide feedback on a claim"""
    is_correct: bool = Field(..., description="Whether the claim is correct")
    corrected_value: Optional[str] = Field(None, description="Corrected value if incorrect")
    notes: Optional[str] = Field(None, description="Optional feedback notes")
    reviewer_id: Optional[str] = Field(None, description="User providing feedback")


class ClaimsListResponse(BaseModel):
    """Response for claims list"""
    claims: List[ClaimResponse]
    total_count: int
    limit: int
    offset: int


@router.get("", response_model=List[ClaimResponse])
async def list_claims(
    document_version_id: Optional[str] = Query(None, description="Filter by DocumentVersion"),
    claim_type: Optional[str] = Query(None, description="Filter by claim type"),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    room_id: Optional[str] = Query(None, description="Filter by Room"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    List claims with optional filtering.
    
    Supports filtering by document, claim type, confidence, and room.
    Results are ordered by page number and confidence.
    """
    try:
        claims_service = Claims(bq_service)
        
        if document_version_id:
            claims = claims_service.get_claims_for_document(
                document_version_id=document_version_id,
                claim_type=claim_type,
                confidence_min=confidence_min,
                room_id=room_id,
                limit=limit,
                offset=offset
            )
        elif claim_type:
            claims = claims_service.get_claims_by_type(
                claim_type=claim_type,
                confidence_min=confidence_min,
                limit=limit,
                offset=offset
            )
        else:
            # Query all claims with filters (expensive - should require at least one filter)
            raise HTTPException(
                status_code=400,
                detail="Must provide at least document_version_id or claim_type filter"
            )
        
        return [ClaimResponse(**claim) for claim in claims]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing claims: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: str = Path(..., description="Claim ID"),
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Get a specific claim by ID.
    
    Returns full claim details including bounding box and provenance.
    """
    try:
        claims_service = Claims(bq_service)
        claim = claims_service.get_claim_by_id(claim_id)
        
        if not claim:
            raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
        
        return ClaimResponse(**claim)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving claim {claim_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{claim_id}/feedback", response_model=ClaimResponse)
async def submit_claim_feedback(
    claim_id: str = Path(..., description="Claim ID"),
    feedback: ClaimFeedbackRequest = ...,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Submit human-in-the-loop feedback for a claim.
    
    Stores feedback without modifying the original claim values (immutability).
    Feedback can be used for model retraining and confidence scoring.
    """
    try:
        claims_service = Claims(bq_service)
        
        # Build feedback object
        feedback_data = {
            "is_correct": feedback.is_correct,
            "corrected_value": feedback.corrected_value,
            "notes": feedback.notes,
            "reviewer_id": feedback.reviewer_id,
            "submitted_at": datetime.utcnow().isoformat()
        }
        
        success = claims_service.update_claim_feedback(claim_id, feedback_data)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
        
        # Fetch updated claim
        updated_claim = claims_service.get_claim_by_id(claim_id)
        logger.info(f"Feedback submitted for Claim {claim_id} by {feedback.reviewer_id or 'anonymous'}")
        
        return ClaimResponse(**updated_claim)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback for claim {claim_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document-versions/{document_version_id}/summary")
async def get_claims_summary(
    document_version_id: str = Path(..., description="DocumentVersion ID"),
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Get summary statistics for claims in a document.
    
    Returns counts by claim type, average confidence, and feedback statistics.
    """
    try:
        claims_service = Claims(bq_service)
        
        # Get all claims for document
        all_claims = claims_service.get_claims_for_document(
            document_version_id=document_version_id,
            limit=10000  # High limit for summary
        )
        
        # Calculate statistics
        total_claims = len(all_claims)
        
        if total_claims == 0:
            return {
                "document_version_id": document_version_id,
                "total_claims": 0,
                "by_type": {},
                "average_confidence": 0.0,
                "feedback_stats": {"reviewed": 0, "correct": 0, "corrected": 0}
            }
        
        # Group by type
        by_type = {}
        total_confidence = 0.0
        feedback_stats = {"reviewed": 0, "correct": 0, "corrected": 0}
        
        for claim in all_claims:
            claim_type = claim["claim_type"]
            if claim_type not in by_type:
                by_type[claim_type] = {"count": 0, "avg_confidence": 0.0, "confidences": []}
            
            by_type[claim_type]["count"] += 1
            by_type[claim_type]["confidences"].append(claim["confidence"])
            total_confidence += claim["confidence"]
            
            # Check feedback
            if claim.get("user_feedback_json"):
                feedback_stats["reviewed"] += 1
                if claim["user_feedback_json"].get("is_correct"):
                    feedback_stats["correct"] += 1
                else:
                    feedback_stats["corrected"] += 1
        
        # Calculate averages
        for claim_type in by_type:
            confidences = by_type[claim_type]["confidences"]
            by_type[claim_type]["avg_confidence"] = sum(confidences) / len(confidences)
            del by_type[claim_type]["confidences"]  # Remove raw list
        
        return {
            "document_version_id": document_version_id,
            "total_claims": total_claims,
            "by_type": by_type,
            "average_confidence": total_confidence / total_claims,
            "feedback_stats": feedback_stats
        }
        
    except Exception as e:
        logger.error(f"Error generating claims summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Import datetime at module level
from datetime import datetime
