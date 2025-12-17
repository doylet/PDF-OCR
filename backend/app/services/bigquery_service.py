from google.cloud import bigquery
from typing import Optional, Dict, List, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BigQueryService:
    """
    Service layer for BigQuery operations.
    Provides CRUD operations for all data_hero entities.
    
    Design: Direct SQL for transparency (Constitution VI).
    No ORM abstraction - BigQuery queries are explicit and auditable.
    """
    
    def __init__(self, bigquery_client: bigquery.Client, dataset_id: str = "data_hero"):
        self.client = bigquery_client
        self.dataset_id = dataset_id
        self.dataset_ref = f"{bigquery_client.project}.{dataset_id}"
        logger.info(f"BigQueryService initialized for dataset: {self.dataset_ref}")
    
    def insert_row(self, table_name: str, row_dict: Dict[str, Any]) -> str:
        """
        Atomically insert a single row into a table.
        
        Args:
            table_name: Table name (without dataset prefix)
            row_dict: Dictionary of column_name: value pairs
            
        Returns:
            Row ID if 'id' field exists in row_dict, else confirmation string
            
        Raises:
            Exception if insert fails
        """
        table_ref = f"{self.dataset_ref}.{table_name}"
        
        try:
            # Use streaming insert for immediate availability
            errors = self.client.insert_rows_json(table_ref, [row_dict])
            
            if errors:
                error_msg = f"Insert failed for {table_name}: {errors}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            row_id = row_dict.get('id', 'inserted')
            logger.info(f"Inserted row into {table_name}: {row_id}")
            return row_id
            
        except Exception as e:
            logger.error(f"Error inserting into {table_name}: {e}")
            raise
    
    def get_by_id(
        self, 
        table_name: str, 
        id_field: str, 
        id_value: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single row by ID field.
        
        Args:
            table_name: Table name (without dataset prefix)
            id_field: Name of the ID column
            id_value: Value to search for
            
        Returns:
            Dictionary of row data, or None if not found
        """
        table_ref = f"{self.dataset_ref}.{table_name}"
        
        query = f"""
            SELECT *
            FROM `{table_ref}`
            WHERE {id_field} = @id_value
            LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id_value", "STRING", id_value)
            ]
        )
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            if results:
                row = dict(results[0])
                logger.info(f"Retrieved {table_name} by {id_field}={id_value}")
                return row
            else:
                logger.info(f"No row found in {table_name} for {id_field}={id_value}")
                return None
                
        except Exception as e:
            logger.error(f"Error querying {table_name}: {e}")
            raise
    
    def query(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query table with filters, ordering, and pagination.
        
        Args:
            table_name: Table name (without dataset prefix)
            filters: Dictionary of column_name: value pairs (AND conditions)
            order_by: Column name to order by (use "-column" for DESC)
            limit: Maximum number of rows to return
            offset: Number of rows to skip (for pagination)
            
        Returns:
            List of dictionaries representing rows
        """
        table_ref = f"{self.dataset_ref}.{table_name}"
        
        # Build WHERE clause
        where_clauses = []
        query_parameters = []
        
        if filters:
            for idx, (col, val) in enumerate(filters.items()):
                param_name = f"param_{idx}"
                where_clauses.append(f"{col} = @{param_name}")
                
                # Infer type from value
                if isinstance(val, bool):
                    param_type = "BOOL"
                elif isinstance(val, int):
                    param_type = "INT64"
                elif isinstance(val, float):
                    param_type = "FLOAT64"
                else:
                    param_type = "STRING"
                
                query_parameters.append(
                    bigquery.ScalarQueryParameter(param_name, param_type, val)
                )
        
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        # Build ORDER BY clause
        order_clause = ""
        if order_by:
            if order_by.startswith("-"):
                order_clause = f"ORDER BY {order_by[1:]} DESC"
            else:
                order_clause = f"ORDER BY {order_by} ASC"
        
        # Build LIMIT/OFFSET clause
        limit_clause = f"LIMIT {limit}" if limit else ""
        offset_clause = f"OFFSET {offset}" if offset else ""
        
        query = f"""
            SELECT *
            FROM `{table_ref}`
            {where_clause}
            {order_clause}
            {limit_clause}
            {offset_clause}
        """
        
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = [dict(row) for row in query_job.result()]
            
            logger.info(f"Query returned {len(results)} rows from {table_name}")
            return results
            
        except Exception as e:
            logger.error(f"Error querying {table_name}: {e}")
            raise
    
    def update_row(
        self,
        table_name: str,
        id_field: str,
        id_value: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Atomically update a single row.
        
        Args:
            table_name: Table name (without dataset prefix)
            id_field: Name of the ID column
            id_value: Value of the row to update
            updates: Dictionary of column_name: new_value pairs
            
        Returns:
            True if row was updated, False if row not found
            
        Raises:
            Exception if update fails
        """
        table_ref = f"{self.dataset_ref}.{table_name}"
        
        # Build SET clause
        set_clauses = []
        query_parameters = [
            bigquery.ScalarQueryParameter("id_value", "STRING", id_value)
        ]
        
        for idx, (col, val) in enumerate(updates.items()):
            param_name = f"update_{idx}"
            set_clauses.append(f"{col} = @{param_name}")
            
            # Infer type from value
            if isinstance(val, bool):
                param_type = "BOOL"
            elif isinstance(val, int):
                param_type = "INT64"
            elif isinstance(val, float):
                param_type = "FLOAT64"
            elif isinstance(val, datetime):
                param_type = "TIMESTAMP"
            else:
                param_type = "STRING"
            
            query_parameters.append(
                bigquery.ScalarQueryParameter(param_name, param_type, val)
            )
        
        # Always update updated_at timestamp if column exists
        set_clauses.append("updated_at = CURRENT_TIMESTAMP()")
        
        query = f"""
            UPDATE `{table_ref}`
            SET {', '.join(set_clauses)}
            WHERE {id_field} = @id_value
        """
        
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            # Check if any rows were updated
            updated = query_job.num_dml_affected_rows > 0
            
            if updated:
                logger.info(f"Updated {table_name} row: {id_field}={id_value}")
            else:
                logger.warning(f"No row found to update in {table_name}: {id_field}={id_value}")
            
            return updated
            
        except Exception as e:
            logger.error(f"Error updating {table_name}: {e}")
            raise
    
    def execute_query(self, query: str, parameters: Optional[List] = None) -> List[Dict[str, Any]]:
        """
        Execute arbitrary SQL query (for complex operations).
        
        Args:
            query: SQL query string
            parameters: Optional list of query parameters
            
        Returns:
            List of dictionaries representing rows
        """
        job_config = bigquery.QueryJobConfig()
        
        if parameters:
            job_config.query_parameters = parameters
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = [dict(row) for row in query_job.result()]
            
            logger.info(f"Custom query returned {len(results)} rows")
            return results
            
        except Exception as e:
            logger.error(f"Error executing custom query: {e}")
            raise
    
    @staticmethod
    def Query():
        # Expose query directions for compatibility with existing code
        class _Query:
            DESCENDING = "DESC"
            ASCENDING = "ASC"
        return _Query()
