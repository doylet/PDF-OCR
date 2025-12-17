# System Dependencies Installation Guide

This document covers installation of system-level dependencies required by the PDF-OCR backend.

## Required Dependencies

### 1. Ghostscript (CRITICAL)

**Purpose**: Required by Camelot for PDF table extraction

**Symptoms if missing**:
```
Error: Ghostscript is not installed
Camelot table extraction will fail
```

**Installation**:

**macOS**:
```bash
brew install ghostscript
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install ghostscript
```

**RHEL/CentOS**:
```bash
sudo yum install ghostscript
```

**Verify installation**:
```bash
gs --version
# Should output: GPL Ghostscript 10.x.x or similar
```

---

### 2. Poppler (Required)

**Purpose**: Required by pdf2image for PDF to image conversion

**Symptoms if missing**:
```
Error: Unable to convert PDF to images
Region extraction may fail
```

**Installation**:

**macOS**:
```bash
brew install poppler
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

**RHEL/CentOS**:
```bash
sudo yum install poppler-utils
```

**Verify installation**:
```bash
pdftoppm -v
# Should output version information
```

---

## Python Dependencies

After installing system dependencies, install Python packages:

```bash
cd backend
pip install -r requirements.txt
```

**Key Python packages**:
- `camelot-py[cv]` - Table extraction (requires Ghostscript)
- `pdf2image` - PDF to image conversion (requires Poppler)
- `google-cloud-documentai` - Document AI OCR
- `fastapi` - Web framework
- `uvicorn` - ASGI server

---

## Dependency Verification

### Automated Check

Run the dependency checker:

```bash
cd backend
python -m app.utils.dependency_checker
```

**Output if successful**:
```
INFO: Checking system dependencies...
INFO: ✓ All dependencies are installed
✓ All dependencies verified
```

**Output if dependencies missing**:
```
ERROR: ✗ Missing system dependencies:
  - Ghostscript
    Installation:
    Install via Homebrew:
        brew install ghostscript

ERROR: ✗ Missing Python packages:
  - camelot-py[cv]
    Installation: pip install camelot-py[cv]
```

### API Health Check

Start the server and check health endpoints:

```bash
# Terminal 1: Start server
cd backend
uvicorn app.main:app --reload

# Terminal 2: Check health
curl http://localhost:8000/health/dependencies
```

**Expected response (all healthy)**:
```json
{
  "system": {
    "ghostscript": {
      "installed": true,
      "version": "10.02.0"
    },
    "poppler": {
      "installed": true,
      "version": "24.01.0"
    }
  },
  "python": {
    "camelot-py[cv]": {
      "installed": true,
      "version": "0.11.0"
    },
    ...
  },
  "status": "healthy"
}
```

**Response if Ghostscript missing**:
```json
{
  "system": {
    "ghostscript": {
      "installed": false,
      "error": "Not found in PATH",
      "install_instructions": "brew install ghostscript (macOS) or apt-get install ghostscript (Ubuntu)"
    }
  },
  "status": "degraded"
}
```

---

## Docker/Production Deployment

For containerized deployments, add to your `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ghostscript \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ... rest of Dockerfile
```

For Cloud Run, ensure the Dockerfile includes these dependencies.

---

## Troubleshooting

### Issue: "Ghostscript is not installed"

**Cause**: Ghostscript binary not in PATH

**Solution**:
1. Install via package manager (see above)
2. Verify installation: `which gs`
3. Restart terminal/shell to reload PATH
4. If using Docker, rebuild container

### Issue: "pdftoppm: command not found"

**Cause**: Poppler tools not in PATH

**Solution**:
1. Install poppler-utils (see above)
2. Verify: `which pdftoppm`
3. Restart shell

### Issue: "ImportError: No module named 'camelot'"

**Cause**: Python package not installed

**Solution**:
```bash
pip install 'camelot-py[cv]'
```

Note the `[cv]` extra - this installs OpenCV dependencies.

### Issue: "Table extraction fails silently"

**Symptoms**:
- No error messages
- Tables not detected
- Falls back to Document AI

**Debug steps**:
1. Check logs for Camelot warnings
2. Run dependency checker
3. Try manual Ghostscript test:
   ```bash
   gs --version
   ```
4. Check health endpoint:
   ```bash
   curl http://localhost:8000/health/diagnostics
   ```

---

## Monitoring in Production

### Health Check Endpoints

Add to your monitoring/alerting:

- `GET /health/` - Basic liveness check (200 = healthy)
- `GET /health/dependencies` - Dependency status
- `GET /health/diagnostics` - Full system diagnostics

### Recommended Alerts

Set up alerts for:
1. `/health/dependencies` returns `"status": "degraded"` or `"status": "unhealthy"`
2. Logs contain "CRITICAL: Ghostscript"
3. Camelot extraction success rate drops below 70%

### Logging

The application logs dependency issues at startup:
```
INFO: Verifying system dependencies...
INFO: Ghostscript is available
INFO: Camelot library loaded successfully
ERROR: CRITICAL: Ghostscript is not installed! ...
```

Monitor these logs in Cloud Logging (GCP) or equivalent.

---

## CI/CD Integration

### GitHub Actions

Add to `.github/workflows/test.yml`:

```yaml
- name: Install system dependencies
  run: |
    sudo apt-get update
    sudo apt-get install -y ghostscript poppler-utils

- name: Verify dependencies
  run: |
    cd backend
    python -m app.utils.dependency_checker
```

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: check-dependencies
      name: Check system dependencies
      entry: python backend/app/utils/dependency_checker.py
      language: python
      pass_filenames: false
```

---

## Summary Checklist

- [ ] Ghostscript installed (`gs --version`)
- [ ] Poppler installed (`pdftoppm -v`)
- [ ] Python packages installed (`pip list | grep camelot`)
- [ ] Dependency checker passes (`python -m app.utils.dependency_checker`)
- [ ] Health endpoint returns healthy (`curl /health/dependencies`)
- [ ] Table extraction working (test with sample PDF)
- [ ] Dockerfile includes system deps (if using Docker)
- [ ] Monitoring alerts configured (production)

---

## References

- Ghostscript: https://www.ghostscript.com/
- Poppler: https://poppler.freedesktop.org/
- Camelot docs: https://camelot-py.readthedocs.io/en/master/user/install-deps.html
- pdf2image: https://github.com/Belval/pdf2image
