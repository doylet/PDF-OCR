# Feature Specification: Data Hero Backend MVP - All Epics

**Feature Branch**: `001-backend-epics-gcp`  
**Created**: 2025-12-17  
**Status**: Draft  
**Input**: Implement all backend epics for Data Hero MVP with GCP infrastructure including BigQuery for persistence, covering document versioning, processing runs, profiling, claims extraction, rooms, and evidence bundles

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Traceable Document Processing (Priority: P1)

Service managers upload PDF documents and receive extraction results where every piece of data can be traced back to its exact source location in the original document, including which processing step and model version produced it.

**Why this priority**: Core differentiator for Data Hero - defensible lineage is the foundation of trust. Without this, the product has no competitive advantage.

**Independent Test**: Upload a single PDF, extract data, and verify that clicking any extracted value shows: original document hash, page number, bounding box coordinates, processing step ID, and model version used.

**Acceptance Scenarios**:

1. **Given** a PDF document is uploaded, **When** the system processes it, **Then** a unique immutable DocumentVersion ID (SHA-256 hash) is created and stored in BigQuery
2. **Given** a document is being processed, **When** any extraction step executes, **Then** a ProcessingRun record is created with unique ID, timestamp, and document version reference
3. **Given** an extraction step completes, **When** results are generated, **Then** each StepRun record includes idempotency key, model version, parameters hash, and output references
4. **Given** the same document is uploaded twice, **When** hash is computed, **Then** the system recognizes it as the same DocumentVersion and reuses existing processing results
5. **Given** a processing step fails and retries, **When** retry occurs with same inputs, **Then** idempotency key prevents duplicate processing and returns cached results

---

### User Story 2 - Evidence-Backed Claims (Priority: P1)

Users view extracted data as individual claims where each claim displays its confidence score and can be clicked to highlight the exact text span and bounding box on the original PDF page.

**Why this priority**: Claims are the atomic unit of truth in Data Hero. Without claims + evidence, the system cannot prove where data came from.

**Independent Test**: View extracted data in UI, click any value, and verify PDF viewer jumps to correct page and highlights exact bounding box where that value was extracted.

**Acceptance Scenarios**:

1. **Given** a document contains extractable data, **When** processing completes, **Then** system creates Claim records in BigQuery with value, type, confidence, page number, bounding box, and source document version
2. **Given** multiple extraction agents process the same document, **When** they produce overlapping claims, **Then** each claim references the specific StepRun and model version that produced it
3. **Given** a claim is viewed in the UI, **When** user clicks the claim, **Then** system retrieves the source span (page + bbox) and highlights it on the PDF
4. **Given** an extraction has low confidence, **When** claim is created, **Then** confidence score between 0-1 is stored and displayed to users
5. **Given** claims are queried, **When** filtering by document, room, or claim type, **Then** BigQuery efficiently returns matching claims with evidence references

---

### User Story 3 - Document Profiling for Routing (Priority: P2)

System automatically analyzes uploaded documents to produce a meta-profile including page count, quality assessment, table detection, and skew measurements, which informs routing decisions for subsequent processing.

**Why this priority**: Enables intelligent routing and early detection of quality issues. Improves extraction accuracy but not strictly required for MVP functionality.

**Independent Test**: Upload a variety of PDFs (born-digital, scanned, skewed, low-quality) and verify each receives a DocumentProfile with accurate quality scores and routing recommendations.

**Acceptance Scenarios**:

1. **Given** a PDF is uploaded, **When** profiling runs, **Then** DocumentProfile is created in BigQuery with page count, born-digital detection, quality score, and table count
2. **Given** a document is scanned with skew, **When** profiling analyzes it, **Then** per-page skew angles are measured and stored in the profile
3. **Given** a document contains tables, **When** table detection runs, **Then** coarse table bounding boxes are identified and counted
4. **Given** a profile indicates poor quality, **When** extraction routing occurs, **Then** system selects appropriate extraction method (e.g., enhanced OCR for scans)
5. **Given** profile creation completes, **When** stored in BigQuery, **Then** profile JSON artifact is also stored in GCS with reference link

---

