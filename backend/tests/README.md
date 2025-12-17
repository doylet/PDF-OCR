# Backend Tests

Test suite for the PDF-OCR backend services.

## Structure

```
tests/
├── __init__.py           # Test package initialization
├── conftest.py           # Pytest fixtures and configuration
├── test_services/        # Service layer tests
│   ├── test_bigquery_service.py
│   ├── test_claims_service.py
│   └── ...
├── test_routers/         # API endpoint tests
│   ├── test_upload.py
│   ├── test_claims.py
│   └── ...
└── test_agentic_api.py   # Agentic pipeline integration tests
```

## Running Tests

### All Tests
```bash
cd backend
pytest
```

### Specific Test File
```bash
pytest tests/test_services/test_bigquery_service.py
```

### With Coverage
```bash
pytest --cov=app --cov-report=html
```

### Verbose Output
```bash
pytest -v
```

## Test Categories

### Unit Tests
Test individual functions and methods in isolation with mocked dependencies.

Example:
```python
def test_create_claim(mock_bq_service):
    service = ClaimsService(mock_bq_service)
    claim = service.create_claim(
        document_version_id="test-doc",
        claim_type="policy_number",
        normalized_value="12345"
    )
    assert claim["claim_type"] == "policy_number"
```

### Integration Tests
Test complete workflows with real database connections (BigQuery emulator or test dataset).

Example:
```python
@pytest.mark.integration
def test_processing_run_workflow(bq_client):
    # Create document
    # Create processing run
    # Execute steps
    # Verify state transitions
```

### API Tests
Test HTTP endpoints with TestClient.

Example:
```python
def test_upload_document(client):
    response = client.post(
        "/api/upload/documents",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 201
    assert "document_id" in response.json()
```

## Fixtures

Common fixtures are defined in `conftest.py`:

- `bq_client`: BigQuery client (mocked or real)
- `app_client`: FastAPI TestClient
- `sample_pdf`: Sample PDF bytes for testing
- `mock_document_ai`: Mocked Document AI service

## TODO

- [ ] Add unit tests for all services
- [ ] Add integration tests for processing workflows
- [ ] Add API contract tests
- [ ] Set up CI/CD test automation
- [ ] Add performance benchmarks
- [ ] Mock BigQuery for faster unit tests
