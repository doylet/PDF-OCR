# Backend Architecture

## Overview

This backend follows Clean Architecture principles with clear separation of concerns across layers:

```
domain/        → Pure business logic, domain models
models/        → State machines, schemas
repositories/  → Data access abstractions
services/      → Business logic orchestration
routers/       → API endpoints, request/response handling
```

## Key Architectural Decisions

### 1. State Machines (Constitution II)

**Decision**: Centralize state machine definitions in `app/models/state_machines.py`

**Rationale**: 
- Single source of truth for state transitions
- Validation logic co-located with state definitions
- Prevents inconsistencies across codebase

**Implementation**:
- `ProcessingRunState`: pending → running → completed/failed
- `StepRunState`: pending → running → completed/failed_retryable/failed_terminal
- Validation functions: `validate_processing_run_transition()`, `validate_step_run_transition()`
- Logging: `log_state_transition()` for audit trail

**Usage**:
```python
from app.models.state_machines import ProcessingRunState, validate_processing_run_transition

# Validate before transitioning
validate_processing_run_transition(current_state, new_state)

# Check if terminal
if ProcessingRunState.is_terminal(run.status):
    # No further transitions allowed
```

---

### 2. Repository Pattern (Partial Implementation)

**Decision**: Hybrid approach - repositories for complex entities, direct BigQuery service for simple CRUD

**Rationale**:
- Balance clean architecture with pragmatism
- Full repositories for entities with complex querying (Claims, ProcessingRuns)
- Direct BigQuery service acceptable for simple entities (Rooms, DocumentProfiles)

**Implementation Status**:
- ✅ **ClaimRepository** (repositories/bigquery.py): Full implementation with specialized queries
- ✅ **ProcessingRunRepository** (repositories/bigquery.py): Full implementation with status tracking
- ⚠️ **RoomRepository**: Interface exists, service layer uses BigQuery directly
- ⚠️ **DocumentProfileRepository**: Interface exists, service layer uses BigQuery directly
- ⚠️ **EvidenceBundleRepository**: Interface exists, bundles are ephemeral (see below)

**When to Use Repositories**:
- Complex querying logic (joins, aggregations)
- Multiple ways to retrieve same entity
- Business logic in data access (validation, computed fields)
- Need to mock data access in tests

**When to Use BigQuery Service Directly**:
- Simple CRUD operations
- Single lookup patterns
- No business logic in data access

---

### 3. Evidence Bundles (Ephemeral Results)

**Decision**: Evidence bundles are query results, not persisted entities

**Rationale**:
- Evidence bundles are search results, not first-class entities
- Always computed fresh from current claims data
- No stale data issues
- Reduced storage costs

**Implementation**:
- `evidence.py` service constructs bundles on-the-fly
- No `evidence_bundles` BigQuery table
- Bundle metadata can be cached if needed (future optimization)

**Usage**:
```python
# Search claims and build bundle
bundle = evidence_service.search_evidence(
    room_id="room-123",
    query="loan amount",
    min_confidence=0.8
)
# Bundle is ephemeral, not stored
```

---

### 4. SetTemplate Management (Code-Defined)

**Decision**: SetTemplates are code-defined constants for MVP

**Rationale**:
- MVP scope: small, known set of document types
- No UI for template management yet
- Easier deployment and versioning

**Implementation**:
- `set_templates` BigQuery table exists for storage
- Templates seeded via migration script
- Service layer reads from BigQuery

**Future**: User-configurable templates via admin UI

---

### 5. Domain Models (Selective Implementation)

**Decision**: Domain models for entities with business logic, dictionaries for simple DTOs

**Rationale**:
- Type safety where it matters (validation, state transitions)
- Avoid boilerplate for simple data transfer

**Implemented Domain Models**:
- ✅ **Claim** (dataclass): Validation in `__post_init__`, confidence checks, high_confidence methods
- ✅ **ProcessingRun** (dataclass): State transition validation, terminal state checks
- ✅ **Room** (dataclass): Active status checks
- ✅ **BoundingBox** (dataclass): Overlap detection

**Simple DTOs** (no domain model):
- DocumentVersion (simple CRUD, no business logic)
- StepRun (handled by service layer with state machine)
- SetTemplate (code-defined, minimal logic)
- SetCompletenessStatus (computed result, no behavior)

---

### 6. Error Handling

**Decision**: Standard FastAPI HTTPException with descriptive messages

**Rationale**:
- Consistent with FastAPI ecosystem
- Built-in HTTP status code mapping
- Clear error messages for debugging

