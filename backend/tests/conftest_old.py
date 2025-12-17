"""
Pytest Configuration and Fixtures

Shared test fixtures and configuration for the entire test suite.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock
from google.cloud import bigquery

from app.main import app
from app.services.bigquery_service import BigQueryService


@pytest.fixture
def app_client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_bq_client():
    """Mock BigQuery client."""
    mock = Mock(spec=bigquery.Client)
    mock.project = "test-project"
    return mock


@pytest.fixture
def mock_bq_service(mock_bq_client):
    """Mock BigQueryService."""
    return BigQueryService(mock_bq_client, dataset_id="test_dataset")


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF file bytes for testing."""
    # Minimal valid PDF
    return b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000052 00000 n
0000000101 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
190
%%EOF"""


@pytest.fixture
def sample_document_data():
    """Sample document data for testing."""
    return {
        "id": "test-doc-123",
        "name": "test.pdf",
        "uploaded_by_user_id": "user-456",
        "status": "active"
    }


@pytest.fixture
def sample_claim_data():
    """Sample claim data for testing."""
    return {
        "id": "claim-789",
        "document_version_id": "doc-version-123",
        "claim_type": "policy_number",
        "normalized_value": "POL-12345",
        "confidence": 0.95,
        "step_run_id": "step-run-456"
    }


# Test markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (slower, require real services)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "agentic: marks tests for agentic AI pipeline"
    )
