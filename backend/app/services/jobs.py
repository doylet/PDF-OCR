from google.cloud import firestore
from app.config import get_settings
from app.dependencies import get_firestore_client
from app.models import JobStatus
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class JobService:
    """Service for managing extraction jobs in Firestore"""
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection = settings.firestore_collection
    
    def create_job(self, job_id: str, pdf_id: str, regions_count: int) -> JobStatus:
        """Create a new extraction job"""
        now = datetime.utcnow()
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "pdf_id": pdf_id,
            "regions_count": regions_count,
            "result_url": None,
            "error_message": None
        }
        
        self.db.collection(self.collection).document(job_id).set(job_data)
        logger.info(f"Created job: {job_id}")
        
        return JobStatus(**job_data)
    
    def get_job(self, job_id: str) -> Optional[JobStatus]:
        """Get job status"""
        doc = self.db.collection(self.collection).document(job_id).get()
        
        if not doc.exists:
            return None
        
        return JobStatus(**doc.to_dict())
    
    def update_job_status(self, job_id: str, status: str, result_url: Optional[str] = None, error_message: Optional[str] = None):
        """Update job status"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if result_url:
            update_data["result_url"] = result_url
        
        if error_message:
            update_data["error_message"] = error_message
        
        self.db.collection(self.collection).document(job_id).update(update_data)
        logger.info(f"Updated job {job_id} to status: {status}")


job_service = JobService()
