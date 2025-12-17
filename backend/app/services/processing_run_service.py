from google.cloud import bigquery
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import logging

from app.models.state_machines import (
    ProcessingRunState,
    validate_processing_run_transition,
    log_state_transition
)

logger = logging.getLogger(__name__)


class ProcessingRunService:
    """
    Service for managing ProcessingRun lifecycle.
    
    ProcessingRuns track the execution of document processing pipelines.
    Each run has multiple StepRuns that execute sequentially or in parallel.
    
    Constitution II: State Machine-Driven Processing
    """
    
    def __init__(self, bigquery_client: bigquery.Client, dataset_id: str = "data_hero"):
        self.client = bigquery_client
        self.dataset_id = dataset_id
        self.dataset_ref = f"{bigquery_client.project}.{dataset_id}"
        logger.info("ProcessingRunService initialized")
    
    def create_processing_run(
        self,
        document_version_id: str,
        config: Dict[str, Any],
        created_by_user_id: Optional[str] = None
    ) -> str:
        """
        Create a new ProcessingRun.
        
        Args:
            document_version_id: ID of the DocumentVersion to process
            config: Configuration for processing (model versions, parameters, etc.)
            created_by_user_id: Optional user ID who initiated the run
            
        Returns:
            ProcessingRun ID (UUID)
            
        Example:
            run_id = service.create_processing_run(
                document_version_id="abc123...",
                config={
                    "pipeline": "claims_extraction",
                    "model_version": "v1.2.0",
                    "steps": ["profile", "extract", "validate"]
                }
            )
        """
        run_id = str(uuid.uuid4())
        table_ref = f"{self.dataset_ref}.processing_runs"
        
        row_data = {
            "id": run_id,
            "document_version_id": document_version_id,
            "status": ProcessingRunState.PENDING,
            "config": config,
            "created_by_user_id": created_by_user_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "completed_at": None,
            "error_message": None
        }
        
        try:
            errors = self.client.insert_rows_json(table_ref, [row_data])
            
            if errors:
                error_msg = f"Failed to create ProcessingRun: {errors}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info(f"Created ProcessingRun: {run_id} for document {document_version_id}")
            log_state_transition("ProcessingRun", run_id, "none", ProcessingRunState.PENDING, "created")
            
            return run_id
            
        except Exception as e:
            logger.error(f"Error creating ProcessingRun: {e}")
            raise
    
    def get_processing_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a ProcessingRun by ID.
        
        Args:
            run_id: ProcessingRun ID (UUID)
            
        Returns:
            Dictionary with run details, or None if not found
        """
        table_ref = f"{self.dataset_ref}.processing_runs"
        
        query = f"""
        SELECT
            id,
            document_version_id,
            status,
            config,
            created_by_user_id,
            created_at,
            updated_at,
            started_at,
            completed_at,
            error_message
        FROM `{table_ref}`
        WHERE id = @run_id
        LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id)
            ]
        )
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            if results:
                row = dict(results[0])
                logger.debug(f"Retrieved ProcessingRun: {run_id}")
                return row
            else:
                logger.warning(f"ProcessingRun not found: {run_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving ProcessingRun {run_id}: {e}")
            raise
    
    def update_status(
        self,
        run_id: str,
        new_status: ProcessingRunState,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update ProcessingRun status with state machine validation.
        
        Args:
            run_id: ProcessingRun ID (UUID)
            new_status: New status (must be valid transition)
            error_message: Optional error message if transitioning to failed
            
        Returns:
            True if update succeeded, False if run not found
            
        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        # Get current status
        current_run = self.get_processing_run(run_id)
        
        if not current_run:
            logger.error(f"Cannot update status: ProcessingRun {run_id} not found")
            return False
        
        current_status = ProcessingRunState(current_run["status"])
        
        # Validate transition
        validate_processing_run_transition(current_status, new_status)
        
        # Build update query
        table_ref = f"{self.dataset_ref}.processing_runs"
        
        updates = {
            "status": new_status.value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Set timestamps based on state
        if new_status == ProcessingRunState.RUNNING and not current_run.get("started_at"):
            updates["started_at"] = datetime.utcnow().isoformat()
        
        if new_status in {ProcessingRunState.COMPLETED, ProcessingRunState.FAILED}:
            updates["completed_at"] = datetime.utcnow().isoformat()
        
        if error_message:
            updates["error_message"] = error_message
        
        # Build SET clause
        set_clauses = []
        query_parameters = [
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id)
        ]
        
        for idx, (col, val) in enumerate(updates.items()):
            param_name = f"update_{idx}"
            set_clauses.append(f"{col} = @{param_name}")
            
            # Infer type
            param_type = "STRING"  # Most fields are strings or serialized
            
            query_parameters.append(
                bigquery.ScalarQueryParameter(param_name, param_type, val)
            )
        
        update_query = f"""
        UPDATE `{table_ref}`
        SET {', '.join(set_clauses)}
        WHERE id = @run_id
        """
        
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        try:
            query_job = self.client.query(update_query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            updated = query_job.num_dml_affected_rows > 0
            
            if updated:
                log_state_transition(
                    "ProcessingRun",
                    run_id,
                    current_status.value,
                    new_status.value,
                    error_message
                )
                logger.info(f"Updated ProcessingRun {run_id}: {current_status} → {new_status}")
            else:
                logger.warning(f"No rows updated for ProcessingRun {run_id}")
            
            return updated
            
        except Exception as e:
            logger.error(f"Error updating ProcessingRun {run_id}: {e}")
            raise
    
    def list_runs(
        self,
        document_version_id: Optional[str] = None,
        status: Optional[ProcessingRunState] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List ProcessingRuns with optional filters.
        
        Args:
            document_version_id: Filter by document version
            status: Filter by status
            limit: Maximum number of results
            offset: Number of results to skip (for pagination)
            
        Returns:
            List of ProcessingRun dictionaries
        """
        table_ref = f"{self.dataset_ref}.processing_runs"
        
        where_clauses = []
        query_parameters = []
        
        if document_version_id:
            where_clauses.append("document_version_id = @document_version_id")
            query_parameters.append(
                bigquery.ScalarQueryParameter("document_version_id", "STRING", document_version_id)
            )
        
        if status:
            where_clauses.append("status = @status")
            query_parameters.append(
                bigquery.ScalarQueryParameter("status", "STRING", status.value)
            )
        
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        query = f"""
        SELECT
            id,
            document_version_id,
            status,
            config,
            created_by_user_id,
            created_at,
            updated_at,
            started_at,
            completed_at,
            error_message
        FROM `{table_ref}`
        {where_clause}
        ORDER BY created_at DESC
        LIMIT {limit}
        OFFSET {offset}
        """
        
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = [dict(row) for row in query_job.result()]
            
            logger.info(f"Listed {len(results)} ProcessingRuns")
            return results
            
        except Exception as e:
            logger.error(f"Error listing ProcessingRuns: {e}")
            raise
