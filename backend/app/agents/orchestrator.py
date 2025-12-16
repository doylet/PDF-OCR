"""
Expert Orchestrator: The main agentic loop.

Responsibilities:
1. Ingest PDF → decide per page: PDF native text vs OCR
2. Generate candidate regions (via Layout Agent)
3. Dispatch to specialist extractors based on region type
4. Run validators
5. If validation fails: controlled retries (pad crop, raise DPI, switch engine)
6. Produce final structured output + audit trail

This is mostly rules + simple scoring, not LLM-heavy.
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from app.models.document_graph import (
    DocumentGraph, Region, Extraction, AgentDecision,
    RegionType, ValidationStatus, ExtractionMethod, JobOutcome
)
from app.agents.layout_agent import LayoutAgent

logger = logging.getLogger(__name__)


class ExpertOrchestrator:
    """
    Main orchestrator for the agentic extraction pipeline.
    Keeps agents on a tight leash - they decide and validate, not "magically extract".
    """
    
    # Retry limits
    MAX_RETRIES = 2
    
    def __init__(self, pdf_path: str, job_id: str):
        """
        Initialize orchestrator with a PDF.
        
        Args:
            pdf_path: Path to PDF file (local or GCS)
            job_id: Unique job identifier
        """
        self.pdf_path = pdf_path
        self.job_id = job_id
        self.graph = DocumentGraph(
            job_id=job_id,
            pdf_path=pdf_path
        )
        
        logger.info(f"ExpertOrchestrator initialized for job {job_id}")
    
    def run(self) -> DocumentGraph:
        """
        Main orchestration loop.
        
        Returns:
            Completed DocumentGraph with extractions and audit trail
        """
        logger.info(f"Starting orchestration for job {self.job_id}")
        self.graph.status = "running"
        
        try:
            # Step 1: Ingest PDF
            self._ingest_pdf()
            
            # Step 2: Process each page
            for page_num in range(len(self.graph.pages)):
                self._process_page(page_num)
            
            # Step 3: Validate all extractions
            self._validate_extractions()
            
            # Step 4: Handle retries for failed validations
            self._handle_retries()
            
            # Step 5: Determine outcome
            self._determine_outcome()
            
            self.graph.status = "completed"
            logger.info(f"Orchestration completed for job {self.job_id}, outcome: {self.graph.outcome}")
            
        except Exception as e:
            logger.error(f"Orchestration failed for job {self.job_id}: {e}")
            self.graph.status = "failed"
            self.graph.outcome = "FAILED"
            self.graph.trace.append({
                "step": "orchestration",
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            self.graph.decisions.append({
                "agent": "orchestrator",
                "timestamp": datetime.now().isoformat(),
                "decision": "failed",
                "error": str(e)
            })
        
        return self.graph
    
    def _ingest_pdf(self) -> None:
        """
        Ingest PDF and decide extraction strategy per page.
        
        Decision: PDF native text vs OCR
        """
        from pypdf import PdfReader
        
        logger.info(f"Ingesting PDF: {self.pdf_path}")
        
        self.graph.trace.append({
            "step": "ingest_pdf",
            "status": "started",
            "pdf_path": str(self.pdf_path),
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            reader = PdfReader(self.pdf_path)
            num_pages = len(reader.pages)
            
            logger.info(f"PDF has {num_pages} pages")
            
            self.graph.trace.append({
                "step": "ingest_pdf",
                "status": "completed",
                "pages_found": num_pages,
                "timestamp": datetime.now().isoformat()
            })
            
            # Analyze each page
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                text = page.extract_text()
                
                # Decision: use PDF text or fall back to OCR?
                use_ocr = False
                reason = "PDF has native text"
                
                if not text or len(text.strip()) < 20:
                    use_ocr = True
                    reason = "Insufficient native text"
                
                # Store page metadata
                page_info = {
                    "page_num": page_num,
                    "width": float(page.mediabox.width),
                    "height": float(page.mediabox.height),
                    "use_ocr": use_ocr,
                    "text_length": len(text) if text else 0
                }
                self.graph.pages.append(page_info)
                
                # Log decision
                self.graph.decisions.append({
                    "agent": "orchestrator",
                    "page": page_num,
                    "decision": "use_ocr" if use_ocr else "use_pdf_text",
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Page {page_num}: {reason} → {'OCR' if use_ocr else 'PDF text'}")
        
        except Exception as e:
            logger.error(f"Failed to ingest PDF: {e}")
            raise
    
    def _process_page(self, page_num: int) -> None:
        """
        Process a single page through the agent pipeline.
        
        Steps:
        1. Layout Agent: build tokens + propose regions
        2. For each region: dispatch to specialist
        3. Store extractions in graph
        """
        logger.info(f"Processing page {page_num}")
        
        self.graph.trace.append({
            "step": "process_page",
            "status": "started",
            "page_num": page_num,
            "timestamp": datetime.now().isoformat()
        })
        
        page_info = self.graph.pages[page_num]
        
        # Step 1: Layout Agent
        if page_info["use_ocr"]:
            # TODO: Implement OCR path
            logger.warning(f"Page {page_num} needs OCR - not yet implemented")
            return
        
        # Process with PDF native text
        LayoutAgent.process_page(self.graph, page_num, self.pdf_path)
        
        # Step 2: Dispatch to specialists
        page_regions = [r for r in self.graph.regions if r.page == page_num]
        
        self.graph.trace.append({
            "step": "layout_agent",
            "status": "completed",
            "page_num": page_num,
            "regions_proposed": len(page_regions),
            "region_types": [r.region_type.value for r in page_regions],
            "timestamp": datetime.now().isoformat()
        })
        
        for region in page_regions:
            self._dispatch_to_specialist(region)
        
        # Fallback: If no table regions detected, try Camelot on full page
        table_regions = [r for r in page_regions if r.region_type == RegionType.TABLE]
        if not table_regions:
            self._extract_tables_with_camelot(page_num)
    
    def _dispatch_to_specialist(self, region: Region) -> None:
        """
        Route a region to the appropriate specialist extractor.
        
        Specialists:
        - TABLE → Table Agent
        - KEY_VALUE → Key-Value Agent
        - LIST → List Agent
        - TOTALS → Totals Agent
        """
        logger.info(f"Dispatching {region.region_id} (type: {region.region_type}) to specialist")
        
        self.graph.trace.append({
            "step": "dispatch_to_specialist",
            "status": "started",
            "region_id": region.region_id,
            "region_type": region.region_type.value,
            "page": region.page,
            "bbox": {
                "x": region.bbox.x,
                "y": region.bbox.y,
                "w": region.bbox.w,
                "h": region.bbox.h
            } if region.bbox else None,
            "timestamp": datetime.now().isoformat()
        })
        
        # Route based on type
        if region.region_type == RegionType.TABLE:
            self._extract_table(region)
        elif region.region_type == RegionType.KEY_VALUE:
            self._extract_key_value(region)
        elif region.region_type == RegionType.LIST:
            self._extract_list(region)
        elif region.region_type == RegionType.TOTALS:
            self._extract_totals(region)
        elif region.region_type == RegionType.HEADING:
            # Headings are for structure, not extraction
            pass
        else:
            logger.warning(f"Unknown region type: {region.region_type}")
    
    def _extract_table(self, region: Region) -> None:
        """
        Extract structured table from region.
        Calls Table Agent.
        """
        from app.agents.table_agent import TableAgent
        
        logger.info(f"Table extraction for {region.region_id}")
        
        extraction = TableAgent.extract_table(self.graph, region)
        if extraction:
            self.graph.add_extraction(extraction)
            self.graph.trace.append({
                "step": "table_extraction",
                "status": "success",
                "region_id": region.region_id,
                "rows_extracted": len(extraction.data.get('rows', [])),
                "confidence": extraction.confidence,
                "timestamp": datetime.now().isoformat()
            })
        else:
            logger.warning(f"TableAgent returned no extraction for {region.region_id}")
            self.graph.trace.append({
                "step": "table_extraction",
                "status": "failed",
                "region_id": region.region_id,
                "reason": "TableAgent returned None",
                "timestamp": datetime.now().isoformat()
            })
    
    def _extract_key_value(self, region: Region) -> None:
        """Extract key-value pairs (invoice details, etc.)"""
        logger.info(f"Key-value extraction for {region.region_id} - placeholder")
        
        extraction = Extraction(
            extraction_id=f"ext_{region.region_id}",
            region_id=region.region_id,
            data={"pairs": []},
            confidence=0.0,
            validation_status=ValidationStatus.PENDING,
            extracted_by="kv_agent_placeholder"
        )
        self.graph.add_extraction(extraction)
    
    def _extract_list(self, region: Region) -> None:
        """Extract list items"""
        logger.info(f"List extraction for {region.region_id} - placeholder")
        
        extraction = Extraction(
            extraction_id=f"ext_{region.region_id}",
            region_id=region.region_id,
            data={"items": []},
            confidence=0.0,
            validation_status=ValidationStatus.PENDING,
            extracted_by="list_agent_placeholder"
        )
        self.graph.add_extraction(extraction)
    
    def _extract_totals(self, region: Region) -> None:
        """Extract totals/summary section"""
        logger.info(f"Totals extraction for {region.region_id} - placeholder")
        
        extraction = Extraction(
            extraction_id=f"ext_{region.region_id}",
            region_id=region.region_id,
            data={"totals": {}},
            confidence=0.0,
            validation_status=ValidationStatus.PENDING,
            extracted_by="totals_agent_placeholder"
        )
        self.graph.add_extraction(extraction)
    
    def _extract_tables_with_camelot(self, page_num: int) -> None:
        """
        Fallback: Use Camelot to extract tables from full page.
        Called when LayoutAgent doesn't detect any table regions.
        """
        import camelot
        
        logger.info(f"Using Camelot fallback for page {page_num}")
        
        try:
            # Camelot uses 1-indexed pages
            tables = camelot.read_pdf(
                self.pdf_path,
                pages=str(page_num + 1),
                flavor='lattice',
                strip_text='\n'
            )
            
            if not tables:
                logger.info(f"Camelot found no tables on page {page_num}")
                return
            
            # Process each table found
            for table_idx, table in enumerate(tables):
                # Convert to list of rows
                rows = []
                for row in table.df.values.tolist():
                    # Filter empty cells
                    cleaned_row = [str(cell).strip() for cell in row if str(cell).strip()]
                    if cleaned_row:
                        rows.append(cleaned_row)
                
                if len(rows) < 2:
                    continue
                
                # Create extraction
                extraction = Extraction(
                    extraction_id=f"camelot_p{page_num}_t{table_idx}",
                    region_id=f"camelot_region_p{page_num}_t{table_idx}",
                    data={"rows": rows, "columns": len(rows[0]) if rows else 0},
                    confidence=0.85,
                    validation_status=ValidationStatus.PENDING,
                    extracted_by="camelot_fallback",
                    method=ExtractionMethod.AGENT_INFERRED
                )
                self.graph.add_extraction(extraction)
                logger.info(f"Camelot extracted {len(rows)} rows from page {page_num} table {table_idx}")
        
        except Exception as e:
            logger.error(f"Camelot fallback failed for page {page_num}: {e}")
    
    def _validate_extractions(self) -> None:
        """
        Run validators on all extractions using ValidatorAgent.
        
        Checks:
        - Totals match sums
        - Row counts make sense
        - Types parse cleanly
        - "Total ..." lines not mistaken as data rows
        """
        from app.agents.validator_agent import ValidatorAgent
        
        logger.info("Validating all extractions")
        
        for extraction in self.graph.extractions:
            decision = ValidatorAgent.validate_extraction(self.graph, extraction)
            
            self.graph.decisions.append({
                "agent": "validator",
                "extraction_id": extraction.extraction_id,
                "decision": decision.action.value,
                "confidence": decision.confidence,
                "explanation": decision.explanation,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Validated {extraction.extraction_id}: {extraction.validation_status} (conf={extraction.confidence:.2f})")
    
    def _handle_retries(self) -> None:
        """
        Handle failed validations with controlled retry strategies.
        
        Retry strategies:
        - RETRY_PAD: expand crop margins and re-extract
        - RETRY_OCR: force OCR instead of PDF text
        - RETRY_HIGHER_DPI: increase OCR resolution
        """
        failed = [e for e in self.graph.extractions 
                 if e.validation_status == ValidationStatus.FAIL]
        
        if not failed:
            logger.info("No failed extractions, skipping retries")
            return
        
        logger.info(f"Handling {len(failed)} failed extractions")
        
        for extraction in failed:
            if extraction.extraction_id.endswith("_retry"):
                logger.warning(f"Already retried {extraction.extraction_id}, escalating")
                extraction.validation_status = ValidationStatus.WARNING
                continue
            
            # Decide retry strategy
            decision = self._decide_retry_strategy(extraction)
            
            logger.info(f"Retry decision for {extraction.extraction_id}: {decision.action.value}")
            
            self.graph.decisions.append({
                "agent": "orchestrator",
                "extraction_id": extraction.extraction_id,
                "decision": decision.action.value,
                "confidence": decision.confidence,
                "explanation": decision.explanation,
                "timestamp": datetime.now().isoformat()
            })
            
            # Actually execute the retry
            if decision.action == AgentDecision.Action.RETRY_PAD:
                self._retry_with_padding(extraction, decision.next_params)
            elif decision.action == AgentDecision.Action.RETRY_OCR:
                self._retry_with_ocr(extraction, decision.next_params)
            elif decision.action == AgentDecision.Action.RETRY_HIGHER_DPI:
                self._retry_with_higher_dpi(extraction, decision.next_params)
    
    def _retry_with_padding(self, extraction: Extraction, params: Dict) -> None:
        """Re-extract region with expanded bounding box."""
        region = next((r for r in self.graph.regions if r.region_id == extraction.region_id), None)
        if not region:
            logger.error(f"Region {extraction.region_id} not found for retry")
            return
        
        pad_fraction = params.get("pad_fraction", 0.1)
        logger.info(f"Retrying {region.region_id} with {pad_fraction:.2%} padding")
        
        # Create padded region
        padded_bbox = BBox(
            x=max(0, region.bbox.x - pad_fraction),
            y=max(0, region.bbox.y - pad_fraction),
            w=min(1.0, region.bbox.w + 2 * pad_fraction),
            h=min(1.0, region.bbox.h + 2 * pad_fraction)
        )
        
        padded_region = Region(
            region_id=f"{region.region_id}_retry",
            region_type=region.region_type,
            bbox=padded_bbox,
            page=region.page,
            confidence=region.confidence,
            source_agent="orchestrator_retry"
        )
        
        # Mark original as superseded
        extraction.validation_status = ValidationStatus.WARNING
        extraction.validation_errors.append("Superseded by padded retry")
        
        # Re-dispatch to specialist
        self.graph.add_region(padded_region)
        self._dispatch_to_specialist(padded_region)
    
    def _retry_with_ocr(self, extraction: Extraction, params: Dict) -> None:
        """Re-extract region using OCR instead of native text."""
        logger.info(f"OCR retry not yet implemented for {extraction.extraction_id}")
        # TODO: Force OCR path
    
    def _retry_with_higher_dpi(self, extraction: Extraction, params: Dict) -> None:
        """Re-extract region at higher DPI."""
        logger.info(f"Higher DPI retry not yet implemented for {extraction.extraction_id}")
        # TODO: Increase DPI and re-extract
    
    def _decide_retry_strategy(self, extraction: Extraction) -> AgentDecision:
        """
        Decide how to retry a failed extraction.
        
        Returns:
            AgentDecision with action and parameters
        """
        # Simple heuristic: if low confidence, try padding
        if extraction.confidence < 0.5:
            return AgentDecision(
                action=AgentDecision.Action.RETRY_PAD,
                confidence=0.7,
                evidence=[extraction.extraction_id],
                explanation="Low confidence suggests crop may be incomplete",
                next_params={"pad_fraction": 0.1}
            )
        
        # If validation errors mention missing data, try OCR
        if any("missing" in err.lower() for err in extraction.validation_errors):
            return AgentDecision(
                action=AgentDecision.Action.RETRY_OCR,
                confidence=0.8,
                evidence=[extraction.extraction_id],
                explanation="Missing data suggests OCR may help",
                next_params={"dpi": 300}
            )
        
        # Default: escalate
        return AgentDecision(
            action=AgentDecision.Action.ESCALATE,
            confidence=0.9,
            evidence=[extraction.extraction_id],
            explanation="Unable to determine automatic fix"
        )
    
    def _determine_outcome(self) -> None:
        """
        Determine overall job outcome based on regions and extractions.
        
        Critical rule: If regions_proposed == 0 → NO_MATCH, not SUCCESS
        """
        from app.models.document_graph import JobOutcome
        
        regions_proposed = len(self.graph.regions)
        extractions_count = len(self.graph.extractions)
        passed = [e for e in self.graph.extractions if e.validation_status.name == "PASS"]
        failed = [e for e in self.graph.extractions if e.validation_status.name == "FAIL"]
        
        logger.info(f"Determining outcome: {regions_proposed} regions, {extractions_count} extractions, {len(passed)} passed")
        
        if regions_proposed == 0:
            # Agent ran but found nothing
            self.graph.outcome = JobOutcome.NO_MATCH
            self.graph.trace.append({
                "step": "determine_outcome",
                "status": "no_match",
                "reason": "No extractable regions detected",
                "regions_proposed": 0,
                "timestamp": datetime.now().isoformat()
            })
        elif len(passed) == 0:
            # Regions found but all extractions failed
            self.graph.outcome = JobOutcome.NO_MATCH
            self.graph.trace.append({
                "step": "determine_outcome",
                "status": "no_match",
                "reason": "Extractions failed validation",
                "regions_proposed": regions_proposed,
                "extractions_attempted": extractions_count,
                "timestamp": datetime.now().isoformat()
            })
        elif len(failed) > 0:
            # Some passed, some failed
            self.graph.outcome = JobOutcome.PARTIAL_SUCCESS
            self.graph.trace.append({
                "step": "determine_outcome",
                "status": "partial_success",
                "passed": len(passed),
                "failed": len(failed),
                "timestamp": datetime.now().isoformat()
            })
        else:
            # All passed
            self.graph.outcome = JobOutcome.SUCCESS
            self.graph.trace.append({
                "step": "determine_outcome",
                "status": "success",
                "extractions": len(passed),
                "timestamp": datetime.now().isoformat()
            })
