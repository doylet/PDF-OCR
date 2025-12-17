"""
Refactored Claims Service

Clean architecture with separated concerns:
- Domain logic in domain/models.py
- Data access via repositories
- Business rules and orchestration here
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from app.domain.models import Claim, ClaimType, BoundingBox
from app.repositories.interfaces import IClaimRepository


logger = logging.getLogger(__name__)


class Claims:
    """
    Claims business logic.
    
    Handles:
    - Claim creation with validation
    - Claim retrieval and filtering
    - User feedback processing
    - Batch operations
    
    Does NOT handle:
    - Storage implementation (delegated to repository)
    - BigQuery-specific logic (abstracted away)
    """
    
    def __init__(self, claim_repository: IClaimRepository):
        """
        Initialize with dependency injection.
        
        Args:
            claim_repository: Repository implementing IClaimRepository
        """
        self.repo = claim_repository
        logger.info("Claims initialized")
    
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
    ) -> Claim:
        """
        Create a new claim with validation.
        
        Args:
            document_version_id: Document being processed
            step_run_id: Step that produced this claim
            claim_type: Type of claim (e.g., 'loan_amount')
            value: Extracted value
            confidence: Model confidence (0.0-1.0)
            page_number: Page number (1-indexed)
            bbox: Bounding box dict
            source_text: Original text
            normalized_value: Cleaned value
            room_id: Optional room context
            metadata: Additional metadata
            
        Returns:
            Created Claim domain model
            
        Raises:
            ValueError: If validation fails
        """
        # Create domain model (validates in __post_init__)
        claim = Claim(
            id=str(uuid.uuid4()),
            document_version_id=document_version_id,
            step_run_id=step_run_id,
            claim_type=ClaimType(claim_type),
            value=value,
            confidence=confidence,
            page_number=page_number,
            bbox=BoundingBox.from_dict(bbox),
            created_at=datetime.now(timezone.utc),
            normalized_value=normalized_value,
            source_text=source_text,
            room_id=room_id,
            metadata=metadata or {}
        )
        
        # Persist via repository
        claim_id = self.repo.create(claim.to_dict())
        
        logger.info(
            f"Created claim {claim_id} of type {claim_type} "
            f"for document {document_version_id}"
        )
        
        return claim
    
    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """
        Retrieve a claim by ID.
        
        Args:
            claim_id: Claim ID
            
        Returns:
            Claim domain model or None if not found
        """
        data = self.repo.get_by_id(claim_id)
        
        if not data:
            return None
        
        return Claim.from_dict(data)
    
    def get_claims_for_document(
        self,
        document_version_id: str,
        claim_type: Optional[str] = None,
        min_confidence: Optional[float] = None,
        verified_only: bool = False
    ) -> List[Claim]:
        """
        Get claims for a document with optional filters.
        
        Args:
            document_version_id: Document to query
            claim_type: Optional type filter
            min_confidence: Optional confidence threshold
            verified_only: Only return human-verified claims
            
        Returns:
            List of Claim domain models
        """
        if verified_only:
            results = self.repo.get_verified_claims(document_version_id)
        else:
            results = self.repo.get_by_document_version(
                document_version_id,
                claim_type=claim_type
            )
        
        # Convert to domain models
        claims = [Claim.from_dict(data) for data in results]
        
        # Apply confidence filter
        if min_confidence is not None:
            claims = [c for c in claims if c.confidence >= min_confidence]
        
        return claims
    
    def batch_create_claims(
        self,
        claims_data: List[Dict[str, Any]]
    ) -> List[Claim]:
        """
        Create multiple claims in batch.
        
        Args:
            claims_data: List of claim data dictionaries
            
        Returns:
            List of created Claim domain models
        """
        created_claims = []
        
        for data in claims_data:
            # Validate each claim via domain model
            claim = Claim(
                id=str(uuid.uuid4()),
                document_version_id=data["document_version_id"],
                step_run_id=data["step_run_id"],
                claim_type=ClaimType(data["claim_type"]),
                value=data["value"],
                confidence=data["confidence"],
                page_number=data["page_number"],
                bbox=BoundingBox.from_dict(data["bbox"]),
                created_at=datetime.now(timezone.utc),
                normalized_value=data.get("normalized_value"),
                source_text=data.get("source_text"),
                room_id=data.get("room_id"),
                metadata=data.get("metadata", {})
            )
            
            created_claims.append(claim)
        
        # Batch persist
        claim_dicts = [c.to_dict() for c in created_claims]
        self.repo.batch_create(claim_dicts)
        
        logger.info(f"Batch created {len(created_claims)} claims")
        
        return created_claims
    
    def update_user_feedback(
        self,
        claim_id: str,
        feedback: Dict[str, Any]
    ) -> bool:
        """
        Add user feedback to a claim.
        
        Args:
            claim_id: Claim to update
            feedback: Feedback data (e.g., {"is_correct": true, "correction": "..."})
            
        Returns:
            True if successful
        """
        # Validate feedback structure
        if "is_correct" not in feedback:
            raise ValueError("Feedback must include 'is_correct' field")
        
        updates = {
            "user_feedback_json": feedback,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        success = self.repo.update(claim_id, updates)
        
        if success:
            logger.info(f"Updated feedback for claim {claim_id}")
        
        return success
    
    def get_high_confidence_claims(
        self,
        document_version_id: str,
        threshold: float = 0.9
    ) -> List[Claim]:
        """
        Get high-confidence claims for a document.
        
        Args:
            document_version_id: Document to query
            threshold: Confidence threshold
            
        Returns:
            List of high-confidence claims
        """
        all_claims = self.get_claims_for_document(document_version_id)
        return [c for c in all_claims if c.is_high_confidence(threshold)]
    
    def aggregate_by_type(
        self,
        document_version_id: str
    ) -> Dict[str, List[Claim]]:
        """
        Group claims by type for a document.
        
        Args:
            document_version_id: Document to query
            
        Returns:
            Dictionary mapping claim types to lists of claims
        """
        claims = self.get_claims_for_document(document_version_id)
        
        aggregated = {}
        for claim in claims:
            claim_type = claim.claim_type.value
            if claim_type not in aggregated:
                aggregated[claim_type] = []
            aggregated[claim_type].append(claim)
        
        return aggregated
