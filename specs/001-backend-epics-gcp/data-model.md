# Data Model: Backend Epics BigQuery Schema

**Feature**: Data Hero Backend MVP - All Epics  
**Date**: 2025-12-17  
**Dataset**: `data_hero` (BigQuery dataset in GCP project)

## Core Design Principles

### 1. Immutability
- **Claims are append-only** - reprocessing produces new Claims linked to new StepRuns, never updates existing Claims
- **DocumentVersions are immutable** - identified by SHA-256 hash, never modified
- **State transitions are persisted** - ProcessingRuns and StepRuns record every state change with timestamps

### 2. Normalization
- All entities in separate tables with explicit foreign keys
- No nested/repeated fields (use JOINs)
- Partitioning by date for lifecycle management
- Clustering by primary query keys (document_version_id, room_id)

### 3. Traceability
- Every Claim references: DocumentVersion + StepRun + model version
- Every StepRun references: ProcessingRun + idempotency key
- Every ProcessingRun references: DocumentVersion

---

## State Machines (Authoritative Definitions)

### ProcessingRunState
```python
class ProcessingRunState(str, Enum):
    PENDING = "pending"      # Created, awaiting execution
    RUNNING = "running"      # At least one StepRun active
    COMPLETED = "completed"  # All StepRuns succeeded
    FAILED = "failed"        # At least one StepRun failed (terminal)
```

**Valid Transitions**:
- `pending` → `running`, `failed`
- `running` → `completed`, `failed`
- `completed` → (terminal state, no transitions)
- `failed` → (terminal state, no transitions)

**Invariant**: Transitions are append-only. No state may be skipped.

---

### StepRunState
```python
class StepRunState(str, Enum):
    PENDING = "pending"              # Created, awaiting execution
    RUNNING = "running"              # Currently executing
    COMPLETED = "completed"          # Succeeded
    FAILED_RETRYABLE = "failed_retryable"  # Failed but can retry
    FAILED_TERMINAL = "failed_terminal"    # Failed permanently
```

**Valid Transitions**:
- `pending` → `running`, `failed_terminal`
- `running` → `completed`, `failed_retryable`, `failed_terminal`
- `completed` → (terminal state)
- `failed_retryable` → `running` (retry allowed)
- `failed_terminal` → (terminal state)

**Invariant**: Same StepRun ID can transition `failed_retryable` → `running` → `completed` on retry. Idempotency key ensures logical idempotence even across physical retries.

---

## Entity Schemas

### 1. Room
Workspace representing a decision context (loan application, compliance review).

```sql
CREATE TABLE `data_hero.rooms` (
  id STRING NOT NULL,                      -- UUID
  name STRING NOT NULL,
  description STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP,
  status STRING NOT NULL,                  -- 'active', 'archived', 'deleted'
  set_template_id STRING,                  -- FK to set_templates (optional)
  created_by_user_id STRING,               -- User who created room
  metadata JSON,                           -- Optional user metadata
  
  PARTITION BY DATE(created_at)
  CLUSTER BY id, status
);

-- Primary query: Get room by ID
-- Secondary query: List rooms by status and user
```

**Notes**:
- `status = 'deleted'` for soft deletes (preserves audit trail)
- `set_template_id` is nullable - not all Rooms require set validation

---

### 2. Document
User-facing document entity with name and upload metadata.

```sql
CREATE TABLE `data_hero.documents` (
  id STRING NOT NULL,                      -- UUID
  name STRING NOT NULL,                    -- User-provided filename
  description STRING,
  uploaded_by_user_id STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP,
  status STRING NOT NULL,                  -- 'active', 'deleted'
  metadata JSON,                           -- Optional user metadata
  
  PARTITION BY DATE(created_at)
  CLUSTER BY id, uploaded_by_user_id
);

-- Primary query: Get document by ID
-- User-facing operations reference Document, not DocumentVersion
```

**Boundary Rule**: 
- **User-facing operations reference Document**
- **Processing operations reference DocumentVersion only**
- This prevents API confusion between mutable user metadata and immutable content

---

### 3. DocumentVersion
Immutable content identified by SHA-256 hash.