### User Story 4 - Multi-Document Rooms (Priority: P2)

Users create a "Room" representing a decision context (e.g., loan application, compliance review) and upload multiple related documents into that room, viewing them as a cohesive set.

**Why this priority**: Enables multi-document analysis which is core to Data Hero's value proposition, but simpler single-doc flows work first.

**Independent Test**: Create a room, upload 3 different PDFs to it, and verify all documents are associated with the room and queryable as a set.

**Acceptance Scenarios**:

1. **Given** a user needs to analyze multiple documents, **When** they create a Room, **Then** a Room record is created in BigQuery with unique ID, name, and creation timestamp
2. **Given** a Room exists, **When** documents are uploaded to it, **Then** DocumentVersion records are linked to the Room via junction table
3. **Given** multiple documents exist in a Room, **When** user views the Room, **Then** all associated documents are listed with their profiles and processing status
4. **Given** a Room contains documents of different types, **When** querying Room data, **Then** claims from all documents can be retrieved and filtered by document type
5. **Given** a Room is deleted, **When** deletion occurs, **Then** Room record is marked as deleted but DocumentVersions and Claims remain intact for audit trail

---

### User Story 5 - Set Completeness Validation (Priority: P3)

System evaluates whether a Room contains all expected document types based on predefined templates (e.g., "Bank Statement Set" requires statement, ledger, invoice) and shows what's missing.

**Why this priority**: Important for compliance workflows but can be added after core extraction works. Users can manually verify completeness initially.

**Independent Test**: Define a SetTemplate requiring 3 document types, upload only 2 matching documents to a room, and verify system reports 67% complete with specific missing document type.

**Acceptance Scenarios**:

1. **Given** SetTemplates are defined (e.g., "Bank Statement Set"), **When** stored in BigQuery, **Then** each template lists required document roles and expected count
2. **Given** a Room is associated with a SetTemplate, **When** completeness is evaluated, **Then** system compares present document roles against required roles
3. **Given** a Room is missing required documents, **When** completeness check runs, **Then** system returns percentage complete and lists specific missing roles
4. **Given** documents are classified by role (rules-based initially), **When** classification runs, **Then** document role is stored in DocumentProfile
5. **Given** completeness status changes, **When** documents are added/removed, **Then** SetCompletenessStatus record is updated in BigQuery with timestamp

---

### User Story 6 - Evidence Bundles for LLM Synthesis (Priority: P3)

System can retrieve a bounded EvidenceBundle containing relevant claims with citations and source spans for a given Room and query, preparing for future LLM-based synthesis.

**Why this priority**: Prepares infrastructure for future LLM features but not needed for MVP extraction and lineage demonstration.

**Independent Test**: Query a Room with a question like "What is the total amount?" and verify system returns structured EvidenceBundle with matching claims, confidence scores, and source references.

**Acceptance Scenarios**:

1. **Given** a Room contains multiple claims, **When** an evidence query is submitted, **Then** system retrieves relevant claims based on query keywords or semantic matching
2. **Given** retrieved claims, **When** evidence bundle is constructed, **Then** bundle includes claim values, confidence scores, source spans (page + bbox), and document version references
3. **Given** an evidence bundle exceeds size limits, **When** bundle is returned, **Then** claims are ranked by relevance and confidence, returning top N results
4. **Given** evidence bundles are queried frequently, **When** queries run, **Then** BigQuery efficiently handles filtering and sorting by room, document, claim type, and confidence
5. **Given** evidence bundle is prepared for LLM, **When** formatted, **Then** output includes structured JSON with all provenance metadata preserved

---

### Edge Cases

- What happens when identical documents are uploaded to different Rooms? System recognizes same DocumentVersion hash and reuses processing results but creates separate Room associations.
- How does system handle corrupted or invalid PDFs? Processing fails gracefully, creates failed ProcessingRun record, and returns error to user with specific failure reason.
- What if processing is interrupted mid-stream? StepRun records track completion status; system can resume from last completed step using idempotency keys.
- How are concurrent uploads of the same document handled? First upload computes hash and creates DocumentVersion; subsequent uploads detect existing hash and link to same version.
- What happens when model versions change? New model version in StepRun parameters creates different idempotency key, allowing reprocessing with new model while preserving old results.
- How does system handle documents with hundreds of pages? Processing is chunked by page ranges; Claims reference specific pages; BigQuery handles large claim volumes efficiently.
- What if BigQuery is temporarily unavailable? System queues operations with retry logic; critical path operations fail fast with error messages to users.

