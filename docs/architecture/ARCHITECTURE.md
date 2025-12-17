# PDF-OCR MVP - System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                             │
│                         (Next.js Frontend)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ PDF Viewer   │  │ Region       │  │ Job Status   │             │
│  │ (PDF.js)     │  │ Selection    │  │ Display      │             │
│  │              │  │ (Canvas)     │  │ (Polling)    │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ HTTPS/REST API
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND API LAYER                             │
│                       (FastAPI on Cloud Run)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ Upload       │  │ Extraction   │  │ Job Status   │             │
│  │ Endpoints    │  │ Endpoints    │  │ Endpoints    │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                 │                       │
│         │                 │                 │                       │
└─────────┼─────────────────┼─────────────────┼───────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Cloud Storage  │  │  Document AI    │  │   Firestore     │
│  (PDFs/Results) │  │  (OCR/Extract)  │  │  (Job Tracking) │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Data Flow

### 1. PDF Upload Flow

```
User → Frontend → Backend API → Cloud Storage
                      ↓
                 Generate Signed URL
                      ↓
Frontend ← Backend (returns signed URL + PDF ID)
    ↓
Upload PDF directly to Cloud Storage
```

### 2. Region Extraction Flow

```
User draws region → Frontend captures coordinates
         ↓
    POST /api/extract/ with {pdf_id, regions[], format}
         ↓
Backend creates job in Firestore (status: queued)
         ↓
Background task starts processing
         ↓
Download PDF from Cloud Storage
         ↓
Crop each region (pypdf + pdf2image)
         ↓
Send cropped images to Document AI
         ↓
Document AI returns structured data (text, tables, forms)
         ↓
Format results as CSV/TSV/JSON
         ↓
Upload results to Cloud Storage
         ↓
Update job status in Firestore (status: completed, result_url)
```

### 3. Status Polling Flow

```
Frontend polls GET /api/extract/{job_id} every 2 seconds
         ↓
Backend queries Firestore for job status
         ↓
Returns: {status, result_url, error_message}
         ↓
When status = "completed":
    Frontend downloads result from signed URL
```

## Technology Stack

### Frontend
- **Framework**: Next.js 14+ (React 18)
- **PDF Rendering**: react-pdf (wrapper for PDF.js)
- **UI**: Tailwind CSS + Lucide icons
- **State Management**: React hooks (useState, useEffect)
- **API Client**: Custom fetch wrapper

### Backend
- **Framework**: FastAPI 0.115+
- **Server**: Uvicorn (ASGI)
- **PDF Processing**: pypdf, pdf2image, Pillow
- **GCP SDKs**:
  - google-cloud-storage
  - google-cloud-documentai
  - google-cloud-firestore
- **Validation**: Pydantic

### GCP Services
- **Cloud Run**: Serverless containers (backend + optional frontend)
- **Document AI**: OCR and form/table extraction
- **Cloud Storage**: PDF and result file storage
- **Firestore**: Job status tracking (NoSQL)
- **Cloud Tasks**: Async job queue (not used in MVP for simplicity)

## API Endpoints

### Upload Endpoints

#### `POST /api/upload/generate-url`
Generate signed URL for PDF upload.

**Request:**
```json
{
  "file_name": "invoice.pdf"
}
```

**Response:**
```json
{
  "pdf_id": "uuid",
  "upload_url": "https://storage.googleapis.com/...",
  "file_name": "invoice.pdf"
}
```

### Extraction Endpoints

#### `POST /api/extract/`
Create extraction job.

**Request:**
```json
{
  "pdf_id": "uuid",
  "regions": [
    {
      "x": 100,
      "y": 200,
      "width": 300,
      "height": 150,
      "page": 1,
      "label": "vendor_info"
    }
  ],
  "output_format": "csv"
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "created_at": "2025-12-13T10:00:00Z",
  "pdf_id": "uuid",
  "regions_count": 1
}
```

