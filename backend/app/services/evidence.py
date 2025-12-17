"""
Evidence Service

Search and aggregate claims across documents to build evidence packages.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple

from google.cloud import bigquery

from app.services.bigquery import BigQuery


logger = logging.getLogger(__name__)

EVIDENCE_BUNDLES_TABLE = "evidence_bundles"


class Evidence:
    """Searches claims and builds evidence packages."""
    
    def __init__(self, bq_service: BigQuery):
        self.bq = bq_service
    
    def search_evidence(
        self,
        room_id: Optional[str] = None,
        document_version_ids: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        claim_types: Optional[List[str]] = None,
        confidence_min: float = 0.0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for claims that match evidence criteria.
        
        Performs keyword search across source_text and normalized_value fields.
        Can scope to a Room or specific DocumentVersions.
        
        Args:
            room_id: Optional Room to search within
            document_version_ids: Optional list of specific documents
            keywords: Optional keywords for text search
            claim_types: Optional claim types to filter
            confidence_min: Minimum confidence threshold
            limit: Maximum results to return
            
        Returns:
            List of matching claims with relevance ranking
        """
        conditions = ["confidence >= @confidence_min"]
        params = [
            bigquery.ScalarQueryParameter("confidence_min", "FLOAT64", confidence_min)
        ]
        
        if room_id:
            conditions.append("""
                document_version_id IN (
                    SELECT document_version_id 
                    FROM `{project}.{dataset}.room_documents`
                    WHERE room_id = @room_id
                )
            """)
            params.append(bigquery.ScalarQueryParameter("room_id", "STRING", room_id))
        
        if document_version_ids:
            conditions.append("document_version_id IN UNNEST(@doc_version_ids)")
            params.append(
                bigquery.ArrayQueryParameter("doc_version_ids", "STRING", document_version_ids)
            )
        
        if claim_types:
            conditions.append("claim_type IN UNNEST(@claim_types)")
            params.append(
                bigquery.ArrayQueryParameter("claim_types", "STRING", claim_types)
            )
        
        select_clause = "*, 0 as relevance_score"
        
        if keywords:
            keyword_conditions = []
            for i, keyword in enumerate(keywords):
                param_name = f"keyword_{i}"
                keyword_conditions.append(
                    f"(LOWER(source_text) LIKE CONCAT('%', @{param_name}, '%') "
                    f"OR LOWER(normalized_value) LIKE CONCAT('%', @{param_name}, '%'))"
                )
                params.append(
                    bigquery.ScalarQueryParameter(param_name, "STRING", keyword.lower())
                )
            
            conditions.append(f"({' OR '.join(keyword_conditions)})")
            
            relevance_expression = " + ".join([
                f"(CASE WHEN LOWER(source_text) LIKE CONCAT('%', @keyword_{i}, '%') THEN 1 ELSE 0 END)"
                for i in range(len(keywords))
            ])
            select_clause = f"*, ({relevance_expression}) as relevance_score"
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT {select_clause}
            FROM `{self.bq.project}.{self.bq.dataset}.claims`
            WHERE {where_clause}
            ORDER BY relevance_score DESC, confidence DESC
            LIMIT @limit
        """
        
        params.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        results = self.bq.client.query(query, job_config=job_config).result()
        
        return [dict(row) for row in results]
    
    def create_evidence_bundle(
        self,
        name: str,
        room_id: Optional[str],
        claim_ids: List[str],
        description: Optional[str] = None,
        created_by_user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create an Evidence Bundle linking selected claims.
        
        Evidence bundles are immutable packages of claims that provide
        audit trails for decision-making processes.
        
        Args:
            name: Bundle name
            room_id: Optional associated Room
            claim_ids: List of claim IDs to include
            description: Optional description
            created_by_user_id: User who created the bundle
            metadata: Optional additional metadata
            
        Returns:
            Dictionary containing the bundle data
        """
        bundle_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        bundle_data = {
            "id": bundle_id,
            "name": name,
            "description": description,
            "room_id": room_id,
            "claim_ids": claim_ids,
            "claim_count": len(claim_ids),
            "created_at": now,
            "created_by_user_id": created_by_user_id,
            "metadata": metadata
        }
        
        self.bq.insert_row(EVIDENCE_BUNDLES_TABLE, bundle_data)
        logger.info(
            f"Created evidence bundle {bundle_id} with {len(claim_ids)} claims"
        )
        
        return bundle_data
    
    def get_evidence_bundle(self, bundle_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an evidence bundle by its ID."""
        return self.bq.get_by_id(EVIDENCE_BUNDLES_TABLE, bundle_id)
    
    def get_evidence_bundle_with_claims(
        self, bundle_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve an evidence bundle with full claim details.
        
        Returns the bundle plus all associated claims in a single response.
        """
        bundle = self.get_evidence_bundle(bundle_id)
        
        if not bundle:
            return None
        
        claim_ids = bundle.get("claim_ids", [])
        
        if not claim_ids:
            bundle["claims"] = []
            return bundle
        
        query = f"""
            SELECT * FROM `{self.bq.project}.{self.bq.dataset}.claims`
            WHERE id IN UNNEST(@claim_ids)
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("claim_ids", "STRING", claim_ids)
            ]
        )
        
        results = self.bq.client.query(query, job_config=job_config).result()
        claims = [dict(row) for row in results]
        
        bundle["claims"] = claims
        return bundle
    
    def list_evidence_bundles(
        self,
        room_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List evidence bundles with optional Room filtering."""
        conditions = []
        params = []
        
        if room_id:
            conditions.append("room_id = @room_id")
            params.append(bigquery.ScalarQueryParameter("room_id", "STRING", room_id))
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT * FROM `{self.bq.project}.{self.bq.dataset}.{EVIDENCE_BUNDLES_TABLE}`
            {where_clause}
            ORDER BY created_at DESC
            LIMIT @limit OFFSET @offset
        """
        
        params.extend([
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
            bigquery.ScalarQueryParameter("offset", "INT64", offset)
        ])
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        results = self.bq.client.query(query, job_config=job_config).result()
        
        return [dict(row) for row in results]
    
    def get_claim_statistics_for_bundle(
        self, bundle_id: str
    ) -> Dict[str, Any]:
        """
        Calculate statistics for claims in an evidence bundle.
        
        Returns claim type distribution, average confidence, source documents.
        """
        bundle = self.get_evidence_bundle(bundle_id)
        
        if not bundle:
            return None
        
        claim_ids = bundle.get("claim_ids", [])
        
        if not claim_ids:
            return {
                "bundle_id": bundle_id,
                "claim_count": 0,
                "claim_types": {},
                "avg_confidence": 0.0,
                "document_count": 0
            }
        
        query = f"""
            SELECT 
                claim_type,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence,
                COUNT(DISTINCT document_version_id) as document_count
            FROM `{self.bq.project}.{self.bq.dataset}.claims`
            WHERE id IN UNNEST(@claim_ids)
            GROUP BY claim_type
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("claim_ids", "STRING", claim_ids)
            ]
        )
        
        results = list(self.bq.client.query(query, job_config=job_config).result())
        
        claim_types = {}
        total_confidence = 0.0
        total_count = 0
        document_count = 0
        
        for row in results:
            claim_type = row["claim_type"]
            count = row["count"]
            avg_conf = row["avg_confidence"]
            
            claim_types[claim_type] = {
                "count": count,
                "avg_confidence": round(avg_conf, 4)
            }
            
            total_confidence += avg_conf * count
            total_count += count
            document_count = max(document_count, row["document_count"])
        
        overall_avg_confidence = (
            total_confidence / total_count if total_count > 0 else 0.0
        )
        
        return {
            "bundle_id": bundle_id,
            "claim_count": total_count,
            "claim_types": claim_types,
            "avg_confidence": round(overall_avg_confidence, 4),
            "document_count": document_count
        }
