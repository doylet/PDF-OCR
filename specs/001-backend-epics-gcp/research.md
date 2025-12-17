# Phase 0: Research - Backend Epics Implementation

**Feature**: Data Hero Backend MVP - All Epics  
**Date**: 2025-12-17  
**Purpose**: Document existing codebase patterns, architectural decisions, and best practices to inform implementation of 6 backend epics.

## 1. Existing Codebase Analysis

### Current Architecture Patterns

#### Service Layer Pattern
**Decision**: Extend existing service layer architecture in `backend/app/services/`

**Current Implementation**:
- `storage.py`: GCS operations (signed URLs, blob management, artifact uploads)
- `documentai.py`: Document AI client wrapper (OCR, layout analysis, region cropping)
- `firestore_service.py`: Data persistence layer (currently Firestore, **requires migration to BigQuery**)
- `llm_service.py`: LLM synthesis for agentic features

**Pattern to Follow**:
```python
class ServiceName:
    def __init__(self):
        self.client = get_client()  # Dependency injection via dependencies.py
        
    def operation_name(self, params) -> ReturnType:
        """Operation with error logging"""
        try:
            # Business logic
            logger.info(f"Operation completed: {context}")
            return result
        except Exception as e:
            logger.error(f"Operation failed: {e}")
            raise
```

**Rationale**: Established pattern provides clear separation between FastAPI routers (thin controllers) and business logic (services). Consistent error logging and dependency injection already implemented.

**Alternatives Considered**:
- Repository pattern: Rejected - Constitution VI requires direct BigQuery SQL for transparency, not abstracted ORMs
- Functional approach: Rejected - Class-based services provide better state management for GCP clients

---

#### Data Model Pattern
**Decision**: Pydantic models for API contracts, separate domain models for internal logic

**Current Implementation**:
- `models/api.py`: Request/response schemas (`ExtractionRequest`, `UploadResponse`)
- `models/document_graph.py`: Domain models with enums and dataclasses (`BBox`, `TokenType`, `RegionType`, `ExtractionMethod`, `ValidationStatus`, `JobOutcome`)

**Pattern to Follow**:
```python
# API schemas (models/api.py)
class EntityRequest(BaseModel):
    field: str
    model_config = ConfigDict(json_schema_extra={"example": {...}})

# Domain models (models/document_graph.py)
class Entity(str, Enum):
    VALUE = "value"

@dataclass
class DomainEntity:
    id: str
    field: str
```

**Rationale**: Separation allows API evolution without breaking domain logic. Pydantic provides automatic validation and OpenAPI documentation.

**Alternatives Considered**: Single model layer - Rejected because mixing API contracts with domain logic creates tight coupling

---

#### Router Pattern
**Decision**: FastAPI routers with explicit path prefixes and tags

**Current Implementation**:
- `routers/upload.py`: `/api/upload` prefix, signed URL generation
- `routers/extraction.py`: (implied from imports) Processing endpoints
- `routers/feedback.py`: (implied) HITL feedback endpoints

**Pattern to Follow**:
```python
router = APIRouter(prefix="/api/resource", tags=["resource"])
logger = logging.getLogger(__name__)

@router.post("/", response_model=ResponseSchema)
async def create_resource(request: RequestSchema):
    try:
        result = service.create(request)
        return ResponseSchema(**result)
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Rationale**: Consistent URL structure, automatic OpenAPI grouping via tags, explicit error handling.

---

### GCP Integration Patterns

#### Client Initialization
**Decision**: Singleton clients via `dependencies.py` with lazy initialization

**Current Pattern**:
```python
# dependencies.py
def get_storage_client() -> storage.Client:
    return storage.Client(project=settings.gcp_project_id)

# Service usage
class StorageService:
    def __init__(self):
        self.client = get_storage_client()
