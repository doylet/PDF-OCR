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
    from app.agents.orchestrator import ExpertOrchestrator
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
        
        orchestrator = ExpertOrchestrator(pdf_path, job_id)
        graph = orchestrator.run()
        
        results = []
        for idx, extraction in enumerate(graph.extractions):
            if extraction.validation_status.name == "PASS":
                # Get region for page info
                region = next((r for r in graph.regions if r.region_id == extraction.region_id), None)
                page = region.page if region else 0
                
                # Convert to ExtractionResult for formatter compatibility
                from app.models.api import ExtractionResult
                result = ExtractionResult(
                    region_index=idx,
                    page=page,
                    text=extraction.data.get("text", str(extraction.data)),
                    confidence=extraction.confidence,
                    structured_data=extraction.data if extraction.data else None
                )
                results.append(result)
        
        # Log outcome
        outcome = graph.outcome if graph.outcome else "unknown"
        logger.info(f"Job {job_id} outcome: {outcome}, regions={len(graph.regions)}, extractions={len(results)}")
        
        # Add metadata to results
        summary = {
            "outcome": outcome,
            "pages": len(graph.pages),
            "regions_proposed": len(graph.regions),
            "regions_extracted": len(results),
            "trace": graph.trace
        }
        
        if request.output_format == "csv":
            formatted_content = formatter_service.format_as_csv(results)
        elif request.output_format == "tsv":
            formatted_content = formatter_service.format_as_tsv(results)
        else:
            # JSON includes metadata
            import json
            formatted_content = json.dumps({
                "summary": summary,
                "results": [r.dict() for r in results]
            }, indent=2)
        
        result_url = storage_service.upload_result(job_id, formatted_content, request.output_format)
        
        # Store full graph with metadata as proper JSON
        import json
        graph_dict = graph.to_dict()
        graph_dict["summary"] = summary
        graph_json = json.dumps(graph_dict, indent=2, default=str)
        debug_graph_url = storage_service.upload_result(job_id, graph_json, "json", suffix="_graph")
        
        # Status message based on outcome
        if outcome == "no_match":
            status_msg = f"No extractable data found ({len(graph.regions)} regions detected)"
        elif outcome == "partial_success":
            status_msg = f"Partial extraction: {len(results)} of {len(graph.extractions)} succeeded"
        else:
            status_msg = None
        
        job_service.update_job_status(
            job_id, 
            "completed", 
            result_url=result_url,
            error_message=status_msg if outcome == "no_match" else None,
            debug_graph_url=debug_graph_url
        )
        
        logger.info(f"Completed agentic extraction job: {job_id}, outcome: {outcome}")
    
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