**Pattern**:
```python
from fastapi import HTTPException

if not entity:
    raise HTTPException(
        status_code=404,
        detail=f"Entity {entity_id} not found"
    )
```

**Common Status Codes**:
- `400`: Bad request (validation errors)
- `401`: Unauthorized (task queue auth)
- `404`: Not found
- `500`: Internal server error

**Future Enhancement**: Custom error codes (e.g., `APP-001`) for categorization

---

### 7. Idempotency (Constitution IV)

**Decision**: Hash-based idempotency with atomic check-and-insert

**Rationale**:
- Prevent duplicate processing
- Support retries without side effects
- BigQuery-native atomicity via MERGE

**Implementation**:
- Idempotency key = hash(document_version + step + model + params)
- `idempotency_keys` table for fast lookups
- `check_and_insert_key()` ensures atomicity

**Usage**:
```python
idempotency_key = compute_key_hash(
    document_version_id=doc_id,
    step_name="ocr",
    model_version="v1",
    parameters={"lang": "en"}
)

cached_result = check_and_insert_key(idempotency_key, step_run_id)
if cached_result:
    return cached_result  # Skip processing
```

---

## Project Structure

```
backend/
├── app/
│   ├── domain/              # Pure business logic
│   │   ├── models.py        # Domain models (Claim, ProcessingRun, Room)
│   │   └── __init__.py      # Exports
│   ├── models/              # Schemas and state machines
│   │   ├── api.py           # API request/response models
│   │   └── state_machines.py # State definitions (AUTHORITATIVE)
│   ├── repositories/        # Data access layer
│   │   ├── interfaces.py    # Repository interfaces
│   │   └── bigquery.py      # BigQuery implementations
│   ├── services/            # Business logic orchestration
│   │   ├── bigquery.py      # Base BigQuery operations
│   │   ├── claims.py        # Claims business logic
│   │   ├── processing_run.py # ProcessingRun lifecycle
│   │   ├── step_run.py      # StepRun with idempotency
│   │   ├── room.py          # Room management
│   │   ├── evidence.py      # Evidence search
│   │   ├── idempotency.py   # Idempotency checking
│   │   └── ...              # Other services
│   └── routers/             # API endpoints
│       ├── claims.py        # Claims API
│       ├── processing_runs.py # ProcessingRuns API
│       ├── rooms.py         # Rooms API
│       └── ...              # Other routers
├── scripts/
│   ├── create_bigquery_schema.py # Schema creation
│   └── migrate_firestore_to_bigquery.py # Migration
└── main.py                  # FastAPI app
```

---

## Constitution Compliance

All architectural decisions align with project constitution (specs/001-backend-epics-gcp/plan.md):

1. **Defensible Lineage**: Every claim links to DocumentVersion, StepRun, model version
2. **State Machine-Driven**: ProcessingRunState and StepRunState enforce valid transitions
3. **Immutability**: Documents, claims never mutated; reprocessing creates new records
4. **Idempotent Retry**: Hash-based deduplication prevents duplicate processing
5. **Explicit Provenance**: All artifacts tagged with source, timestamp, version
6. **Queryable Transparency**: BigQuery enables ad-hoc analysis of full pipeline
7. **Testable Results**: State machines, repositories, services all unit-testable

---

## Testing Strategy

### Unit Tests
- Domain models: Validation logic, state transitions
- State machines: Valid/invalid transition scenarios
- Repositories: CRUD operations (mock BigQuery)
- Services: Business logic (mock repositories)

### Integration Tests
- API endpoints: Request/response validation
- BigQuery operations: Schema compliance
- State transitions: End-to-end pipeline

### Performance Tests
- Claims queries: Sub-2s for 1000+ documents (SC-005)
- Processing: <5min for 100-page PDFs (SC-004)
- Concurrent uploads: 100 uploads, <30s queue delay (SC-009)

---

## Future Enhancements

1. **Complete Repository Pattern**: Implement remaining repositories if complex querying emerges
2. **Custom Error Codes**: Add app-specific codes for better categorization
3. **Domain Models**: Add DocumentVersion, StepRun models for type safety
4. **Evidence Bundle Caching**: Cache bundle metadata for performance
5. **SetTemplate UI**: Admin interface for template management
6. **Semantic Search**: Embeddings for evidence queries (beyond keyword matching)

---

## References

- **Specification**: specs/001-backend-epics-gcp/spec.md
- **Data Model**: specs/001-backend-epics-gcp/data-model.md
- **Implementation Plan**: specs/001-backend-epics-gcp/plan.md
- **Gap Analysis**: specs/001-backend-epics-gcp/gap-analysis.md
- **Verification**: specs/001-backend-epics-gcp/verification-summary.md
