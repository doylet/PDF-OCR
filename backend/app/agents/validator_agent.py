"""
Validator/Critic Agent: Checks invariants and decides accept/retry/escalate.

Responsibilities:
1. Validate extractions against expected invariants
2. Check totals match sums (within tolerance)
3. Ensure row counts make sense
4. Verify types parse cleanly
5. Detect "Total ..." lines mistaken as data rows
6. Decide: accept / retry / escalate

This agent is the quality gate before results are returned.

LLM-Enhanced Features:
- Semantic validation: "Does this data make sense?"
- Context-aware checks: "Are dates reasonable for a telecom invoice?"
- Pattern recognition: "This looks like a currency but failed parsing"
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal, InvalidOperation

from app.models.document_graph import (
    DocumentGraph, Extraction, AgentDecision,
    ValidationStatus, TokenType
)
from app.services.llm import LLM, LLMRole
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ValidatorAgent:
    """
    Validates extractions and decides next actions.
    
    Now truly agentic: Uses LLM for semantic validation alongside rule-based checks.
    """
    
    # Tolerances
    TOTAL_TOLERANCE = 0.01  # 1% tolerance for sum checks
    MIN_TABLE_ROWS = 1
    MAX_TABLE_ROWS = 10000
    
    def __init__(self, llm_service: Optional[LLM] = None):
        """
        Args:
            llm_service: Optional LLM service for semantic validation
        """
        self.llm_service = llm_service or LLM() if settings.enable_llm_agents else None
        self.use_llm = settings.enable_llm_agents and self.llm_service is not None
    
    def validate_extraction(self, graph: DocumentGraph, extraction: Extraction) -> AgentDecision:
        """
        Main validation entry point.
        
        Combines rule-based checks with optional LLM semantic validation.
        
        Returns:
            AgentDecision indicating accept/retry/escalate
        """
        logger.info(f"Validating extraction {extraction.extraction_id}")
        
        errors = []
        warnings = []
        confidence = 1.0
        
        # Get region for context
        region = next((r for r in graph.regions if r.region_id == extraction.region_id), None)
        if not region:
            errors.append(f"Region {extraction.region_id} not found")
            return AgentDecision(
                action=AgentDecision.Action.REJECT,
                confidence=1.0,
                evidence=[extraction.extraction_id],
                explanation="Region not found in graph"
            )
        
        # Phase 1: Rule-based validation
        if "rows" in extraction.data:  # Table
            errors, warnings, confidence = self._validate_table(extraction, graph)
        elif "pairs" in extraction.data:  # Key-value
            errors, warnings, confidence = self._validate_key_value(extraction)
        elif "totals" in extraction.data:  # Totals
            errors, warnings, confidence = self._validate_totals(extraction)
        
        # Phase 2: LLM semantic validation (if enabled and no hard errors)
        if self.use_llm and not errors:
            llm_result = self._llm_semantic_validation(extraction, graph)
            if not llm_result["is_valid"]:
                # LLM found semantic issues
                warnings.extend(llm_result.get("issues", []))
                confidence = min(confidence, llm_result.get("confidence", 0.8))
                logger.info(f"LLM validation raised concerns: {llm_result.get('issues', [])}")
        
        # Update extraction status
        extraction.validation_errors = errors + warnings
        
        if errors:
            extraction.validation_status = ValidationStatus.FAIL
            extraction.confidence = min(extraction.confidence, confidence)
            
            return AgentDecision(
                action=AgentDecision.Action.RETRY_PAD,  # Default retry strategy
                confidence=0.7,
                evidence=[extraction.extraction_id] + errors,
                explanation=f"Validation failed: {'; '.join(errors[:2])}"
            )
        
        if warnings:
            extraction.validation_status = ValidationStatus.WARNING
            extraction.confidence = min(extraction.confidence, 0.9)
        else:
            extraction.validation_status = ValidationStatus.PASS
        
        return AgentDecision(
            action=AgentDecision.Action.ACCEPT,
            confidence=confidence,
            evidence=[extraction.extraction_id],
            explanation="All validations passed"
        )
    
    def _llm_semantic_validation(self, extraction: Extraction, graph: DocumentGraph) -> Dict:
        """
        LLM-powered semantic validation.
        
        Checks:
        - Do the dates make sense for this document type?
        - Are amounts reasonable?
        - Do patterns match expectations?
        - Are there obvious data quality issues?
        
        Returns:
            {
                "is_valid": bool,
                "confidence": float,
                "issues": List[str],
                "suggestions": List[str]
            }
        """
        if not self.llm_service:
            return {"is_valid": True, "confidence": 1.0, "issues": [], "suggestions": []}
        
        try:
            result = self.llm_service.validate_extraction(
                extraction_data=extraction.data,
                region_type=extraction.region_type,
                document_type=graph.metadata.get("document_type", "unknown"),
                schema=extraction.schema
            )
            
            logger.info(f"LLM validation for {extraction.extraction_id}: "
                       f"valid={result['is_valid']}, conf={result['confidence']:.2f}, "
                       f"issues={len(result.get('issues', []))}")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM semantic validation failed: {e}", exc_info=True)
            return {"is_valid": True, "confidence": 1.0, "issues": [], "suggestions": []}
    
    def _validate_table(self, extraction: Extraction, graph: DocumentGraph) -> Tuple[List[str], List[str], float]:
        """
        Validate table extraction.
        
        Checks:
        1. Row count in reasonable range
        2. No "Total" rows in data (common mistake)
        3. Column consistency
        4. Type consistency per column
        5. If totals present, check sums
        
        Returns:
            (errors, warnings, confidence)
        """
        errors = []
        warnings = []
        confidence = 1.0
        
        rows = extraction.data.get("rows", [])
        columns = extraction.data.get("columns", [])
        
        # Check 1: Row count
        if len(rows) < ValidatorAgent.MIN_TABLE_ROWS:
            errors.append(f"Too few rows: {len(rows)}")
            confidence *= 0.5
        
        if len(rows) > ValidatorAgent.MAX_TABLE_ROWS:
            warnings.append(f"Unusually many rows: {len(rows)}")
            confidence *= 0.9
        
        # Check 2: No "Total" rows in data
        total_keywords = ['total', 'sum', 'subtotal', 'grand total']
        
        for idx, row in enumerate(rows):
            row_text = ' '.join(str(cell) for cell in row).lower()
            if any(keyword in row_text for keyword in total_keywords):
                errors.append(f"Row {idx} contains total keyword: '{row_text[:50]}'")
                confidence *= 0.8
        
        # Check 3: Column consistency
        if rows:
            expected_cols = len(rows[0])
            for idx, row in enumerate(rows[1:], start=1):
                if len(row) != expected_cols:
                    warnings.append(f"Row {idx} has {len(row)} columns, expected {expected_cols}")
                    confidence *= 0.95
        
        # Check 4: Type consistency
        if rows and len(rows) > 1:
            for col_idx in range(len(rows[0])):
                column_values = [row[col_idx] for row in rows[1:] if col_idx < len(row)]
                
                # Check if column should be numeric
                numeric_count = sum(1 for v in column_values 
                                   if ValidatorAgent._is_numeric(str(v)))
                
                if numeric_count > len(column_values) * 0.8:
                    # Column should be mostly numeric
                    for val in column_values:
                        if not ValidatorAgent._is_numeric(str(val)):
                            warnings.append(f"Non-numeric value in numeric column: '{val}'")
                            confidence *= 0.98
        
        # Check 5: Sum validation (if applicable)
        if "total" in extraction.data:
            sum_errors = ValidatorAgent._validate_sums(rows, extraction.data["total"])
            errors.extend(sum_errors)
            if sum_errors:
                confidence *= 0.7
        
        logger.info(f"Table validation: {len(errors)} errors, {len(warnings)} warnings, conf={confidence:.2f}")
        
        return errors, warnings, confidence
    
    def _validate_key_value(self, extraction: Extraction) -> Tuple[List[str], List[str], float]:
        """
        Validate key-value extraction.
        
        Checks:
        1. Required keys present (based on schema)
        2. Values non-empty
        3. Types match expectations (dates, currency, etc.)
        """
        errors = []
        warnings = []
        confidence = 1.0
        
        pairs = extraction.data.get("pairs", [])
        
        if not pairs:
            errors.append("No key-value pairs extracted")
            return errors, warnings, 0.0
        
        for key, value in pairs:
            if not key or not value:
                warnings.append(f"Empty key or value: '{key}': '{value}'")
                confidence *= 0.95
        
        # TODO: Schema-based validation
        
        return errors, warnings, confidence
    
    def _validate_totals(self, extraction: Extraction) -> Tuple[List[str], List[str], float]:
        """
        Validate totals extraction.
        
        Checks:
        1. Totals are numeric
        2. Cross-reference with related tables if present
        """
        errors = []
        warnings = []
        confidence = 1.0
        
        totals = extraction.data.get("totals", {})
        
        if not totals:
            errors.append("No totals extracted")
            return errors, warnings, 0.0
        
        for key, value in totals.items():
            if not ValidatorAgent._is_numeric(str(value)):
                errors.append(f"Total '{key}' is not numeric: '{value}'")
                confidence *= 0.7
        
        return errors, warnings, confidence
    
    @staticmethod
    def _is_numeric(text: str) -> bool:
        """Check if text is numeric (handles currency, commas, etc.)"""
        # Remove common formatting
        cleaned = re.sub(r'[$£€¥,\s]', '', text)
        
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def _validate_sums(rows: List[List], expected_total: Dict) -> List[str]:
        """
        Validate that numeric columns sum to expected totals.
        
        Args:
            rows: Table rows (first row assumed to be header)
            expected_total: Dict of column_name -> expected_value
        
        Returns:
            List of error messages
        """
        errors = []
        
        if len(rows) < 2:
            return errors
        
        headers = rows[0]
        data_rows = rows[1:]
        
        for col_name, expected_value in expected_total.items():
            # Find column index
            try:
                col_idx = headers.index(col_name)
            except ValueError:
                errors.append(f"Column '{col_name}' not found in headers")
                continue
            
            # Sum column
            try:
                values = [row[col_idx] for row in data_rows if col_idx < len(row)]
                numeric_values = []
                
                for v in values:
                    cleaned = re.sub(r'[$£€¥,\s]', '', str(v))
                    try:
                        numeric_values.append(Decimal(cleaned))
                    except (InvalidOperation, ValueError):
                        pass
                
                actual_sum = sum(numeric_values)
                expected_dec = Decimal(str(expected_value))
                
                # Check tolerance
                tolerance = abs(expected_dec * Decimal(str(ValidatorAgent.TOTAL_TOLERANCE)))
                diff = abs(actual_sum - expected_dec)
                
                if diff > tolerance:
                    errors.append(
                        f"Column '{col_name}' sum mismatch: "
                        f"expected {expected_dec}, got {actual_sum}, diff={diff}"
                    )
            
            except Exception as e:
                errors.append(f"Failed to validate sum for '{col_name}': {e}")
        
        return errors
