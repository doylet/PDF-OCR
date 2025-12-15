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
    RegionType, ValidationStatus, ExtractionMethod
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
            
            self.graph.status = "completed"
            logger.info(f"Orchestration completed for job {self.job_id}")
            
        except Exception as e:
            logger.error(f"Orchestration failed for job {self.job_id}: {e}")
            self.graph.status = "failed"
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
        
        try:
            reader = PdfReader(self.pdf_path)
            num_pages = len(reader.pages)
            
            logger.info(f"PDF has {num_pages} pages")
            
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
        
        for region in page_regions:
            self._dispatch_to_specialist(region)
    
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
        Calls Table Agent (to be implemented).
        """
        logger.info(f"Table extraction for {region.region_id} - placeholder")
        
        # Placeholder: create empty extraction
        extraction = Extraction(
            extraction_id=f"ext_{region.region_id}",
            region_id=region.region_id,
            data={"rows": [], "columns": []},
            schema=None,
            confidence=0.0,
            validation_status=ValidationStatus.PENDING,
            extracted_by="table_agent_placeholder",
            method=ExtractionMethod.AGENT_INFERRED
        )
        self.graph.add_extraction(extraction)
    
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
    
    def _validate_extractions(self) -> None:
        """
        Run validators on all extractions.
        
        Checks:
        - Totals match sums
        - Row counts make sense
        - Types parse cleanly
        - "Total ..." lines not mistaken as data rows
        """
        logger.info("Validating all extractions")
        
        for extraction in self.graph.extractions:
            # Placeholder validation
            extraction.validation_status = ValidationStatus.PASS
            extraction.confidence = 0.8
            
            logger.info(f"Validated {extraction.extraction_id}: {extraction.validation_status}")
    
    def _handle_retries(self) -> None:
        """
        Handle failed validations with controlled retry strategies.
        
        Retry strategies:
        - RETRY_PAD: expand crop margins
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
            
            logger.info(f"Retry decision for {extraction.extraction_id}: {decision}")
            
            self.graph.decisions.append({
                "agent": "orchestrator",
                "extraction_id": extraction.extraction_id,
                "decision": decision.action.value,
                "confidence": decision.confidence,
                "explanation": decision.explanation,
                "timestamp": datetime.now().isoformat()
            })
    
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
