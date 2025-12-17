# Project Structure

## Overview

This project is organized into three main components:

```
PDF-OCR/
├── backend/          # FastAPI backend with BigQuery persistence
├── frontend/         # Next.js frontend with PDF.js viewer
├── scripts/          # Deployment and setup scripts
├── docs/             # Documentation
└── test-pdfs/        # Sample PDFs for testing
```

## Backend Structure

```
backend/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── app/
│   ├── config.py             # Configuration management
│   ├── dependencies.py       # FastAPI dependency injection
│   ├── models/               # Data models and state machines
│   │   ├── api.py           # Pydantic request/response models
│   │   ├── state_machines.py # ProcessingRun and StepRun states
│   │   └── document_graph.py # Document structure models
│   ├── routers/              # API endpoint definitions
│   │   ├── upload.py        # Document upload with deduplication
│   │   ├── documents.py     # Document CRUD operations
│   │   ├── document_profiles.py # Document quality analysis
│   │   ├── rooms.py         # Multi-document workspaces
│   │   ├── processing_runs.py # Pipeline execution tracking
│   │   ├── step_runs.py     # Individual step management
│   │   ├── claims.py        # Extracted data with HITL feedback
│   │   ├── evidence.py      # Evidence search and bundles
│   │   ├── extraction.py    # Legacy: Direct extraction
│   │   └── feedback.py      # Legacy: HITL feedback
│   ├── services/             # Business logic layer
│   │   ├── bigquery_service.py        # Core BigQuery operations
│   │   ├── idempotency_service.py     # Deduplication with MERGE
│   │   ├── processing_run_service.py  # Run lifecycle management
│   │   ├── step_run_service.py        # Step execution with retry
│   │   ├── claims_service.py          # Claims CRUD operations
│   │   ├── document_profile_service.py # Quality profiling
│   │   ├── room_service.py            # Room management
│   │   ├── evidence_service.py        # Evidence aggregation
│   │   ├── documentai.py              # Document AI integration
│   │   ├── storage.py                 # GCS operations
│   │   ├── firestore_service.py       # Legacy: Firestore DB
│   │   └── ...                        # Other utilities
│   └── agents/               # Agentic processing pipeline
│       ├── orchestrator.py   # Multi-agent coordination
│       ├── layout_agent.py   # Layout analysis
│       ├── table_agent.py    # Table extraction
│       ├── schema_agent.py   # Schema inference
│       └── ...
└── scripts/
    └── create_bigquery_schema.py # BigQuery table creation
```

## Frontend Structure

```
frontend/
├── app/
│   ├── layout.tsx           # Root layout with metadata
│   ├── page.tsx             # Main application entry
│   └── globals.css          # Global styles
├── components/
│   ├── pages/               # Page-level components
│   │   ├── WelcomeScreen.tsx
│   │   ├── PDFWorkspace.tsx
│   │   └── RegionsSidebar.tsx
│   ├── pdf/                 # PDF viewer components
│   │   ├── PDFViewer.tsx
│   │   ├── PageNavigation.tsx
│   │   ├── ThumbnailStrip.tsx
│   │   └── ...
│   ├── processing/          # Processing status components
│   │   ├── FileUpload.tsx
│   │   ├── JobStatusDisplay.tsx
│   │   └── ...
│   └── ui/                  # Reusable UI components
│       ├── Button.tsx
│       ├── Card.tsx
│       └── ...
├── hooks/                   # React hooks
│   ├── usePDFUpload.ts
│   ├── useExtractionJob.ts
│   └── useRegionManagement.ts
├── lib/
│   ├── api-client.ts        # Backend API client
│   └── theme.ts             # Theme configuration
└── types/
    └── api.ts               # TypeScript type definitions
```

## Key Architecture Principles

### Backend

1. **Immutability**
   - DocumentVersions are identified by SHA-256 content hash
   - Claims are append-only with feedback stored separately
   - Evidence bundles are immutable snapshots

2. **Idempotency**
   - MERGE-based atomic operations prevent duplicates
   - Idempotency keys for all write operations
   - Safe retry logic for failed steps

3. **State Machines**
   - ProcessingRuns: pending → in_progress → completed/failed/cancelled
   - StepRuns: pending → in_progress → completed/failed/failed_retryable
   - Validated transitions prevent invalid state changes

4. **Provenance**
   - Every entity tracks created_at, updated_at timestamps
   - User IDs captured for all mutations
   - Full audit trails for compliance

### Frontend

1. **Component Hierarchy**
   - Pages → Feature components → UI primitives
   - Hooks for state management and API interaction
   - Reusable UI components for consistency

2. **State Management**
   - Custom hooks for complex interactions
   - React state for UI state
   - API client for server state

## Documentation

- `docs/IMPLEMENTATION_COMPLETE.md` - Implementation summary
- `docs/README_DEMO.md` - Demo script usage
- `docs/architecture/` - Architecture diagrams and details
- `docs/guides/` - Developer guides
- `docs/legacy/` - Historical documentation

## Development Workflow

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Testing

```bash
cd backend
pytest tests/

cd frontend
npm test
```

## Deployment

See `docs/guides/` for deployment instructions:
- Cloud Run deployment
- BigQuery schema setup
- GCS bucket configuration
- Document AI processor setup