```

**Rationale**: Avoids repeated client initialization, supports dependency injection for testing.

---

#### Storage Operations
**Decision**: Signed URLs for client-side uploads, artifact retention in structured paths

**Current Pattern**:
- Upload path: `{gcs_pdf_folder}/{pdf_id}/{file_name}`
- Results path: `{gcs_results_folder}/{job_id}/result.{format}`
- Debug artifacts: `{gcs_results_folder}/{job_id}/debug/{artifact_name}`

**Best Practice for New Epics**:
- Document versions: `documents/{document_version_id}/{original_filename}` (SHA-256 as ID)
- Processing artifacts: `processing-runs/{run_id}/step-{step_name}/{artifact_name}`
- Evidence bundles: `evidence-bundles/{bundle_id}/context.json`

**Rationale**: Hierarchical paths enable lifecycle management, audit trails, and replay capability (Constitution VII).

---

#### Document AI Integration
**Decision**: Crop PDF regions to images before processing

**Current Pattern**:
```python
# 1. Convert PDF page to image (200 DPI)
# 2. Add 5% padding around normalized region coordinates
# 3. Crop to bounding box
# 4. Send PNG to Document AI processor
```

**Rationale**: Document AI performs better on focused regions than full pages. Padding handles imperfect user selections.

**Application to New Epics**: Profiling (Epic C) will process full pages, Claims extraction (Epic D) will use region cropping.

---

## 2. BigQuery Migration Strategy

### Current State: Firestore
`firestore_service.py` provides basic CRUD operations. **Constitution VI mandates BigQuery for structured data.**

### Migration Decision

**What to Migrate**:
- All entity CRUD operations (Room, Document, DocumentVersion, ProcessingRun, StepRun, Claim, etc.)
- Query operations (filtering, joins, aggregations)

**What to Preserve**:
- Service class structure (`FirestoreService` → `BigQueryService`)
- Service method signatures where possible
- Dependency injection pattern

**Implementation Approach**:
```python
# NEW: backend/app/services/bigquery_service.py
from google.cloud import bigquery
from app.config import get_settings
from app.dependencies import get_bigquery_client

class BigQueryService:
    def __init__(self):
        self.client = get_bigquery_client()
        self.project_id = settings.gcp_project_id
        self.dataset_id = "data_hero"  # Main dataset
        
    def insert_row(self, table_id: str, row: dict) -> str:
        """Insert single row, return inserted ID"""
        table_ref = f"{self.project_id}.{self.dataset_id}.{table_id}"
        errors = self.client.insert_rows_json(table_ref, [row])
        if errors:
            raise Exception(f"Insert failed: {errors}")
        return row.get("id")
    
    def query(self, sql: str, params: dict = None) -> list[dict]:
        """Execute parameterized query, return rows as dicts"""
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(k, "STRING", v)
                for k, v in (params or {}).items()
            ]
        )
        query_job = self.client.query(sql, job_config=job_config)
        return [dict(row) for row in query_job]
```

**Rationale**: Direct SQL execution (per Constitution VI), parameterized queries for safety, row-to-dict conversion for Pydantic compatibility.

**Alternatives Considered**:
- SQLAlchemy ORM: Rejected - Constitution explicitly requires "No ORMs - direct BigQuery SQL for transparency"
- Keep Firestore: Rejected - Constitutional violation (Principle VI)

---

## 3. Schema Design Patterns

### Normalized BigQuery Schema (Architectural Decision Q2:A)

**Decision**: Separate tables with explicit joins (not nested/repeated fields)

**Table Design Pattern**:
```sql
-- Pattern for all entity tables
CREATE TABLE `project.dataset.entity_name` (
  id STRING NOT NULL,                    -- UUID or SHA-256 hash
  created_at TIMESTAMP NOT NULL,         -- UTC timezone
  updated_at TIMESTAMP,                  -- NULL allowed
  status STRING NOT NULL,                -- State machine value
  -- Entity-specific fields
  PARTITION BY DATE(created_at)
  CLUSTER BY id, {primary_query_key}
);
```

**Join Pattern**:
```sql
-- Example: Get all claims for a document version
SELECT 
  c.id, c.value, c.confidence, c.source_span,
  sr.step_name, sr.model_version,
  pr.status as processing_status