```sql
CREATE TABLE `data_hero.document_versions` (
  id STRING NOT NULL,                      -- SHA-256 hash of document bytes
  document_id STRING NOT NULL,             -- FK to documents
  file_size_bytes INT64 NOT NULL,
  gcs_uri STRING NOT NULL,                 -- gs://bucket/path
  mime_type STRING NOT NULL,               -- 'application/pdf'
  original_filename STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,           -- First upload time
  
  PARTITION BY DATE(created_at)
  CLUSTER BY id, document_id
);

-- Primary query: Get version by hash (for deduplication)
-- Secondary query: Get all versions for a document
-- NOTE: Same hash uploaded twice = same DocumentVersion, different Document records
```

**Idempotency Note**: Duplicate uploads (identical bytes) reuse same `id` (hash). New `Document` record created, but links to existing `DocumentVersion`.

---

### 4. RoomDocument
Junction table linking Rooms to DocumentVersions (many-to-many).

```sql
CREATE TABLE `data_hero.room_documents` (
  room_id STRING NOT NULL,                 -- FK to rooms
  document_version_id STRING NOT NULL,     -- FK to document_versions
  added_at TIMESTAMP NOT NULL,
  added_by_user_id STRING,
  
  PARTITION BY DATE(added_at)
  CLUSTER BY room_id, document_version_id
);

-- Primary query: Get all documents in a room
-- Secondary query: Find all rooms containing a document version
-- Composite key: (room_id, document_version_id) enforced at application level
```

---

### 5. DocumentProfile
Metadata about document quality and structure (Epic C).

```sql
CREATE TABLE `data_hero.document_profiles` (
  id STRING NOT NULL,                      -- UUID
  document_version_id STRING NOT NULL,     -- FK to document_versions (unique)
  page_count INT64 NOT NULL,
  file_size_bytes INT64 NOT NULL,
  is_born_digital BOOL,                    -- TRUE if not scanned
  quality_score FLOAT64,                   -- 0.0-1.0
  has_tables BOOL,
  table_count INT64,
  skew_detected BOOL,
  max_skew_angle_degrees FLOAT64,
  document_role STRING,                    -- 'bank_statement', 'invoice', etc. (rules-based)
  profile_artifact_gcs_uri STRING,         -- Full profile JSON in GCS
  created_at TIMESTAMP NOT NULL,
  
  PARTITION BY DATE(created_at)
  CLUSTER BY document_version_id, document_role
);

-- Primary query: Get profile for a document version
-- Secondary query: Filter documents by role or quality
-- Uniqueness: One profile per document_version_id
```

**Profiling is synchronous**: Results returned <2s (P95), stored immediately.

---

### 6. ProcessingRun
One execution of the processing pipeline for a DocumentVersion (Epic B).

```sql
CREATE TABLE `data_hero.processing_runs` (
  id STRING NOT NULL,                      -- UUID
  document_version_id STRING NOT NULL,     -- FK to document_versions
  run_type STRING NOT NULL,                -- 'profile', 'extract', 'validate'
  status STRING NOT NULL,                  -- ProcessingRunState enum
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  error_message STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP,
  
  PARTITION BY DATE(created_at)
  CLUSTER BY id, document_version_id, status
);

-- Primary query: Get processing run by ID
-- Secondary query: List runs for a document version
-- Status query: Filter by status (pending, running, completed, failed)
```

**State Machine**: See ProcessingRunState enum above. Transitions are append-only (tracked via `updated_at`).

---

### 7. StepRun
Execution of one processing stage within a ProcessingRun (Epic B).

```sql
CREATE TABLE `data_hero.step_runs` (
  id STRING NOT NULL,                      -- UUID
  processing_run_id STRING NOT NULL,       -- FK to processing_runs
  step_name STRING NOT NULL,               -- 'ocr', 'layout_analysis', 'claim_extraction'
  idempotency_key STRING NOT NULL,         -- hash(doc_version + step + model + params)
  model_version STRING NOT NULL,           -- 'document-ai-v1', 'gpt-4-turbo-2024-04-09'
  parameters_hash STRING NOT NULL,         -- hash(JSON.stringify(params))
  parameters JSON,                         -- Full parameters for replay
  status STRING NOT NULL,                  -- StepRunState enum
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  output_artifact_gcs_uri STRING,          -- GCS path to step outputs
  error_message STRING,
  retry_count INT64 DEFAULT 0,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP,
  
  PARTITION BY DATE(created_at)
  CLUSTER BY idempotency_key, processing_run_id, status
);

-- Primary query: Check idempotency key before execution
-- Secondary query: Get all steps for a processing run
-- NOTE: Clustering by idempotency_key optimizes deduplication checks
```

