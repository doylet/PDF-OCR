"""
Pytest configuration - simplified without GCP dependencies.
"""

import pytest
import os
from unittest.mock import MagicMock

os.environ["TESTING"] = "true"


@pytest.fixture
def sample_document_data():
    """Sample document data."""
    return {
        "id": "doc-123",
        "name": "test.pdf",
        "status": "active",
        "gcs_uri": "gs://bucket/test.pdf",
        "created_at": "2025-12-17T10:00:00+00:00"
    }


@pytest.fixture
def sample_claim_data():
    """Sample claim data."""
    return {
        "id": "claim-456",
        "document_id": "doc-123",
        "claim_type": "diagnosis",
        "claim_text": "Patient has Type 2 Diabetes",
        "confidence": 0.92,
        "page_number": 1,
        "created_at": "2025-12-17T10:00:00+00:00"
    }


@pytest.fixture
def sample_processing_run():
    """Sample processing run data."""
    return {
        "id": "run-789",
        "document_id": "doc-123",
        "status": "processing",
        "pipeline_version": "2.0.0",
        "agents_used": ["layout", "table"],
        "started_at": "2025-12-17T10:00:00+00:00"
    }


@pytest.fixture
def mock_bq_service():
    """Mock BigQueryService."""
    service = MagicMock()
    service.insert_row.return_value = "generated-id-123"
    service.get_by_id.return_value = None
    service.query.return_value = []
    service.update_row.return_value = True
    return service
