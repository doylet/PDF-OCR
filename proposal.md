Below is a **Copilot-ready specification** you can paste directly into your repo (e.g. `DATA_HERO_SPEC.md`) or into a Copilot “system prompt / project brief”.

It is structured to do **exactly** what you asked:

1. Give **context, vision, and architectural decisions**
2. Provide a **concrete execution plan with tasks**
3. Make clear **what not to do yet**

It is intentionally explicit, opinionated, and non-agentic-hand-wavey.

---

# Data Hero MVP — Specification, Plan, and Task Breakdown

## 1. Context & Vision (Read First)

### What this project is

This project is evolving into **Data Hero**:
a B2B system for **trusted, traceable analysis of unstructured financial documents**.

The core problem:

* Service managers and risk/compliance teams must make high-stakes decisions
* Inputs are fragmented, inconsistent documents (PDFs, spreadsheets, scans)
* Existing “document AI” tools extract data but **cannot prove where it came from or why it’s correct**

**Data Hero’s differentiator** is not better OCR.
It is **defensible lineage**: every output can be traced back to exact document bytes, processing steps, models, and evidence spans.

---

### What the MVP must prove

The MVP must demonstrate that:

* Documents are **immutable, versioned, and identifiable**
* Processing is **idempotent and replayable**
* Extracted data is represented as **Claims with evidence**
* Users can **click any value and see exactly where it came from**
* Multiple documents can be grouped into a **Room**
* The system can show **set completeness** (what’s present vs missing)

If these are true, Data Hero works — even without advanced ML or LLM synthesis.

---

## 2. Core Architectural Decisions (Non-negotiable)

These are deliberate decisions. Copilot should not “simplify them away”.

### 2.1 Immutable document identity

* Every uploaded file is hashed (SHA-256)
* The hash is the `DocumentVersion.id`
* The same bytes must always map to the same version
* Reprocessing never overwrites prior results

**Why:** deduplication, replay, auditability

---

### 2.2 State machine–driven processing

* Document processing is modeled as **ProcessingRuns**
* Each stage is a **StepRun**
* StepRuns have:

  * step name
  * idempotency key
  * model/tool version
  * parameters hash
  * output references

**Why:** retries, failure isolation, regulatory traceability

---

### 2.3 Idempotency everywhere

* Step execution must be safe to retry
* Same inputs + same model/version = same logical result
* Idempotency key = hash(doc_version + step + model + params)

**Why:** distributed systems fail; trust systems must not

---

### 2.4 Claims, not “results”

* The atomic unit of truth is a **Claim**
* A Claim always includes:

  * value
  * confidence
  * source span (page + bounding box)
  * originating document version
  * producing step + model version

Everything else (normalized values, graphs, insights) is derived from Claims.

**Why:** explainability and defensibility

---

### 2.5 Separation of concerns

* **Profiling** measures documents (skew, tables, quality)
* **Extraction** produces claims
* **Normalization / graphing** happens later
* **LLMs do not invent facts**

---

## 3. MVP Scope (Explicit)

### Included

* Rooms (workspace for a decision)
* Multiple documents per room
* Document profiling (meta map)
* Claim extraction for at least one document type
* Claim viewer with click-to-evidence
* Set completeness (expected vs present)
* Full lineage from output → document bytes

### Explicitly excluded (for now)

* Advanced agent planning
* Full graph database
* LLM-generated insights
* Perfect extraction accuracy

---

## 4. Domain Model (Minimal but Correct)

### Core entities

* `Room`
* `Document`
* `DocumentVersion` (immutable, hash-based)
* `DocumentProfile`
* `ProcessingRun`
* `StepRun`
* `Claim`
* `SetTemplate`
* `SetCompletenessStatus`

These live in:

```
backend/app/models/domain.py
```

---

## 5. System Flow (End-to-End)

1. User creates or enters a **Room**
2. User uploads documents into the Room
3. System computes document hash → `DocumentVersion`
4. System starts a `ProcessingRun`
5. Steps execute (idempotently):

   * PROFILE
   * EXTRACT
   * FORMAT / STORE
6. Extraction emits **Claims**
7. Claims are viewable and evidence-linked in UI
8. Room evaluates **set completeness**

---

## 6. Execution Plan (Backend)

### Phase 0 — Harden existing pipeline (Foundation)

**Goal:** traceable, replayable processing

Tasks:

* Add document content hashing
* Introduce `ProcessingRun` and `StepRun`
* Add idempotency keys to extraction paths
* Persist all intermediate artifacts with references

---

### Phase 1 — Document Profile service

**Goal:** meta map + routing justification

Tasks:

* Create `/api/documents/{doc_version_id}/profile`
* Measure:

  * page count
  * born-digital vs scan
  * skew / quality
  * table count + bounding boxes
* Persist `DocumentProfile`
* Attach profile to ProcessingRun

---

### Phase 2 — Claims

**Goal:** atomic, evidence-linked facts

Tasks:

* Define `Claim` model
* Convert current extraction outputs into Claims
* Store claims with:

  * value
  * confidence
  * page + bbox
  * producing step
* Add `/api/claims` query endpoint

---

### Phase 3 — Rooms & completeness

**Goal:** “Room” concept becomes real

Tasks:

* Create Room CRUD
* Attach DocumentVersions to Rooms
* Define simple SetTemplates (rules-based)
* Evaluate completeness (expected vs present)

---

## 7. Execution Plan (Frontend)

### Minimal UI changes only

1. **Rooms**

   * Create/select room
   * Upload documents into room

2. **Claims panel**

   * List claims for selected document
   * On click → highlight bounding box in PDF viewer
   * Show confidence + provenance

3. **Completeness widget**

   * Display “X of Y artefacts present”
   * Explicitly list missing items

Reuse existing PDF overlay and region-rendering logic wherever possible.

---

## 8. Task Breakdown (Copilot-Executable)

### Backend

* [ ] Add document hashing service
* [ ] Create `ProcessingRun` / `StepRun` models
* [ ] Implement idempotency key helper
* [ ] Wrap extraction in ProcessingRuns
* [ ] Implement DocumentProfile service
* [ ] Create Claim model + persistence
* [ ] Emit claims from extraction
* [ ] Create Rooms API
* [ ] Implement Set completeness evaluator

### Frontend

* [ ] Add Room state
* [ ] Wire uploads to Rooms
* [ ] Add Claims panel
* [ ] Add claim → PDF highlight interaction
* [ ] Add completeness summary widget

---

## 9. Guardrails for Copilot (Very Important)

Copilot **must not**:

* Collapse multiple steps into one “job”
* Overwrite prior results
* Invent data without evidence
* Remove provenance fields for convenience
* Optimize away idempotency or state records

Copilot **should**:

* Prefer explicit data models over clever abstractions
* Preserve intermediate artifacts
* Treat uncertainty as first-class
* Favor traceability over elegance

---

## 10. Success Criteria (MVP “Done”)

The MVP is successful if:

> A user can point at any extracted value and the system can show
> the original document, page, bounding box, processing step, and model version that produced it — and prove whether the document set was complete at the time of the decision.

That is **Data Hero**.

---

If you want, next I can:

* Compress this into a **single Copilot system prompt**
* Convert the task breakdown into **GitHub Issues**
* Or create a **repo-level TODO map** aligned to your current files
