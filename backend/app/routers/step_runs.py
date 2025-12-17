from fastapi import APIRouter, HTTPException, Depends, Path
from app.services.bigquery import BigQuery
from app.services.step_run import StepRun
from app.dependencies import get_bigquery_service
from pydantic import BaseModel
import logging
from typing import Optional

router = APIRouter(prefix="/api/step-runs", tags=["step-runs"])
logger = logging.getLogger(__name__)


class StepRunResponse(BaseModel):
    """Response for step run"""
    id: str
    processing_run_id: str
    step_name: str
    status: str
    model_version: str
    step_order: int
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    retry_count: int
    output_artifact_gcs_uri: Optional[str]


class StepRunRetryResponse(BaseModel):
    """Response after retry request"""
    step_run_id: str
    old_status: str
    new_status: str
    retry_count: int
    message: str


@router.get("/{step_run_id}", response_model=StepRunResponse)
async def get_step_run(
    step_run_id: str = Path(..., description="StepRun ID"),
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Get step run by ID
    
    Returns detailed information about a specific step execution.
    """
    try:
        step_run_service = StepRun(bq_service)
        step = step_run_service.get_step_run(step_run_id)
        
        if not step:
            raise HTTPException(status_code=404, detail=f"StepRun {step_run_id} not found")
        
        return StepRunResponse(**step)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving step run {step_run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{step_run_id}/retry", response_model=StepRunRetryResponse)
async def retry_step_run(
    step_run_id: str = Path(..., description="StepRun ID"),
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Retry a failed step run
    
    Only works for steps in FAILED_RETRYABLE status.
    Transitions step to PENDING and increments retry_count.
    """
    try:
        step_run_service = StepRun(bq_service)
        
        # Check step exists and is retryable
        step = step_run_service.get_step_run(step_run_id)
        if not step:
            raise HTTPException(status_code=404, detail=f"StepRun {step_run_id} not found")
        
        old_status = step["status"]
        
        if old_status != "failed_retryable":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot retry step in {old_status} status. Only failed_retryable steps can be retried."
            )
        
        # Perform retry
        step_run_service.retry_step_run(step_run_id)
        
        # Fetch updated step
        updated_step = step_run_service.get_step_run(step_run_id)
        new_status = updated_step["status"]
        retry_count = updated_step["retry_count"]
        
        logger.info(f"Retried StepRun {step_run_id}: {old_status} → {new_status} (retry_count={retry_count})")
        
        # TODO: Enqueue Cloud Task to re-execute this step
        # task_client.create_task(
        #     parent=task_queue_path,
        #     task={
        #         "http_request": {
        #             "http_method": "POST",
        #             "url": f"{settings.backend_url}/internal/execute-step-run",
        #             "body": json.dumps({"step_run_id": step_run_id}).encode(),
        #             "headers": {"Content-Type": "application/json"}
        #         }
        #     }
        # )
        
        return StepRunRetryResponse(
            step_run_id=step_run_id,
            old_status=old_status,
            new_status=new_status,
            retry_count=retry_count,
            message=f"Step queued for retry (attempt {retry_count})"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying step run {step_run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
