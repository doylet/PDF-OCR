from google.cloud import storage
from google.cloud import firestore
from google.cloud import bigquery
from google.cloud import documentai_v1 as documentai
from google.cloud import tasks_v2
from google.oauth2 import service_account
from app.config import get_settings
from typing import Optional
import logging
import os
import json

logger = logging.getLogger(__name__)
settings = get_settings()


class GCPClients:
    """Singleton wrapper for GCP client instances"""
    
    _storage_client: Optional[storage.Client] = None
    _firestore_client: Optional[firestore.Client] = None
    _bigquery_client: Optional[bigquery.Client] = None
    _documentai_client: Optional[documentai.DocumentProcessorServiceClient] = None
    _tasks_client: Optional[tasks_v2.CloudTasksClient] = None
    _credentials: Optional[service_account.Credentials] = None
    
    @classmethod
    def get_credentials(cls) -> Optional[service_account.Credentials]:
        """Get service account credentials from mounted secret if available"""
        if cls._credentials is None:
            key_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '/secrets/service-account-key.json')
            if os.path.exists(key_path):
                try:
                    cls._credentials = service_account.Credentials.from_service_account_file(key_path)
                    logger.info(f"Loaded service account credentials from {key_path}")
                except Exception as e:
                    logger.warning(f"Failed to load service account key from {key_path}: {e}")
        return cls._credentials
    
    @classmethod
    def get_storage_client(cls) -> storage.Client:
        if cls._storage_client is None:
            credentials = cls.get_credentials()
            if credentials:
                cls._storage_client = storage.Client(project=settings.gcp_project_id, credentials=credentials)
                logger.info("Initialized Cloud Storage client with service account credentials")
            else:
                cls._storage_client = storage.Client(project=settings.gcp_project_id)
                logger.info("Initialized Cloud Storage client with default credentials")
        return cls._storage_client
    
    @classmethod
    def get_firestore_client(cls) -> firestore.Client:
        if cls._firestore_client is None:
            cls._firestore_client = firestore.Client(project=settings.gcp_project_id)
            logger.info("Initialized Firestore client")
        return cls._firestore_client
    
    @classmethod
    def get_bigquery_client(cls) -> bigquery.Client:
        if cls._bigquery_client is None:
            credentials = cls.get_credentials()
            if credentials:
                cls._bigquery_client = bigquery.Client(project=settings.gcp_project_id, credentials=credentials)
                logger.info("Initialized BigQuery client with service account credentials")
            else:
                cls._bigquery_client = bigquery.Client(project=settings.gcp_project_id)
                logger.info("Initialized BigQuery client with default credentials")
        return cls._bigquery_client
    
    @classmethod
    def get_documentai_client(cls) -> documentai.DocumentProcessorServiceClient:
        if cls._documentai_client is None:
            cls._documentai_client = documentai.DocumentProcessorServiceClient()
            logger.info("Initialized Document AI client")
        return cls._documentai_client
    
    @classmethod
    def get_tasks_client(cls) -> tasks_v2.CloudTasksClient:
        if cls._tasks_client is None:
            cls._tasks_client = tasks_v2.CloudTasksClient()
            logger.info("Initialized Cloud Tasks client")
        return cls._tasks_client


def get_storage_client() -> storage.Client:
    return GCPClients.get_storage_client()


def get_firestore_client() -> firestore.Client:
    return GCPClients.get_firestore_client()


def get_bigquery_client() -> bigquery.Client:
    return GCPClients.get_bigquery_client()


def get_documentai_client() -> documentai.DocumentProcessorServiceClient:
    return GCPClients.get_documentai_client()


def get_tasks_client() -> tasks_v2.CloudTasksClient:
    return GCPClients.get_tasks_client()


def get_firestore_service():
    """Dependency for Firestore"""
    from app.services.firestore import Firestore
    return Firestore(get_firestore_client())


def get_bigquery_service():
    """Dependency for BigQuery"""
    from app.services.bigquery import BigQuery
    return BigQuery(get_bigquery_client())
