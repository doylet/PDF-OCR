"""
LLM Service: Wrapper for Google Gemini API (Vertex AI).

Provides structured prompts and response parsing for agentic decision-making.
"""
import logging
import json
from typing import Dict, List, Optional, Any
from enum import Enum
import google.generativeai as genai
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMRole(Enum):
    """Specific roles for LLM agents"""
    LAYOUT_ANALYZER = "layout_analyzer"
    SCHEMA_DETECTOR = "schema_detector"
    VALIDATOR = "validator"
    ERROR_DIAGNOSTICIAN = "error_diagnostician"


class LLM:
    """
    Centralized LLM service for agentic decisions.
    Uses Google Gemini via Vertex AI for consistency with GCP stack.
    """
    
    def __init__(self):
        """Initialize Gemini client"""
        try:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("LLM Service initialized with Gemini 1.5 Flash")
        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {e}")
            self.model = None
    
    def is_available(self) -> bool:
        """Check if LLM service is configured and ready"""
        return self.model is not None
    
    def analyze_layout_ambiguity(
        self, 
        text: str, 
        token_count: int,
        has_alignment: bool,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLM decision: Is this a table, list, or just aligned text?
        
        Args:
            text: OCR text from region
            token_count: Number of tokens
            has_alignment: Whether tokens show vertical alignment
            context: Additional context (page_num, nearby_text, etc.)
        
        Returns:
            {
                "region_type": "TABLE" | "LIST" | "KEY_VALUE" | "TEXT",
                "confidence": 0.0-1.0,
                "reasoning": "explanation",
                "suggested_extraction_method": "geometry" | "llm_parse"
            }
        """
        if not self.is_available():
            return self._fallback_layout_decision(has_alignment)
        
        prompt = f"""You are a document structure analyzer. Analyze this text and determine its type.

TEXT:
{text[:2000]}  # Limit to avoid token overflow

METADATA:
- Token count: {token_count}
- Has vertical alignment: {has_alignment}
- Page: {context.get('page_num', 'unknown')}

Determine if this is:
1. TABLE - Structured data in rows/columns (dates, amounts, multiple aligned values)
2. LIST - Sequential items (bullets, numbered, or simple vertical list)
3. KEY_VALUE - Label-value pairs (Invoice #: 12345, Name: John, etc.)
4. TEXT - Just regular paragraph text that happens to be aligned

Respond ONLY with valid JSON:
{{
  "region_type": "TABLE|LIST|KEY_VALUE|TEXT",
  "confidence": 0.0-1.0,
  "reasoning": "one sentence explanation",
  "suggested_extraction_method": "geometry|llm_parse"
}}"""
        
        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text.strip())
            
            logger.info(f"LLM layout analysis: {result['region_type']} "
                       f"(confidence: {result['confidence']}, "
                       f"method: {result['suggested_extraction_method']})")
            
            return result
        except Exception as e:
            logger.error(f"LLM layout analysis failed: {e}")
            return self._fallback_layout_decision(has_alignment)
    
    def detect_table_schema(
        self,
        table_data: List[List[str]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLM decision: What do these columns mean?
        
        Args:
            table_data: Extracted table rows
            context: Additional context
        
        Returns:
            {
                "columns": [
                    {"name": "date", "type": "DATE", "description": "Transaction date"},
                    {"name": "amount", "type": "CURRENCY", "description": "Charge amount"},
                    ...
                ],
                "confidence": 0.0-1.0,
                "likely_domain": "telecom_invoice" | "bank_statement" | "receipt" | "unknown"
            }
        """
        if not self.is_available() or not table_data or len(table_data) < 2:
            return self._fallback_schema(table_data)
        
        # Sample first 10 rows for analysis
        sample_rows = table_data[:10]
        sample_text = "\n".join([" | ".join(row) for row in sample_rows])
        
        prompt = f"""You are a data schema expert. Analyze this table and identify column meanings.

TABLE SAMPLE (first {len(sample_rows)} rows):
{sample_text}

Identify:
1. What each column represents (date, amount, description, etc.)
2. Data type for each column (DATE, CURRENCY, TEXT, NUMBER, etc.)
3. Brief description of each column
4. Overall domain (telecom invoice, bank statement, receipt, etc.)

Respond ONLY with valid JSON:
{{
  "columns": [
    {{"name": "descriptive_name", "type": "DATA_TYPE", "description": "brief description"}},
    ...
  ],
  "confidence": 0.0-1.0,
  "likely_domain": "domain_type"
}}"""
        
        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text.strip())
            
            logger.info(f"LLM schema detection: {len(result['columns'])} columns, "
                       f"domain: {result['likely_domain']}, "
                       f"confidence: {result['confidence']}")
            
            return result
        except Exception as e:
            logger.error(f"LLM schema detection failed: {e}")
            return self._fallback_schema(table_data)
    
    def validate_extraction(
        self,
        extraction_data: Dict[str, Any],
        region_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLM validation: Does this extracted data make sense?
        
        Args:
            extraction_data: The extracted data
            region_type: Type of region (TABLE, KEY_VALUE, etc.)
            context: Additional context
        
        Returns:
            {
                "is_valid": True|False,
                "confidence": 0.0-1.0,
                "issues": ["list", "of", "problems"],
                "suggestions": ["possible", "fixes"]
            }
        """
        if not self.is_available():
            return {"is_valid": True, "confidence": 0.5, "issues": [], "suggestions": []}
        
        data_preview = json.dumps(extraction_data, indent=2)[:1500]
        
        prompt = f"""You are a data quality validator. Check if this extracted data makes sense.

REGION TYPE: {region_type}
EXTRACTED DATA:
{data_preview}

CONTEXT:
{json.dumps(context, indent=2)[:500]}

Validate:
1. Are dates valid and reasonable?
2. Are amounts/numbers sensible (no negatives where impossible, reasonable ranges)?
3. Are required fields present?
4. Is structure consistent?
5. Any obvious OCR errors or misalignments?

Respond ONLY with valid JSON:
{{
  "is_valid": true|false,
  "confidence": 0.0-1.0,
  "issues": ["list of specific problems found"],
  "suggestions": ["possible ways to fix issues"]
}}"""
        
        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text.strip())
            
            logger.info(f"LLM validation: valid={result['is_valid']}, "
                       f"confidence={result['confidence']}, "
                       f"issues={len(result.get('issues', []))}")
            
            return result
        except Exception as e:
            logger.error(f"LLM validation failed: {e}")
            return {"is_valid": True, "confidence": 0.5, "issues": [], "suggestions": []}
    
    def diagnose_extraction_failure(
        self,
        region_text: str,
        extraction_attempt: Dict[str, Any],
        error_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLM decision: Why did extraction fail and what should we try?
        
        Args:
            region_text: Original OCR text
            extraction_attempt: What we tried to extract
            error_info: Error details
        
        Returns:
            {
                "diagnosis": "explanation of failure",
                "root_cause": "OCR_QUALITY|LAYOUT_COMPLEXITY|WRONG_TYPE|OTHER",
                "recommended_retry": "pad_crop|higher_dpi|ocr_fallback|manual_parse|none",
                "confidence": 0.0-1.0
            }
        """
        if not self.is_available():
            return self._fallback_diagnosis()
        
        prompt = f"""You are an extraction failure diagnostician. Analyze why data extraction failed.

ORIGINAL TEXT:
{region_text[:1000]}

EXTRACTION ATTEMPT:
{json.dumps(extraction_attempt, indent=2)[:500]}

ERROR INFO:
{json.dumps(error_info, indent=2)[:500]}

Diagnose:
1. Why did extraction fail?
2. Root cause category
3. Best retry strategy

Respond ONLY with valid JSON:
{{
  "diagnosis": "clear explanation of failure",
  "root_cause": "OCR_QUALITY|LAYOUT_COMPLEXITY|WRONG_TYPE|OTHER",
  "recommended_retry": "pad_crop|higher_dpi|ocr_fallback|manual_parse|none",
  "confidence": 0.0-1.0
}}"""
        
        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text.strip())
            
            logger.info(f"LLM diagnosis: {result['root_cause']} → "
                       f"retry: {result['recommended_retry']}")
            
            return result
        except Exception as e:
            logger.error(f"LLM diagnosis failed: {e}")
            return self._fallback_diagnosis()
    
    # Fallback methods (when LLM unavailable)
    
    def _fallback_layout_decision(self, has_alignment: bool) -> Dict[str, Any]:
        """Rule-based fallback for layout analysis"""
        return {
            "region_type": "TABLE" if has_alignment else "TEXT",
            "confidence": 0.6,
            "reasoning": "Fallback: geometry-based decision (LLM unavailable)",
            "suggested_extraction_method": "geometry"
        }
    
    def _fallback_schema(self, table_data: List[List[str]]) -> Dict[str, Any]:
        """Rule-based fallback for schema detection"""
        if not table_data:
            return {"columns": [], "confidence": 0.0, "likely_domain": "unknown"}
        
        num_cols = len(table_data[0]) if table_data else 0
        columns = [
            {"name": f"column_{i}", "type": "TEXT", "description": "Unknown"}
            for i in range(num_cols)
        ]
        
        return {
            "columns": columns,
            "confidence": 0.3,
            "likely_domain": "unknown"
        }
    
    def _fallback_diagnosis(self) -> Dict[str, Any]:
        """Rule-based fallback for error diagnosis"""
        return {
            "diagnosis": "Unable to diagnose (LLM unavailable)",
            "root_cause": "OTHER",
            "recommended_retry": "pad_crop",
            "confidence": 0.3
        }


# Global instance
llm_service = LLM()
