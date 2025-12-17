# Data Hero Backend API Demo

This demo showcases the newly implemented Epic A (Document Versioning) and Epic B (ProcessingRuns API) functionality.

## Prerequisites

1. **Start BigQuery Emulator** (for local testing):
   ```bash
   # Install BigQuery emulator
   pip install bigquery-emulator
   
   # Start emulator
   bigquery-emulator --project=your-project --dataset=data_hero
   ```

2. **Set Environment Variables**:
   ```bash
   export GOOGLE_CLOUD_PROJECT="your-project-id"
   export GCS_BUCKET="your-bucket-name"
   export BIGQUERY_DATASET="data_hero"
   export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
   ```

3. **Initialize BigQuery Schema**:
   ```bash
   cd /Users/thomasdoyle/Daintree/frameworks/gcloud/PDF-OCR
   python scripts/create_bigquery_schema.py --project your-project-id
   ```

4. **Start Backend Server**:
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

## Run the Demo

```bash
cd /Users/thomasdoyle/Daintree/frameworks/gcloud/PDF-OCR
python demo_api.py
```

## What the Demo Shows

### Epic A: Document Versioning

1. **Upload Document (First Time)**
   - Creates test PDF with invoice content
   - Computes SHA-256 hash
   - Uploads to GCS
   - Creates Document and DocumentVersion records
   - Returns `was_duplicate: false`

2. **Upload Same Document Again**
   - Uploads identical PDF bytes with different filename
   - SHA-256 hash matches existing DocumentVersion
   - **No GCS upload performed** (deduplication!)
   - Creates new Document record
   - Links to existing DocumentVersion
   - Returns `was_duplicate: true`

3. **Retrieve Document Information**
   - GET `/api/documents/{id}` - User-facing document entity
   - GET `/api/documents/versions/{version_id}` - Immutable content
   - Shows two Documents sharing one DocumentVersion

4. **Update Document Metadata**
   - PATCH `/api/documents/{id}` - Update name, description, metadata
   - DocumentVersion remains immutable
   - Demonstrates separation of concerns

### Epic B: ProcessingRuns API

5. **Create Processing Run**
   - POST `/api/processing-runs` - Initialize pipeline
   - Links to DocumentVersion (not Document)
   - Status starts as `pending`
   - Returns run ID for polling

6. **Get Processing Run Status**
   - GET `/api/processing-runs/{run_id}` - Basic status
   - GET `/api/processing-runs/{run_id}?include_steps=true` - With step details
   - Shows state machine status

7. **List Processing Runs**
   - GET `/api/processing-runs?document_version_id={id}` - Filter by document
   - Supports pagination and status filtering

8. **Upload Different Document**
   - Different content = different SHA-256 hash
   - New DocumentVersion created
   - GCS upload performed
   - Demonstrates deduplication working correctly

## Key Features Demonstrated

### 🔐 SHA-256 Deduplication
- Identical bytes → same DocumentVersion
- Multiple Documents can reference same content
- Storage efficiency: no duplicate GCS uploads

### 🔄 Immutability
- DocumentVersion never changes (identified by content hash)
- Document metadata is mutable (name, description)
- ProcessingRun tracks all state transitions

### 📊 State Machine Enforcement
- ProcessingRun: `pending` → `running` → `completed`/`failed`
- Invalid transitions rejected by service layer
- Audit trail preserved

### ⚡ Idempotency (Foundation)
- IdempotencyService ready for step-level deduplication
- StepRunService integrates idempotency checks
- MERGE pattern prevents race conditions

## Expected Output

```
============================================================
  DATA HERO BACKEND API DEMO
============================================================

Base URL: http://localhost:8000
Demo User: demo-user-123

============================================================
  1. Upload Document (First Time)
============================================================

📄 Created test PDF: invoice_12345.pdf
   Size: 410 bytes
   SHA-256: abc123...def789

✅ Upload successful!
   Document ID: 550e8400-e29b-41d4-a716-446655440000
   Version ID (hash): abc123...
   Was Duplicate: False
   Filename: invoice_12345.pdf

============================================================
  2. Upload Same Document Again (Deduplication)
============================================================

✅ Upload successful!
   Document ID: 660e8400-e29b-41d4-a716-446655440001
   Version ID (hash): abc123...
   Was Duplicate: True ⭐

💡 Notice: Different Document ID but SAME Version ID!
   - No duplicate GCS upload needed
   - Storage saved: 410 bytes

... [continued]
```

## Next Steps

After running the demo, you can:

1. **Explore the API** using the generated document/run IDs
2. **Test error cases** (invalid IDs, state transitions)
3. **Check BigQuery** to see the data structure
4. **Verify GCS** to confirm no duplicate uploads

## Troubleshooting

**Connection Error:**
```bash
# Make sure backend is running
cd backend
uvicorn main:app --reload
```

**BigQuery Errors:**
```bash
# Verify schema exists
python scripts/create_bigquery_schema.py --project your-project-id

# Check credentials
echo $GOOGLE_APPLICATION_CREDENTIALS
```

**Import Errors:**
```bash
# Install requirements
cd backend
pip install -r requirements.txt
```

## Architecture Validated

This demo confirms:
- ✅ Constitution I: All structured data in BigQuery
- ✅ Constitution II: State machine-driven processing
- ✅ Constitution III: Idempotency everywhere (foundation ready)
- ✅ Constitution IV: Immutable document versioning
- ✅ Constitution V: Pipeline execution tracking
- ✅ Constitution VI: Transparent SQL (no ORM magic)

## Related Files

- **Backend Services**: `backend/app/services/`
  - `bigquery_service.py` - Core CRUD operations
  - `idempotency_service.py` - MERGE-based deduplication
  - `processing_run_service.py` - Run lifecycle
  - `step_run_service.py` - Step lifecycle with idempotency

- **API Routers**: `backend/app/routers/`
  - `upload.py` - Document upload with deduplication
  - `documents.py` - Document/version retrieval
  - `processing_runs.py` - Run management
  - `step_runs.py` - Step retry functionality

- **Data Model**: `specs/001-backend-epics-gcp/data-model.md`
- **Tasks**: `specs/001-backend-epics-gcp/tasks.md`