## Requirements *(mandatory)*

### Functional Requirements

#### Epic A: Foundational Identity & Storage

- **FR-001**: System MUST compute SHA-256 hash of uploaded document bytes and use hash as immutable DocumentVersion ID
- **FR-002**: System MUST store DocumentVersion records in BigQuery with hash, upload timestamp, file size, and GCS URI
- **FR-003**: System MUST detect duplicate documents by comparing hashes before reprocessing
- **FR-004**: System MUST preserve original uploaded bytes in GCS with immutable storage policy
- **FR-005**: System MUST maintain separate Document entity (user-facing name/metadata) from DocumentVersion (immutable content)

#### Epic B: Processing Runs & Step Runs

- **FR-006**: System MUST create a ProcessingRun record for every document processing pipeline execution with unique ID, DocumentVersion reference, start time, and status
- **FR-007**: System MUST create StepRun records for each processing stage with step name, idempotency key, start time, end time, status, and output references
- **FR-008**: System MUST compute idempotency key as hash of (DocumentVersion ID + step name + model version + parameters)
- **FR-009**: System MUST check idempotency key before executing any step and return cached results if key exists
- **FR-010**: System MUST store all intermediate artifacts in GCS with references in StepRun records
- **FR-011**: System MUST record model/tool version used for each StepRun in BigQuery
- **FR-012**: System MUST support retry of failed steps without duplicating successful steps
- **FR-013**: System MUST track processing state machine transitions (pending → running → completed/failed)

#### Epic C: Document Profiling

- **FR-014**: System MUST create DocumentProfile for each DocumentVersion containing page count, born-digital detection, quality score, and table count
- **FR-015**: System MUST measure per-page skew angles for scanned documents and store in DocumentProfile
- **FR-016**: System MUST detect and count tables with coarse bounding box coordinates
- **FR-017**: System MUST classify documents as born-digital or scanned based on image analysis
- **FR-018**: System MUST store DocumentProfile in BigQuery and full profile JSON artifact in GCS
- **FR-019**: System MUST expose profiling results via API endpoint for routing decisions

#### Epic D: Claims Extraction

- **FR-020**: System MUST extract data as Claim records with value, type, confidence (0-1), page number, bounding box, and source DocumentVersion reference
- **FR-021**: System MUST link each Claim to the producing StepRun ID and model version
- **FR-022**: System MUST store Claims in BigQuery with indexed fields for efficient querying
- **FR-023**: System MUST preserve source span text for each claim where available
- **FR-024**: System MUST support claim types including: text, number, date, table_cell, and custom types
- **FR-025**: System MUST handle multiple overlapping claims from different extraction agents for the same content
- **FR-026**: System MUST expose Claims via API endpoint supporting filters by Room, Document, type, and confidence threshold

#### Epic E: Rooms & Set Completeness

- **FR-027**: System MUST create Room records in BigQuery with unique ID, name, creation timestamp, and optional SetTemplate reference
- **FR-028**: System MUST associate DocumentVersions with Rooms via junction table allowing many-to-many relationships
- **FR-029**: System MUST define SetTemplate records in BigQuery listing required document roles and expected counts
- **FR-030**: System MUST classify documents by role using rules-based matching and store in DocumentProfile
- **FR-031**: System MUST evaluate Room completeness by comparing present document roles against SetTemplate requirements
- **FR-032**: System MUST store SetCompletenessStatus records with percentage complete, missing roles, and evaluation timestamp
- **FR-033**: System MUST expose Rooms API for CRUD operations and document association

#### Epic F: Evidence Bundles

