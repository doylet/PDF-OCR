from fastapi import APIRouter, HTTPException, Header, Request
from app.models import ExtractionRequest, JobStatus
from app.services.jobs import job_service
from app.services.storage import storage_service
from app.services.documentai import documentai_service
from app.services.formatter import formatter_service
from app.config import get_settings
import uuid
import logging

router = APIRouter(prefix="/api/extract", tags=["extraction"])
logger = logging.getLogger(__name__)
settings = get_settings()

try:
    from app.agents.orchestrator import ExpectOrchestrator
    from app.models.document_graph import DocumentGraph
    AGENTIC_AVAILABLE = True
except ImportError:
    AGENTIC_AVAILABLE = False
    logger.warning("Agentic pipeline not available - module import failed")


def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key"""
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


async def process_extraction(job_id: str, request: ExtractionRequest):
    """Background task to process extraction"""
    try:
        # Update job status to processing
        job_service.update_job_status(job_id, "processing")
        
        # Download PDF
        pdf_bytes = storage_service.download_pdf(request.pdf_id)
        
        # Process regions with Document AI (pass job_id for debug artifacts)
        results = documentai_service.process_regions(pdf_bytes, request.regions, job_id=job_id)
        
        # Format results
        if request.output_format == "csv":
            formatted_content = formatter_service.format_as_csv(results)
        elif request.output_format == "tsv":
            formatted_content = formatter_service.format_as_tsv(results)
        else:  # json
            formatted_content = formatter_service.format_as_json(results)
        
        # Upload result
        result_url = storage_service.upload_result(job_id, formatted_content, request.output_format)
        
        # Update job status to completed
        job_service.update_job_status(job_id, "completed", result_url=result_url)
        
        logger.info(f"Completed extraction job: {job_id}")
    
    except Exception as e:
        logger.error(f"Error processing extraction job {job_id}: {e}")
        job_service.update_job_status(job_id, "failed", error_message=str(e))


@router.post("/", response_model=JobStatus)
async def create_extraction_job(
    extraction_request: ExtractionRequest,
    request: Request,
    api_key: str = Header(None, alias="X-API-Key")
):
    """
    Create an extraction job for processing PDF regions
    
    - **pdf_id**: ID of the uploaded PDF
    - **regions**: List of regions to extract (with coordinates and page numbers)
    - **output_format**: Desired output format (csv, tsv, or json)
    """
    # Skip API key check for testing
    # TODO: Re-enable with correct key management
    # if request.method != "OPTIONS":
    #     verify_api_key(api_key if api_key else "")
    
    if not extraction_request.regions:
        raise HTTPException(status_code=400, detail="At least one region is required")
    
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job in Firestore with request data
        job = job_service.create_job(
            job_id, 
            extraction_request.pdf_id, 
            len(extraction_request.regions),
            request_data=extraction_request.dict()
        )
        
        # For MVP: Process synchronously to avoid Cloud Run CPU throttling issues
        # TODO: Move to Cloud Tasks for production
        await process_extraction(job_id, extraction_request)
        
        # Return updated job status
        return job_service.get_job(job_id)
    
    except Exception as e:
        logger.error(f"Error creating extraction job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agentic", response_model=JobStatus)
async def create_agentic_extraction_job(
    extraction_request: ExtractionRequest,
    request: Request,
    api_key: str = Header(None, alias="X-API-Key")
):
    """
    Create an extraction job using the agentic document understanding pipeline
    
    - **pdf_id**: ID of the uploaded PDF
    - **regions**: List of regions to extract (optional - auto-detects if empty)
    - **output_format**: Desired output format (csv, tsv, or json)
    """
    if not AGENTIC_AVAILABLE:
        raise HTTPException(status_code=501, detail="Agentic pipeline not available")
    
    # Skip API key check for testing
    # TODO: Re-enable with correct key management
    # if request.method != "OPTIONS":
    #     verify_api_key(api_key if api_key else "")
    
    try:
        job_id = str(uuid.uuid4())
        
        job = job_service.create_job(
            job_id,
            extraction_request.pdf_id,
            len(extraction_request.regions) if extraction_request.regions else 0,
            request_data={**extraction_request.dict(), "method": "agentic"}
        )
        
        await process_agentic_extraction(job_id, extraction_request)
        
        return job_service.get_job(job_id)
    
    except Exception as e:
        logger.error(f"Error creating agentic extraction job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_agentic_extraction(job_id: str, request: ExtractionRequest):
    """Process extraction using agentic pipeline"""
    try:
        job_service.update_job_status(job_id, "processing")
        
        pdf_bytes = storage_service.download_pdf(request.pdf_id)
        
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            pdf_path = tmp.name
        
        orchestrator = ExpectOrchestrator(pdf_path, job_id)
        graph = orchestrator.run()
        
        results = []
        for extraction in graph.extractions:
            if extraction.validation_status.name == "PASS":
                results.append({
                    "region_id": extraction.region_id,
                    "data": extraction.data,
                    "confidence": extraction.confidence,
                    "method": extraction.method.name
                })
        
        if request.output_format == "csv":
            formatted_content = formatter_service.format_as_csv(results)
        elif request.output_format == "tsv":
            formatted_content = formatter_service.format_as_tsv(results)
        else:
            formatted_content = formatter_service.format_as_json(results)
        
        result_url = storage_service.upload_result(job_id, formatted_content, request.output_format)
        
        graph_dict = graph.to_dict()
        storage_service.upload_result(job_id, str(graph_dict), "json", suffix="_graph")
        
        job_service.update_job_status(job_id, "completed", result_url=result_url)
        
        logger.info(f"Completed agentic extraction job: {job_id}")
    
    except Exception as e:
        logger.error(f"Error processing agentic extraction job {job_id}: {e}")
        job_service.update_job_status(job_id, "failed", error_message=str(e))


@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(
    job_id: str,
    request: Request,
    api_key: str = Header(None, alias="X-API-Key")
):
    """
    Get the status of an extraction job
    
    - **job_id**: ID of the extraction job
    """
    # Skip API key check for testing
    # TODO: Re-enable with correct key management
    # if request.method != "OPTIONS":
    #     verify_api_key(api_key if api_key else "")
    
    job = job_service.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job