FROM `data_hero.claims` c
JOIN `data_hero.step_runs` sr ON c.step_run_id = sr.id
JOIN `data_hero.processing_runs` pr ON sr.processing_run_id = pr.id
WHERE c.document_version_id = @doc_version_id
  AND DATE(c.created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)  -- Leverage partition pruning
```

**Rationale**: 
- Normalized structure enables flexible queries without restructuring
- Partitioning by `created_at` enables lifecycle policies (90-day retention)
- Clustering by ID + query keys optimizes common access patterns

**Alternatives Considered**:
- Nested/repeated fields: Rejected in Arch Decision Q2 - harder to query, harder to join
- Firestore-style collections: Rejected - violates Constitution VI GCP-native requirement

---

## 4. Idempotency Implementation

### Separate Idempotency Keys Table (Architectural Decision Q3:A)

**Decision**: Dedicated `idempotency_keys` table with composite indexes

**Schema**:
```sql
CREATE TABLE `data_hero.idempotency_keys` (
  key STRING NOT NULL,                   -- hash(doc_version + step + model + params)
  result_reference STRING,               -- GCS path or entity ID
  created_at TIMESTAMP NOT NULL,
  expires_at TIMESTAMP,                  -- Optional TTL
  PARTITION BY DATE(created_at)
  CLUSTER BY key
);

-- Unique constraint via BigQuery query-time deduplication
-- Application enforces: INSERT IGNORE or check-before-insert
```

**Usage Pattern**:
```python
def ensure_idempotent_step(doc_version_id: str, step_name: str, model_version: str, params: dict) -> Optional[str]:
    """Check for existing result, return reference if found"""
    key = hashlib.sha256(
        f"{doc_version_id}:{step_name}:{model_version}:{json.dumps(params, sort_keys=True)}".encode()
    ).hexdigest()
    
    sql = """
    SELECT result_reference 
    FROM `data_hero.idempotency_keys`
    WHERE key = @key
      AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP())
    LIMIT 1
    """
    results = bigquery_service.query(sql, {"key": key})
    return results[0]["result_reference"] if results else None
```

**Rationale**: 
- Separate table avoids polluting entity tables with technical keys
- Hash-based keys ensure deterministic collision detection
- Expiration support enables cache invalidation

**Alternatives Considered**:
- Embedded in StepRuns table: Rejected in Arch Decision Q3 - couples idempotency to processing state
- Redis/Memorystore: Rejected - persistence required for audit (Constitution VII)

---

## 5. State Machine Pattern

### ProcessingRun State Transitions (Constitution II)

**Decision**: Explicit state enum with validation

**State Model**:
```python
class ProcessingRunStatus(str, Enum):
    PENDING = "pending"      # Created, not started
    RUNNING = "running"      # At least one step active
    COMPLETED = "completed"  # All steps succeeded
    FAILED = "failed"        # At least one step failed
    CANCELLED = "cancelled"  # User-initiated stop

# Allowed transitions
VALID_TRANSITIONS = {
    "pending": ["running", "cancelled"],
    "running": ["completed", "failed", "cancelled"],
    "completed": [],  # Terminal state
    "failed": [],     # Terminal state
    "cancelled": []   # Terminal state
}
```

**Validation Pattern**:
```python
def update_processing_run_status(run_id: str, new_status: str):
    current = bigquery_service.query(
        "SELECT status FROM processing_runs WHERE id = @run_id",
        {"run_id": run_id}
    )[0]["status"]
    
    if new_status not in VALID_TRANSITIONS[current]:
        raise ValueError(f"Invalid transition: {current} -> {new_status}")
    
    bigquery_service.execute(
        "UPDATE processing_runs SET status = @new_status, updated_at = CURRENT_TIMESTAMP() WHERE id = @run_id",
        {"run_id": run_id, "new_status": new_status}
    )
