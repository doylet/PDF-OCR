# Quickstart: Backend Epics Implementation

**Feature**: Data Hero Backend MVP - All Epics  
**Date**: 2025-12-17  
**Audience**: Developers setting up local environment for implementation

## Prerequisites

- Python 3.11+ installed
- Google Cloud SDK (`gcloud`) installed and authenticated
- Docker Desktop installed (for BigQuery emulator)
- Access to GCP project with required APIs enabled
- Git repository cloned locally

---

## 1. GCP Project Setup

### Enable Required APIs
```bash
# Set project ID
export GCP_PROJECT="your-project-id"
gcloud config set project $GCP_PROJECT

# Enable APIs
gcloud services enable \
  bigquery.googleapis.com \
  storage.googleapis.com \
  cloudtasks.googleapis.com \
  documentai.googleapis.com \
  logging.googleapis.com \
  run.googleapis.com
```

### Create BigQuery Dataset
```bash
bq mk --dataset \
  --location=us \
  --description="Data Hero MVP dataset" \
  ${GCP_PROJECT}:data_hero
```

### Create GCS Buckets
```bash
# Documents bucket
gsutil mb -l us-central1 gs://${GCP_PROJECT}-documents
gsutil lifecycle set gcs-lifecycle.json gs://${GCP_PROJECT}-documents

# Artifacts bucket
gsutil mb -l us-central1 gs://${GCP_PROJECT}-artifacts
gsutil lifecycle set gcs-lifecycle.json gs://${GCP_PROJECT}-artifacts
```

**gcs-lifecycle.json** (90-day retention):
```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90}
      }
    ]
  }
}
```

### Create Cloud Tasks Queue
```bash
gcloud tasks queues create extraction-queue \
  --location=us-central1 \
  --max-dispatches-per-second=100 \
  --max-concurrent-dispatches=100
```

---

## 2. Local Development Setup

### Clone Repository
```bash
cd /Users/thomasdoyle/Daintree/frameworks/gcloud/PDF-OCR
git checkout 001-backend-epics-gcp
```

### Create Python Virtual Environment
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate  # On Windows

pip install --upgrade pip
pip install -r requirements.txt
```

### Install Development Dependencies
```bash
pip install pytest pytest-cov pytest-asyncio
pip install black flake8 mypy  # Linting/formatting
```

---

## 3. Environment Configuration

### Create .env File
```bash
cat > backend/.env <<EOF
# GCP Configuration
GCP_PROJECT_ID=${GCP_PROJECT}
GCP_LOCATION=us
GCP_PROCESSOR_ID=your-documentai-processor-id

# Cloud Storage
GCS_BUCKET_NAME=${GCP_PROJECT}-documents
GCS_PDF_FOLDER=documents
GCS_RESULTS_FOLDER=processing-runs
GCS_ARTIFACTS_FOLDER=artifacts

# BigQuery
BIGQUERY_DATASET=data_hero
BIGQUERY_LOCATION=us

# Cloud Tasks
CLOUD_TASKS_QUEUE=extraction-queue
CLOUD_TASKS_LOCATION=us-central1
WORKER_SERVICE_URL=http://localhost:8000  # For local testing

# LLM Configuration (Optional)
GEMINI_API_KEY=your-gemini-api-key
ENABLE_LLM_AGENTS=true

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# API Key (for testing)
API_KEY=dev-test-key-do-not-use-in-prod

# Debug
DEBUG=true
EOF
```

**Important**: Add `.env` to `.gitignore` to prevent committing secrets.

---

## 4. Database Schema Setup

### Create BigQuery Tables
```bash
# Navigate to schema directory
cd specs/001-backend-epics-gcp/schema

# Run DDL scripts in order
for sql_file in $(ls -1 *.sql | sort); do
  echo "Creating table from $sql_file..."
  bq query --use_legacy_sql=false < $sql_file
done

