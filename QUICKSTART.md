# Quick Start Guide - Local Development

Get the PDF-OCR MVP running locally in under 10 minutes.

## Prerequisites

- Python 3.11+
- Node.js 18+
- GCP account (for Document AI)
- `gcloud` CLI installed

## Step 1: GCP Setup (One-Time)

```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable documentai.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable firestore.googleapis.com

# Authenticate
gcloud auth application-default login
```

### Create Document AI Processor

1. Visit: https://console.cloud.google.com/ai/document-ai/processors
2. Create a **Document OCR** or **Form Parser** processor
3. Note the Processor ID

### Create Storage Bucket

```bash
gsutil mb -p YOUR_PROJECT_ID gs://your-bucket-name
```

### Initialize Firestore

```bash
gcloud firestore databases create --region=us-central
```

## Step 2: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env <<EOF
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us
GCP_PROCESSOR_ID=your-processor-id
GCS_BUCKET_NAME=your-bucket-name
GCS_PDF_FOLDER=pdfs
GCS_RESULTS_FOLDER=results
FIRESTORE_COLLECTION=extraction_jobs
CORS_ORIGINS=["http://localhost:3000"]
API_KEY=dev-api-key-change-in-production
DEBUG=true
EOF

# Run backend
uvicorn app.main:app --reload --port 8000
```

**Test Backend:**
```bash
# In another terminal
curl http://localhost:8000/health
# Should return: {"status":"ok"}
```

## Step 3: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local
cat > .env.local <<EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=dev-api-key-change-in-production
EOF

# Run frontend
npm run dev
```

**Open Browser:**
```bash
open http://localhost:3000
```

## Step 4: Test Extraction

1. **Upload PDF**: Use any PDF with text or tables
2. **Select Region**: Click and drag on the PDF
3. **Extract**: Click "Extract Data" button
4. **Download**: Wait for processing, then download CSV

## Common Issues

### "Authentication failed"
```bash
gcloud auth application-default login
```

### "Bucket not found"
```bash
gsutil mb -p YOUR_PROJECT_ID gs://your-bucket-name
```

### "Processor not found"
- Double-check Processor ID in .env
- Ensure processor is in `us` location

### Frontend can't connect to backend
- Ensure backend is running on port 8000
- Check CORS settings in backend/.env

## Demo Data

Sample test documents:
- Invoice with vendor details
- Form with fields
- Table with data rows
- Receipt with line items

## What's Next?

- See `DEPLOYMENT.md` for production deployment
- See `README.md` for architecture details
- See `backend/README.md` for API documentation

## Quick Commands

```bash
# Start backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload

# Start frontend
cd frontend && npm run dev

# View backend logs
# Logs appear in terminal where uvicorn is running

# View API docs
open http://localhost:8000/docs
```
