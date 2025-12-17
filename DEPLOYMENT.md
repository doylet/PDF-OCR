# PDF-OCR Deployment Guide

## Overview

This document covers deployment and infrastructure setup for the PDF-OCR backend API on Google Cloud Run.

## Prerequisites

- GCP Project with billing enabled
- gcloud CLI installed and authenticated
- Docker installed
- Required GCP APIs enabled:
  - Cloud Run
  - Cloud Build
  - Cloud Tasks
  - BigQuery
  - Cloud Storage
  - Document AI
  - Secret Manager

## Initial Setup

### 1. Create Secrets

```bash
echo -n "YOUR_API_KEY" | gcloud secrets create pdf-ocr-api-key --data-file=-
echo -n "YOUR_GEMINI_KEY" | gcloud secrets create gemini-api-key --data-file=-
```

### 2. Create Service Account

```bash
gcloud iam service-accounts create pdf-ocr-service-account \
  --display-name="PDF OCR Service Account"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:pdf-ocr-service-account@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:pdf-ocr-service-account@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:pdf-ocr-service-account@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/documentai.apiUser"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:pdf-ocr-service-account@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudtasks.enqueuer"
```

### 3. Create BigQuery Dataset and Tables

```bash
python scripts/create_bigquery_schema.py --project PROJECT_ID
```

### 4. Setup Cloud Tasks Queue

```bash
./scripts/setup-cloud-tasks.sh
```

### 5. Migrate Firestore Data (Optional)

```bash
python scripts/migrate_firestore_to_bigquery.py --project PROJECT_ID --dry-run
python scripts/migrate_firestore_to_bigquery.py --project PROJECT_ID
```

## Deployment Methods

### Method 1: Manual Deployment with Script

```bash
cd backend
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
./deploy.sh
```

### Method 2: Cloud Build

```bash
gcloud builds submit --config=backend/cloudbuild.yaml
```

### Method 3: GitHub Actions (CI/CD)

Push to main branch - deployment happens automatically via `.github/workflows/deploy-backend.yml`

Required GitHub Secrets:
- `WIF_PROVIDER`: Workload Identity Federation provider
- `WIF_SERVICE_ACCOUNT`: Service account email
- `GCS_BUCKET_NAME`: Cloud Storage bucket name
- `GCP_PROCESSOR_ID`: Document AI processor ID
- `CORS_ORIGINS`: Allowed CORS origins

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | GCP project ID | Required |
| `GCP_LOCATION` | GCP region | `us` |
| `GCS_BUCKET_NAME` | Storage bucket | Required |
| `BIGQUERY_DATASET` | BigQuery dataset | `data_hero` |
| `TASK_QUEUE_NAME` | Cloud Tasks queue | `extraction-queue` |
| `API_BASE_URL` | Service URL | Required |
| `GCP_PROCESSOR_ID` | Document AI processor | Required |
| `CORS_ORIGINS` | CORS allowed origins | Comma-separated |
| `DEBUG` | Debug mode | `false` |

## Secrets (from Secret Manager)

| Secret | Description |
|--------|-------------|
| `API_KEY` | API authentication key |
| `GEMINI_API_KEY` | Google Gemini API key (optional) |

## Health Checks

After deployment, verify service health:

```bash
SERVICE_URL=$(gcloud run services describe pdf-ocr-api \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)')

curl $SERVICE_URL/health
```

Expected response:
```json
{"status": "ok"}
```

## Monitoring

### Logs

```bash
gcloud run services logs read pdf-ocr-api --region us-central1 --limit 50
```

### Metrics

View in Cloud Console:
- Cloud Run → pdf-ocr-api → Metrics
- Monitor request count, latency, errors

### Alerts

Set up alerts for:
- Error rate > 5%
- Request latency > 5s
- Instance count > 8

## Rollback

```bash
REVISION=$(gcloud run revisions list \
  --service pdf-ocr-api \
  --region us-central1 \
  --format 'value(name)' \
  --limit 2 | tail -n 1)

gcloud run services update-traffic pdf-ocr-api \
  --to-revisions $REVISION=100 \
  --region us-central1
```

## Scaling Configuration

Current settings:
- Memory: 2Gi
- CPU: 2
- Min instances: 0 (scales to zero)
- Max instances: 10
- Timeout: 300s

Adjust for production:

```bash
gcloud run services update pdf-ocr-api \
  --min-instances 1 \
  --max-instances 50 \
  --memory 4Gi \
  --cpu 4 \
  --region us-central1
```

## Cost Optimization

1. **Scale to zero**: Min instances = 0 for dev/test
2. **Request timeout**: 300s prevents long-running requests
3. **Max instances**: Limit to 10 to control costs
4. **CPU allocation**: Only during request processing

## Troubleshooting

### Common Issues

**Issue: Service won't start**
- Check logs: `gcloud run services logs read pdf-ocr-api`
- Verify secrets exist: `gcloud secrets list`
- Check IAM permissions on service account

**Issue: BigQuery errors**
- Verify dataset exists: `bq ls data_hero`
- Check service account has `bigquery.dataEditor` role

**Issue: Cloud Tasks not triggering**
- Verify queue exists: `gcloud tasks queues describe extraction-queue --location us-central1`
- Check service account has `cloudtasks.enqueuer` role

**Issue: Authentication failures**
- Verify API_KEY secret matches client requests
- Check Cloud Run allows unauthenticated if needed

## Security

1. **API Key**: Rotate regularly, store in Secret Manager
2. **Service Account**: Minimum required permissions
3. **CORS**: Restrict to known origins in production
4. **Cloud Run**: Use `--no-allow-unauthenticated` for internal services
5. **Secrets**: Never commit to git, use Secret Manager

## Production Checklist

- [ ] Secrets created in Secret Manager
- [ ] Service account created with minimal permissions
- [ ] BigQuery dataset and tables created
- [ ] Cloud Tasks queue created
- [ ] CORS origins restricted to production domains
- [ ] Min instances > 0 for production traffic
- [ ] Monitoring and alerts configured
- [ ] Backup strategy for BigQuery data
- [ ] Log retention configured
- [ ] API key rotation schedule established