# Verify tables created
bq ls data_hero
```

**Expected Output**:
```
tableId                     Type
---------------------------  ------
rooms                        TABLE
documents                    TABLE
document_versions            TABLE
room_documents              TABLE
document_profiles           TABLE
processing_runs             TABLE
step_runs                   TABLE
idempotency_keys            TABLE
claims                      TABLE
set_templates               TABLE
set_completeness_statuses   TABLE
```

### Seed Initial Data
```bash
# Seed SetTemplates
bq query --use_legacy_sql=false <<EOF
INSERT INTO \`${GCP_PROJECT}.data_hero.set_templates\` (id, name, description, required_roles, created_at)
VALUES 
  ('tpl-001', 'Bank Statement Set', 'Standard bank statement package', ['bank_statement', 'ledger'], CURRENT_TIMESTAMP()),
  ('tpl-002', 'Loan Application Package', 'Commercial loan application documents', ['bank_statement', 'paystub', 'tax_return'], CURRENT_TIMESTAMP()),
  ('tpl-003', 'Compliance Audit Set', 'Compliance review document set', ['policy_document', 'audit_report', 'evidence_log'], CURRENT_TIMESTAMP());
EOF
```

---

## 5. Local Testing with BigQuery Emulator

### Start BigQuery Emulator (Optional)
```bash
# Using Docker
docker run -d \
  --name bigquery-emulator \
  -p 9050:9050 \
  ghcr.io/goccy/bigquery-emulator:latest \
  --project=${GCP_PROJECT} \
  --dataset=data_hero
```

### Configure Environment for Emulator
```bash
export BIGQUERY_EMULATOR_HOST=localhost:9050
```

---

## 6. Run Backend Locally

### Start FastAPI Server
```bash
cd backend
source venv/bin/activate
python main.py
```

**Expected Output**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Verify API Health
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "1.0.0"}
```

### View OpenAPI Docs
Navigate to: http://localhost:8000/docs

---

## 7. Test Document Upload Flow

### Upload Test PDF
```bash
# Generate upload URL
curl -X POST http://localhost:8000/api/documents \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test-pdfs/sample_bank_statement.pdf" \
  -F "name=Test Bank Statement" \
  | jq .

# Expected response:
# {
#   "document_id": "uuid-here",
#   "document_version_id": "sha256-hash-here",
#   "is_duplicate": false,
#   "upload_url": "gs://...",
#   "profile": { ... }
# }
```

### Verify Data in BigQuery
```bash
# Check document created
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${GCP_PROJECT}.data_hero.documents\` ORDER BY created_at DESC LIMIT 1"

# Check document version created
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${GCP_PROJECT}.data_hero.document_versions\` ORDER BY created_at DESC LIMIT 1"

# Check profile created
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${GCP_PROJECT}.data_hero.document_profiles\` ORDER BY created_at DESC LIMIT 1"
```

---

## 8. Run Tests

### Unit Tests
```bash
cd backend
pytest tests/unit/ -v
```

### Integration Tests (Requires GCP Access)
```bash
pytest tests/integration/ -v --cov=app --cov-report=html
```

### Contract Tests (API Validation)
```bash
pytest tests/contract/ -v
```

### View Coverage Report
```bash
open htmlcov/index.html  # On macOS
# Or navigate to backend/htmlcov/index.html in browser
```

---

## 9. Frontend Setup (Optional)

### Install Frontend Dependencies
```bash
cd frontend
npm install
```

### Start Frontend Dev Server
```bash
npm run dev
# Navigate to http://localhost:3000
```

---

## 10. Troubleshooting

### Issue: BigQuery Permission Denied
**Solution**: Ensure service account has BigQuery Data Editor role
```bash
gcloud projects add-iam-policy-binding $GCP_PROJECT \
  --member=serviceAccount:your-service-account@$GCP_PROJECT.iam.gserviceaccount.com \
  --role=roles/bigquery.dataEditor
```