```

**Rationale**: Prevents invalid state transitions, provides clear failure modes.

---

## 6. Async Processing Pattern

### Cloud Tasks for Extraction (Architectural Decision Q1:C)

**Decision**: Hybrid sync/async - profiling synchronous, extraction asynchronous

**Current Pattern** (from existing extraction queue):
```python
# Router initiates async task
@router.post("/processing-runs")
async def start_extraction(request: ExtractionRequest):
    run_id = str(uuid.uuid4())
    
    # Create pending ProcessingRun in BigQuery
    bigquery_service.insert_row("processing_runs", {
        "id": run_id,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    })
    
    # Enqueue Cloud Task
    task_client.create_task(
        parent=task_client.queue_path(project, location, queue),
        task={
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.worker_service_url}/worker/extract",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"run_id": run_id}).encode()
            }
        }
    )
    
    return {"run_id": run_id, "status": "pending"}

# Worker endpoint processes task
@router.post("/worker/extract")
async def worker_extract(payload: dict):
    run_id = payload["run_id"]
    
    # Update to running
    update_processing_run_status(run_id, "running")
    
    try:
        # Execute extraction steps
        # ...
        update_processing_run_status(run_id, "completed")
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        update_processing_run_status(run_id, "failed")
```

**Profiling Synchronous Pattern** (NEW for Epic C):
```python
@router.post("/profiles", response_model=DocumentProfileResponse)
async def profile_document(doc_version_id: str):
    """Synchronous profiling - must respond <2s (P95)"""
    # 1. Check idempotency
    existing = ensure_idempotent_step(doc_version_id, "profile", "v1", {})
    if existing:
        return load_profile(existing)
    
    # 2. Execute profiling (fast: page count, file size, basic structure)
    profile = region_analyzer_service.analyze_structure(doc_version_id)
    
    # 3. Store profile
    profile_id = bigquery_service.insert_row("document_profiles", profile)
    
    # 4. Record idempotency key
    record_idempotency_key(idempotency_key, profile_id)
    
    return DocumentProfileResponse(**profile)
```

**Rationale**: 
- Profiling is fast (<2s) and required for routing - synchronous acceptable
- Extraction is slow (OCR, LLM) - async prevents timeouts
- Cloud Tasks provides retry, dead-letter queues, observability

---

## 7. Testing Strategy

### Current Testing Infrastructure
- Framework: pytest (existing)
- Coverage target: 80%+ (documented in constitution)
- Integration tests: Use GCP emulators (planned)

### Testing Patterns for New Epics

**Unit Tests** (`tests/unit/`):
```python
# Test service logic with mocked GCP clients
def test_bigquery_service_insert(mocker):
    mock_client = mocker.patch("app.services.bigquery_service.get_bigquery_client")
    service = BigQueryService()
    
    service.insert_row("test_table", {"id": "123", "name": "test"})
    
    mock_client.return_value.insert_rows_json.assert_called_once()
```

**Integration Tests** (`tests/integration/`):
```python
# Test against BigQuery emulator
def test_processing_run_lifecycle():
    # Create run
    run_id = create_processing_run(doc_version_id="test-doc")
    
    # Verify state transitions
    update_processing_run_status(run_id, "running")
    run = get_processing_run(run_id)
    assert run["status"] == "running"
    
    # Verify invalid transition raises
    with pytest.raises(ValueError):
        update_processing_run_status(run_id, "pending")
```

**Contract Tests** (`tests/contract/`):
```python
# Test API request/response schemas
def test_create_room_contract(client):
    response = client.post("/api/rooms", json={
        "name": "Test Room",
        "document_ids": ["doc-1", "doc-2"]
    })
    
    assert response.status_code == 201
    assert "room_id" in response.json()
    assert response.json()["status"] == "active"
