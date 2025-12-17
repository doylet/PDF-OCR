# Implementation Plan: Data Hero Backend MVP - All Epics

**Branch**: `001-backend-epics-gcp` | **Date**: 2025-12-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-backend-epics-gcp/spec.md`

## Summary

Implements six backend epics for Data Hero MVP: (A) Immutable document versioning with SHA-256 hashing, (B) State machine-driven processing with ProcessingRuns and StepRuns, (C) Document profiling for quality assessment and routing, (D) Evidence-backed Claims extraction with provenance, (E) Multi-document Rooms with set completeness validation, and (F) Evidence bundles for LLM synthesis preparation.

**Core Value**: Defensible lineage - every extracted data point can be traced to exact document bytes, processing steps, model versions, and evidence spans. System uses BigQuery for all structured data, GCS for artifacts, Cloud Tasks for async extraction, and maintains complete audit trails for regulatory compliance.

## Technical Context

**Language/Version**: Python 3.11+ with type hints enforced  
**Primary Dependencies**: FastAPI (web framework), Pydantic (validation), google-cloud-bigquery, google-cloud-storage, google-cloud-tasks, google-cloud-documentai, pytest (testing)  
**Storage**: BigQuery (structured data with normalized schema, partitioning/clustering), Cloud Storage (PDF binaries, OCR outputs, processing artifacts)  
**Testing**: pytest with 80%+ coverage requirement, integration tests against GCP emulators  
**Target Platform**: Linux containers deployed to Cloud Run (stateless, auto-scaling)
**Project Type**: web (RESTful API microservice backend)  
**Performance Goals**: Profiling API <2s (P95), async extraction tracked via job status, 90-day artifact retention  
**Constraints**: GCP-native only (no AWS/Azure), BigQuery queries optimized for partitions/clusters, all operations idempotent  
**Scale/Scope**: MVP supports 1-10 documents per Room, 100s of claims per document, single-tenant initially

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Core Principles Compliance

| Principle | Status | Evidence from Spec |
|-----------|--------|-------------------|
| **I. Immutable Document Identity** | ✅ PASS | FR-001: SHA-256 hashing for DocumentVersion IDs, FR-002: immutable storage in GCS |
| **II. State Machine-Driven Processing** | ✅ PASS | FR-008 to FR-013: ProcessingRuns with StepRuns tracking state transitions, idempotency keys, model versions |
| **III. Idempotency Everywhere** | ✅ PASS | FR-019: hash-based idempotency keys, FR-020: cached results retrieval, separate idempotency_keys table (Arch Decision Q3:A) |
| **IV. Claims-Based Evidence** | ✅ PASS | FR-021 to FR-029: Claims with confidence scores, source spans, provenance metadata, complete audit trails |
| **V. Separation of Processing Concerns** | ✅ PASS | FR-014 to FR-018: Profiling (quality/structure analysis) separate from extraction, LLM synthesis bounded by evidence (FR-040 to FR-043) |
| **VI. GCP-Native Infrastructure** | ✅ PASS | Arch Decision Q2:A: normalized BigQuery schema with partitioning/clustering, GCS for binaries, Cloud Tasks for async (Arch Decision Q1:C) |
| **VII. Observability & Audit Trail** | ✅ PASS | FR-009/FR-013: processing metadata logged, FR-041: 90-day artifact retention, replay capability from original document bytes |

### Technology Standards Compliance

- ✅ **Backend**: Python 3.11+, FastAPI, Pydantic, BigQuery/GCS/Cloud Tasks clients specified
- ✅ **Data Schema**: UTC timestamps (FR-003), string IDs (FR-001: SHA-256), partitioning/clustering (Arch Decision Q2:A), no soft deletes (state flags in FR-009)
- ✅ **Version Control**: Model versions in StepRun metadata (FR-010), old results preserved (FR-013)
- ✅ **Quality Gates**: Failed StepRuns (FR-013), confidence scores (FR-024), profiling before extraction (FR-014), set completeness (FR-034 to FR-037)

### Data & Processing Integrity

- ✅ **Version Control**: All model versions tracked in StepRun metadata (FR-010)
- ✅ **Quality Gates**: Processing failures create failed StepRun records (FR-013), confidence scores included (FR-024)

### Violations/Justifications

**NONE** - All constitutional requirements are satisfied by the specification.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/                           # Python 3.11+ FastAPI microservice
├── app/
│   ├── __init__.py
│   ├── config.py                 # Environment config, GCP project settings
│   ├── dependencies.py           # FastAPI dependencies (auth, clients)
│   │
│   ├── models/                   # Pydantic data models
│   │   ├── __init__.py
│   │   ├── api.py               # Request/response schemas
│   │   └── document_graph.py    # Domain models (Room, Document, DocumentVersion, Claim, etc.)
│   │
│   ├── services/                # Business logic layer
│   │   ├── __init__.py
│   │   ├── documentai.py        # Document AI client wrapper
│   │   ├── storage.py           # GCS operations (upload, artifact retrieval)
│   │   ├── firestore_service.py # BigQuery operations (CRUD for all entities)
│   │   ├── jobs.py              # Cloud Tasks queue operations
│   │   ├── llm_service.py       # LLM synthesis (existing, scope: evidence bundles)
│   │   ├── text_parser.py       # Claim extraction logic
│   │   ├── region_analyzer.py   # Profiling logic (quality assessment)
│   │   └── formatter.py         # Output formatting utilities
│   │
│   ├── routers/                 # FastAPI route handlers (controllers)
│   │   ├── __init__.py
│   │   ├── upload.py            # POST /documents (Epic A: document versioning)
│   │   ├── extraction.py        # POST /processing-runs, GET /processing-runs/{id} (Epic B)
│   │   ├── feedback.py          # POST /claims/{id}/feedback (HITL reinforcement)
│   │   ├── rooms.py             # NEW: POST /rooms, GET /rooms/{id}, POST /rooms/{id}/documents (Epic E)
│   │   ├── profiles.py          # NEW: GET /profiles/{doc_version_id} (Epic C)
│   │   ├── claims.py            # NEW: GET /claims?document_version_id=... (Epic D)
│   │   └── evidence_bundles.py  # NEW: POST /evidence-bundles (Epic F)
│   │
│   └── agents/                  # Existing agentic orchestration
│       ├── __init__.py
│       ├── orchestrator.py      # Multi-agent coordinator (preserved)
│       ├── layout_agent.py      # Layout analysis
│       ├── table_agent.py       # Table extraction
│       ├── schema_agent.py      # Schema inference
│       ├── validator_agent.py   # Validation agent
│       └── structure_gate.py    # Quality gates
│
├── tests/                       # pytest test suite
│   ├── unit/                    # Unit tests (80%+ coverage target)
│   ├── integration/             # Integration tests (GCP emulators)
│   └── conftest.py              # pytest fixtures
│
├── main.py                      # FastAPI application entrypoint
├── requirements.txt             # Python dependencies
└── cloudbuild.yaml              # Cloud Build deployment config

frontend/                         # Next.js 14+ TypeScript (out of scope for this plan)
├── app/
├── components/
├── hooks/
├── lib/
└── types/

```

