from google.cloud import bigquery
from typing import Dict, List, Optional, Any
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class ClaimsService:
    """
    Service for managing Claims - atomic extracted data from documents.
    
    Claims are append-only and never updated. Each reprocessing creates new Claims.
    Critical for Constitution: Immutable extraction results with full provenance.
    """
    
    def __init__(self, bq_service):
        """
        Initialize ClaimsService.
        
        Args:
            bq_service: BigQueryService instance for database operations
        """
        self.bq_service = bq_service
        logger.info("ClaimsService initialized")
    
    def create_claim(
        self,
        document_version_id: str,
        step_run_id: str,
        claim_type: str,
        value: str,
        confidence: float,
        page_number: int,
        bbox: Dict[str, float],
        source_text: Optional[str] = None,
        normalized_value: Optional[str] = None,
        room_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new claim from extraction results.
        
        Args:
            document_version_id: DocumentVersion being processed
            step_run_id: StepRun that produced this claim
            claim_type: Type of claim (e.g., 'loan_amount', 'date', 'account_number')
            value: Raw extracted value
            confidence: Model confidence score (0.0-1.0)
            page_number: Page where claim was found (1-indexed)
            bbox: Bounding box dict with keys: x, y, width, height
            source_text: Original text from which claim was extracted
            normalized_value: Standardized/cleaned version of value
            room_id: Optional Room context
            metadata: Additional metadata (stored as JSON)
            
        Returns:
            Created claim record
        """
        claim_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        claim_row = {
            "id": claim_id,
            "document_version_id": document_version_id,
            "room_id": room_id,
            "step_run_id": step_run_id,
            "claim_type": claim_type,
            "value": value,
            "normalized_value": normalized_value or value,
            "confidence": confidence,
            "page_number": page_number,
            "bbox_x": bbox["x"],
            "bbox_y": bbox["y"],
            "bbox_width": bbox["width"],
            "bbox_height": bbox["height"],
            "source_text": source_text,
            "user_feedback_json": None,
            "metadata": metadata or {},
            "created_at": now
        }
        
        self.bq_service.insert_row("claims", claim_row)
        logger.info(f"Created Claim {claim_id}: type={claim_type}, confidence={confidence:.2f}")
        
        return claim_row
    
    def create_claims_batch(
        self,
        claims: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Create multiple claims in batch for efficiency.
        
        Args:
            claims: List of claim dictionaries with required fields
            
        Returns:
            List of created claim IDs
        """
        now = datetime.utcnow().isoformat()
        claim_ids = []
        
        for claim_data in claims:
            claim_id = str(uuid.uuid4())
            claim_ids.append(claim_id)
            
            claim_row = {
                "id": claim_id,
                "document_version_id": claim_data["document_version_id"],
                "room_id": claim_data.get("room_id"),
                "step_run_id": claim_data["step_run_id"],
                "claim_type": claim_data["claim_type"],
                "value": claim_data["value"],
                "normalized_value": claim_data.get("normalized_value") or claim_data["value"],
                "confidence": claim_data["confidence"],
                "page_number": claim_data["page_number"],
                "bbox_x": claim_data["bbox"]["x"],
                "bbox_y": claim_data["bbox"]["y"],
                "bbox_width": claim_data["bbox"]["width"],
                "bbox_height": claim_data["bbox"]["height"],
                "source_text": claim_data.get("source_text"),
                "user_feedback_json": None,
                "metadata": claim_data.get("metadata", {}),
                "created_at": now
            }
            
            self.bq_service.insert_row("claims", claim_row)
        
        logger.info(f"Created {len(claim_ids)} claims in batch")
        return claim_ids
    
    def get_claim_by_id(self, claim_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a claim by ID.
        
        Args:
            claim_id: Claim ID
            
        Returns:
            Claim record or None if not found
        """
        return self.bq_service.get_by_id(
            table_name="claims",
            id_field="id",
            id_value=claim_id
        )
    
    def get_claims_for_document(
        self,
        document_version_id: str,
        claim_type: Optional[str] = None,
        confidence_min: Optional[float] = None,
        room_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve claims for a document version with optional filtering.
        
        Args:
            document_version_id: DocumentVersion ID to query
            claim_type: Optional filter by claim type
            confidence_min: Optional minimum confidence threshold
            room_id: Optional filter by Room
            limit: Maximum results to return
            offset: Pagination offset
            
        Returns:
            List of claim records
        """
        filters = [{"field": "document_version_id", "op": "=", "value": document_version_id}]
        
        if claim_type:
            filters.append({"field": "claim_type", "op": "=", "value": claim_type})
        
        if confidence_min is not None:
            filters.append({"field": "confidence", "op": ">=", "value": confidence_min})
        
        if room_id:
            filters.append({"field": "room_id", "op": "=", "value": room_id})
        
        claims = self.bq_service.query(
            table_name="claims",
            filters=filters,
            order_by=[
                {"field": "page_number", "direction": "ASC"},
                {"field": "confidence", "direction": "DESC"}
            ],
            limit=limit,
            offset=offset
        )
        
        logger.debug(f"Retrieved {len(claims)} claims for document {document_version_id[:16]}...")
        return claims
    
    def get_claims_for_step_run(
        self,
        step_run_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all claims produced by a specific step run.
        
        Args:
            step_run_id: StepRun ID
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of claim records
        """
        return self.bq_service.query(
            table_name="claims",
            filters=[{"field": "step_run_id", "op": "=", "value": step_run_id}],
            order_by=[{"field": "created_at", "direction": "ASC"}],
            limit=limit,
            offset=offset
        )
    
    def update_claim_feedback(
        self,
        claim_id: str,
        feedback: Dict[str, Any]
    ) -> bool:
        """
        Store HITL feedback for a claim.
        
        Updates the user_feedback_json field with corrections or confirmations.
        Does NOT modify the original claim values (immutability preserved).
        
        Args:
            claim_id: Claim ID
            feedback: Feedback dictionary with corrections/confirmations
            
        Returns:
            True if update succeeded, False if claim not found
        """
        # Verify claim exists
        claim = self.get_claim_by_id(claim_id)
        if not claim:
            logger.warning(f"Cannot add feedback - Claim {claim_id} not found")
            return False
        
        # Update feedback field only
        self.bq_service.update_row(
            table_name="claims",
            id_field="id",
            id_value=claim_id,
            updates={"user_feedback_json": feedback}
        )
        
        logger.info(f"Updated feedback for Claim {claim_id}")
        return True
    
    def get_claims_by_type(
        self,
        claim_type: str,
        document_version_id: Optional[str] = None,
        confidence_min: Optional[float] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query claims by type across documents or within a specific document.
        
        Useful for aggregations and analytics.
        
        Args:
            claim_type: Claim type to filter
            document_version_id: Optional document filter
            confidence_min: Optional confidence threshold
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of claim records
        """
        filters = [{"field": "claim_type", "op": "=", "value": claim_type}]
        
        if document_version_id:
            filters.append({"field": "document_version_id", "op": "=", "value": document_version_id})
        
        if confidence_min is not None:
            filters.append({"field": "confidence", "op": ">=", "value": confidence_min})
        
        return self.bq_service.query(
            table_name="claims",
            filters=filters,
            order_by=[{"field": "confidence", "direction": "DESC"}],
            limit=limit,
            offset=offset
        )
    
    def count_claims(
        self,
        document_version_id: Optional[str] = None,
        claim_type: Optional[str] = None,
        confidence_min: Optional[float] = None
    ) -> int:
        """
        Count claims matching filters.
        
        Args:
            document_version_id: Optional document filter
            claim_type: Optional claim type filter
            confidence_min: Optional confidence threshold
            
        Returns:
            Count of matching claims
        """
        # Build WHERE clause
        where_parts = []
        params = []
        
        if document_version_id:
            where_parts.append("document_version_id = @doc_version_id")
            params.append(bigquery.ScalarQueryParameter("doc_version_id", "STRING", document_version_id))
        
        if claim_type:
            where_parts.append("claim_type = @claim_type")
            params.append(bigquery.ScalarQueryParameter("claim_type", "STRING", claim_type))
        
        if confidence_min is not None:
            where_parts.append("confidence >= @confidence_min")
            params.append(bigquery.ScalarQueryParameter("confidence_min", "FLOAT64", confidence_min))
        
        where_clause = " AND ".join(where_parts) if where_parts else "TRUE"
        
        query = f"""
        SELECT COUNT(*) as count
        FROM `{self.bq_service.dataset_ref}.claims`
        WHERE {where_clause}
        """
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        results = list(self.bq_service.execute_query(query, job_config))
        
        return results[0]["count"] if results else 0
