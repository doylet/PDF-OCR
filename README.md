# PDF-OCR - Document Processing Platform

Enterprise-grade document processing using GCP Document AI, BigQuery, and multi-agent AI.

## Features

- ✅ Document versioning with SHA-256 deduplication
- ✅ Processing pipeline with state machine tracking
- ✅ Claims extraction with HITL feedback
- ✅ Document quality profiling and role classification
- ✅ Multi-document workspace management (Rooms)
- ✅ Evidence search and bundle creation
- ✅ Agentic AI processing with structure validation

## Documentation

📖 **[Full Documentation](docs/)** - Implementation details, guides, and architecture
- [Implementation Complete](docs/IMPLEMENTATION_COMPLETE.md) - Current status and features
- [Project Structure](PROJECT_STRUCTURE.md) - Codebase organization
- [Demo Guide](docs/README_DEMO.md) - Interactive demonstration
- [Architecture](docs/architecture/) - System design
- [Roadmap](docs/roadmap.md) - Future plans

## Architecture

- **Frontend**: Next.js 14+ with PDF.js for PDF rendering and region selection
- **Backend**: FastAPI with BigQuery persistence and Document AI integration
- **GCP Services**: Document AI, BigQuery, Cloud Storage, Cloud Run
- **AI Pipeline**: Multi-agent orchestration with layout, table, and schema agents

## Project Structure

```
PDF-OCR/
├── frontend/          # Next.js application
├── backend/           # FastAPI microservice
├── scripts/           # Deployment scripts
└── README.md
```

## Quick Start

### Prerequisites

1. GCP Project with billing enabled
2. Enable APIs:
   ```bash
   gcloud services enable documentai.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable storage.googleapis.com
   gcloud services enable firestore.googleapis.com
   gcloud services enable cloudtasks.googleapis.com
   ```
3. Create service account:
   ```bash
   gcloud iam service-accounts create pdf-ocr-service \
     --display-name="PDF OCR Service Account"
   
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:pdf-ocr-service@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/documentai.apiUser"
   
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:pdf-ocr-service@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:pdf-ocr-service@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/datastore.user"
   ```

### Local Development

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Deployment

#### Deploy Backend to Cloud Run
```bash
cd backend
./scripts/deploy.sh
```

#### Deploy Frontend to Cloud Run
```bash
cd frontend
./deploy.sh
```

## Features

- ✅ PDF upload and visualization
- ✅ Canvas-based region selection (lightbox modal)
- ✅ Async job processing with status tracking
- ✅ Document AI integration for text/table extraction
- ✅ CSV/TSV export of structured data
- ✅ Cloud Storage integration for PDFs and results

## Configuration

See individual README files in `frontend/` and `backend/` directories for detailed configuration options.

## Cost Estimate

- Document AI: ~$50-200/month
- Cloud Run: ~$10-30/month
- Cloud Storage: ~$5-20/month
- Firestore: ~$10-25/month
- **Total: $75-275/month** (moderate usage)

## License

MIT
