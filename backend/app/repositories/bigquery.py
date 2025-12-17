"""
BigQuery Repository Implementations

Concrete implementations of repository interfaces using BigQuery for structured data.
PDFs and outputs are stored in Cloud Storage (GCS).
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from google.cloud import bigquery

from app.repositories.interfaces import (
    IClaimRepository,
    IProcessingRunRepository,
    IRoomRepository,
    IEvidenceBundleRepository,
    IDocumentProfileRepository
)
from app.services.bigquery import BigQuery


logger = logging.getLogger(__name__)


class ClaimRepository(IClaimRepository):
    """BigQuery implementation of claim repository."""
    
    def __init__(self, bq_service: BigQuery):
        self.bq = bq_service
        self.table = "claims"
    
    def create(self, data: Dict[str, Any]) -> str:
        """Create a new claim."""
        claim_id = data.get("id") or str(uuid.uuid4())
        data["id"] = claim_id
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        
        self.bq.insert_row(self.table, data)
        logger.info(f"Created claim {claim_id}")
        return claim_id
    
    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get claim by ID."""
        return self.bq.get_by_id(self.table, entity_id)
    
    def update(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """Update claim (primarily for user feedback)."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self.bq.update_row(self.table, entity_id, updates)
    
    def delete(self, entity_id: str) -> bool:
        """Delete claim (soft delete recommended)."""
        query = f"""
            DELETE FROM `{self.bq.dataset_ref}.{self.table}`
            WHERE id = @claim_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("claim_id", "STRING", entity_id)
            ]
        )
        
        result = self.bq.client.query(query, job_config=job_config).result()
        return result.total_rows > 0
    
    def query(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query claims with filters."""
        conditions = []
        params = []
        
        if filters:
            for key, value in filters.items():
                conditions.append(f"{key} = @{key}")
                params.append((key, self._infer_type(value), value))
        
        where_clause = " AND ".join(conditions) if conditions else None
        return self.bq.query(
            self.table,
            where=where_clause,
            params=params,
            order_by=order_by,
            limit=limit
        )
    
    def get_by_document_version(
        self,
        document_version_id: str,
        claim_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get claims for a document version."""
        filters = {"document_version_id": document_version_id}
        if claim_type:
            filters["claim_type"] = claim_type
        
        return self.query(filters, order_by="page_number, bbox_y")
    
    def get_by_step_run(self, step_run_id: str) -> List[Dict[str, Any]]:
        """Get claims produced by a step run."""
        return self.query({"step_run_id": step_run_id})
    
    def get_verified_claims(
        self,
        document_version_id: str
    ) -> List[Dict[str, Any]]:
        """Get human-verified claims."""
        query = f"""
            SELECT * FROM `{self.bq.dataset_ref}.{self.table}`
            WHERE document_version_id = @doc_version_id
            AND user_feedback_json IS NOT NULL
            ORDER BY page_number, bbox_y
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("doc_version_id", "STRING", document_version_id)
            ]
        )
        
        return list(self.bq.client.query(query, job_config=job_config).result())
    
    def batch_create(self, claims: List[Dict[str, Any]]) -> List[str]:
        """Batch create multiple claims."""
        claim_ids = []
        
        for claim_data in claims:
            claim_id = self.create(claim_data)
            claim_ids.append(claim_id)
        
        return claim_ids
    
    def _infer_type(self, value: Any) -> str:
        """Infer BigQuery type from Python value."""
        if isinstance(value, bool):
            return "BOOL"
        elif isinstance(value, int):
            return "INT64"
        elif isinstance(value, float):
            return "FLOAT64"
        else:
            return "STRING"


class ProcessingRunRepository(IProcessingRunRepository):
    """BigQuery implementation of processing run repository."""
    
    def __init__(self, bq_service: BigQuery):
        self.bq = bq_service
        self.table = "processing_runs"
    
    def create(self, data: Dict[str, Any]) -> str:
        """Create a new processing run."""
        run_id = data.get("id") or str(uuid.uuid4())
        data["id"] = run_id
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        self.bq.insert_row(self.table, data)
        logger.info(f"Created processing run {run_id}")
        return run_id
    
    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get run by ID."""
        return self.bq.get_by_id(self.table, entity_id)
    
    def update(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """Update processing run."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self.bq.update_row(self.table, entity_id, updates)
    
    def delete(self, entity_id: str) -> bool:
        """Delete processing run (not recommended - use status instead)."""
        query = f"""
            DELETE FROM `{self.bq.dataset_ref}.{self.table}`
            WHERE id = @run_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", entity_id)
            ]
        )
        
        result = self.bq.client.query(query, job_config=job_config).result()
        return result.total_rows > 0
    
    def query(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query processing runs."""
        conditions = []
        params = []
        
        if filters:
            for key, value in filters.items():
                conditions.append(f"{key} = @{key}")
                param_type = "STRING" if isinstance(value, str) else "INT64"
                params.append((key, param_type, value))
        
        where_clause = " AND ".join(conditions) if conditions else None
        return self.bq.query(
            self.table,
            where=where_clause,
            params=params,
            order_by=order_by or "created_at DESC",
            limit=limit
        )
    
    def get_by_document_version(
        self,
        document_version_id: str
    ) -> List[Dict[str, Any]]:
        """Get all runs for a document version."""
        return self.query(
            filters={"document_version_id": document_version_id},
            order_by="created_at DESC"
        )
    
    def get_latest_run(
        self,
        document_version_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get most recent run for a document version."""
        results = self.query(
            filters={"document_version_id": document_version_id},
            order_by="created_at DESC",
            limit=1
        )
        return results[0] if results else None
    
    def get_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all runs with a specific status."""
        return self.query(filters={"status": status})
    
    def update_status(
        self,
        run_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update run status."""
        updates = {"status": status}
        
        if status == "processing" and not self.get_by_id(run_id).get("started_at"):
            updates["started_at"] = datetime.now(timezone.utc).isoformat()
        
        if status in ["completed", "failed"]:
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        if error_message:
            updates["error_message"] = error_message
        
        return self.update(run_id, updates)


# Similar implementations for Room, EvidenceBundle, and DocumentProfile repositories
# Following the same pattern...