```

---

## 8. Configuration Management

### Environment Variables Pattern

**Current Pattern** (`config.py`):
- Pydantic Settings with validators
- Optional fields with defaults
- JSON parsing for complex types (CORS origins)

**New Configuration for Epics**:
```python
class Settings(BaseSettings):
    # Existing GCP config preserved
    
    # NEW: BigQuery configuration
    bigquery_dataset: str = "data_hero"
    bigquery_location: str = "us"
    
    # NEW: Processing configuration
    profiling_timeout_seconds: int = 2
    extraction_timeout_seconds: int = 300
    artifact_retention_days: int = 90
    
    # NEW: Idempotency configuration
    idempotency_ttl_hours: int = 24
```

**Rationale**: Centralized config enables environment-specific tuning without code changes.

---

## 9. Technology Decisions Summary

### Core Stack (Confirmed)
- **Language**: Python 3.11+ with type hints
- **Web Framework**: FastAPI
- **Validation**: Pydantic V2
- **Storage**: BigQuery (structured data), Cloud Storage (artifacts)
- **Async**: Cloud Tasks
- **OCR**: Document AI
- **Testing**: pytest with 80%+ coverage

### Key Libraries (Existing + New)
- `google-cloud-bigquery` (NEW - replaces Firestore)
- `google-cloud-storage` (existing)
- `google-cloud-tasks` (existing)
- `google-cloud-documentai` (existing)
- `fastapi` (existing)
- `pydantic` (existing)
- `pytest` (existing)
- `pypdf` (existing - PDF manipulation)
- `pdf2image` (existing - PDF rendering)

### Deployment (Unchanged)
- Platform: Cloud Run (Linux containers)
- CI/CD: Cloud Build with `cloudbuild.yaml`
- Deployment script: `deploy.sh`

---

## 10. Open Questions Resolved

### Q1: Processing Model (Architectural Decision Q1)
**Answer**: C - Hybrid (sync profiling, async extraction via Cloud Tasks)

### Q2: BigQuery Schema Design (Architectural Decision Q2)
**Answer**: A - Normalized schema with separate tables and joins

### Q3: Idempotency Storage (Architectural Decision Q3)
**Answer**: A - Separate `idempotency_keys` table with composite indexes

---

## 11. Implementation Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Firestore → BigQuery migration breaks existing features | Medium | High | Incremental migration: New entities first, gradual cutover with dual-write period |
| BigQuery query performance at scale | Low | Medium | Follow partitioning/clustering strategy, monitor query costs |
| Cloud Tasks retry storms on failures | Low | Medium | Implement exponential backoff, dead-letter queue monitoring |
| Idempotency key collisions | Very Low | High | Use SHA-256 (collision probability ~2^-256), add created_at to key if needed |

---

## 12. Next Steps (Phase 1)

Based on this research, Phase 1 will produce:

1. **data-model.md**: BigQuery schema DDL for 10 entities (Room, Document, DocumentVersion, DocumentProfile, ProcessingRun, StepRun, Claim, SetTemplate, SetCompletenessStatus, EvidenceBundle)

2. **contracts/**: OpenAPI specifications for 6 new routers:
   - `rooms.yaml` (POST /rooms, GET /rooms/{id}, POST /rooms/{id}/documents)
   - `profiles.yaml` (GET /profiles/{doc_version_id})
   - `claims.yaml` (GET /claims?document_version_id=...)
   - `evidence-bundles.yaml` (POST /evidence-bundles)
   - `documents.yaml` (POST /documents - Epic A versioning)
   - `processing-runs.yaml` (updates to existing extraction endpoints)

3. **quickstart.md**: Setup steps for local development (BigQuery emulator, env vars, test data)

**Confidence Level**: High - All unknowns resolved, existing patterns identified, constitutional compliance verified.
