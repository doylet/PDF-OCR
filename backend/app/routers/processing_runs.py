from fastapi import APIRouter, HTTPException, Depends, Path, Query
from app.services.bigquery_service import BigQueryService
from app.services.processing_run_service import ProcessingRunService
from app.services.step_run_service import StepRunService
from app.dependencies import get_bigquery_service
from pydantic import BaseModel, Field
import logging
from typing import Optional, List
from datetime import datetime

router = APIRouter(prefix="/api/processing-runs", tags=["processing-runs"])
logger = logging.getLogger(__name__)


class ProcessingRunCreateRequest(BaseModel):
    """Request to create a processing run"""
    document_version_id: str = Field(..., description="DocumentVersion ID (SHA-256 hash)")
    run_type: str = Field("full_extraction", description="Type of processing run")
    user_id: Optional[str] = Field(None, description="User initiating the run")
    config: Optional[dict] = Field(default_factory=dict, description="Processing configuration")


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


class ProcessingRunResponse(BaseModel):
    """Response for processing run"""
    id: str
    document_version_id: str
    run_type: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    created_at: str
    updated_at: Optional[str]
    steps: Optional[List[StepRunResponse]] = None


@router.post("", response_model=ProcessingRunResponse, status_code=201)
async def create_processing_run(
    request: ProcessingRunCreateRequest,
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Create a new processing run for a document version
    
    Initializes ProcessingRun with PENDING status.
    In production, this would also enqueue a Cloud Task to execute the pipeline.
    """
    try:
        # Verify document version exists
        doc_version = bq_service.get_by_id(
            table_name="document_versions",
            id_field="id",
            id_value=request.document_version_id
        )
        
        if not doc_version:
            raise HTTPException(
                status_code=404,
                detail=f"DocumentVersion {request.document_version_id} not found"
            )
        
        # Create processing run
        processing_run_service = ProcessingRunService(bq_service)
        run = processing_run_service.create_processing_run(
            doc_version_id=request.document_version_id,
            run_type=request.run_type,
            config=request.config,
            user_id=request.user_id
        )
        
        logger.info(f"Created ProcessingRun {run['id']} for DocumentVersion {request.document_version_id}")
        
        # TODO: Enqueue Cloud Task to execute pipeline
        # task_client.create_task(
        #     parent=task_queue_path,
        #     task={
        #         "http_request": {
        #             "http_method": "POST",
        #             "url": f"{settings.backend_url}/internal/execute-processing-run",
        #             "body": json.dumps({"run_id": run["id"]}).encode(),
        #             "headers": {"Content-Type": "application/json"}
        #         }
        #     }
        # )
        
        return ProcessingRunResponse(**run)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating processing run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}", response_model=ProcessingRunResponse)
async def get_processing_run(
    run_id: str = Path(..., description="ProcessingRun ID"),
    include_steps: bool = Query(False, description="Include step details"),
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Get processing run status with optional step details
    
    Used for polling run progress.
    """
    try:
        processing_run_service = ProcessingRunService(bq_service)
        run = processing_run_service.get_processing_run(run_id)
        
        if not run:
            raise HTTPException(status_code=404, detail=f"ProcessingRun {run_id} not found")
        
        response_data = {**run}
        
        if include_steps:
            # Fetch all steps for this run
            step_run_service = StepRunService(bq_service)
            steps = step_run_service.list_steps_for_run(run_id)
            response_data["steps"] = [StepRunResponse(**step) for step in steps]
        
        return ProcessingRunResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving processing run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[ProcessingRunResponse])
async def list_processing_runs(
    document_version_id: Optional[str] = Query(None, description="Filter by DocumentVersion"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    List processing runs with filters
    
    Supports pagination and filtering by document_version_id and status.
    """
    try:
        processing_run_service = ProcessingRunService(bq_service)
        runs = processing_run_service.list_runs(
            doc_version_id=document_version_id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return [ProcessingRunResponse(**run) for run in runs]
        
    except Exception as e:
        logger.error(f"Error listing processing runs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{run_id}/cancel", response_model=ProcessingRunResponse)
async def cancel_processing_run(
    run_id: str = Path(..., description="ProcessingRun ID"),
    bq_service: BigQueryService = Depends(get_bigquery_service)
):
    """
    Cancel a processing run
    
    Transitions run to FAILED status with cancellation message.
    """
    try:
        processing_run_service = ProcessingRunService(bq_service)
        
        # Check run exists and is cancellable
        run = processing_run_service.get_processing_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"ProcessingRun {run_id} not found")
        
        if run["status"] in ["completed", "failed"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel run in {run['status']} status"
            )
        
        # Update to FAILED with cancellation message
        processing_run_service.update_status(
            run_id=run_id,
            new_status="failed",
            error_msg="Cancelled by user"
        )
        
        # Fetch updated run
        updated_run = processing_run_service.get_processing_run(run_id)
        logger.info(f"Cancelled ProcessingRun {run_id}")
        
        return ProcessingRunResponse(**updated_run)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling processing run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
