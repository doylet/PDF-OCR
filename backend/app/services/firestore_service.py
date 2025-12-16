from google.cloud import firestore
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class FirestoreService:
    def __init__(self, firestore_client: firestore.Client):
        self.db = firestore_client
        logger.info("FirestoreService initialized")
    
    @staticmethod
    def increment(value: int):
        """Helper for Firestore field increment"""
        return firestore.Increment(value)
    
    class Query:
        """Expose Firestore query directions"""
        DESCENDING = firestore.Query.DESCENDING
        ASCENDING = firestore.Query.ASCENDING
