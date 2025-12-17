"""
Document Profile Service

Analyzes document quality and structure to inform routing decisions.
"""

import uuid
import logging
import math
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

from google.cloud import bigquery, documentai_v1 as documentai, storage
from google.api_core.exceptions import NotFound

from app.services.bigquery import BigQuery
from app.services.documentai import DocumentAI
from app.services.storage import get_storage_client


logger = logging.getLogger(__name__)

PROFILE_TABLE = "document_profiles"


class DocumentProfile:
    """Generates and manages document profile metadata."""
    
    def __init__(self, bq_service: BigQuery):
        self.bq = bq_service
        self.documentai_service = DocumentAI()
        self.storage_client = get_storage_client()
    
    def profile_document(
        self,
        document_version_id: str,
        gcs_uri: str,
        file_size_bytes: int,
        docai_document: Optional[documentai.Document] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive profile of a document.
        
        Args:
            document_version_id: The DocumentVersion being profiled
            gcs_uri: GCS location of the document
            file_size_bytes: Size of the document in bytes
            docai_document: Optional pre-parsed Document AI response
            
        Returns:
            Dictionary containing the profile data
        """
        profile_id = str(uuid.uuid4())
        
        page_count = 0
        is_born_digital = None
        quality_score = 0.0
        has_tables = False
        table_count = 0
        skew_detected = False
        max_skew_angle_degrees = 0.0
        document_role = "unknown"
        
        if docai_document:
            page_count = len(docai_document.pages)
            
            if page_count > 0:
                avg_quality = sum(
                    page.image_quality_scores.quality_score
                    for page in docai_document.pages
                    if page.image_quality_scores and page.image_quality_scores.quality_score
                ) / page_count
                quality_score = round(avg_quality, 4) if avg_quality else 0.0
                
                for page in docai_document.pages:
                    if page.tables:
                        has_tables = True
                        table_count += len(page.tables)
                    
                    if page.transforms:
                        for transform in page.transforms:
                            if hasattr(transform, "rows") and transform.rows > 0:
                                m = [
                                    [transform.rows[i][j] for j in range(3)]
                                    for i in range(2)
                                ]
                                angle_rad = math.atan2(m[1][0], m[0][0])
                                angle_deg = math.degrees(angle_rad)
                                
                                if abs(angle_deg) > 1.0:
                                    skew_detected = True
                                    max_skew_angle_degrees = max(
                                        max_skew_angle_degrees, abs(angle_deg)
                                    )
                
                if docai_document.entities:
                    entity_types = {e.type_ for e in docai_document.entities}
                    
                    if "claim_form" in entity_types or "insurance_claim" in entity_types:
                        document_role = "primary_claim_form"
                    elif "medical_record" in entity_types or "diagnosis" in entity_types:
                        document_role = "medical_evidence"
                    elif "bill" in entity_types or "invoice" in entity_types:
                        document_role = "billing_statement"
                    elif "policy" in entity_types:
                        document_role = "policy_document"
                    else:
                        document_role = "supporting_document"
        
        profile_data = {
            "id": profile_id,
            "document_version_id": document_version_id,
            "page_count": page_count,
            "file_size_bytes": file_size_bytes,
            "is_born_digital": is_born_digital,
            "quality_score": quality_score,
            "has_tables": has_tables,
            "table_count": table_count,
            "skew_detected": skew_detected,
            "max_skew_angle_degrees": round(max_skew_angle_degrees, 2),
            "document_role": document_role,
            "profile_artifact_gcs_uri": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        row = self.bq.insert_row(PROFILE_TABLE, profile_data)
        logger.info(
            f"Created document profile {profile_id} for document_version {document_version_id}"
        )
        
        return profile_data
    
    def get_profile_by_id(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document profile by its ID."""
        query = f"""
            SELECT * FROM `{self.bq.project}.{self.bq.dataset}.{PROFILE_TABLE}`
            WHERE id = @profile_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("profile_id", "STRING", profile_id)
            ]
        )
        
        results = list(self.bq.client.query(query, job_config=job_config).result())
        
        if not results:
            return None
        
        return dict(results[0])
    
    def get_profile_for_document_version(
        self, document_version_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the document profile for a specific DocumentVersion."""
        query = f"""
            SELECT * FROM `{self.bq.project}.{self.bq.dataset}.{PROFILE_TABLE}`
            WHERE document_version_id = @document_version_id
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("document_version_id", "STRING", document_version_id)
            ]
        )
        
        results = list(self.bq.client.query(query, job_config=job_config).result())
        
        if not results:
            return None
        
        return dict(results[0])
    
    def get_profiles_by_role(
        self,
        document_role: str,
        quality_min: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve document profiles filtered by role and quality.
        
        Useful for analytics queries like "show me all high-quality claim forms".
        """
        conditions = ["document_role = @document_role"]
        params = [
            bigquery.ScalarQueryParameter("document_role", "STRING", document_role)
        ]
        
        if quality_min is not None:
            conditions.append("quality_score >= @quality_min")
            params.append(bigquery.ScalarQueryParameter("quality_min", "FLOAT64", quality_min))
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT * FROM `{self.bq.project}.{self.bq.dataset}.{PROFILE_TABLE}`
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT @limit
        """
        
        params.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        results = self.bq.client.query(query, job_config=job_config).result()
        
        return [dict(row) for row in results]
    
    def get_skewed_documents(
        self, min_skew_degrees: float = 5.0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Find documents with skew issues requiring correction.
        
        Useful for identifying poor-quality scans that may need pre-processing.
        """
        query = f"""
            SELECT * FROM `{self.bq.project}.{self.bq.dataset}.{PROFILE_TABLE}`
            WHERE skew_detected = TRUE
              AND max_skew_angle_degrees >= @min_skew
            ORDER BY max_skew_angle_degrees DESC
            LIMIT @limit
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("min_skew", "FLOAT64", min_skew_degrees),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )
        
        results = self.bq.client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]