**Retry Semantics**: Same `id` can transition `failed_retryable` → `running` → `completed`. The `retry_count` increments on each retry.

---

### 8. IdempotencyKey
Separate table for fast idempotency lookups (Epic B, Arch Decision Q3:A).

```sql
CREATE TABLE `data_hero.idempotency_keys` (
  key STRING NOT NULL,                     -- hash(doc_version + step + model + params)
  step_run_id STRING NOT NULL,             -- FK to step_runs
  result_reference STRING,                 -- GCS path or entity ID
  created_at TIMESTAMP NOT NULL,
  expires_at TIMESTAMP,                    -- Optional TTL (e.g., 24 hours)
  
  PARTITION BY DATE(created_at)
  CLUSTER BY key
);

-- Primary query: SELECT result_reference WHERE key = @key AND expires_at > NOW()
-- Enforces uniqueness via application-level MERGE pattern (see below)
```

**Atomicity Pattern** (BigQuery does not support traditional transactions):
```sql
-- Check-and-insert pattern with MERGE
MERGE `data_hero.idempotency_keys` T
USING (SELECT @key AS key, @step_run_id AS step_run_id, @result_ref AS result_reference, CURRENT_TIMESTAMP() AS created_at) S
ON T.key = S.key
WHEN NOT MATCHED THEN
  INSERT (key, step_run_id, result_reference, created_at)
  VALUES (S.key, S.step_run_id, S.result_reference, S.created_at);
```

If key exists, MERGE does nothing. If key doesn't exist, inserts atomically. Application then queries result to determine if it was the "winner".

**Alternative**: Use `INSERT IGNORE` semantics with error handling if MERGE is unavailable in BigQuery client library.

---

### 9. Claim
Atomic unit of extracted data with provenance (Epic D).

```sql
CREATE TABLE `data_hero.claims` (
  id STRING NOT NULL,                      -- UUID
  document_version_id STRING NOT NULL,     -- FK to document_versions
  room_id STRING,                          -- FK to rooms (nullable if claim pre-dates room)
  step_run_id STRING NOT NULL,             -- FK to step_runs (which step produced this)
  
  claim_type STRING NOT NULL,              -- 'text', 'number', 'date', 'table_cell', 'custom'
  value STRING NOT NULL,                   -- Extracted value as string
  normalized_value STRING,                 -- Optional normalized form (e.g., parsed date)
  confidence FLOAT64 NOT NULL,             -- 0.0-1.0
  
  -- Source span (evidence)
  page_number INT64 NOT NULL,              -- 1-indexed
  bbox_x FLOAT64 NOT NULL,                 -- Normalized 0-1
  bbox_y FLOAT64 NOT NULL,
  bbox_width FLOAT64 NOT NULL,
  bbox_height FLOAT64 NOT NULL,
  source_text STRING,                      -- OCR text from this span
  
  created_at TIMESTAMP NOT NULL,
  
  PARTITION BY DATE(created_at)
  CLUSTER BY document_version_id, room_id, claim_type
);

-- Primary query: Get claims for a document version
-- Secondary query: Get claims for a room (all documents)
-- Filter query: Filter by claim_type, confidence threshold
```

**Immutability Rule**: 
- **Claims are NEVER updated or deleted**
- Reprocessing produces new Claims linked to new StepRuns
- "Active" claims determined by ProcessingRun selection (not mutation)
- This is critical for trust and audit trails

---

### 10. SetTemplate
Defines expected document types for a Room category (Epic E).

```sql
CREATE TABLE `data_hero.set_templates` (
  id STRING NOT NULL,                      -- UUID
  name STRING NOT NULL,                    -- 'Bank Statement Set', 'Loan Application Package'
  description STRING,
  required_roles ARRAY<STRING> NOT NULL,   -- ['bank_statement', 'ledger', 'invoice']
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP,
  
  PARTITION BY DATE(created_at)
  CLUSTER BY id
);

-- Primary query: Get template by ID
-- Secondary query: List all templates
-- NOTE: required_roles is ARRAY type in BigQuery
```

**MVP Scope**: SetTemplates are **code-defined** (seeded via migration script), not user-configurable UI.

---

### 11. SetCompletenessStatus
Evaluation result for a Room against its SetTemplate (Epic E).