- **FR-034**: System MUST support evidence queries against Rooms with keyword or semantic filtering
- **FR-035**: System MUST construct EvidenceBundle containing relevant Claims with full provenance metadata
- **FR-036**: System MUST rank claims by relevance and confidence when building evidence bundles
- **FR-037**: System MUST limit evidence bundle size and return top N results based on ranking
- **FR-038**: System MUST preserve all lineage information (DocumentVersion, StepRun, model version) in evidence bundle output
- **FR-039**: System MUST format evidence bundles as structured JSON suitable for LLM consumption

#### Cross-Cutting Requirements

- **FR-040**: System MUST use BigQuery as primary persistence layer for all structured data (Rooms, Documents, DocumentVersions, ProcessingRuns, StepRuns, Claims, Profiles, SetTemplates, SetCompletenessStatus)
- **FR-041**: System MUST use Google Cloud Storage for all document bytes and artifact storage
- **FR-042**: System MUST implement partition and clustering strategies in BigQuery for efficient queries on large datasets
- **FR-043**: System MUST expose RESTful API endpoints for all user-facing operations
- **FR-044**: System MUST implement proper error handling with specific error codes and messages
- **FR-045**: System MUST log all processing activities to Google Cloud Logging for audit trail

### Key Entities

- **Room**: Workspace representing a decision context (loan review, compliance audit); contains multiple documents; optionally linked to SetTemplate
- **Document**: User-facing document entity with name, upload timestamp, user metadata; links to one or more DocumentVersions
- **DocumentVersion**: Immutable content identified by SHA-256 hash; references GCS URI; has one DocumentProfile; produces multiple Claims
- **DocumentProfile**: Metadata about document quality and structure (page count, born-digital flag, skew, tables, quality score); used for routing
- **ProcessingRun**: Represents one execution of the processing pipeline for a DocumentVersion; contains multiple StepRuns; tracks overall status
- **StepRun**: Represents execution of one processing stage; has idempotency key, model version, parameters, status, and output references
- **Claim**: Atomic unit of extracted data; has value, type, confidence, source span (page + bbox + text), producing StepRun reference, DocumentVersion reference
- **SetTemplate**: Defines expected document types for a Room category (e.g., "Bank Statement Set" requires statement + ledger + invoice)
- **SetCompletenessStatus**: Evaluation result for a Room against its SetTemplate; includes percentage complete, missing roles, evaluation timestamp
- **EvidenceBundle**: Query result containing relevant Claims with full provenance for LLM synthesis or user review

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can upload a document and view any extracted value with its exact source location highlighted on the PDF within 3 clicks
- **SC-002**: System processes documents idempotently - uploading identical document twice results in zero duplicate processing work
- **SC-003**: Every extracted claim includes confidence score, page number, bounding box coordinates, and originating model version - 100% provenance coverage
- **SC-004**: System handles documents up to 100 pages with extraction completing in under 5 minutes for standard quality PDFs
- **SC-005**: BigQuery efficiently queries claims across rooms containing 1000+ documents with results returned in under 2 seconds
- **SC-006**: Document profiling correctly identifies born-digital vs scanned documents with 95%+ accuracy
- **SC-007**: Set completeness evaluation correctly identifies missing document types with 90%+ accuracy using rules-based classification
- **SC-008**: Processing failures are traceable - failed StepRuns contain specific error messages and logs accessible for debugging
- **SC-009**: System supports 100 concurrent document uploads without processing queue delays exceeding 30 seconds
- **SC-010**: All intermediate processing artifacts are retained in GCS for audit and replay - 100% retention for 90 days minimum

## Assumptions

- GCP project is configured with BigQuery dataset and GCS buckets before backend deployment
- Document AI API and other required GCP services have appropriate quotas enabled
- BigQuery schema migrations will be managed via scripts in the repository
- Initial SetTemplates will be defined as configuration/code rather than user-configurable UI
- Document role classification starts with simple rules-based matching (filename patterns, basic content analysis) before ML-based classification
- Evidence bundle queries will use keyword matching initially; semantic search can be added later with embeddings
- Users authenticate via existing mechanism; no new auth requirements for these epics
- Frontend changes required to consume new APIs are out of scope for this backend specification
- Performance targets assume standard GCP service SLAs and appropriate resource allocation

