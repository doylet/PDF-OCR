"""
Schema Agent: Uses LLM to detect column meanings and data types.

This agent is TRULY AGENTIC - it uses LLM reasoning instead of rules.
"""
import logging
from typing import List, Dict, Optional
from app.models.document_graph import Extraction
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class SchemaAgent:
    """
    LLM-powered schema detection for extracted tables.
    Replaces manual column naming with intelligent understanding.
    """
    
    @staticmethod
    def detect_schema(extraction: Extraction, context: Dict = None) -> Dict:
        """
        Use LLM to understand what each column means.
        
        Args:
            extraction: Extraction with raw table data
            context: Additional context (page_num, document_type, etc.)
        
        Returns:
            Schema dict with column meanings, types, and metadata
        """
        if not extraction.data or "rows" not in extraction.data:
            logger.warning(f"No table data in extraction {extraction.extraction_id}")
            return None
        
        table_data = extraction.data["rows"]
        if len(table_data) < 2:
            logger.warning(f"Not enough rows for schema detection: {len(table_data)}")
            return None
        
        logger.info(f"Detecting schema for {extraction.extraction_id} "
                   f"({len(table_data)} rows × {len(table_data[0])} cols)")
        
        # Call LLM for schema understanding
        schema_result = llm_service.detect_table_schema(
            table_data=table_data,
            context=context or {}
        )
        
        # Build structured schema
        schema = {
            "columns": schema_result["columns"],
            "domain": schema_result["likely_domain"],
            "confidence": schema_result["confidence"],
            "num_rows": len(table_data),
            "num_cols": len(table_data[0]) if table_data else 0,
            "detected_by": "schema_agent_llm"
        }
        
        logger.info(f"Schema detected: domain={schema['domain']}, "
                   f"cols={[c['name'] for c in schema['columns']]}, "
                   f"confidence={schema['confidence']:.2f}")
        
        return schema
    
    @staticmethod
    def enrich_extraction_with_schema(extraction: Extraction, context: Dict = None) -> Extraction:
        """
        Add schema to an extraction in-place.
        
        Args:
            extraction: Extraction to enrich
            context: Additional context
        
        Returns:
            Same extraction with schema field populated
        """
        schema = SchemaAgent.detect_schema(extraction, context)
        
        if schema:
            extraction.schema = schema
            # Update column names in data
            if "columns" in extraction.data:
                extraction.data["columns"] = [c["name"] for c in schema["columns"]]
            
            logger.info(f"Enriched {extraction.extraction_id} with schema")
        
        return extraction