```sql
CREATE TABLE `data_hero.set_completeness_statuses` (
  id STRING NOT NULL,                      -- UUID
  room_id STRING NOT NULL,                 -- FK to rooms
  set_template_id STRING NOT NULL,         -- FK to set_templates
  
  percentage_complete FLOAT64 NOT NULL,    -- 0.0-100.0
  missing_roles ARRAY<STRING>,             -- ['bank_statement', 'invoice']
  present_roles ARRAY<STRING>,             -- ['ledger']
  
  evaluated_at TIMESTAMP NOT NULL,
  evaluator_version STRING NOT NULL,       -- 'rules-v1' (for versioning classification logic)
  
  PARTITION BY DATE(evaluated_at)
  CLUSTER BY room_id, set_template_id
);

-- Primary query: Get latest completeness status for a room
-- Secondary query: Track completeness over time (historical evaluations)
```

**Evaluation Trigger**: 
- Recomputed when documents added/removed from Room
- Stored as point-in-time evaluation (not live query)
- Allows historical tracking of completeness

---

## Query Patterns & Indexes

### Common Query 1: Get All Claims for a Room with Provenance
```sql
SELECT 
  c.id AS claim_id,
  c.value,
  c.confidence,
  c.page_number,
  c.bbox_x, c.bbox_y, c.bbox_width, c.bbox_height,
  c.source_text,
  dv.id AS document_version_id,
  dv.original_filename,
  sr.step_name,
  sr.model_version,
  pr.status AS processing_status
FROM `data_hero.claims` c
JOIN `data_hero.step_runs` sr ON c.step_run_id = sr.id
JOIN `data_hero.processing_runs` pr ON sr.processing_run_id = pr.id
JOIN `data_hero.document_versions` dv ON c.document_version_id = dv.id
WHERE c.room_id = @room_id
  AND DATE(c.created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)  -- Partition pruning
  AND c.confidence >= @min_confidence
ORDER BY c.confidence DESC, c.created_at DESC
LIMIT 100;
```

**Optimization**: Clustering by `room_id` on `claims` table enables efficient filtering.

---

### Common Query 2: Check Idempotency Before Step Execution
```sql
SELECT result_reference
FROM `data_hero.idempotency_keys`
WHERE key = @idempotency_key
  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP())
LIMIT 1;
```

**Optimization**: Clustering by `key` on `idempotency_keys` table provides O(log n) lookup.

---

### Common Query 3: Get Processing Run Status
```sql
SELECT 
  pr.id AS run_id,
  pr.status AS run_status,
  pr.started_at,
  pr.completed_at,
  COUNT(sr.id) AS total_steps,
  SUM(CASE WHEN sr.status = 'completed' THEN 1 ELSE 0 END) AS completed_steps,
  SUM(CASE WHEN sr.status LIKE 'failed%' THEN 1 ELSE 0 END) AS failed_steps
FROM `data_hero.processing_runs` pr
LEFT JOIN `data_hero.step_runs` sr ON pr.id = sr.processing_run_id
WHERE pr.id = @run_id
GROUP BY pr.id, pr.status, pr.started_at, pr.completed_at;
```

**Use Case**: Async job status polling for frontend.

---

### Common Query 4: Deduplication on Upload
```sql
SELECT id, document_id, created_at
FROM `data_hero.document_versions`
WHERE id = @sha256_hash
LIMIT 1;
```

**Fast Path**: If exists, skip upload and reuse. Clustering by `id` makes this O(1).

---

## Evidence Bundle Query Pattern (Epic F)

### Deterministic Ranking (MVP)
```sql
SELECT 
  c.id,
  c.value,
  c.confidence,
  c.page_number,
  c.bbox_x, c.bbox_y, c.bbox_width, c.bbox_height,
  c.source_text,
  dv.original_filename,
  sr.model_version,
  -- Relevance score (simple keyword match count)
  (
    SELECT COUNT(*)
    FROM UNNEST(SPLIT(LOWER(c.value), ' ')) AS word
    WHERE word IN UNNEST(@query_keywords)
  ) AS relevance_score
FROM `data_hero.claims` c
JOIN `data_hero.document_versions` dv ON c.document_version_id = dv.id
JOIN `data_hero.step_runs` sr ON c.step_run_id = sr.id
WHERE c.room_id = @room_id
  AND (
    -- Keyword match in value or source_text
    LOWER(c.value) LIKE CONCAT('%', @keyword, '%')
    OR LOWER(c.source_text) LIKE CONCAT('%', @keyword, '%')
  )
  AND c.confidence >= @min_confidence
ORDER BY 
  relevance_score DESC,    -- Relevance first
  c.confidence DESC,        -- Then confidence
  c.created_at DESC         -- Then recency (tie-breaker)
LIMIT @max_results;
```