## Dependencies

- Google Cloud Platform project with enabled APIs: BigQuery, Cloud Storage, Document AI, Cloud Logging
- Existing Document AI processor configuration for OCR and layout analysis
- Existing upload mechanism delivering PDF bytes to backend service
- PDF rendering library or service for extracting bounding box coordinates during profiling
- BigQuery dataset created with appropriate permissions for backend service account
- GCS buckets created with lifecycle policies for artifact retention
- Existing authentication/authorization mechanism for API endpoints

## Scope Boundaries

### In Scope

- All six backend epics (A through F) as described in Requirements section
- BigQuery schema design and table creation
- GCS artifact storage patterns
- RESTful API endpoints for Rooms, Documents, Claims, Profiles, Evidence Bundles
- Idempotency and retry logic for processing steps
- Basic document role classification (rules-based)
- Profiling using PDF analysis and existing Document AI outputs

### Out of Scope

- Frontend UI changes (separate feature/epic)
- Advanced ML-based document classification
- LLM-based evidence synthesis (infrastructure only in MVP)
- Real-time collaboration features in Rooms
- User permission management for Rooms
- Advanced semantic search with embeddings
- GraphQL API (REST only for MVP)
- Webhook notifications for processing completion
- Bulk document upload optimization
- Document version comparison/diff functionality

## Technical Constraints

- Must use Google BigQuery for all structured data persistence (Firestore explicitly excluded per requirement)
- Must use Google Cloud Storage for document bytes and processing artifacts
- Must maintain backward compatibility with existing `/api/extract` and `/api/extract/agentic` endpoints during migration
- Must support idempotent retry without external distributed locking service (use BigQuery transactions)
- BigQuery tables must be designed for efficient querying at scale (partitioning by date, clustering by document/room ID)
- Processing artifacts in GCS must include version/timestamp in path to prevent overwrites
- API responses must complete within 30 seconds; long-running processing uses async jobs
- All timestamps must be stored in UTC with timezone information

## Architectural Decisions

The following design decisions were resolved during specification clarification:

### 1. Processing Concurrency Model
**Decision**: Hybrid approach - synchronous for profiling, asynchronous for extraction

**Rationale**: Balances user experience with system complexity. Document profiling completes quickly and provides immediate feedback to users about document quality and routing decisions. Heavy extraction work happens asynchronously via Cloud Tasks, allowing the system to handle large documents and high concurrency without blocking API responses.

**Implementation Notes**:
- Profiling endpoint returns results synchronously within 5-10 seconds
- Extraction processing uses Cloud Tasks queue with job polling API
- Frontend polls for extraction job completion status
- ProcessingRun status tracks async job lifecycle

### 2. BigQuery Schema Approach
**Decision**: Fully normalized with separate tables and joins

**Rationale**: Standard SQL patterns make queries more intuitive and flexible. Separate tables for all entities (Rooms, Documents, DocumentVersions, ProcessingRuns, StepRuns, Claims, Profiles) provide clearer relationships, easier filtering, and better support for complex queries. While this requires more tables to manage, it aligns with traditional relational database best practices and makes the schema easier to understand and maintain.

**Implementation Notes**:
- All entities in separate BigQuery tables with foreign key relationships
- `claims` table: references document_version_id, room_id, step_run_id
- `step_runs` table: references processing_run_id, includes idempotency_key column
- `processing_runs` table: references document_version_id
- Partitioned by date fields, clustered by primary foreign keys
- Standard JOIN operations for querying related data

### 3. Idempotency Key Storage
**Decision**: Separate idempotency_keys table with indexes

**Rationale**: Dedicated table optimized for fast lookups provides best performance for deduplication checks without adding external dependencies. The table can be heavily indexed and optimized specifically for the idempotency use case, with separate retention policies from StepRuns if needed.

**Implementation Notes**:
- `idempotency_keys` table: columns for key (hash), step_run_id, created_at
- Clustered by idempotency key for O(log n) lookups
- Before executing step: query this table by key
- After step completion: insert key + step_run_id atomically
- Optional: separate retention policy (e.g., 90 days vs longer StepRun retention)