### Issue: Document AI Processor Not Found
**Solution**: Create Document AI processor
```bash
# List processors
gcloud documentai processors list --location=us

# Create new processor
gcloud documentai processors create \
  --display-name="Data Hero OCR" \
  --type=OCR_PROCESSOR \
  --location=us
```

### Issue: Cloud Tasks Queue Not Found
**Solution**: Verify queue exists and location matches
```bash
gcloud tasks queues describe extraction-queue --location=us-central1
```

### Issue: Module Import Errors
**Solution**: Reinstall dependencies
```bash
pip install --upgrade -r requirements.txt
```

---

## 11. Development Workflow

### Feature Branch Development
```bash
# Already on feature branch
git checkout 001-backend-epics-gcp

# Create new working branch for specific task
git checkout -b feature/001-implement-rooms-api

# Make changes, commit frequently
git add .
git commit -m "Implement POST /rooms endpoint"

# Push to remote
git push origin feature/001-implement-rooms-api
```

### Pre-commit Checks
```bash
# Format code
black backend/app

# Lint
flake8 backend/app

# Type check
mypy backend/app

# Run tests
pytest backend/tests/
```

---

## 12. Deployment (After Implementation)

### Deploy Backend to Cloud Run
```bash
cd backend
./deploy.sh
```

### Deploy Frontend to Cloud Run
```bash
cd frontend
./deploy.sh
```

### Verify Deployment
```bash
# Get service URL
gcloud run services describe pdf-ocr-api --region=us-central1 --format='value(status.url)'

# Test health endpoint
curl https://pdf-ocr-api-<hash>-uc.a.run.app/health
```

---

## 13. Monitoring & Debugging

### View Cloud Logging
```bash
# Stream logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=pdf-ocr-api" \
  --limit=50 \
  --format=json \
  --freshness=5m

# Or use Logs Explorer: https://console.cloud.google.com/logs
```

### Monitor BigQuery Usage
```bash
# Query execution stats
bq ls -j --max_results=10
```

### Monitor Cloud Tasks Queue
```bash
gcloud tasks queues describe extraction-queue --location=us-central1
```

---

## 14. Key Files Reference

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI application entrypoint |
| `backend/app/config.py` | Environment configuration |
| `backend/app/dependencies.py` | Dependency injection |
| `backend/app/routers/` | API endpoint handlers |
| `backend/app/services/` | Business logic layer |
| `backend/app/models/` | Pydantic data models |
| `backend/requirements.txt` | Python dependencies |
| `specs/001-backend-epics-gcp/data-model.md` | BigQuery schema documentation |
| `specs/001-backend-epics-gcp/contracts/` | OpenAPI specifications |

---

## 15. Next Steps

After completing setup:

1. **Implement Rooms API**: See [contracts/rooms.yaml](contracts/rooms.yaml)
2. **Implement Claims API**: See [contracts/claims.yaml](contracts/claims.yaml)
3. **Implement Evidence Bundles API**: See [contracts/evidence-bundles.yaml](contracts/evidence-bundles.yaml)
4. **Migrate Firestore → BigQuery**: Update `firestore_service.py` to use BigQuery
5. **Add Integration Tests**: Cover all new endpoints
6. **Update Frontend**: Consume new APIs

For detailed implementation tasks, run:
```bash
# After Phase 1 completion
/speckit.tasks
```

---

## Resources

- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Cloud Tasks Documentation](https://cloud.google.com/tasks/docs)
- [Document AI Documentation](https://cloud.google.com/document-ai/docs)
- [Data Model Reference](data-model.md)
- [API Contracts Reference](contracts/)

---

## Support

For questions or issues:
- Check [ARCHITECTURE.md](../../ARCHITECTURE.md) for system design
- Review [Constitution](../../.specify/memory/constitution.md) for principles
- Consult [research.md](research.md) for implementation patterns
