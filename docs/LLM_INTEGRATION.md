# LLM Integration - Truly Agentic Document Processing

## Overview

The PDF-OCR pipeline has been transformed from deterministic rule-based agents into truly agentic agents powered by Google Gemini 1.5 Flash. Agents now use LLM reasoning for ambiguous decisions while maintaining rule-based fallbacks for reliability.

## Architecture

### Core LLM Service
**File**: `backend/app/services/llm_service.py`

Centralized LLM interface with 4 agentic decision methods:

1. **analyze_layout_ambiguity()**: "Is this a table or just aligned text?"
   - Input: Region text, current classification, alignment score
   - Output: `{region_type, confidence, reasoning, suggested_extraction_method}`
   - Use case: Resolve borderline layout detection

2. **detect_table_schema()**: "What do these columns mean?"
   - Input: Table data (rows/columns), domain context
   - Output: `{columns: [{name, type, description}], domain, confidence}`
   - Use case: Replace generic "col_0, col_1" with meaningful names

3. **validate_extraction()**: "Does this data make sense?"
   - Input: Extraction data, region type, document type, schema
   - Output: `{is_valid, confidence, issues, suggestions}`
   - Use case: Semantic validation beyond rule-based checks

4. **diagnose_extraction_failure()**: "Why did extraction fail?"
   - Input: Extraction data, validation errors, region type, confidence
   - Output: `{diagnosis, root_cause, recommended_retry: {strategy, params}, confidence}`
   - Use case: Intelligent retry strategy selection

### Pattern: LLM + Fallback
Each method has a corresponding fallback for when LLM is unavailable:
```python
if self.use_llm:
    result = self.llm_service.some_decision()
else:
    result = self._fallback_decision()
```

## Configuration

**File**: `backend/app/config.py`

```python
class Settings(BaseSettings):
    gemini_api_key: str = ""  # Optional, LLM features disabled if empty
    enable_llm_agents: bool = True  # Feature flag to toggle LLM
```

**Environment Variable**:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

## Agent Enhancements

### 1. LayoutAgent (layout_agent.py)
**Enhancement**: LLM-powered ambiguous layout resolution

```python
class LayoutAgent:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()
        self.use_llm = settings.enable_llm_agents
```

**Key Methods**:
- `_calculate_alignment_score()`: Quantifies column alignment (0-1)
- `enhance_regions_with_llm()`: Queries LLM for regions with confidence < 0.7
  - Reclassifies ambiguous TABLE vs TEXT layouts
  - Updates confidence based on LLM reasoning

**When Used**: After geometry-based detection proposes regions

### 2. SchemaAgent (schema_agent.py) ⭐ NEW
**Purpose**: Truly agentic schema detection using LLM

```python
class SchemaAgent:
    def detect_schema(extraction: Extraction) -> Dict:
        # Calls LLM to understand column meanings
        return llm_service.detect_table_schema(...)
    
    def enrich_extraction_with_schema(extraction: Extraction) -> Extraction:
        # Updates Extraction.schema with LLM-detected column names
```

**Example Transformation**:
```python
# Before:
columns = ["col_0", "col_1", "col_2"]

# After LLM:
columns = ["date", "amount", "description"]
schema = {
    "date": {"type": "date", "format": "DD/MM/YYYY"},
    "amount": {"type": "currency", "unit": "USD"},
    "description": {"type": "text"}
}
```

**When Used**: After table extraction, before validation

### 3. ValidatorAgent (validator_agent.py)
**Enhancement**: LLM-powered semantic validation

```python
class ValidatorAgent:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
```

**Key Methods**:
- `_llm_semantic_validation()`: Calls LLM after rule-based checks
  - Checks: "Are dates reasonable for a telecom invoice?"
  - Checks: "Do amounts match expected patterns?"
  - Adds warnings if LLM finds semantic issues

**Validation Flow**:
1. Run rule-based checks (row count, type consistency, sums)
2. If no hard errors, run LLM semantic validation
3. Combine rule-based + LLM issues
4. Return decision (ACCEPT / RETRY / ESCALATE)

**When Used**: After extraction, before retry decisions

### 4. Orchestrator (orchestrator.py)
**Enhancement**: LLM-powered retry strategy selection

```python
class ExpertOrchestrator:
    def __init__(self, pdf_path, job_id, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service
```

**Key Methods**:
- `_llm_diagnose_failure()`: Asks LLM "Why did this fail?"
  - Analyzes validation errors + extraction data
  - Returns recommended retry strategy: `pad_crop`, `higher_dpi`, `force_ocr`, or `escalate`
- `_decide_retry_strategy()`: Uses LLM diagnosis if available, falls back to heuristics

**Retry Strategy Decision**:
```python
# LLM diagnosis might return:
{
    "diagnosis": "Table region cropped headers",
    "root_cause": "incomplete_crop",
    "recommended_retry": {
        "strategy": "pad_crop",
        "params": {"pad_fraction": 0.15}
    },
    "confidence": 0.85
}
```

**When Used**: After validation fails, before retry execution

## Prompt Engineering

### Structured JSON Responses
All LLM prompts request structured JSON for consistent parsing:

```python
prompt = f"""Analyze this table and detect the schema.

Table data:
{json.dumps(rows[:5], indent=2)}

Respond with JSON:
{{
    "columns": [
        {{"name": "...", "type": "date|currency|text|number", "description": "..."}},
        ...
    ],
    "domain": "telecom|financial|general",
    "confidence": 0.0-1.0
}}
"""
```

### Error Handling
```python
try:
    response = model.generate_content(prompt)
    result = json.loads(response.text)
except Exception as e:
    logger.error(f"LLM call failed: {e}")
    return fallback_result
```

## Testing Strategy

### Unit Tests (to be added)
- `test_llm_service.py`: Mock Gemini API, test prompt/response parsing
- `test_schema_agent.py`: Test column name detection
- `test_validator_llm.py`: Test semantic validation
- `test_orchestrator_retry.py`: Test LLM-powered retry decisions

### Integration Tests
1. **Set API Key**: `export GEMINI_API_KEY=...`
2. **Test with Ambiguous PDF**: Upload invoice with borderline table layouts
3. **Verify LLM Calls**: Check debug graph for LLM decisions
4. **Test Fallback**: Disable LLM (`enable_llm_agents=False`), verify rule-based fallback

### Sample Test PDFs
- `tests/fixtures/ambiguous_table.pdf`: Aligned text that looks like a table
- `tests/fixtures/complex_invoice.pdf`: Multiple regions, unclear schema
- `tests/fixtures/malformed_data.pdf`: Data quality issues for validation

## Deployment

### Environment Variables
```bash
# Required for LLM features
export GEMINI_API_KEY="your-google-gemini-api-key"

# Optional: Disable LLM (use only rule-based agents)
export ENABLE_LLM_AGENTS=false
```

### Cloud Run Secrets
```bash
gcloud secrets create gemini-api-key --data-file=- <<< "your-api-key"

gcloud run services update pdf-ocr-backend \
    --update-secrets=GEMINI_API_KEY=gemini-api-key:latest
```

### Cost Estimation
- **Model**: Gemini 1.5 Flash (cheapest Google LLM)
- **Calls per document**: 5-10 (layout ambiguity, schema, validation, retry)
- **Token usage**: ~500-2000 tokens per call
- **Estimated cost**: $0.01-0.05 per document

## Observability

### Debug Graph Enhancements
LLM decisions are logged in `debug_graph.json`:

```json
{
    "trace": [
        {
            "step": "llm_layout_analysis",
            "region_id": "table_p0_l5",
            "llm_decision": {
                "region_type": "TABLE",
                "confidence": 0.85,
                "reasoning": "Clear column structure with aligned numeric data"
            }
        },
        {
            "step": "llm_schema_detection",
            "extraction_id": "ext_123",
            "schema": {
                "columns": ["date", "amount", "description"],
                "domain": "telecom",
                "confidence": 0.9
            }
        },
        {
            "step": "llm_validation",
            "extraction_id": "ext_123",
            "result": {
                "is_valid": false,
                "issues": ["Date '2025-13-01' is invalid month"],
                "confidence": 0.95
            }
        },
        {
            "step": "llm_retry_diagnosis",
            "extraction_id": "ext_123",
            "diagnosis": {
                "root_cause": "incomplete_crop",
                "recommended_retry": "pad_crop"
            }
        }
    ]
}
```

### Logging
```python
logger.info(f"LLM enhanced {region.region_id}: {llm_result['region_type']} (conf={llm_result['confidence']:.2f})")
logger.info(f"LLM detected schema: {schema['columns']}")
logger.info(f"LLM validation raised concerns: {llm_result['issues']}")
logger.info(f"LLM recommended retry: {diagnosis['recommended_retry']['strategy']}")
```

## Next Steps

### Immediate
1. ✅ Create LLM service wrapper
2. ✅ Integrate into all 4 agents
3. ⏳ Test with Gemini API key
4. ⏳ Add unit tests
5. ⏳ Deploy to Cloud Run

### Future Enhancements
- **Multi-modal**: Send page images to Gemini for visual layout understanding
- **Few-shot learning**: Include example extractions in prompts
- **Chain-of-thought**: Ask LLM to explain reasoning step-by-step
- **Adaptive prompts**: Adjust prompts based on document type
- **LLM caching**: Cache common layout patterns to reduce API calls
- **A/B testing**: Compare LLM vs rule-based performance

## Files Changed

### New Files
1. `backend/app/services/llm_service.py` (400+ lines)
2. `backend/app/agents/schema_agent.py` (150+ lines)
3. `backend/LLM_INTEGRATION.md` (this file)

### Modified Files
1. `backend/app/config.py`: Added `gemini_api_key`, `enable_llm_agents`
2. `backend/app/agents/layout_agent.py`: Added LLM ambiguity resolution
3. `backend/app/agents/validator_agent.py`: Added LLM semantic validation
4. `backend/app/agents/orchestrator.py`: Added LLM retry diagnosis

## Conclusion

The PDF-OCR pipeline is now **truly agentic**. Agents make intelligent decisions using LLM reasoning for:
- Layout ambiguity: "Is this a table?"
- Schema detection: "What do these columns mean?"
- Semantic validation: "Does this data make sense?"
- Error recovery: "Why did this fail, and how should I retry?"

The system maintains reliability through rule-based fallbacks and graceful degradation when LLM is unavailable.
