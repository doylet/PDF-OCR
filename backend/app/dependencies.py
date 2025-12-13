from google.cloud import storage
from google.cloud import firestore
from google.cloud import documentai_v1 as documentai
from google.cloud import tasks_v2
from app.config import get_settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class GCPClients:
    """Singleton wrapper for GCP client instances"""
    
    _storage_client: Optional[storage.Client] = None
    _firestore_client: Optional[firestore.Client] = None
    _documentai_client: Optional[documentai.DocumentProcessorServiceClient] = None
    _tasks_client: Optional[tasks_v2.CloudTasksClient] = None
    
    @classmethod
    def get_storage_client(cls) -> storage.Client:
        if cls._storage_client is None:
            cls._storage_client = storage.Client(project=settings.gcp_project_id)
            logger.info("Initialized Cloud Storage client")
        return cls._storage_client
    
    @classmethod
    def get_firestore_client(cls) -> firestore.Client:
        if cls._firestore_client is None:
            cls._firestore_client = firestore.Client(project=settings.gcp_project_id)
            logger.info("Initialized Firestore client")
        return cls._firestore_client
    
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


def get_documentai_client() -> documentai.DocumentProcessorServiceClient:
    return GCPClients.get_documentai_client()


def get_tasks_client() -> tasks_v2.CloudTasksClient:
    return GCPClients.get_tasks_client()
