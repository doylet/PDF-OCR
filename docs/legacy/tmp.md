You’re *very* close. From looking through your repo, there are two “this won’t work as intended” issues that will bite almost everyone building this on **Cloud Run + region selection**:

## 1) Your region coordinates are almost certainly wrong (96/72 bug)

In `frontend/components/PDFViewer.tsx` you convert the user’s drag rectangle into “pixels at 200 DPI” so the backend can crop the same region after `pdf2image(dpi=200)`.

But `page.getViewport({ scale: 1.0 }).width/height` from pdf.js is in **CSS pixels at ~96 DPI**, *not* PDF “points” (72 DPI). Your current formula assumes those values are points:

```ts
const pdfWidthInPixels = (pageDimensions.width / 72) * dpi;
```

That injects a **96/72 = 1.333× scale error**, so the backend crops the wrong region (often empty or shifted), and OCR/table extraction looks “broken”.

### Fix (frontend)

Replace the conversion block in `handleMouseUp` with this:

```ts
// pageDimensions from pdf.js viewport are CSS px (~96 DPI)
const dpi = 200;
const cssDpi = 96;

const pdfWidthInPixels = pageDimensions.width * (dpi / cssDpi);
const pdfHeightInPixels = pageDimensions.height * (dpi / cssDpi);

const scaleX = pdfWidthInPixels / canvas.width;
const scaleY = pdfHeightInPixels / canvas.height;

const pdfRegion: Region = {
  x: currentRect.x * scaleX,
  y: currentRect.y * scaleY,
  width: currentRect.width * scaleX,
  height: currentRect.height * scaleY,
  page: currentPage,
};
```

Also: your overlay drawing is currently using `region.x/y` directly on the canvas even though those are “200 DPI pixels”, so the rectangles *won’t line up* visually. That’s not just cosmetic—people will “correct” their selection to match the overlay and make things worse. You should inverse-transform when drawing (same `scaleX/scaleY`, but divide).

---

## 2) Your async processing model won’t run reliably on Cloud Run

In `backend/app/routers/extraction.py` you do:

```py
background_tasks.add_task(process_extraction, job_id, extraction_request)
return job
```

On **Cloud Run (default CPU allocation)**, once the HTTP response is returned, CPU is often **throttled/paused**. That means your background task may never complete, and jobs stay `"queued"` / `"processing"` forever.

### Fix (backend architecture)

You already have a Cloud Tasks client stubbed in `dependencies.py`, which is the right move. The MVP pattern:

1. **Create job in Firestore**
2. **Enqueue a Cloud Task** to call a worker endpoint (Cloud Run service URL)
3. Worker endpoint runs `process_extraction(...)` synchronously and updates Firestore

This gives you: retries, observability, and it works under serverless constraints.

#### Concrete shape

* `POST /api/extract` (fast)

  * create job
  * enqueue task (payload = job_id + request params OR job_id only if you store request in Firestore)
* `POST /api/extract/worker` (slow)

  * validates task auth
  * loads job + request
  * runs extraction
  * writes results

If you want the *absolute simplest MVP* without Cloud Tasks: run extraction **synchronously** inside the request (just `await process_extraction(...)`) and increase Cloud Run timeout. But you’ll hit timeouts quickly on big PDFs.

---

## A practical MVP pipeline/algorithm that will feel “it just works”

Right now you do **per-region**: convert page → crop → OCR/table extract. That’s okay for MVP, but performance and accuracy improve a lot if you treat “region selection” as a *hint*, not the whole algorithm.

Here’s a robust pipeline that still matches your UX:

### Stage A — Normalize the document once

* Render each page to image at a fixed DPI (200 is fine)
* Cache rendered pages (GCS or in-memory per job) so multiple regions don’t re-render

### Stage B — For each region

1. **Try PDF-native extraction first** (cheap)

   * `pdfplumber` / `pypdf` text within bbox
   * If it yields enough characters, prefer it over OCR (cleaner + faster)
2. **Then try table extraction** (Camelot/Tabula) *only if* it’s likely a table

   * Quick heuristic: region aspect ratio, density of lines, repeated whitespace patterns
3. **Fallback to OCR** (Document AI)

   * Crop image region
   * OCR it
4. **Post-process**

   * Clean currency, dates, invoice numbers
   * Return structured output

### Stage C — “Handle the rest” (your future direction)

Once region selection works reliably, the next leap is **templates**:

* Let users save a “Bill Template” per provider: regions + labels + parsing rules
* Next upload: auto-detect provider (logo text / header) and auto-apply template
* Later: learned detection (embeddings / classifier) + automation triggers

---

## Quick “do these first” checklist

1. ✅ Fix the 96/72 coordinate bug (this alone may make it “work”)
2. ✅ Fix overlay rendering so users trust the selection
3. ✅ Move background processing off FastAPI `BackgroundTasks` and onto Cloud Tasks (or temporarily synchronous)
4. ✅ Add debug artifacts per job:

   * Upload the cropped region PNG to GCS when processing
   * Save OCR raw text + confidence
     This makes failures obvious in minutes.

---

If you tell me what you’re seeing when it “doesn’t work” (job stuck in queued/processing vs completes with empty text vs errors), I can point you to the exact failure path in *your* code and suggest the smallest patch.
