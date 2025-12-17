from google.cloud import bigquery
from typing import Dict, Optional, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Idempotency:
    """
    Service for atomic idempotency key management using BigQuery MERGE pattern.
    
    Ensures that duplicate operations (same key_hash) are detected atomically
    and only one execution proceeds. Losers receive cached results.
    
    Critical for Constitution III: Idempotency Everywhere
    """
    
    def __init__(self, bigquery_client: bigquery.Client, dataset_id: str = "data_hero"):
        self.client = bigquery_client
        self.dataset_id = dataset_id
        self.dataset_ref = f"{bigquery_client.project}.{dataset_id}"
        logger.info("Idempotency initialized")
    
    def check_and_insert_key(
        self,
        key_hash: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Atomically check if idempotency key exists and insert if not.
        
        Uses BigQuery MERGE pattern for atomicity:
        - If key doesn't exist: INSERT and return {"was_inserted": True}
        - If key exists: Return {"was_inserted": False, "existing_result": {...}}
        
        Args:
            key_hash: SHA-256 hash of operation parameters
            context: Metadata about the operation (step_name, doc_version_id, etc.)
            
        Returns:
            Dictionary with:
            - was_inserted (bool): True if this call won the race, False if key already existed
            - existing_result (dict|None): If was_inserted=False, contains cached result
            - key_hash (str): The idempotency key
            
        Example:
            result = service.check_and_insert_key("abc123", {"step": "extract", "doc": "xyz"})
            if result["was_inserted"]:
                # This is the first call - proceed with operation
                do_expensive_operation()
            else:
                # Duplicate call - return cached result
                return result["existing_result"]
        """
        table_ref = f"{self.dataset_ref}.idempotency_keys"
        
        # First, try to get existing key
        existing = self.get_cached_result(key_hash)
        
        if existing:
            logger.info(f"Idempotency key already exists: {key_hash[:16]}...")
            return {
                "was_inserted": False,
                "existing_result": existing.get("result_reference"),
                "key_hash": key_hash,
                "created_at": existing.get("created_at")
            }
        
        # Key doesn't exist - try to insert
        # Use MERGE for atomicity (handles race conditions)
        merge_query = f"""
        MERGE `{table_ref}` AS target
        USING (
            SELECT
                @key_hash AS key_hash,
                @context AS context,
                NULL AS result_reference,
                CURRENT_TIMESTAMP() AS created_at,
                NULL AS completed_at
        ) AS source
        ON target.key_hash = source.key_hash
        WHEN NOT MATCHED THEN
            INSERT (key_hash, context, result_reference, created_at, completed_at)
            VALUES (source.key_hash, source.context, source.result_reference, source.created_at, source.completed_at)
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("key_hash", "STRING", key_hash),
                bigquery.ScalarQueryParameter("context", "JSON", context)
            ]
        )
        
        try:
            query_job = self.client.query(merge_query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            # Check how many rows were inserted
            num_inserted = query_job.num_dml_affected_rows
            
            if num_inserted > 0:
                # This call won the race - key was inserted
                logger.info(f"Idempotency key inserted: {key_hash[:16]}...")
                return {
                    "was_inserted": True,
                    "existing_result": None,
                    "key_hash": key_hash
                }
            else:
                # Another call won the race - key already exists
                # Fetch the existing result
                existing = self.get_cached_result(key_hash)
                logger.info(f"Idempotency key race lost: {key_hash[:16]}...")
                return {
                    "was_inserted": False,
                    "existing_result": existing.get("result_reference") if existing else None,
                    "key_hash": key_hash
                }
                
        except Exception as e:
            logger.error(f"Error in check_and_insert_key for {key_hash[:16]}...: {e}")
            raise
    
    def store_result(
        self,
        key_hash: str,
        result_reference: Dict[str, Any]
    ) -> bool:
        """
        Store the result of an operation after completion.
        
        Updates the idempotency_keys row with the result reference (e.g., GCS URI,
        StepRun ID, Claim IDs) so future duplicate calls can retrieve cached results.
        
        Args:
            key_hash: SHA-256 hash of operation parameters
            result_reference: Reference to operation result (GCS URI, DB IDs, etc.)
            
        Returns:
            True if update succeeded, False if key not found
        """
        table_ref = f"{self.dataset_ref}.idempotency_keys"
        
        update_query = f"""
        UPDATE `{table_ref}`
        SET
            result_reference = @result_reference,
            completed_at = CURRENT_TIMESTAMP()
        WHERE key_hash = @key_hash
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("key_hash", "STRING", key_hash),
                bigquery.ScalarQueryParameter("result_reference", "JSON", result_reference)
            ]
        )
        
        try:
            query_job = self.client.query(update_query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            updated = query_job.num_dml_affected_rows > 0
            
            if updated:
                logger.info(f"Stored result for idempotency key: {key_hash[:16]}...")
            else:
                logger.warning(f"No idempotency key found to update: {key_hash[:16]}...")
            
            return updated
            
        except Exception as e:
            logger.error(f"Error storing result for {key_hash[:16]}...: {e}")
            raise
    
    def get_cached_result(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached result for an idempotency key.
        
        Args:
            key_hash: SHA-256 hash of operation parameters
            
        Returns:
            Dictionary with key metadata and result_reference, or None if not found
        """
        table_ref = f"{self.dataset_ref}.idempotency_keys"
        
        query = f"""
        SELECT
            key_hash,
            context,
            result_reference,
            created_at,
            completed_at
        FROM `{table_ref}`
        WHERE key_hash = @key_hash
        LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("key_hash", "STRING", key_hash)
            ]
        )
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            if results:
                row = dict(results[0])
                logger.debug(f"Retrieved cached result for key: {key_hash[:16]}...")
                return row
            else:
                logger.debug(f"No cached result found for key: {key_hash[:16]}...")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving cached result for {key_hash[:16]}...: {e}")
            raise
    
    @staticmethod
    def compute_key_hash(
        document_version_id: str,
        step_name: str,
        model_version: str,
        parameters: Dict[str, Any]
    ) -> str:
        """
        Compute idempotency key hash from operation parameters.
        
        Convention: SHA-256(doc_version + step_name + model_version + params_json)
        
        Args:
            document_version_id: Document version being processed
            step_name: Processing step name (e.g., "extract_claims")
            model_version: Model/processor version
            parameters: Additional parameters that affect output
            
        Returns:
            SHA-256 hash as hexadecimal string
        """
        import hashlib
        import json
        
        # Canonical JSON representation (sorted keys for determinism)
        params_json = json.dumps(parameters, sort_keys=True)
        
        # Concatenate all components
        key_string = f"{document_version_id}|{step_name}|{model_version}|{params_json}"
        
        # Compute SHA-256 hash
        hash_obj = hashlib.sha256(key_string.encode('utf-8'))
        key_hash = hash_obj.hexdigest()
        
        logger.debug(f"Computed idempotency key: {key_hash[:16]}... for {step_name}")
        return key_hash
