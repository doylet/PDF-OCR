"""
Dependency Injection Container

Manages service instantiation with proper dependency injection.
Makes testing easier and decouples components.
"""

import os
from app.config import get_settings

settings = get_settings()


class Container:
    """
    Dependency injection container.
    
    Lazy initialization, no GCP clients created until property accessed.
    """
    
    def __init__(self):
        if os.getenv('DISABLE_GCP_INIT') == 'true':
            raise RuntimeError("Cannot instantiate Container in test mode")
        self._bigquery_client = None
        self._bigquery = None
        self._claim_repository = None
        self._processing_run_repository = None
        self._claims = None
    
    @property
    def bigquery_client(self):
        """Get or create BigQuery client."""
        if self._bigquery_client is None:
            from google.cloud import bigquery
            self._bigquery_client = bigquery.Client(
                project=settings.GOOGLE_CLOUD_PROJECT
            )
        return self._bigquery_client
    
    @property
    def bigquery(self):
        """Get or create BigQuery service."""
        if self._bigquery is None:
            from app.services.bigquery import BigQuery
            self._bigquery = BigQuery(
                bigquery_client=self.bigquery_client,
                dataset_id=settings.BIGQUERY_DATASET
            )
        return self._bigquery
    
    @property
    def claim_repository(self):
        """Get or create Claim repository."""
        if self._claim_repository is None:
            from app.repositories.bigquery import ClaimRepository
            self._claim_repository = ClaimRepository(
                self.bigquery
            )
        return self._claim_repository
    
    @property
    def processing_run_repository(self):
        """Get or create ProcessingRun repository."""
        if self._processing_run_repository is None:
            from app.repositories.bigquery import ProcessingRunRepository
            self._processing_run_repository = ProcessingRunRepository(
                self.bigquery
            )
        return self._processing_run_repository
    
    @property
    def claims(self):
        """Get or create Claims service."""
        if self._claims is None:
            from app.services.claims import Claims
            self._claims = Claims(
                claim_repository=self.claim_repository
            )
        return self._claims
    
    def override_for_testing(
        self,
        claim_repository=None,
        processing_run_repository=None
    ):
        """Override dependencies for testing."""
        if claim_repository:
            self._claim_repository = claim_repository
        if processing_run_repository:
            self._processing_run_repository = processing_run_repository


# Global container instance
_container = None


def get_container():
    """Get the global container."""
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container():
    """Reset the container (useful for testing)."""
    global _container
    _container = None


# FastAPI dependency functions
def get_claims():
    """FastAPI dependency."""
    return get_container().claims
