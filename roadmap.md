Absolutely — here’s a **concrete engineering backlog** that’s grounded in your current repo structure, reuses your existing primitives, and gets you to a **Data Hero MVP** with the smallest possible rewiring.

I’m going to give you:

1. **Target MVP scope (“Data Hero Room MVP”)**
2. **New models + where they live**
3. **Backend epics → stories → tasks (with file placements)**
4. **Frontend smallest-changes plan (claim overlays + room sets)**
5. **Cut list (what not to build yet)**

---

# Data Hero MVP scope built on your foundation

**MVP outcomes**

* Upload **multiple documents into a Room**
* System produces a **DocumentProfile** for each document (meta map)
* System extracts **Claims** (value + confidence + source span) from at least one doc type
* UI can **click a claim and highlight evidence** on the PDF (your existing overlay infra)
* Room shows **Set completeness** (expected artefacts vs present docs) at a basic level
* All steps are **traceable + replayable** (ProcessingRun / StepRun + idempotency keys)

---

# 1) New Models (and where they should go)

## Backend placement

You currently have:

* `backend/app/models/api.py` (Pydantic request/response models)
* `backend/app/models/document_graph.py` (internal deterministic IR)

**Recommendation**

* Keep `document_graph.py` as your internal IR.
* Create a new file for domain models that represent Data Hero primitives:

✅ `backend/app/models/domain.py` (Pydantic + dataclasses as needed)

### Models to add

* **Room**
* **Document**
* **DocumentVersion**
* **DocumentProfile**
* **ProcessingRun**
* **StepRun**
* **Claim**
* **RoomSetTemplate** (or just `SetTemplate`)
* **SetCompletenessStatus**

> Note: Don’t over-model “graph” yet. In MVP, your “graph” can be edges derived from claims later. Start with Claims + Evidence + Sets.

---

# 2) Backend roadmap as epics → stories → tasks

## Epic A — Foundational Identity + Storage Contracts

### A1 — DocumentVersion hashing (immutable identity)

**Stories**

* Compute `sha256` for uploaded bytes and store as `document_version_id`
* Preserve current `pdf_id` so you don’t break the frontend

**Tasks**

* Add `StorageService.download_pdf()` call to a new “register document version” step
* Add new service:

  * ✅ `backend/app/services/documents.py` (Document registry + hashing + versioning)
* Create Firestore collections:

  * `rooms`, `documents`, `document_versions`

**Implementation notes**

* First pass can hash on-demand when processing starts (avoid upload callback complexity).

---

## Epic B — Processing runs + step runs (state + idempotency)

### B1 — Introduce ProcessingRun / StepRun records

**Stories**

* Every pipeline action becomes a `ProcessingRun`
* Every stage becomes a `StepRun` with idempotency key

**Tasks**

* Create service:

  * ✅ `backend/app/services/runs.py`
* Add Firestore collections:

  * `processing_runs`, `step_runs`
* Add helper:

  * `compute_idempotency_key(doc_version_id, step, model_version, params_hash)`
* Update `routers/extraction.py`:

  * Wrap both `/api/extract` and `/api/extract/agentic` in a `ProcessingRun`
  * Emit StepRuns for: `DOWNLOAD`, `PROFILE` (stub for now), `EXTRACT`, `FORMAT`, `UPLOAD_RESULT`

**Where to touch**

* `backend/app/routers/extraction.py`
* `backend/app/services/jobs.py` (optional: jobs can become “views” over processing runs later)

---

## Epic C — Document Profile service (your “meta map”)

### C1 — Add `/api/documents/{doc_version_id}/profile`

**Stories**

* Produce a profile that includes:

  * born-digital vs scanned heuristic
  * page count
  * skew (per page)
  * table count + bboxes (coarse)
  * quality risk score + routing hints

**Tasks**

* Add router:

  * ✅ `backend/app/routers/documents.py`
* Add service:

  * ✅ `backend/app/services/profiling.py`
* Persist output:

  * `DocumentProfile` stored in Firestore + optionally JSON artifact in GCS (like your `_graph`)
* Minimal implementation approach:

  * use PDF rendering + basic image metrics first
  * table detection can be “cheap” initially (Document AI layout or your existing region detectors)

**Why this fits your code**

* You already persist debug artifacts; a profile is just a formalized artifact + summary.

---

## Epic D — Claims: the atomic unit of truth

### D1 — Introduce Claims and emit them from current extraction outputs

**Stories**

* Convert extraction outputs into Claims (even if simplistic)
* Claims must include evidence: page + bbox + originating doc_version_id

**Tasks**

* Create model:

  * `Claim { claim_id, doc_version_id, value, type, confidence, span:{page,bbox,text?}, produced_by_step_run_id }`
