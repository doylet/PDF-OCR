# Service Layer Refactoring

## Problem Statement

Our current services have several architectural issues:
1. **Tight coupling to BigQuery** - Services directly instantiate `bigquery.Client` and call BigQuery-specific methods
2. **Mixed concerns** - Business logic, data access, and validation mixed together
3. **Hard to test** - Cannot easily mock storage or swap implementations
4. **No abstraction** - Services know about BigQuery table schemas and SQL
5. **Inconsistent patterns** - Some services use `BigQueryService`, others use raw `bigquery.Client`

## Solution: Clean Architecture

We implement a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────┐
│      API Layer (routers/)           │
│  - HTTP endpoints                   │
│  - Request/Response models          │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Service Layer (services/)         │
│  - Business logic                   │
│  - Orchestration                    │
│  - Validation                       │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Repository Layer (repositories/)   │
│  - Data access abstraction          │
│  - Storage implementation           │
│  - Query building                   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Domain Layer (domain/)           │
│  - Business entities                │
│  - Domain logic                     │
│  - Value objects                    │
└─────────────────────────────────────┘
```

## Key Improvements

### 1. Repository Pattern

**Before:**
```python
class ClaimsService:
    def __init__(self, bq_service):
        self.bq_service = bq_service
    
    def create_claim(self, ...):
        # Directly calling BigQuery
        self.bq_service.insert_row("claims", row_data)
```

**After:**
```python
class ClaimsService:
    def __init__(self, claim_repository: IClaimRepository):
        self.repo = claim_repository
    
    def create_claim(self, ...):
        # Works with any repository implementation
        self.repo.create(claim_data)
```

**Benefits:**
- Can swap BigQuery for Firestore, PostgreSQL, or in-memory storage
- Easy to mock for testing
- Storage logic isolated in one place

### 2. Domain Models

**Before:**
```python
# Mixed concerns - validation, storage format, business logic all mixed
claim_row = {
    "id": claim_id,
    "confidence": confidence,  # No validation
    "bbox_x": bbox["x"],  # Storage format leaked
    # ...
}
```

**After:**
```python
@dataclass
class Claim:
    confidence: float
    bbox: BoundingBox
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Invalid confidence")
    
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.9
```

**Benefits:**
- Self-validating
- Business logic lives with the entity
- Clear data contracts
- Type safety

### 3. Dependency Injection

**Before:**
```python
# Hard-coded dependencies
service = ClaimsService(BigQueryService(bigquery.Client()))
```

**After:**
```python
# Injected dependencies
container = get_container()
service = container.claims_service

# For testing:
mock_repo = MockClaimRepository()
service = ClaimsService(mock_repo)
```

**Benefits:**
- Testable without GCP
- Configurable for different environments
- Clear dependency graph

## Migration Path

### Phase 1: Add Abstractions (Current)
- ✅ Create repository interfaces
- ✅ Create domain models
- ✅ Create BigQuery implementations
- ✅ Create refactored service example

### Phase 2: Gradual Migration
- Replace `claims_service.py` with `claims_service_refactored.py`
- Update routers to use dependency injection
- Refactor other services one by one

### Phase 3: Remove Old Code
- Delete old service implementations
- Remove direct BigQuery dependencies from services
- Clean up imports

## Testing Strategy

### Before (Hard to Test)
```python
# Requires real BigQuery connection
def test_create_claim():
    bq_client = bigquery.Client()  # Hangs/fails without credentials
    bq_service = BigQueryService(bq_client)
    service = ClaimsService(bq_service)
    # ...
```

### After (Easy to Test)
```python
# Pure unit test with mocks
def test_create_claim():
    mock_repo = Mock(spec=IClaimRepository)
    service = ClaimsService(mock_repo)
    
    claim = service.create_claim(...)
    
    assert claim.confidence == 0.92
    mock_repo.create.assert_called_once()
```

## Example: Refactored Claims Service

See [services/claims_service_refactored.py](../app/services/claims_service_refactored.py) for a complete example.

Key differences:
- Takes `IClaimRepository` instead of `BigQueryService`
- Returns domain models (`Claim`) instead of dicts
- Business logic (filtering, aggregation) in service
- No BigQuery-specific code

## Benefits Summary

1. **Testability**: Mock repositories instead of GCP services
2. **Flexibility**: Swap storage without changing business logic
3. **Maintainability**: Clear separation of concerns
4. **Type Safety**: Domain models with validation
5. **Reusability**: Repositories can be shared across services
6. **Team Productivity**: Developers can work on layers independently

## Next Steps

1. Review repository interfaces and domain models
2. Test refactored claims service
3. Decide on migration timeline
4. Refactor remaining services (processing_run, room, evidence, etc.)
5. Update integration tests
