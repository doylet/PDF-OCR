# PDF-OCR Backend (FastAPI)

Python FastAPI microservice for processing PDF regions with GCP Document AI.

## Features

- PDF upload to Cloud Storage with signed URLs
- Region-based extraction using Document AI
- Async job processing with status tracking (Firestore)
- Multiple output formats (CSV, TSV, JSON)
- RESTful API with automatic OpenAPI docs

## Setup

### Prerequisites

1. Python 3.11+
2. GCP Project with enabled APIs:
   - Document AI API
   - Cloud Storage API
   - Firestore API
   - Cloud Run API

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
```

### Configuration

Edit `.env` file with your GCP settings:

```env
GCP_PROJECT_ID=your-project-id
GCP_PROCESSOR_ID=your-document-ai-processor-id
GCS_BUCKET_NAME=your-bucket-name
API_KEY=your-secure-api-key
```

### Document AI Processor Setup

1. Go to [Document AI Console](https://console.cloud.google.com/ai/document-ai)
2. Create a new processor:
   - Type: Document OCR or Form Parser (recommended for structured data)
   - Location: us (or your preferred region)
3. Copy the Processor ID to your `.env` file

### Cloud Storage Setup

```bash
# Create bucket
gsutil mb -p YOUR_PROJECT_ID -c STANDARD -l US gs://your-bucket-name

# Set CORS for frontend access
echo '[{"origin": ["http://localhost:3000"], "method": ["GET", "PUT"], "maxAgeSeconds": 3600}]' > cors.json
gsutil cors set cors.json gs://your-bucket-name
```

### Firestore Setup

```bash
# Create Firestore database (if not exists)
gcloud firestore databases create --region=us-central
```

## Local Development

```bash
# Run with hot reload
uvicorn app.main:app --reload --port 8000

# Access API docs
open http://localhost:8000/docs
```

## API Endpoints

### Upload PDF

```bash
POST /api/upload/generate-url
Headers: X-API-Key: your-api-key
Body: { "file_name": "document.pdf" }

Response:
{
  "pdf_id": "uuid",
  "upload_url": "signed-url",
  "file_name": "document.pdf"
}
```

Then upload PDF to signed URL:
```bash
curl -X PUT -H "Content-Type: application/pdf" --upload-file document.pdf "signed-url"
```

### Extract Regions

```bash
POST /api/extract
Headers: X-API-Key: your-api-key
Body:
{
  "pdf_id": "uuid",
  "regions": [
    {
      "x": 100,
      "y": 200,
      "width": 300,
      "height": 150,
      "page": 1,
      "label": "table"
    }
  ],
  "output_format": "csv"
}

Response:
{
  "job_id": "uuid",
  "status": "queued",
  "created_at": "2025-12-13T10:00:00Z",
  "pdf_id": "uuid",
  "regions_count": 1
}
```

### Check Job Status

```bash
GET /api/extract/{job_id}
Headers: X-API-Key: your-api-key

Response:
{
  "job_id": "uuid",
  "status": "completed",
  "result_url": "signed-url-to-download-result",
  "created_at": "2025-12-13T10:00:00Z",
  "updated_at": "2025-12-13T10:01:00Z"
}
```

## Docker Build

```bash
# Build image
docker build -t pdf-ocr-backend .

# Run locally
docker run -p 8080:8080 --env-file .env pdf-ocr-backend
```

## Deployment to Cloud Run

```bash
# Build and deploy
gcloud run deploy pdf-ocr-api \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=your-project-id,GCP_PROCESSOR_ID=your-processor-id \
  --memory 2Gi \
  --timeout 300

# Get service URL
gcloud run services describe pdf-ocr-api --region us-central1 --format 'value(status.url)'
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── config.py            # Configuration
│   ├── models.py            # Pydantic models
│   ├── dependencies.py      # Shared dependencies
│   ├── routers/
│   │   ├── upload.py        # Upload endpoints
│   │   └── extraction.py    # Extraction endpoints
│   └── services/
│       ├── storage.py       # Cloud Storage service
│       ├── jobs.py          # Firestore job tracking
│       ├── documentai.py    # Document AI processing
│       └── formatter.py     # Result formatting
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Testing

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

## Troubleshooting

### Authentication Issues

If you see authentication errors:
```bash
# Set application default credentials
gcloud auth application-default login

# Or use service account
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Memory Issues

For large PDFs, increase Cloud Run memory:
```bash
gcloud run services update pdf-ocr-api --memory 4Gi --region us-central1
```

## License

MIT