* Create service:

  * ✅ `backend/app/services/claims.py` (CRUD + query by room/doc)
* Update extraction paths:

  * Non-agentic path (`process_extraction`) should emit claims per region/table cell where possible
  * Agentic path should map `DocumentGraph.extractions` → claims with evidence:

    * use `Region.bbox` + `Region.page`
    * optional: attach token text evidence later

**Where to touch**

* `backend/app/routers/extraction.py`
* `backend/app/models/document_graph.py` (small additions: optional “span text” references if desired)

---

## Epic E — Rooms + Sets + completeness

### E1 — Create Rooms and attach documents

**Stories**

* Create a room
* Upload docs into a room
* List docs in room

**Tasks**

* Add router:

  * ✅ `backend/app/routers/rooms.py`
* Add service:

  * ✅ `backend/app/services/rooms.py`
* Firestore collections:

  * `rooms`, `room_documents` (or embed doc IDs in Room)

### E2 — Add Set templates + completeness check

**Stories**

* Define a simple SetTemplate (e.g., “Bank statement”, “Ledger extract”, “Invoice pack”)
* Show completeness: expected doc roles vs detected roles in the room

**Tasks**

* Add `SetTemplate` model + seed 1–2 templates in code
* Add a completeness evaluator:

  * ✅ `backend/app/services/completeness.py`
* Extend DocumentProfile or DocumentClassification:

  * add `doc_role` classification (start rules-based)

---

## Epic F — Query + evidence bundles (for later LLM synthesis)

*(You don’t need the LLM yet, but you should structure for it.)*

### F1 — Evidence bundle endpoint

**Story**

* Given a room + question, return a bounded EvidenceBundle:

  * claims + citations + doc spans

**Tasks**

* Add router:

  * ✅ `backend/app/routers/insights.py` (stub returning evidence only)
* EvidenceBundle builder:

  * ✅ `backend/app/services/evidence.py`

---

# 3) Frontend: smallest set of changes (claim overlays + room sets)

You already have:

* PDF viewer with overlay regions (`PDFViewer.tsx`)
* job polling
* debug graph URL fetch
* selection UX for regions

We’ll reuse that.

## Frontend Epic 1 — Rooms (minimal UI)

**Tasks**

* Add `roomId` state in `frontend/app/page.tsx`
* Add “Create Room” button (or auto-create on first upload)
* On upload, call new endpoint:

  * `POST /api/rooms`
  * `POST /api/rooms/{roomId}/documents` (or similar)

**Files**

* `frontend/app/page.tsx`
* `frontend/lib/api-client.ts`
* `frontend/types/api.ts`

## Frontend Epic 2 — Claims panel + click-to-highlight

**Tasks**

* Add a “Claims” panel (right sidebar or below RegionList)
* Fetch claims for current room/doc:

  * `GET /api/claims?room_id=...&doc_version_id=...`
* On claim click:

  * set `selectedRegionId`-like state but for claims
  * reuse your overlay renderer to draw claim spans as boxes

**Files**

* `frontend/components/PDFViewer.tsx` (add `claimSpans` prop)
* `frontend/components/RegionList.tsx` (or create `ClaimList.tsx`)
* `frontend/types/api.ts` (add `Claim` type)
* `frontend/lib/api-client.ts` (add `getClaims()`)

## Frontend Epic 3 — Set completeness widget

**Tasks**

* Add a simple widget at top:

  * “Completeness: 2 / 4 artefacts present”
* Pull from endpoint:

  * `GET /api/rooms/{roomId}/completeness`

**Files**

* `frontend/app/page.tsx`
* `frontend/lib/api-client.ts`

---

# 4) Sequencing: the fastest path to a working Data Hero MVP

Here’s the order that minimizes rework:

1. **ProcessingRun + StepRun** (Epic B)
2. **DocumentVersion hashing** (Epic A)
3. **DocumentProfile** (Epic C)
4. **Claims emission + claims API** (Epic D)
5. **Claim overlay UI** (Frontend Epic 2)
6. **Rooms + attach docs** (Epic E1)
7. **Completeness** (Epic E2)

That gets you “Room + evidence-backed claims + traceability” quickly.

---

# 5) Cut list (don’t build yet)

To stay MVP-fast and Data Hero-aligned:

* Don’t build “true agent planning” (your orchestrator interface is enough)
* Don’t build a full graph database yet
* Don’t do LLM synthesis until EvidenceBundles are real
* Don’t chase perfect table extraction—Claims + provenance first

---

If you want, I can turn the above into a **GitHub Issues-ready backlog** (titles + acceptance criteria + definition of done) and a **repo-level diff plan** (“create these files, modify these functions”) so you can execute it step-by-step.
