<!--
Sync Impact Report (Version N/A → 1.0.0):
- Constitution Version: Initial creation from template
- Modified Principles: None (initial creation)
- Added Sections: All core principles (I-VII), Technology Standards, Data & Processing Integrity, Governance
- Removed Sections: None
- Templates Requiring Updates: 
  ✅ .specify/templates/plan-template.md - Constitution Check section present and aligned
  ✅ .specify/templates/spec-template.md - Requirements structure uses MUST/mandatory aligned with constitution
  ✅ .specify/templates/tasks-template.md - Task categorization supports principle-driven development (user stories, tests)
  ✅ .github/prompts/*.md - Verified no agent-specific names (CLAUDE, etc.) - all generic
- Follow-up TODOs: None - all placeholders resolved based on:
  * proposal.md: Data Hero vision and architectural decisions
  * specs/001-backend-epics-gcp/spec.md: Current feature specification
  * README.md: Technology stack and infrastructure
  * Project structure: GCP-native architecture with FastAPI/Next.js
-->


# Data Hero Constitution

## Core Principles

### I. Immutable Document Identity (NON-NEGOTIABLE)
Every uploaded document MUST be hashed using SHA-256 to create an immutable DocumentVersion ID. The same byte sequence MUST always map to the same version identifier. Reprocessing MUST never overwrite prior results. Documents MUST be preserved in their original form in Google Cloud Storage with immutable storage policies.

**Rationale**: Deduplication, replay capability, and regulatory auditability depend on immutable identity. Without this, the system cannot guarantee defensible lineage.

### II. State Machine-Driven Processing (NON-NEGOTIABLE)
All document processing MUST be modeled as ProcessingRuns containing StepRuns. Each StepRun MUST record: step name, idempotency key, model/tool version, parameters hash, and output references. Processing state transitions MUST be tracked (pending → running → completed/failed). No processing logic may bypass this state machine.

**Rationale**: Enables retry, failure isolation, and regulatory traceability. Distributed systems fail; trust systems must be resilient.

### III. Idempotency Everywhere (NON-NEGOTIABLE)
Every processing step MUST be safe to retry. Same inputs + same model version MUST produce the same logical result. Idempotency keys MUST be computed as hash(document_version + step + model + parameters). Before executing any step, the system MUST check for existing results using the idempotency key and return cached results if found.

**Rationale**: Network failures and retries are inevitable. Data integrity requires guaranteed idempotent operations.

### IV. Claims-Based Evidence
The atomic unit of extracted data MUST be a Claim. Every Claim MUST include: value, confidence score (0-1), source span (page + bounding box), originating DocumentVersion reference, producing StepRun ID, and model version. No extracted data may be surfaced to users without complete provenance metadata. All derivative data (normalized values, graphs, insights) MUST be traceable to source Claims.

**Rationale**: Explainability and defensibility are the product's core value proposition. Without evidence-backed claims, Data Hero is just another extraction tool.

### V. Separation of Processing Concerns
Document processing MUST separate: (1) Profiling - measuring document quality, structure, and routing metadata; (2) Extraction - producing Claims with evidence; (3) Normalization - deriving structured data from Claims; (4) Synthesis - LLM-based insights that never invent facts. These stages MUST not be collapsed. LLMs MUST only work with existing Claims and MUST NOT generate data without evidence.

**Rationale**: Clear boundaries enable testing, debugging, and reasoning about system behavior. Prevents hallucination and data fabrication.

### VI. GCP-Native Infrastructure
All structured data MUST persist in Google BigQuery with proper partitioning and clustering. All binary artifacts (PDFs, processing outputs) MUST persist in Google Cloud Storage. Async processing MUST use Cloud Tasks. Caching (when needed) MUST use Cloud Memorystore. No alternative persistence layers (Firestore, self-hosted databases) may be introduced without constitutional amendment. Schema design MUST favor normalized tables over nested structures for queryability.

**Rationale**: GCP services provide scalability, audit trails, and compliance capabilities required for B2B financial document processing. Consistency prevents operational fragmentation.

### VII. Observability & Audit Trail
All processing activities MUST be logged to Google Cloud Logging with structured metadata. All errors MUST include context (document ID, step, model version). All intermediate artifacts MUST be retained for minimum 90 days. System MUST support complete replay of any processing pipeline from original document bytes. No processing step may execute without creating audit records.

**Rationale**: Trust systems require complete observability. Debugging and compliance depend on comprehensive audit trails.

## Technology Standards

### Backend Requirements
- Python 3.11+ with FastAPI framework
- Pydantic for all data models and validation
- BigQuery client libraries for persistence
- GCS client libraries for artifact storage
- Cloud Tasks for async job processing
- Structured logging (JSON format) for all operations
- Type hints required for all function signatures
- No ORMs - direct BigQuery SQL for transparency

### Frontend Requirements
- Next.js 14+ with TypeScript
- PDF.js for document rendering
- Canvas-based region selection for evidence highlighting
- RESTful API consumption (no GraphQL in MVP)
- Polling for async job status (no websockets in MVP)
- Type-safe API client with explicit error handling

### Data Schema Standards
- All timestamps in UTC with timezone information
- All IDs as strings (UUIDs or content hashes)
- All BigQuery tables partitioned by date field
- All BigQuery tables clustered by primary query key (document_version_id, room_id)
- Foreign key relationships explicitly documented in schema comments
- No soft deletes - use status flags with timestamps

## Data & Processing Integrity

### Version Control
- All model versions MUST be recorded in StepRun metadata
- Model version changes MUST create new idempotency keys
- Old processing results MUST be preserved when reprocessing with new models
- API versioning follows semantic versioning (MAJOR.MINOR.PATCH)
- Breaking API changes require MAJOR version bump

### Quality Gates
- Processing failures MUST create failed StepRun records with error details
- Low confidence Claims (< 0.7) MUST be flagged in UI
- Document profiling MUST detect quality issues before extraction
- Set completeness evaluation MUST identify missing required documents
- All extraction outputs MUST include confidence scores

### Security Requirements
- Service account authentication for all GCP services
- No API keys or secrets in code or logs
- All GCS artifacts MUST have access controls
- BigQuery datasets MUST restrict public access
- User authentication required for all frontend operations (existing mechanism)

## Governance

This Constitution supersedes all other development practices and documentation. Any code, architecture, or process that conflicts with these principles MUST be revised to comply.

### Amendment Process
1. Amendments MUST be proposed with rationale and impact analysis
2. Proposed changes MUST be reviewed against existing codebase
3. Breaking changes require MAJOR version bump (X.0.0)
4. New principles require MINOR version bump (x.Y.0)
5. Clarifications/typos require PATCH version bump (x.y.Z)
6. All amendments MUST update this document and sync dependent templates

### Compliance Verification
- All feature specifications MUST pass Constitution Check before implementation
- All pull requests MUST verify compliance with applicable principles
- Non-compliance MUST be explicitly justified or code must be revised
- Complexity that violates simplicity principles MUST be justified with measurable benefits

### Development Guidance
Runtime development guidance is maintained separately in project documentation and .github/copilot-instructions.md. This Constitution defines architectural invariants; guidance defines best practices.

**Version**: 1.0.0 | **Ratified**: 2025-12-17 | **Last Amended**: 2025-12-17
