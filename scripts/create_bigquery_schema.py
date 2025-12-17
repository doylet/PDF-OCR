#!/usr/bin/env python3
"""
BigQuery Schema Creation Script for Data Hero Backend MVP

Creates all 11 tables with proper partitioning and clustering.
Supports idempotent execution and rollback capability.

Usage:
    python scripts/create_bigquery_schema.py --project PROJECT_ID
    python scripts/create_bigquery_schema.py --project PROJECT_ID --drop-all
"""

import argparse
import logging
import sys
from typing import List

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATASET_ID = "data_hero"

TABLE_DEFINITIONS = {
    "rooms": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.rooms` (
            id STRING NOT NULL,
            name STRING NOT NULL,
            description STRING,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP,
            status STRING NOT NULL,
            set_template_id STRING,
            created_by_user_id STRING,
            metadata JSON
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY id, status
        OPTIONS(
            description="Workspaces for multi-document analysis contexts"
        )
    """,
    
    "documents": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.documents` (
            id STRING NOT NULL,
            name STRING NOT NULL,
            description STRING,
            uploaded_by_user_id STRING NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP,
            status STRING NOT NULL,
            metadata JSON
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY id, uploaded_by_user_id
        OPTIONS(
            description="User-facing document entities with mutable metadata"
        )
    """,
    
    "document_versions": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.document_versions` (
            id STRING NOT NULL,
            document_id STRING NOT NULL,
            file_size_bytes INT64 NOT NULL,
            gcs_uri STRING NOT NULL,
            mime_type STRING NOT NULL,
            original_filename STRING NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY id, document_id
        OPTIONS(
            description="Immutable document content identified by SHA-256 hash"
        )
    """,
    
    "room_documents": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.room_documents` (
            room_id STRING NOT NULL,
            document_version_id STRING NOT NULL,
            added_at TIMESTAMP NOT NULL,
            added_by_user_id STRING
        )
        PARTITION BY DATE(added_at)
        CLUSTER BY room_id, document_version_id
        OPTIONS(
            description="Junction table linking Rooms to DocumentVersions (many-to-many)"
        )
    """,
    
    "document_profiles": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.document_profiles` (
            id STRING NOT NULL,
            document_version_id STRING NOT NULL,
            page_count INT64 NOT NULL,
            file_size_bytes INT64 NOT NULL,
            is_born_digital BOOL,
            quality_score FLOAT64,
            has_tables BOOL,
            table_count INT64,
            skew_detected BOOL,
            max_skew_angle_degrees FLOAT64,
            document_role STRING,
            profile_artifact_gcs_uri STRING,
            created_at TIMESTAMP NOT NULL
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY document_version_id, document_role
        OPTIONS(
            description="Document quality and structure metadata for routing decisions"
        )
    """,
    
    "processing_runs": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.processing_runs` (
            id STRING NOT NULL,
            document_version_id STRING NOT NULL,
            run_type STRING NOT NULL,
            status STRING NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message STRING,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY id, document_version_id, status
        OPTIONS(
            description="Pipeline execution tracking with state machine"
        )
    """,
    
    "step_runs": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.step_runs` (
            id STRING NOT NULL,
            processing_run_id STRING NOT NULL,
            step_name STRING NOT NULL,
            idempotency_key STRING NOT NULL,
            model_version STRING NOT NULL,
            parameters_hash STRING NOT NULL,
            parameters JSON,
            status STRING NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            output_artifact_gcs_uri STRING,
            error_message STRING,
            retry_count INT64 DEFAULT 0,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY idempotency_key, processing_run_id, status
        OPTIONS(
            description="Individual processing stages with idempotency and retry support"
        )
    """,
    
    "idempotency_keys": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.idempotency_keys` (
            key STRING NOT NULL,
            step_run_id STRING NOT NULL,
            result_reference STRING,
            created_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY key
        OPTIONS(
            description="Fast idempotency lookup table for atomic deduplication"
        )
    """,
    
    "claims": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.claims` (
            id STRING NOT NULL,
            document_version_id STRING NOT NULL,
            room_id STRING,
            step_run_id STRING NOT NULL,
            claim_type STRING NOT NULL,
            value STRING NOT NULL,
            normalized_value STRING,
            confidence FLOAT64 NOT NULL,
            page_number INT64 NOT NULL,
            bbox_x FLOAT64 NOT NULL,
            bbox_y FLOAT64 NOT NULL,
            bbox_width FLOAT64 NOT NULL,
            bbox_height FLOAT64 NOT NULL,
            source_text STRING,
            user_feedback_json JSON,
            metadata JSON,
            created_at TIMESTAMP NOT NULL
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY document_version_id, room_id, claim_type
        OPTIONS(
            description="Atomic extracted data with provenance - NEVER updated or deleted"
        )
    """,
    
    "set_templates": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.set_templates` (
            id STRING NOT NULL,
            name STRING NOT NULL,
            description STRING,
            required_roles ARRAY<STRING> NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP
        )
        PARTITION BY DATE(created_at)
        CLUSTER BY id
        OPTIONS(
            description="Expected document types for Room categories"
        )
    """,
    
    "set_completeness_statuses": """
        CREATE TABLE IF NOT EXISTS `{project}.{dataset}.set_completeness_statuses` (
            id STRING NOT NULL,
            room_id STRING NOT NULL,
            set_template_id STRING NOT NULL,
            percentage_complete FLOAT64 NOT NULL,
            missing_roles ARRAY<STRING>,
            present_roles ARRAY<STRING>,
            evaluated_at TIMESTAMP NOT NULL,
            evaluator_version STRING NOT NULL
        )
        PARTITION BY DATE(evaluated_at)
        CLUSTER BY room_id, set_template_id
        OPTIONS(
            description="Room completeness evaluation results against SetTemplates"
        )
    """,
}


def create_dataset(client: bigquery.Client, project_id: str) -> None:
    """Create BigQuery dataset if it doesn't exist."""
    dataset_id = f"{project_id}.{DATASET_ID}"
    
    try:
        client.get_dataset(dataset_id)
        logger.info(f"Dataset {dataset_id} already exists")
    except NotFound:
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = "US"
        dataset.description = "Data Hero Backend MVP - All document processing data"
        client.create_dataset(dataset)
        logger.info(f"Created dataset {dataset_id}")


def create_table(client: bigquery.Client, project_id: str, table_name: str, ddl: str) -> None:
    """Create a single table using DDL."""
    formatted_ddl = ddl.format(project=project_id, dataset=DATASET_ID)
    
    try:
        query_job = client.query(formatted_ddl)
        query_job.result()
        logger.info(f"✓ Table {table_name} created/verified")
    except Exception as e:
        logger.error(f"✗ Failed to create table {table_name}: {e}")
        raise


def create_all_tables(client: bigquery.Client, project_id: str) -> None:
    """Create all tables in dependency order."""
    logger.info("Creating all tables...")
    
    for table_name, ddl in TABLE_DEFINITIONS.items():
        create_table(client, project_id, table_name, ddl)
    
    logger.info(f"✓ All {len(TABLE_DEFINITIONS)} tables created successfully")


def drop_all_tables(client: bigquery.Client, project_id: str) -> None:
    """Drop all tables in reverse dependency order."""
    logger.warning("⚠️  Dropping all tables - THIS WILL DELETE ALL DATA")
    
    for table_name in reversed(list(TABLE_DEFINITIONS.keys())):
        table_id = f"{project_id}.{DATASET_ID}.{table_name}"
        try:
            client.delete_table(table_id, not_found_ok=True)
            logger.info(f"✓ Dropped table {table_name}")
        except Exception as e:
            logger.error(f"✗ Failed to drop table {table_name}: {e}")
    
    logger.info("✓ All tables dropped")


def verify_schema(client: bigquery.Client, project_id: str) -> bool:
    """Verify all tables exist and have correct partitioning/clustering."""
    logger.info("Verifying schema...")
    
    all_valid = True
    for table_name in TABLE_DEFINITIONS.keys():
        table_id = f"{project_id}.{DATASET_ID}.{table_name}"
        try:
            table = client.get_table(table_id)
            
            has_partition = table.time_partitioning is not None
            has_clustering = table.clustering_fields is not None
            
            status = "✓" if has_partition and has_clustering else "⚠️"
            logger.info(f"{status} {table_name}: partition={has_partition}, clustering={has_clustering}")
            
            if not (has_partition and has_clustering):
                all_valid = False
                
        except NotFound:
            logger.error(f"✗ Table {table_name} not found")
            all_valid = False
    
    return all_valid


def main():
    parser = argparse.ArgumentParser(description="Create BigQuery schema for Data Hero Backend")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--drop-all", action="store_true", help="Drop all tables (DESTRUCTIVE)")
    parser.add_argument("--verify-only", action="store_true", help="Only verify schema, don't create")
    args = parser.parse_args()
    
    try:
        client = bigquery.Client(project=args.project)
        logger.info(f"Connected to project: {args.project}")
        
        if args.drop_all:
            confirm = input("⚠️  This will DELETE ALL DATA. Type 'DELETE' to confirm: ")
            if confirm != "DELETE":
                logger.info("Aborted")
                return
            drop_all_tables(client, args.project)
            return
        
        if not args.verify_only:
            create_dataset(client, args.project)
            create_all_tables(client, args.project)
        
        if verify_schema(client, args.project):
            logger.info("✓ Schema verification passed")
        else:
            logger.warning("⚠️  Schema verification found issues")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to create schema: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
