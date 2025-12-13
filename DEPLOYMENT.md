# PDF-OCR MVP - Complete Deployment Guide

This guide walks you through deploying the complete PDF-OCR system for your investor presentation.

## Prerequisites

- GCP account with billing enabled
- `gcloud` CLI installed and authenticated
- Node.js 18+ and npm
- Python 3.11+

## Step 1: GCP Setup (10-15 minutes)

### 1.1 Set Your GCP Project

```bash
# List projects
gcloud projects list

# Set active project
gcloud config set project YOUR_PROJECT_ID
```

### 1.2 Run Automated Setup Script

```bash
cd scripts
./setup-gcp.sh
```

This script will:
- Enable required APIs (Document AI, Cloud Run, Storage, Firestore)
- Create service account with proper IAM roles
- Set up Cloud Storage bucket with CORS
- Initialize Firestore database
- Generate `.env` file for backend

### 1.3 Create Document AI Processor

The script will prompt you to create a Document AI processor manually:

1. Go to [Document AI Console](https://console.cloud.google.com/ai/document-ai/processors)
2. Click **Create Processor**
3. Select **Document OCR** or **Form Parser** (Form Parser recommended for tables)
4. Choose location: **us (United States)**
5. Click **Create**
6. Copy the **Processor ID** (format: `abc123def456`)
7. Paste it when prompted by the setup script

## Step 2: Deploy Backend (5-10 minutes)

### 2.1 Test Locally (Optional)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn app.main:app --reload --port 8000

# Test health endpoint
curl http://localhost:8000/health
```

### 2.2 Deploy to Cloud Run

```bash
cd backend
./deploy.sh
```

Follow the prompts to enter:
- Document AI Processor ID
- GCS Bucket Name
- API Key (or use default)

After deployment, note the **Service URL** (e.g., `https://pdf-ocr-api-xxx.run.app`)

### 2.3 Verify Backend

```bash
# Test health endpoint
curl https://YOUR_SERVICE_URL/health

# View API docs
open https://YOUR_SERVICE_URL/docs
```

## Step 3: Deploy Frontend (5-10 minutes)

### 3.1 Configure Environment

```bash
cd frontend

# Update .env.local with backend URL
cat > .env.local <<EOF
NEXT_PUBLIC_API_URL=https://YOUR_BACKEND_URL
NEXT_PUBLIC_API_KEY=your-api-key
EOF
```

### 3.2 Test Locally

```bash
npm install
npm run dev

# Open browser
open http://localhost:3000
```

### 3.3 Deploy to Cloud Run

```bash
# Deploy frontend
cd frontend
./deploy.sh

# Follow prompts to enter:
# - Backend API URL
# - API Key
```

The script will:
- Build Next.js app with Docker
- Deploy to Cloud Run
- Configure environment variables
- Return your frontend URL

### 3.4 Alternative: Manual Docker Build

```bash
# Create Dockerfile for Next.js
cat > Dockerfile <<EOF
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
ENV PORT=3000
EXPOSE 3000
CMD ["npm", "start"]
EOF

# Build and deploy
gcloud run deploy pdf-ocr-frontend \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars NEXT_PUBLIC_API_URL=https://your-backend.run.app,NEXT_PUBLIC_API_KEY=your-api-key
```

## Step 4: Update CORS Settings

After deploying frontend, update backend CORS to allow your frontend domain:

```bash
cd backend

# Redeploy with updated CORS
gcloud run services update pdf-ocr-api \
  --region us-central1 \
  --update-env-vars CORS_ORIGINS='["http://localhost:3000","https://pdf-ocr-frontend-xxx.run.app"]'
```

## Step 5: Testing End-to-End

### 5.1 Prepare Test PDF

Use a sample invoice, form, or document with tables/text.

### 5.2 Test Workflow

1. Open your frontend URL
2. Upload PDF
3. Draw regions on PDF (click and drag)
4. Select output format (CSV recommended)
5. Click "Extract Data"
6. Wait for processing (status updates every 2 seconds)
7. Download results

### 5.3 Verify Results

- CSV file should contain extracted text
- Tables should be properly formatted
- Confidence scores should be present

## Step 6: Investor Demo Preparation

### 6.1 Create Demo Scenarios

1. **Simple Text Extraction**: Invoice with vendor info
2. **Table Extraction**: Financial statement with tables
3. **Form Extraction**: Application form with fields
4. **Multi-Region**: Document with header, table, and footer

### 6.2 Performance Optimization

```bash
# Increase backend memory for faster processing
gcloud run services update pdf-ocr-api \
  --region us-central1 \
  --memory 4Gi
```

### 6.3 Monitoring Setup

```bash
# View logs
gcloud run services logs read pdf-ocr-api --region us-central1

# Set up alerts (optional)
gcloud alpha monitoring channels create \
  --display-name="PDF-OCR Alerts" \
  --type=email \
  --channel-labels=email_address=your-email@example.com
```

## Troubleshooting

### Backend Issues

**Error: "Document AI API not enabled"**
```bash
gcloud services enable documentai.googleapis.com
```

**Error: "Permission denied on bucket"**
```bash
# Grant storage admin role to service account
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:pdf-ocr-service@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"
```

### Frontend Issues

**CORS Error**
- Update backend CORS_ORIGINS environment variable with frontend domain
- Redeploy backend

**PDF.js Worker Error**
- Ensure worker is loaded from unpkg CDN
- Check browser console for specific error

### Processing Issues

**Slow Extraction**
- Increase backend memory (2Gi → 4Gi)
- Reduce PDF resolution before upload
- Use smaller regions

**Low Confidence Scores**
- Use higher resolution PDFs (300 DPI recommended)
- Ensure clear, legible text
- Try Form Parser instead of Document OCR processor

## Cost Estimate

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Cloud Run (Backend) | 100 requests/day | $5-10 |
| Cloud Run (Frontend) | 500 requests/day | $10-15 |
| Document AI | 100 pages/month | $35-70 |
| Cloud Storage | 10 GB | $0.20 |
| Firestore | 50k reads/writes | $5-10 |
| **Total** | | **$55-105/month** |

For investor demo (1-2 weeks): **~$10-20**

## Production Checklist

Before going to production:

- [ ] Change API key from default
- [ ] Set up proper authentication (OAuth/IAP)
- [ ] Configure custom domain
- [ ] Enable Cloud Armor for DDoS protection
- [ ] Set up monitoring and alerting
- [ ] Implement rate limiting
- [ ] Add error tracking (Sentry)
- [ ] Set up backup for Firestore
- [ ] Configure Cloud CDN for frontend
- [ ] Enable Cloud Logging
- [ ] Implement user management
- [ ] Add usage analytics

## Support

- **Backend API Docs**: `https://your-backend.run.app/docs`
- **GCP Console**: https://console.cloud.google.com
- **Document AI Docs**: https://cloud.google.com/document-ai/docs

## Quick Reference

```bash
# View backend logs
gcloud run services logs read pdf-ocr-api --region us-central1 --limit 50

# Update backend environment variable
gcloud run services update pdf-ocr-api \
  --region us-central1 \
  --update-env-vars KEY=VALUE

# Rollback backend deployment
gcloud run services update-traffic pdf-ocr-api \
  --region us-central1 \
  --to-revisions PREVIOUS_REVISION=100

# Delete all resources
gcloud run services delete pdf-ocr-api --region us-central1
gsutil rm -r gs://your-bucket-name
```

## Next Steps

After successful demo:
1. Gather investor feedback
2. Prioritize features for v2
3. Implement user authentication
4. Add batch processing
5. Create API dashboard
6. Set up CI/CD pipeline