**Ranking Logic** (explicit for MVP):
- **Relevance**: TF-like keyword match count (no IDF initially)
- **Confidence**: 0.0-1.0 from extraction model
- **Recency**: Newer claims preferred in ties
- **Semantic ranking deferred**: No embeddings in MVP

---

## Migration Strategy

### Phase 1: Create Tables
```bash
# Run DDL scripts in order:
bq mk --dataset ${GCP_PROJECT}:data_hero
bq query --use_legacy_sql=false < schema/01_rooms.sql
bq query --use_legacy_sql=false < schema/02_documents.sql
# ... (all 11 tables)
```

### Phase 2: Seed SetTemplates
```sql
INSERT INTO `data_hero.set_templates` (id, name, required_roles, created_at)
VALUES 
  ('tpl-001', 'Bank Statement Set', ['bank_statement', 'ledger'], CURRENT_TIMESTAMP()),
  ('tpl-002', 'Loan Application Package', ['bank_statement', 'paystub', 'tax_return'], CURRENT_TIMESTAMP());
```

### Phase 3: Migrate Existing Data (if applicable)
- Export existing Firestore extraction jobs → BigQuery `processing_runs`
- Backfill `idempotency_keys` from StepRuns (if retroactive dedup needed)

---

## Schema Versioning

### Tracking Changes
- All schema changes recorded in `migrations/` directory
- Each migration has:
  - DDL script (e.g., `V002__add_retry_count_to_step_runs.sql`)
  - Rollback script (if applicable)
  - Migration notes (rationale, affected queries)

### Example Migration (Adding Field)
```sql
-- V002__add_retry_count_to_step_runs.sql
ALTER TABLE `data_hero.step_runs`
ADD COLUMN retry_count INT64 DEFAULT 0;
```

---

## Consistency & Integrity Rules

### Application-Level Enforcement (BigQuery Limitations)
BigQuery does not enforce:
- Foreign key constraints
- Unique constraints
- Check constraints

**Mitigation**:
1. **Validation at Service Layer**: All writes validated in Python service before BigQuery insert
2. **Periodic Audit Queries**: Detect orphaned records, invalid states
3. **Schema Comments**: Document FK relationships in table schemas

### Example Audit Query (Detect Orphaned Claims)
```sql
SELECT c.id
FROM `data_hero.claims` c
LEFT JOIN `data_hero.document_versions` dv ON c.document_version_id = dv.id
WHERE dv.id IS NULL;
```

Run weekly via Cloud Scheduler → alert if count > 0.

---

## Performance Targets

| Query Type | Target Latency | Strategy |
|-----------|---------------|----------|
| Idempotency check | <50ms | Clustering by key |
| Claims by room | <2s | Partition pruning + clustering |
| Processing run status | <500ms | Indexed by run ID |
| Evidence bundle | <3s | Keyword filtering + ranking |
| Document deduplication | <100ms | Hash lookup (clustered by ID) |

**Monitoring**: All queries logged to Cloud Logging with execution time metrics.

---

## Lifecycle & Retention

### GCS Artifacts
- **Retention**: 90 days minimum (per Constitution VII)
- **Lifecycle Policy**: Delete after 90 days unless tagged "preserve"
- **Path Pattern**: `gs://bucket/{entity_type}/{entity_id}/{artifact_name}`

### BigQuery Tables
- **Partition Retention**: Keep 90 days of data in hot storage
- **Older Data**: Archive to Cloud Storage (Parquet) for compliance
- **Deletion**: Soft delete via `status = 'deleted'` (no hard deletes)

---

## Summary

This schema provides:
- ✅ **Immutable identity** via SHA-256 hashing (Constitution I)
- ✅ **State machine-driven processing** with explicit enums (Constitution II)
- ✅ **Idempotency everywhere** with MERGE atomicity (Constitution III)
- ✅ **Claims-based evidence** with full provenance (Constitution IV)
- ✅ **Normalized BigQuery schema** with partitioning/clustering (Arch Decision Q2:A)
- ✅ **Separate idempotency_keys table** for fast lookups (Arch Decision Q3:A)
- ✅ **90-day artifact retention** for audit and replay (Constitution VII)

**Next**: API contracts in `contracts/` directory will define REST endpoints that operate on these entities.
