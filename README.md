# PDF-OCR MVP - Region-Based Data Extraction

A complete MVP for extracting structured data from PDF regions using GCP Document AI.

## Documentation

📖 **[Full Documentation](docs/)** - Architecture, guides, and specifications
- [Architecture](docs/architecture/) - System design and implementation details
- [Setup Guides](docs/guides/) - Quickstart, deployment, and CI/CD setup
- [Roadmap](roadmap.md) - Product roadmap and feature planning
- [Feature Specs](specs/) - Detailed feature specifications and implementation plans

## Architecture

- **Frontend**: Next.js 14+ with PDF.js for rendering and canvas-based region selection
- **Backend**: FastAPI microservice for stateful PDF processing
- **GCP Services**: Document AI, Cloud Storage, Cloud Run, Firestore, Cloud Tasks

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
