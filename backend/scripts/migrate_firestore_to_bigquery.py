#!/usr/bin/env python3
"""
Migrate feedback and job data from Firestore to BigQuery.

Creates feedback and jobs tables in BigQuery, then migrates existing Firestore data.

Usage:
    python scripts/migrate_firestore_to_bigquery.py --project PROJECT_ID [--dry-run]
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

from google.cloud import bigquery, firestore
from google.cloud.exceptions import NotFound

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATASET_ID = "data_hero"

FEEDBACK_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.feedback` (
    id STRING NOT NULL,
    job_id STRING NOT NULL,
    corrections JSON NOT NULL,
    corrections_count INT64 NOT NULL,
    user_id STRING,
    session_id STRING,
    timestamp TIMESTAMP NOT NULL,
    status STRING NOT NULL,
    created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY job_id, user_id, status
OPTIONS(
    description="User feedback on region detection corrections from Firestore migration"
)
"""

JOBS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.jobs` (
    job_id STRING NOT NULL,
    pdf_id STRING NOT NULL,
    status STRING NOT NULL,
    regions_count INT64 NOT NULL,
    output_format STRING,
    result_url STRING,
    error_message STRING,
    debug_graph_url STRING,
    has_feedback BOOL DEFAULT FALSE,
    feedback_count INT64 DEFAULT 0,
    last_feedback_at TIMESTAMP,
    request_data JSON,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY job_id, status, pdf_id
OPTIONS(
    description="Extraction job metadata from Firestore migration"
)
"""


def create_migration_tables(client: bigquery.Client, project_id: str) -> None:
    """Create BigQuery tables for migrated Firestore data."""
    logger.info("Creating migration tables...")
    
    tables = {
        "feedback": FEEDBACK_TABLE_DDL,
        "jobs": JOBS_TABLE_DDL
    }
    
    for table_name, ddl in tables.items():
        formatted_ddl = ddl.format(project=project_id, dataset=DATASET_ID)
        try:
            query_job = client.query(formatted_ddl)
            query_job.result()
            logger.info(f"✓ Table {table_name} created/verified")
        except Exception as e:
            logger.error(f"✗ Failed to create table {table_name}: {e}")
            raise


def migrate_feedback_data(
    firestore_db: firestore.Client,
    bq_client: bigquery.Client,
    project_id: str,
    dry_run: bool = False
) -> int:
    """Migrate feedback documents from Firestore to BigQuery."""
    logger.info("Migrating feedback data...")
    
    table_id = f"{project_id}.{DATASET_ID}.feedback"
    
    feedback_docs = firestore_db.collection("region_feedback").stream()
    
    rows_to_insert = []
    count = 0
    
    for doc in feedback_docs:
        data = doc.to_dict()
        count += 1
        
        try:
            timestamp = data.get("timestamp")
            if isinstance(timestamp, str):
                timestamp_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                timestamp_dt = timestamp or datetime.utcnow()
            
            row = {
                "id": doc.id,
                "job_id": data.get("job_id", ""),
                "corrections": data.get("corrections", []),
                "corrections_count": data.get("corrections_count", 0),
                "user_id": data.get("user_id"),
                "session_id": data.get("session_id"),
                "timestamp": timestamp_dt,
                "status": data.get("status", "pending_analysis"),
                "created_at": timestamp_dt
            }
            
            rows_to_insert.append(row)
            
            if len(rows_to_insert) >= 500:
                if not dry_run:
                    errors = bq_client.insert_rows_json(table_id, rows_to_insert)
                    if errors:
                        logger.error(f"Errors inserting batch: {errors}")
                else:
                    logger.info(f"[DRY RUN] Would insert {len(rows_to_insert)} feedback rows")
                rows_to_insert = []
                
        except Exception as e:
            logger.warning(f"Failed to process feedback doc {doc.id}: {e}")
            continue
    
    if rows_to_insert:
        if not dry_run:
            errors = bq_client.insert_rows_json(table_id, rows_to_insert)
            if errors:
                logger.error(f"Errors inserting final batch: {errors}")
        else:
            logger.info(f"[DRY RUN] Would insert {len(rows_to_insert)} feedback rows")
    
    logger.info(f"✓ Migrated {count} feedback documents")
    return count


def migrate_jobs_data(
    firestore_db: firestore.Client,
    bq_client: bigquery.Client,
    project_id: str,
    collection_name: str,
    dry_run: bool = False
) -> int:
    """Migrate job documents from Firestore to BigQuery."""
    logger.info(f"Migrating jobs data from collection: {collection_name}...")
    
    table_id = f"{project_id}.{DATASET_ID}.jobs"
    
    job_docs = firestore_db.collection(collection_name).stream()
    
    rows_to_insert = []
    count = 0
    
    for doc in job_docs:
        data = doc.to_dict()
        count += 1
        
        try:
            created_at = data.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            elif created_at is None:
                created_at = datetime.utcnow()
            
            updated_at = data.get("updated_at")
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            elif updated_at is None:
                updated_at = created_at
            
            last_feedback_at = data.get("last_feedback_at")
            if isinstance(last_feedback_at, str):
                last_feedback_at = datetime.fromisoformat(last_feedback_at.replace('Z', '+00:00'))
            
            row = {
                "job_id": data.get("job_id", doc.id),
                "pdf_id": data.get("pdf_id", ""),
                "status": data.get("status", "unknown"),
                "regions_count": data.get("regions_count", 0),
                "output_format": data.get("output_format", "csv"),
                "result_url": data.get("result_url"),
                "error_message": data.get("error_message"),
                "debug_graph_url": data.get("debug_graph_url"),
                "has_feedback": data.get("has_feedback", False),
                "feedback_count": data.get("feedback_count", 0),
                "last_feedback_at": last_feedback_at,
                "request_data": data.get("request_data"),
                "created_at": created_at,
                "updated_at": updated_at
            }
            
            rows_to_insert.append(row)
            
            if len(rows_to_insert) >= 500:
                if not dry_run:
                    errors = bq_client.insert_rows_json(table_id, rows_to_insert)
                    if errors:
                        logger.error(f"Errors inserting batch: {errors}")
                else:
                    logger.info(f"[DRY RUN] Would insert {len(rows_to_insert)} job rows")
                rows_to_insert = []
                
        except Exception as e:
            logger.warning(f"Failed to process job doc {doc.id}: {e}")
            continue
    
    if rows_to_insert:
        if not dry_run:
            errors = bq_client.insert_rows_json(table_id, rows_to_insert)
            if errors:
                logger.error(f"Errors inserting final batch: {errors}")
        else:
            logger.info(f"[DRY RUN] Would insert {len(rows_to_insert)} job rows")
    
    logger.info(f"✓ Migrated {count} job documents")
    return count


def verify_migration(
    bq_client: bigquery.Client,
    project_id: str,
    expected_counts: Dict[str, int]
) -> bool:
    """Verify migrated data counts in BigQuery."""
    logger.info("Verifying migration...")
    
    all_valid = True
    
    for table_name, expected_count in expected_counts.items():
        query = f"SELECT COUNT(*) as count FROM `{project_id}.{DATASET_ID}.{table_name}`"
        try:
            result = bq_client.query(query).result()
            actual_count = list(result)[0]["count"]
            
            if actual_count == expected_count:
                logger.info(f"✓ {table_name}: {actual_count} rows (matches Firestore)")
            else:
                logger.warning(f"⚠️  {table_name}: {actual_count} rows (expected {expected_count})")
                all_valid = False
                
        except Exception as e:
            logger.error(f"✗ Failed to verify {table_name}: {e}")
            all_valid = False
    
    return all_valid


def main():
    parser = argparse.ArgumentParser(description="Migrate Firestore data to BigQuery")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--collection", default="extraction_jobs", help="Firestore jobs collection name")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without writing")
    args = parser.parse_args()
    
    try:
        bq_client = bigquery.Client(project=args.project)
        firestore_db = firestore.Client(project=args.project)
        
        logger.info(f"Connected to project: {args.project}")
        
        if not args.dry_run:
            create_migration_tables(bq_client, args.project)
        else:
            logger.info("[DRY RUN] Skipping table creation")
        
        feedback_count = migrate_feedback_data(
            firestore_db, bq_client, args.project, dry_run=args.dry_run
        )
        
        jobs_count = migrate_jobs_data(
            firestore_db, bq_client, args.project, args.collection, dry_run=args.dry_run
        )
        
        if not args.dry_run:
            expected_counts = {
                "feedback": feedback_count,
                "jobs": jobs_count
            }
            if verify_migration(bq_client, args.project, expected_counts):
                logger.info("✓ Migration verification passed")
            else:
                logger.warning("⚠️  Migration verification found mismatches")
        else:
            logger.info(f"[DRY RUN] Would migrate {feedback_count} feedback + {jobs_count} jobs")
        
        logger.info("✓ Migration complete")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