#### `GET /api/extract/{job_id}`
Get job status.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "result_url": "https://storage.googleapis.com/...",
  "created_at": "2025-12-13T10:00:00Z",
  "updated_at": "2025-12-13T10:01:30Z"
}
```

## Security Model

### Authentication
- **MVP**: Simple API key (X-API-Key header)
- **Production**: OAuth 2.0 + Cloud IAP

### Authorization
- Service account with minimal IAM roles:
  - `roles/documentai.apiUser`
  - `roles/storage.admin`
  - `roles/datastore.user`

### Data Protection
- PDFs stored in private Cloud Storage bucket
- Signed URLs with time-limited access (1 hour upload, 7 days download)
- CORS configured for specific frontend domains
- No persistent user data (stateless API)

## Scalability

### Current Limits
- **Cloud Run**: Auto-scales 0-10 instances
- **Document AI**: 600 requests/min (default quota)
- **Firestore**: 10k writes/sec, 50k reads/sec
- **Cloud Storage**: Unlimited, $0.020/GB/month

### Optimization for Scale
1. **Caching**: Add Redis for repeated extractions
2. **Batching**: Process multiple regions in parallel
3. **Streaming**: Use streaming for large PDFs
4. **CDN**: CloudFlare/Cloud CDN for frontend assets
5. **Queue**: Implement Cloud Tasks for true async processing

## Cost Breakdown (Monthly)

| Component | Usage | Cost |
|-----------|-------|------|
| Cloud Run (Backend) | 1000 requests, 2GB RAM | $10 |
| Cloud Run (Frontend) | 5000 requests | $15 |
| Document AI | 200 pages | $70 |
| Cloud Storage | 10 GB | $0.20 |
| Firestore | 100k operations | $10 |
| **Total** | | **$105** |

**Per extraction**: ~$0.35-0.70 (Document AI cost)

## Performance Metrics

### Latency
- **PDF Upload**: 1-3 seconds (depends on file size)
- **Region Extraction**: 3-8 seconds per region
  - PDF download: 0.5s
  - Crop: 0.5s
  - Document AI: 2-6s
  - Result upload: 0.5s
- **Status Check**: <100ms (Firestore query)

### Throughput
- **Backend**: 50-100 concurrent extractions
- **Document AI**: 10 pages/second (per processor)

## Monitoring

### Key Metrics
1. **Request count** (Cloud Run metrics)
2. **Error rate** (4xx/5xx responses)
3. **Document AI quota usage**
4. **Average extraction time**
5. **Storage costs**

### Logging
- **Backend**: Structured JSON logs to Cloud Logging
- **Frontend**: Browser console + Vercel logs
- **GCP**: Audit logs for all API calls

## Deployment Environments

### Development
- **Backend**: Local (uvicorn)
- **Frontend**: Local (next dev)
- **GCP**: Shared dev project

### Staging (Optional)
- **Backend**: Cloud Run (staging)
- **Frontend**: Vercel preview
- **GCP**: Separate staging project

### Production
- **Backend**: Cloud Run (prod)
- **Frontend**: Vercel production
- **GCP**: Separate prod project
- **Domain**: Custom domain with SSL

## Disaster Recovery

### Backup Strategy
- **Firestore**: Automated daily exports to Cloud Storage
- **Cloud Storage**: Versioning enabled (retain 30 days)
- **Code**: Git repository (GitHub)

### Recovery Time Objective (RTO)
- **Backend**: 5-10 minutes (redeploy from Cloud Run)
- **Frontend**: <1 minute (Vercel automatic failover)
- **Data**: 24 hours (restore from Firestore backup)

## Future Enhancements

### V2 Features
1. **Batch Processing**: Upload multiple PDFs
2. **Template Management**: Save common region patterns
3. **Export Formats**: Excel, Markdown, HTML
4. **Webhooks**: Notify external systems on completion
5. **API Dashboard**: Usage analytics and billing
6. **User Management**: Multi-tenant with teams
7. **Advanced Extraction**: Custom ML models
8. **Integration**: Zapier, Make, n8n connectors

### Infrastructure
1. **CDN**: Cache static assets
2. **Redis**: Job queue and caching
3. **BigQuery**: Analytics data warehouse
4. **Pub/Sub**: Event-driven architecture
5. **Cloud Armor**: DDoS protection
6. **Identity Platform**: OAuth/SSO

## License

MIT - See LICENSE file for details.
