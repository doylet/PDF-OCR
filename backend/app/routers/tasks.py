from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from app.config import get_settings

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)
settings = get_settings()


class ExtractionTaskPayload(BaseModel):
    job_id: str
    pdf_id: str
    request_data: Dict[str, Any]


class RetryTaskPayload(BaseModel):
    job_id: str
    retry_count: int


def verify_task_auth(x_api_key: Optional[str] = Header(None)):
    """Verify task requests come from Cloud Tasks with correct API key"""
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Unauthorized task request")
    return True


@router.post("/process-extraction")
async def process_extraction_task(
    payload: ExtractionTaskPayload,
    authenticated: bool = Depends(verify_task_auth)
):
    """Process extraction job asynchronously from Cloud Tasks"""
    try:
        from app.services.jobs import job_service
        from app.routers.extraction import process_pdf_extraction
        
        logger.info(f"Processing extraction task for job {payload.job_id}")
        
        job_service.update_job_status(payload.job_id, "processing")
        
        result = await process_pdf_extraction(
            pdf_id=payload.pdf_id,
            job_id=payload.job_id,
            regions=payload.request_data.get("regions", []),
            output_format=payload.request_data.get("output_format", "csv")
        )
        
        job_service.update_job_status(
            payload.job_id,
            "completed",
            result_url=result.get("result_url"),
            debug_graph_url=result.get("debug_graph_url")
        )
        
        logger.info(f"Extraction task completed for job {payload.job_id}")
        return {"status": "completed", "job_id": payload.job_id}
        
    except Exception as e:
        logger.error(f"Extraction task failed for job {payload.job_id}: {e}")
        
        job_service.update_job_status(
            payload.job_id,
            "failed",
            error_message=str(e)
        )
        
        raise HTTPException(status_code=500, detail=f"Task processing failed: {str(e)}")


@router.post("/retry-job")
async def retry_job_task(
    payload: RetryTaskPayload,
    authenticated: bool = Depends(verify_task_auth)
):
    """Retry failed job with exponential backoff"""
    try:
        from app.services.jobs import job_service
        from app.services.task_queue import task_queue
        
        logger.info(f"Retrying job {payload.job_id} (attempt {payload.retry_count})")
        
        job = job_service.get_job(payload.job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if payload.retry_count >= 3:
            job_service.update_job_status(
                payload.job_id,
                "failed",
                error_message="Max retries exceeded"
            )
            logger.warning(f"Job {payload.job_id} exceeded max retries")
            return {"status": "failed", "reason": "max_retries_exceeded"}
        
        request_data = job.request_data if hasattr(job, 'request_data') else {}
        
        task_queue.create_extraction_task(
            job_id=payload.job_id,
            pdf_id=job.pdf_id,
            request_data=request_data,
            delay_seconds=0
        )
        
        logger.info(f"Created retry task for job {payload.job_id}")
        return {"status": "retrying", "job_id": payload.job_id, "retry_count": payload.retry_count}
        
    except Exception as e:
        logger.error(f"Retry task failed for job {payload.job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Retry failed: {str(e)}")
