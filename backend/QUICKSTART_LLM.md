# Quick Start: Testing LLM Integration

## Prerequisites

1. **Get Gemini API Key**
   - Go to https://makersuite.google.com/app/apikey
   - Create a new API key
   - Copy the key

2. **Install Dependencies**
```bash
cd backend
pip install -r requirements.txt
```

## Setup

### Option 1: Environment Variable
```bash
export GEMINI_API_KEY="your-api-key-here"
export ENABLE_LLM_AGENTS=true
```

### Option 2: .env File
```bash
# backend/.env
GEMINI_API_KEY=your-api-key-here
ENABLE_LLM_AGENTS=true
```

## Test LLM Service

### Interactive Python Test
```python
from app.services.llm_service import LLMService
from app.config import get_settings

# Initialize
settings = get_settings()
llm = LLMService()

# Test 1: Layout ambiguity
result = llm.analyze_layout_ambiguity(
    region_text="""
Date        Time    Duration    Cost
01/06/2024  09:30   00:15:30    $2.50
02/06/2024  14:20   00:08:12    $1.30
    """,
    current_type="TABLE",
    alignment_score=0.85
)
print("Layout Analysis:", result)

# Test 2: Schema detection
result = llm.detect_table_schema(
    rows=[
        ["01/06/2024", "09:30", "00:15:30", "$2.50"],
        ["02/06/2024", "14:20", "00:08:12", "$1.30"]
    ],
    columns=["col_0", "col_1", "col_2", "col_3"],
    domain_hint="telecom"
)
print("Schema Detection:", result)

# Test 3: Validation
result = llm.validate_extraction(
    extraction_data={
        "rows": [
            ["01/06/2024", "09:30", "00:15:30", "$2.50"],
            ["02/06/2024", "14:20", "00:08:12", "$1.30"]
        ],
        "columns": ["date", "time", "duration", "cost"]
    },
    region_type="TABLE",
    document_type="telecom_invoice"
)
print("Validation:", result)

# Test 4: Failure diagnosis
result = llm.diagnose_extraction_failure(
    extraction_data={"rows": [], "columns": []},
    validation_errors=["No rows extracted", "Empty data"],
    region_type="TABLE",
    confidence=0.3
)
print("Diagnosis:", result)
```

## Test with Real PDF

### 1. Start Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 2. Upload Test PDF
```bash
# Create test PDF with ambiguous table
curl -X POST "http://localhost:8000/api/v1/detect-regions" \
  -F "file=@tests/fixtures/ambiguous_table.pdf" \
  -F "mode=agentic"
```

### 3. Check Debug Graph
```bash
# Download debug graph
curl "http://localhost:8000/api/v1/jobs/{job_id}/debug-graph" > debug_graph.json

# Check for LLM decisions
cat debug_graph.json | jq '.trace[] | select(.step | contains("llm"))'
```

### Expected Output
```json
{
  "step": "llm_layout_analysis",
  "region_id": "table_p0_l5",
  "llm_decision": {
    "region_type": "TABLE",
    "confidence": 0.85,
    "reasoning": "Clear column structure with aligned numeric data"
  }
}
```

## Verify Fallback Mode

### Disable LLM
```bash
export ENABLE_LLM_AGENTS=false
```

### Run Same Test
- System should use rule-based fallbacks
- No "llm_" steps in debug graph
- Extractions should still work (lower quality)

## Troubleshooting

### Error: "API key not found"
```bash
# Check if environment variable is set
echo $GEMINI_API_KEY

# Or check .env file
cat backend/.env | grep GEMINI_API_KEY
```

### Error: "Import google.generativeai could not be resolved"
```bash
# Reinstall dependencies
pip install -r backend/requirements.txt

# Verify installation
python -c "import google.generativeai; print('OK')"
```

### Error: "Rate limit exceeded"
- Gemini 1.5 Flash has free tier limits: 15 requests/minute
- Add retry logic or wait 60 seconds
- Or upgrade to paid tier

### LLM Returns Empty/Invalid JSON
- Check prompt in `llm_service.py`
- Verify response parsing: `json.loads(response.text)`
- Add more examples to prompt for few-shot learning

## Monitoring

### Log LLM Calls
```python
# Check logs for LLM activity
import logging
logging.basicConfig(level=logging.INFO)

# Look for:
# "LLM enhanced table_p0_l5: TABLE (conf=0.85)"
# "LLM detected schema: ['date', 'amount', 'description']"
# "LLM validation raised concerns: ['Date format inconsistent']"
# "LLM recommended retry: pad_crop"
```

### Cost Tracking
```python
# Add to llm_service.py
import time

class LLMService:
    def __init__(self):
        self.call_count = 0
        self.total_tokens = 0
    
    def _call_llm(self, prompt):
        start = time.time()
        response = self.model.generate_content(prompt)
        latency = time.time() - start
        
        self.call_count += 1
        # Estimate tokens: ~4 chars per token
        self.total_tokens += len(prompt) / 4 + len(response.text) / 4
        
        logger.info(f"LLM call #{self.call_count}: {latency:.2f}s, ~{self.total_tokens} tokens")
```

## Next Steps

1. **Unit Tests**: Create `tests/test_llm_service.py` with mocked API
2. **Integration Tests**: Add PDF fixtures with known ambiguous layouts
3. **Performance Tests**: Measure LLM latency impact on pipeline
4. **Cost Analysis**: Track API usage per document type

## Success Criteria

✅ LLM service initializes without errors
✅ All 4 agentic methods return structured JSON
✅ Fallback mode works when LLM disabled
✅ Debug graph contains LLM decision traces
✅ Schema detection improves column naming
✅ Validation catches semantic issues
✅ Retry strategy adapts to failure type

## Deployment Checklist

- [ ] Set `GEMINI_API_KEY` in Cloud Run secrets
- [ ] Enable `ENABLE_LLM_AGENTS=true` in production
- [ ] Monitor LLM call latency (target: < 2s per call)
- [ ] Set up cost alerts for Gemini API usage
- [ ] Add LLM metrics to observability dashboard
- [ ] Create runbook for LLM service degradation
