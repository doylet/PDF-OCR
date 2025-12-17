from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.services.firestore_service import FirestoreService
from app.dependencies import get_firestore_service

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


class BBox(BaseModel):
    x: float = Field(..., ge=0, le=1)
    y: float = Field(..., ge=0, le=1)
    w: float = Field(..., ge=0, le=1)
    h: float = Field(..., ge=0, le=1)


class DetectedRegion(BaseModel):
    region_id: str
    page: int
    bbox: BBox
    region_type: str
    confidence: float = Field(..., ge=0, le=1)


class RegionCorrection(BaseModel):
    original: DetectedRegion
    corrected: Optional[DetectedRegion] = None
    action: str = Field(..., pattern="^(delete|move|resize|retype)$")
    timestamp: str


class FeedbackSubmission(BaseModel):
    job_id: str
    corrections: List[RegionCorrection]
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    job_id: str
    corrections_count: int
    timestamp: str
    message: str


@router.post("/corrections", response_model=FeedbackResponse)
async def submit_corrections(
    submission: FeedbackSubmission,
    firestore: FirestoreService = Depends(get_firestore_service),
):
    try:
        # Store feedback in Firestore
        feedback_doc = {
            "job_id": submission.job_id,
            "corrections": [c.dict() for c in submission.corrections],
            "corrections_count": len(submission.corrections),
            "user_id": submission.user_id,
            "session_id": submission.session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending_analysis",
        }
        
        # Store in Firestore under 'region_feedback' collection
        doc_ref = firestore.db.collection("region_feedback").document()
        doc_ref.set(feedback_doc)
        
        # Update job document with feedback flag
        job_ref = firestore.db.collection("jobs").document(submission.job_id)
        job_ref.update({
            "has_feedback": True,
            "feedback_count": firestore.increment(len(submission.corrections)),
            "last_feedback_at": datetime.utcnow().isoformat(),
        })
        
        return FeedbackResponse(
            feedback_id=doc_ref.id,
            job_id=submission.job_id,
            corrections_count=len(submission.corrections),
            timestamp=feedback_doc["timestamp"],
            message=f"Successfully recorded {len(submission.corrections)} corrections for reinforcement learning",
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store feedback: {str(e)}")


@router.get("/corrections/{job_id}")
async def get_corrections(
    job_id: str,
    firestore: FirestoreService = Depends(get_firestore_service),
):
    try:
        # Query feedback for this job
        feedback_docs = (
            firestore.db.collection("region_feedback")
            .where("job_id", "==", job_id)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .stream()
        )
        
        results = []
        for doc in feedback_docs:
            data = doc.to_dict()
            data["feedback_id"] = doc.id
            results.append(data)
        
        return {
            "job_id": job_id,
            "feedback_count": len(results),
            "feedback": results,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve feedback: {str(e)}")


@router.get("/stats")
async def get_feedback_stats(
    firestore: FirestoreService = Depends(get_firestore_service),
):
    try:
        # Get all feedback documents
        feedback_docs = firestore.db.collection("region_feedback").stream()
        
        total_feedback = 0
        total_corrections = 0
        action_counts = {"delete": 0, "move": 0, "resize": 0, "retype": 0}
        region_type_errors = {}
        
        for doc in feedback_docs:
            data = doc.to_dict()
            total_feedback += 1
            corrections = data.get("corrections", [])
            total_corrections += len(corrections)
            
            for correction in corrections:
                action = correction.get("action")
                if action in action_counts:
                    action_counts[action] += 1
                
                original = correction.get("original", {})
                region_type = original.get("region_type", "UNKNOWN")
                region_type_errors[region_type] = region_type_errors.get(region_type, 0) + 1
        
        return {
            "total_feedback_submissions": total_feedback,
            "total_corrections": total_corrections,
            "corrections_by_action": action_counts,
            "errors_by_region_type": region_type_errors,
            "avg_corrections_per_submission": round(total_corrections / total_feedback, 2) if total_feedback > 0 else 0,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")
