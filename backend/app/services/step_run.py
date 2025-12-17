from google.cloud import bigquery
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import logging

from app.models.state_machines import (
    StepRunState,
    validate_step_run_transition,
    log_state_transition
)
from app.services.idempotency import Idempotency

logger = logging.getLogger(__name__)


class StepRun:
    """
    Service for managing StepRun lifecycle with idempotency.
    
    StepRuns represent individual processing steps within a ProcessingRun.
    Each step has an idempotency key to prevent duplicate execution.
    
    Constitution II: State Machine-Driven Processing
    Constitution III: Idempotency Everywhere
    """
    
    def __init__(
        self,
        bigquery_client: bigquery.Client,
        idempotency_service: Idempotency,
        dataset_id: str = "data_hero"
    ):
        self.client = bigquery_client
        self.idempotency_service = idempotency_service
        self.dataset_id = dataset_id
        self.dataset_ref = f"{bigquery_client.project}.{dataset_id}"
        logger.info("StepRun initialized")
    
    def create_step_run(
        self,
        processing_run_id: str,
        step_name: str,
        document_version_id: str,
        model_version: str,
        parameters: Dict[str, Any],
        step_order: int = 0
    ) -> Dict[str, Any]:
        """
        Create a new StepRun with idempotency check.
        
        Uses idempotency key to prevent duplicate execution:
        - Computes key_hash from (doc_version, step_name, model_version, params)
        - Atomically checks if key exists in idempotency_keys table
        - If key exists: returns cached result reference
        - If key new: creates StepRun and proceeds
        
        Args:
            processing_run_id: Parent ProcessingRun ID
            step_name: Name of the processing step (e.g., "extract_claims")
            document_version_id: Document being processed
            model_version: Version of model/processor used
            parameters: Step-specific parameters (affects output)
            step_order: Order of step in pipeline (for sequencing)
            
        Returns:
            Dictionary with:
            - step_run_id (str): StepRun ID if created
            - is_duplicate (bool): True if idempotency key already existed
            - cached_result (dict|None): Cached result if duplicate
            
        Example:
            result = service.create_step_run(
                processing_run_id="abc-123",
                step_name="extract_claims",
                document_version_id="sha256...",
                model_version="v1.2.0",
                parameters={"confidence_threshold": 0.8}
            )
            
            if result["is_duplicate"]:
                return result["cached_result"]  # Use cached result
            else:
                step_run_id = result["step_run_id"]
                # Proceed with execution
        """
        # Compute idempotency key
        key_hash = Idempotency.compute_key_hash(
            document_version_id=document_version_id,
            step_name=step_name,
            model_version=model_version,
            parameters=parameters
        )
        
        # Check idempotency atomically
        idempotency_result = self.idempotency_service.check_and_insert_key(
            key_hash=key_hash,
            context={
                "processing_run_id": processing_run_id,
                "step_name": step_name,
                "document_version_id": document_version_id,
                "model_version": model_version,
                "parameters": parameters
            }
        )
        
        # If key already exists, return cached result
        if not idempotency_result["was_inserted"]:
            logger.info(f"Duplicate StepRun detected for key {key_hash[:16]}... - returning cached result")
            return {
                "step_run_id": None,
                "is_duplicate": True,
                "cached_result": idempotency_result["existing_result"],
                "idempotency_key": key_hash
            }
        
        # Key is new - create StepRun
        step_run_id = str(uuid.uuid4())
        table_ref = f"{self.dataset_ref}.step_runs"
        
        row_data = {
            "id": step_run_id,
            "processing_run_id": processing_run_id,
            "step_name": step_name,
            "step_order": step_order,
            "status": StepRunState.PENDING,
            "idempotency_key": key_hash,
            "model_version": model_version,
            "parameters": parameters,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "completed_at": None,
            "output_reference": None,
            "error_message": None,
            "retry_count": 0
        }
        
        try:
            errors = self.client.insert_rows_json(table_ref, [row_data])
            
            if errors:
                error_msg = f"Failed to create StepRun: {errors}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info(f"Created StepRun: {step_run_id} for step '{step_name}' (key: {key_hash[:16]}...)")
            log_state_transition("StepRun", step_run_id, "none", StepRunState.PENDING, "created")
            
            return {
                "step_run_id": step_run_id,
                "is_duplicate": False,
                "cached_result": None,
                "idempotency_key": key_hash
            }
            
        except Exception as e:
            logger.error(f"Error creating StepRun: {e}")
            raise
    
    def get_step_run(self, step_run_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a StepRun by ID.
        
        Args:
            step_run_id: StepRun ID (UUID)
            
        Returns:
            Dictionary with step details, or None if not found
        """
        table_ref = f"{self.dataset_ref}.step_runs"
        
        query = f"""
        SELECT
            id,
            processing_run_id,
            step_name,
            step_order,
            status,
            idempotency_key,
            model_version,
            parameters,
            created_at,
            updated_at,
            started_at,
            completed_at,
            output_reference,
            error_message,
            retry_count
        FROM `{table_ref}`
        WHERE id = @step_run_id
        LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("step_run_id", "STRING", step_run_id)
            ]
        )
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            if results:
                row = dict(results[0])
                logger.debug(f"Retrieved StepRun: {step_run_id}")
                return row
            else:
                logger.warning(f"StepRun not found: {step_run_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving StepRun {step_run_id}: {e}")
            raise
    
    def update_status(
        self,
        step_run_id: str,
        new_status: StepRunState,
        output_reference: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update StepRun status with state machine validation.
        
        Args:
            step_run_id: StepRun ID (UUID)
            new_status: New status (must be valid transition)
            output_reference: Optional reference to step output (GCS URI, Claim IDs, etc.)
            error_message: Optional error message if transitioning to failed state
            
        Returns:
            True if update succeeded, False if step not found
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        # Get current status
        current_step = self.get_step_run(step_run_id)
        
        if not current_step:
            logger.error(f"Cannot update status: StepRun {step_run_id} not found")
            return False
        
        current_status = StepRunState(current_step["status"])
        
        # Validate transition
        validate_step_run_transition(current_status, new_status)
        
        # Build update query
        table_ref = f"{self.dataset_ref}.step_runs"
        
        updates = {
            "status": new_status.value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Set timestamps based on state
        if new_status == StepRunState.RUNNING and not current_step.get("started_at"):
            updates["started_at"] = datetime.utcnow().isoformat()
        
        if new_status in {StepRunState.COMPLETED, StepRunState.FAILED_TERMINAL}:
            updates["completed_at"] = datetime.utcnow().isoformat()
        
        if output_reference:
            updates["output_reference"] = output_reference
            
            # Store result in idempotency cache
            idempotency_key = current_step["idempotency_key"]
            self.idempotency_service.store_result(idempotency_key, output_reference)
        
        if error_message:
            updates["error_message"] = error_message
        
        # Build SET clause
        set_clauses = []
        query_parameters = [
            bigquery.ScalarQueryParameter("step_run_id", "STRING", step_run_id)
        ]
        
        for idx, (col, val) in enumerate(updates.items()):
            param_name = f"update_{idx}"
            
            # Special handling for JSON fields
            if col in {"output_reference"}:
                set_clauses.append(f"{col} = @{param_name}")
                query_parameters.append(
                    bigquery.ScalarQueryParameter(param_name, "JSON", val)
                )
            else:
                set_clauses.append(f"{col} = @{param_name}")
                query_parameters.append(
                    bigquery.ScalarQueryParameter(param_name, "STRING", str(val))
                )
        
        update_query = f"""
        UPDATE `{table_ref}`
        SET {', '.join(set_clauses)}
        WHERE id = @step_run_id
        """
        
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        try:
            query_job = self.client.query(update_query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            updated = query_job.num_dml_affected_rows > 0
            
            if updated:
                log_state_transition(
                    "StepRun",
                    step_run_id,
                    current_status.value,
                    new_status.value,
                    error_message
                )
                logger.info(f"Updated StepRun {step_run_id}: {current_status} → {new_status}")
            else:
                logger.warning(f"No rows updated for StepRun {step_run_id}")
            
            return updated
            
        except Exception as e:
            logger.error(f"Error updating StepRun {step_run_id}: {e}")
            raise
    
    def retry_step_run(self, step_run_id: str) -> bool:
        """
        Retry a failed StepRun.
        
        Only allowed if current status is FAILED_RETRYABLE.
        Transitions to PENDING and increments retry_count.
        
        Args:
            step_run_id: StepRun ID (UUID)
            
        Returns:
            True if retry initiated, False if step not found or not retryable
            
        Raises:
            InvalidStateTransitionError: If step is not in FAILED_RETRYABLE state
        """
        # Get current status
        current_step = self.get_step_run(step_run_id)
        
        if not current_step:
            logger.error(f"Cannot retry: StepRun {step_run_id} not found")
            return False
        
        current_status = StepRunState(current_step["status"])
        
        # Check if retryable
        if not StepRunState.is_retryable(current_status):
            error_msg = f"StepRun {step_run_id} is not retryable (status: {current_status})"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate transition to PENDING (for retry)
        validate_step_run_transition(current_status, StepRunState.PENDING)
        
        # Update status and increment retry count
        table_ref = f"{self.dataset_ref}.step_runs"
        
        update_query = f"""
        UPDATE `{table_ref}`
        SET
            status = @new_status,
            retry_count = retry_count + 1,
            updated_at = CURRENT_TIMESTAMP(),
            error_message = NULL
        WHERE id = @step_run_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("step_run_id", "STRING", step_run_id),
                bigquery.ScalarQueryParameter("new_status", "STRING", StepRunState.PENDING.value)
            ]
        )
        
        try:
            query_job = self.client.query(update_query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            updated = query_job.num_dml_affected_rows > 0
            
            if updated:
                retry_count = current_step.get("retry_count", 0) + 1
                log_state_transition(
                    "StepRun",
                    step_run_id,
                    current_status.value,
                    StepRunState.PENDING.value,
                    f"retry #{retry_count}"
                )
                logger.info(f"Retrying StepRun {step_run_id} (attempt #{retry_count})")
            else:
                logger.warning(f"No rows updated for StepRun retry: {step_run_id}")
            
            return updated
            
        except Exception as e:
            logger.error(f"Error retrying StepRun {step_run_id}: {e}")
            raise
    
    def list_steps_for_run(
        self,
        processing_run_id: str,
        status: Optional[StepRunState] = None
    ) -> List[Dict[str, Any]]:
        """
        List all StepRuns for a ProcessingRun.
        
        Args:
            processing_run_id: ProcessingRun ID
            status: Optional filter by status
            
        Returns:
            List of StepRun dictionaries ordered by step_order
        """
        table_ref = f"{self.dataset_ref}.step_runs"
        
        where_clauses = ["processing_run_id = @processing_run_id"]
        query_parameters = [
            bigquery.ScalarQueryParameter("processing_run_id", "STRING", processing_run_id)
        ]
        
        if status:
            where_clauses.append("status = @status")
            query_parameters.append(
                bigquery.ScalarQueryParameter("status", "STRING", status.value)
            )
        
        where_clause = f"WHERE {' AND '.join(where_clauses)}"
        
        query = f"""
        SELECT
            id,
            processing_run_id,
            step_name,
            step_order,
            status,
            idempotency_key,
            model_version,
            parameters,
            created_at,
            updated_at,
            started_at,
            completed_at,
            output_reference,
            error_message,
            retry_count
        FROM `{table_ref}`
        {where_clause}
        ORDER BY step_order ASC, created_at ASC
        """
        
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = [dict(row) for row in query_job.result()]
            
            logger.info(f"Listed {len(results)} StepRuns for ProcessingRun {processing_run_id}")
            return results
            
        except Exception as e:
            logger.error(f"Error listing StepRuns for ProcessingRun {processing_run_id}: {e}")
            raise
