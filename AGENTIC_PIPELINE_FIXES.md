# Agentic Pipeline Fixes - December 2025

## Problem Statement

The agentic extraction pipeline had structural bugs causing silent failures:
- **Root Cause**: Region detection loop never flushed last table at page end → 0 regions detected
- **Secondary Issue**: No semantic stop cues → tables bleed into footers/totals
- **Observability Gap**: HTTP 200 with empty data appeared as success, not failure

## Solution Implemented

### 1. Fixed Region Detection (LayoutAgent)

**File**: `backend/app/agents/layout_agent.py`

#### Added Semantic Stop Cues
```python
TABLE_STOP_CUES = [
    'total', 'subtotal', 'balance', 'grand total',
    'gigabyte', 'megabyte', 'kilobyte',
    '1 gigabyte', '1 megabyte', '1 gb =', '1 mb ='
]
```

#### Critical End-of-Page Flush
```python
# At end of page loop - CRITICAL FIX
if current_table_lines and len(current_table_lines) >= 3:
    logger.info(f"Flushing open table at end of page: {len(current_table_lines)} lines")
    region = LayoutAgent._create_table_region(current_table_lines, page_num, current_table_start)
    if region:
        regions.append(region)
```

### 2. Added Explicit Job Outcomes

**File**: `backend/app/models/document_graph.py`

```python
class JobOutcome(str, Enum):
    SUCCESS = "success"              # All regions extracted
    PARTIAL_SUCCESS = "partial_success"  # Some regions failed
    NO_MATCH = "no_match"           # No extractable regions found
    FAILED = "failed"               # Complete failure
```

**Key Rule**: `regions_proposed == 0` → `NO_MATCH` (not SUCCESS)

### 3. Added Trace Logging

**Files**: `backend/app/agents/orchestrator.py`, `backend/app/models/document_graph.py`

```python
# Added to DocumentGraph
trace: List[Dict[str, Any]] = field(default_factory=list)
```

**Trace Captures**:
- PDF ingestion start/end
- Page processing start
- Layout Agent region proposal results
- Specialist dispatch for each region
- Extraction success/failure with metrics
- Final outcome determination

### 4. Enhanced API Response

**File**: `backend/app/routers/extraction.py`

```python
summary = {
    "outcome": outcome,
    "pages": len(graph.pages),
    "regions_proposed": len(graph.regions),
    "regions_extracted": len(results),
    "trace": graph.trace
}
```

## Deployment Status

✅ **Deployed**: Revision `pdf-ocr-api-00036-2dd`  
✅ **Service URL**: https://pdf-ocr-api-785693222332.us-central1.run.app  
✅ **Health Check**: Passing

## Testing

### Test Script
```bash
python test_agentic_api.py <path_to_pdf>
```

### Expected Response
```json
{
  "summary": {
    "outcome": "success",
    "pages": 10,
    "regions_proposed": 5,
    "regions_extracted": 5,
    "trace": [
      {"step": "ingest_pdf", "status": "started", "pdf_path": "...", "timestamp": "..."},
      {"step": "ingest_pdf", "status": "completed", "pages_found": 10, "timestamp": "..."},
      {"step": "process_page", "status": "started", "page_num": 0, "timestamp": "..."},
      {"step": "layout_agent", "status": "completed", "page_num": 0, "regions_proposed": 3, "region_types": ["TABLE", "KEY_VALUE"], "timestamp": "..."},
      {"step": "dispatch_to_specialist", "status": "started", "region_id": "...", "region_type": "TABLE", "timestamp": "..."},
      {"step": "table_extraction", "status": "success", "region_id": "...", "rows_extracted": 15, "confidence": 0.95, "timestamp": "..."}
    ]
  },
  "results": [...]
}
```

## What Changed

### Before
- ❌ Tables not flushed at page end → 0 regions detected
- ❌ HTTP 200 with empty data = silent failure
- ❌ No visibility into agent decisions
- ❌ Impossible to debug why extraction failed

### After
- ✅ Tables properly flushed at page end
- ✅ Explicit outcomes: SUCCESS/PARTIAL_SUCCESS/NO_MATCH/FAILED
- ✅ Full trace of agent steps with timestamps
- ✅ Detailed metrics (regions proposed, extracted, confidence)
- ✅ Failures are visible and actionable

## Next Steps

### Frontend (TODO)
1. Display outcome badges (success/partial/no_match/failed)
2. Show trace timeline with agent steps
3. Render detected regions as overlays on PDF
4. Provide user actions for NO_MATCH state

### Backend (TODO)
1. Implement OCR path for scanned documents
2. Add template learning to save successful patterns
3. Add confidence thresholds for extraction validation
4. Implement retry logic for failed extractions

## Commits

- `d384fdc` - Fix region detection + add explicit job outcomes
- `dbb9ff2` - Add trace logging + fix JobOutcome import

## Files Modified

1. `backend/app/agents/layout_agent.py` - Region detection fixes
2. `backend/app/models/document_graph.py` - JobOutcome + trace
3. `backend/app/agents/orchestrator.py` - Outcome determination + trace logging
4. `backend/app/routers/extraction.py` - Enhanced API response
5. `test_agentic_api.py` - Test script (new)