**Structure Decision**: Web application architecture with FastAPI backend and Next.js frontend. Backend follows layered architecture: models (Pydantic schemas), services (business logic + GCP clients), routers (FastAPI endpoints), agents (existing orchestration preserved). All new entity CRUD operations will extend `firestore_service.py` (note: naming is historical; service now uses BigQuery per constitutional requirement VI). New routers added for Rooms, Profiles, Claims, and Evidence Bundles. Frontend modifications out of scope for this backend-focused plan.

## Complexity Tracking

> **No constitutional violations** - This table is empty. All design choices align with constitution principles.

---

## Phase 0: Research (COMPLETED)

**Objective**: Resolve all unknowns from Technical Context and document existing codebase patterns.

**Outputs**:
- ✅ `research.md` - Complete analysis of existing codebase patterns, architectural decisions, and best practices

**Key Findings**:
- Service layer pattern established (storage, documentai, firestore_service → bigquery_service)
- Pydantic models for API contracts, separate domain models for internal logic
- GCP client initialization via dependencies.py with lazy loading
- Signed URLs for client-side uploads, structured GCS artifact paths
- Document AI integration with region cropping (5% padding)
- BigQuery migration strategy documented (MERGE pattern for idempotency atomicity)
- Normalized schema with partitioning/clustering confirmed optimal for queries
- Hybrid sync/async processing pattern (profiling sync <2s, extraction async via Cloud Tasks)
- State machine pattern with explicit enums required
- Idempotency key lookup via clustered BigQuery table

**No blocking unknowns remain** - All NEEDS CLARIFICATION items resolved.

---

## Phase 1: Design & Contracts (COMPLETED)

**Objective**: Generate data model, API contracts, and quickstart guide.

**Outputs**:
- ✅ `data-model.md` - Complete BigQuery schema with 11 tables, state machine definitions, query patterns
- ✅ `contracts/documents.yaml` - Documents API (Epic A: versioning, deduplication)
- ✅ `contracts/processing-runs.yaml` - ProcessingRuns API (Epic B: state machine, idempotency)
- ✅ `contracts/rooms.yaml` - Rooms API (Epic E: multi-document workspaces, set completeness)
- ✅ `contracts/claims.yaml` - Claims API (Epic D: evidence-backed extraction with immutability)
- ✅ `contracts/evidence-bundles.yaml` - Evidence Bundles API (Epic F: deterministic keyword ranking)
- ✅ `quickstart.md` - Complete setup guide (GCP project, local dev, testing, troubleshooting)
- ✅ `.github/agents/copilot-instructions.md` - Updated agent context with new technologies

**Key Design Decisions Incorporated**:
- **Explicit state machines**: ProcessingRunState (4 states) and StepRunState (5 states) with valid transitions
- **Claim immutability rule**: Claims NEVER updated/deleted, reprocessing creates new Claims
- **Document vs DocumentVersion boundary**: User operations reference Document, processing references DocumentVersion only
- **BigQuery MERGE atomicity**: Idempotency keys use MERGE for check-and-insert pattern
- **Deterministic evidence ranking**: TF-like keyword count → confidence → recency (no embeddings in MVP)

**Constitution Re-check (Post-Design)**:
- ✅ All 7 core principles verified in data model
- ✅ Technology standards matched (Python 3.11+, FastAPI, BigQuery, GCS, Cloud Tasks)
- ✅ Data integrity rules embedded in schema (UTC timestamps, string IDs, partitioning/clustering)
- ✅ No new violations introduced

---

## Phase 2: Task Breakdown (NEXT STEP)

**Command**: `/speckit.tasks` (NOT executed by /speckit.plan)

**Expected Output**: `tasks.md` with granular implementation tasks organized by:
- Epic (A-F)
- Priority (P1, P2, P3)
- Dependencies (foundation → features)
- Estimated effort

**Task Categories**:
1. **Foundation** (must be built first):
   - BigQuery schema creation + seeding
   - BigQuery service layer (replaces firestore_service.py)
   - Idempotency key service
   - State machine validation logic
   - ProcessingRun/StepRun CRUD operations

2. **Epic Implementation** (in priority order):
   - P1: Document versioning API (Epic A)
   - P1: Claims extraction API (Epic D)
   - P2: Document profiling (Epic C)
   - P2: Rooms API (Epic E)
   - P3: Evidence bundles API (Epic F)

3. **Testing**:
   - Unit tests for services
   - Integration tests for BigQuery operations
   - Contract tests for API endpoints
   - E2E tests for user stories

4. **Migration**:
   - Firestore → BigQuery data migration (if applicable)
   - Backward compatibility layer for existing endpoints
   - Deprecation plan for Firestore-based endpoints

---

## Summary

**Planning Status**: ✅ **COMPLETE** (Phases 0-1 finished)

**Artifacts Created**:
- research.md (existing patterns analysis)
- data-model.md (BigQuery schema + state machines)
- 5 API contract files (OpenAPI 3.0 specs)
- quickstart.md (setup & development guide)
- Updated agent context

**Next Action**: User should run `/speckit.tasks` to generate granular implementation tasks in `tasks.md`.

**Branch**: `001-backend-epics-gcp` (ready for implementation)  
**Implementation Ready**: ✅ Yes - All design artifacts complete, no blocking unknowns
