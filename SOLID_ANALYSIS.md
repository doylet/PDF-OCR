# SOLID Principles Analysis & Refactoring Plan

## Executive Summary

Several services violate SOLID principles, particularly **Single Responsibility Principle (SRP)** and **Dependency Inversion Principle (DIP)**. This document identifies violations and provides concrete refactoring recommendations.

---

## 🚨 Critical Violations

### 1. DocumentAI Service (HIGH PRIORITY)

**File**: `backend/app/services/documentai.py`

**Current Responsibilities** (violates SRP):
1. PDF manipulation (cropping)
2. Image conversion (PDF → PNG)
3. Document AI API client
4. Text extraction
5. Structured data parsing (tables, forms)
6. Region processing orchestration
7. Camelot table extraction
8. Text parsing fallback
9. Debug artifact upload
10. Region type analysis routing

**Problem**: This class has **10 reasons to change** - it's a god object.

**Refactoring Plan**:

```python
# 1. PDF Operations (separate service)
class PdfProcessor:
    """Handles PDF manipulation (cropping, page extraction)"""
    def crop_region(self, pdf_bytes: bytes, region: Region) -> bytes:
        pass
    
    def extract_page(self, pdf_bytes: bytes, page_num: int) -> bytes:
        pass

# 2. Image Conversion (separate service)
class ImageConverter:
    """Converts between image formats"""
    def pdf_page_to_png(self, pdf_bytes: bytes, page: int, dpi: int = 200) -> bytes:
        pass
    
    def resize_image(self, image_bytes: bytes, max_width: int) -> bytes:
        pass

# 3. Document AI Client (focused on API)
class DocumentAIClient:
    """Google Document AI API client"""
    def __init__(self, processor_name: str):
        self.client = get_documentai_client()
        self.processor_name = processor_name
    
    def process_document(self, document_bytes: bytes, mime_type: str) -> documentai.Document:
        """Process document with Document AI"""
        pass

# 4. Text Extraction (separate concern)
class DocumentTextExtractor:
    """Extracts text from Document AI results"""
    def extract_text(self, document: documentai.Document) -> tuple[str, float]:
        pass
    
    def extract_from_layout(self, full_text: str, layout) -> str:
        pass

# 5. Structured Data Parser (separate concern)
class DocumentStructureParser:
    """Parses structured data (tables, forms) from Document AI"""
    def extract_tables(self, document: documentai.Document) -> List[List[str]]:
        pass
    
    def extract_form_fields(self, document: documentai.Document) -> List[dict]:
        pass

# 6. Region Processor (orchestrator - uses above services)
class RegionProcessor:
    """Orchestrates region extraction using multiple strategies"""
    def __init__(
        self,
        pdf_processor: PdfProcessor,
        image_converter: ImageConverter,
        docai_client: DocumentAIClient,
        text_extractor: DocumentTextExtractor,
        structure_parser: DocumentStructureParser,
        table_extractor: TableExtractor,
        text_parser: TextParser
    ):
        self.pdf = pdf_processor
        self.images = image_converter
        self.docai = docai_client
        self.text = text_extractor
        self.structure = structure_parser
        self.tables = table_extractor
        self.parser = text_parser
    
    def process_region(self, pdf_bytes: bytes, region: Region) -> ExtractionResult:
        """Process a single region using multi-strategy approach"""
        # Try Camelot first
        # Fallback to Document AI
        # Fallback to text parsing
        pass
```

**Benefits**:
- ✅ Each class has **one reason to change**
- ✅ Easy to test in isolation (mock dependencies)
- ✅ Easy to swap implementations (e.g., different OCR providers)
- ✅ Clear dependency graph

---

### 2. Storage Service (MEDIUM PRIORITY)

**File**: `backend/app/services/storage.py`

**Current Responsibilities** (violates SRP):
1. Bucket management
2. Upload URL generation
3. PDF blob operations
4. PDF downloads
5. Result uploads (CSV, JSON)
6. Debug artifact uploads

**Problem**: Mixing infrastructure (bucket management) with business logic (upload URLs, result formatting)

**Refactoring Plan**:

```python
# 1. Bucket Manager (infrastructure)
class BucketManager:
    """Manages GCS bucket lifecycle"""
    def __init__(self, client: storage.Client, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
    
    def get_or_create_bucket(self) -> storage.Bucket:
        """Get or create bucket"""
        pass

# 2. Signed URL Generator (security/auth concern)
class SignedUrlGenerator:
    """Generates signed URLs for GCS operations"""
    def __init__(self, bucket: storage.Bucket):
        self.bucket = bucket
    
    def generate_upload_url(
        self,
        blob_name: str,
        expiration: timedelta,
        content_type: str
    ) -> str:
        """Generate signed upload URL"""
        pass
    
    def generate_download_url(
        self,
        blob_name: str,
        expiration: timedelta
    ) -> str:
        """Generate signed download URL"""
        pass

# 3. Blob Repository (data access)
class BlobRepository:
    """CRUD operations for GCS blobs"""
    def __init__(self, bucket: storage.Bucket):
        self.bucket = bucket
    
    def upload_bytes(self, blob_name: str, data: bytes, content_type: str) -> str:
        """Upload bytes to blob"""
        pass
    
    def download_bytes(self, blob_name: str) -> bytes:
        """Download blob as bytes"""
        pass
    
    def delete_blob(self, blob_name: str) -> None:
        """Delete blob"""
        pass

# 4. PDF Storage (business logic)
class PdfStorage:
    """Business logic for PDF storage"""
    def __init__(
        self,
        blob_repo: BlobRepository,
        url_generator: SignedUrlGenerator,
        folder: str = "pdfs"
    ):
        self.blobs = blob_repo
        self.urls = url_generator
        self.folder = folder
    
    def generate_pdf_upload_url(self, file_name: str) -> tuple[str, str]:
        """Generate upload URL with auto-generated ID"""
        pdf_id = str(uuid.uuid4())
        blob_name = f"{self.folder}/{pdf_id}/{file_name}"
        upload_url = self.urls.generate_upload_url(
            blob_name,
            expiration=timedelta(hours=1),
            content_type="application/pdf"
        )
        return pdf_id, upload_url
    
    def download_pdf(self, pdf_id: str) -> bytes:
        """Download PDF by ID"""
        # Find blob with prefix
        # Download bytes
        pass

# 5. Result Storage (separate from PDF storage)
class ResultStorage:
    """Business logic for extraction result storage"""
    def __init__(
        self,
        blob_repo: BlobRepository,
        url_generator: SignedUrlGenerator,
        folder: str = "results"
    ):
        self.blobs = blob_repo
        self.urls = url_generator
        self.folder = folder
    
    def upload_result(
        self,
        job_id: str,
        content: str,
        file_format: str,
        suffix: str = ""
    ) -> str:
        """Upload extraction result"""
        pass
    
    def upload_debug_artifact(
        self,
        job_id: str,
        artifact_name: str,
        content: bytes,
        content_type: str
    ) -> str:
        """Upload debug artifact"""
        pass
```

**Benefits**:
- ✅ Bucket management separated from business logic
- ✅ Signed URL generation reusable across use cases
- ✅ PDF storage decoupled from result storage
- ✅ Easy to swap GCS for S3/Azure (implement interfaces)

---

### 3. Jobs Service (LOW PRIORITY)

**File**: `backend/app/services/jobs.py`

**Current State**: Actually pretty good! Single responsibility (job lifecycle management).

**Minor Improvement**: Extract Firestore operations to repository pattern

```python
# Repository (data access)
class JobRepository:
    """Data access for jobs"""
    def __init__(self, db: firestore.Client, collection: str):
        self.db = db
        self.collection = collection
    
    def create(self, job_id: str, data: dict) -> None:
        """Create job document"""
        pass
    
    def get(self, job_id: str) -> Optional[dict]:
        """Get job document"""
        pass
    
    def update(self, job_id: str, data: dict) -> None:
        """Update job document"""
        pass

# Service (business logic)
class JobService:
    """Job lifecycle management"""
    def __init__(self, repo: JobRepository):
        self.repo = repo
    
    def create_job(
        self,
        job_id: str,
        pdf_id: str,
        regions_count: int,
        output_format: str = "csv"
    ) -> JobStatus:
        """Create extraction job with defaults"""
        now = datetime.utcnow()
        data = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "pdf_id": pdf_id,
            "regions_count": regions_count,
            "output_format": output_format
        }
        self.repo.create(job_id, data)
        return JobStatus(**data)
```

---

## 🎯 Dependency Inversion Principle (DIP)

**Problem**: Services depend on concrete implementations, not abstractions.

**Example Violation**:
```python
class RegionProcessor:
    def __init__(self):
        self.storage = storage_service  # Concrete dependency!
        self.table_extractor = TableExtractor  # Static class!
```

**Solution**: Inject abstractions (interfaces)

```python
# Define interface (abstract base class)
from abc import ABC, abstractmethod

class IStorageService(ABC):
    @abstractmethod
    def upload_debug_artifact(self, job_id: str, name: str, content: bytes) -> str:
        pass

# Implement interface
class GcsStorageService(IStorageService):
    def upload_debug_artifact(self, job_id: str, name: str, content: bytes) -> str:
        # GCS-specific implementation
        pass

# Inject dependency
class RegionProcessor:
    def __init__(self, storage: IStorageService):
        self.storage = storage  # Depends on abstraction!
```

**Benefits**:
- ✅ Easy to test (inject mocks)
- ✅ Easy to swap implementations (GCS → S3)
- ✅ No circular dependencies

---

## 🔧 Refactoring Strategy

### Phase 1: Extract PDF/Image Operations (Week 1)
1. Create `PdfProcessor` class
2. Create `ImageConverter` class
3. Update `DocumentAI` to use these services
4. Write unit tests

### Phase 2: Split DocumentAI Service (Week 2)
1. Create `DocumentAIClient` (thin API wrapper)
2. Create `DocumentTextExtractor`
3. Create `DocumentStructureParser`
4. Update `RegionProcessor` to use new services
5. Write unit tests

### Phase 3: Refactor Storage Service (Week 3)
1. Create `BucketManager`
2. Create `SignedUrlGenerator`
3. Create `BlobRepository`
4. Create `PdfStorage` and `ResultStorage`
5. Update routers to use new services
6. Write unit tests

### Phase 4: Define Interfaces (Week 4)
1. Create `interfaces.py` for all service abstractions
2. Refactor services to implement interfaces
3. Update dependency injection to use interfaces
4. Add integration tests

---

## 📋 Migration Checklist

- [ ] Create `backend/app/services/pdf_processor.py`
- [ ] Create `backend/app/services/image_converter.py`
- [ ] Refactor `documentai.py` → split into 5 classes
- [ ] Create `backend/app/services/bucket_manager.py`
- [ ] Create `backend/app/services/signed_url_generator.py`
- [ ] Create `backend/app/services/blob_repository.py`
- [ ] Refactor `storage.py` → split into `PdfStorage` and `ResultStorage`
- [ ] Create `backend/app/services/interfaces.py` (abstract base classes)
- [ ] Update all routers to use new services
- [ ] Update dependency injection container
- [ ] Write unit tests for each new service (aim for 80%+ coverage)
- [ ] Update documentation

---

## 🎓 SOLID Principles Summary

1. **Single Responsibility Principle (SRP)**: ✅ Each class should have one reason to change
   - Violated by: `DocumentAI`, `Storage`
   - Fixed by: Extracting responsibilities into focused classes

2. **Open/Closed Principle (OCP)**: ✅ Open for extension, closed for modification
   - Improved by: Using interfaces and composition

3. **Liskov Substitution Principle (LSP)**: ✅ Subtypes should be substitutable
   - Ensured by: Implementing proper interfaces

4. **Interface Segregation Principle (ISP)**: ✅ Many specific interfaces > one general interface
   - Applied by: Creating focused interfaces per concern

5. **Dependency Inversion Principle (DIP)**: ✅ Depend on abstractions, not concretions
   - Violated by: Direct instantiation of concrete classes
   - Fixed by: Constructor injection of interfaces

---

## 🚀 Quick Wins (Can Do Today)

1. **Extract PdfProcessor** (30 min)
   - Move `crop_pdf_region` to standalone class
   - Update `DocumentAI` to use it

2. **Extract ImageConverter** (20 min)
   - Move PDF→PNG conversion logic
   - Update `PdfProcessor` to use it

3. **Create BlobRepository** (40 min)
   - Extract low-level GCS operations
   - Update `Storage` to use it

---

## 📊 Impact Analysis

**Before Refactoring**:
- DocumentAI: 293 lines, 10 responsibilities
- Storage: 118 lines, 6 responsibilities
- Total: ~400 lines in 2 god objects

**After Refactoring**:
- DocumentAIClient: ~50 lines
- DocumentTextExtractor: ~40 lines
- DocumentStructureParser: ~60 lines
- PdfProcessor: ~80 lines
- ImageConverter: ~40 lines
- RegionProcessor: ~100 lines (orchestrator)
- BucketManager: ~30 lines
- SignedUrlGenerator: ~40 lines
- BlobRepository: ~50 lines
- PdfStorage: ~60 lines
- ResultStorage: ~50 lines
- Total: ~600 lines in 11 focused classes

**Tradeoff**: More files, but each is:
- ✅ Easier to understand
- ✅ Easier to test
- ✅ Easier to maintain
- ✅ Easier to swap implementations

---

## 🧪 Testing Strategy

Each extracted service should have:
1. **Unit tests** (mock dependencies)
2. **Integration tests** (real GCP services in test environment)
3. **Contract tests** (ensure interface compliance)

Example:
```python
# Unit test (mock GCS client)
def test_blob_repository_upload():
    mock_bucket = Mock()
    repo = BlobRepository(mock_bucket)
    
    repo.upload_bytes("test.txt", b"hello", "text/plain")
    
    mock_bucket.blob.assert_called_once_with("test.txt")

# Integration test (real GCS)
def test_pdf_storage_roundtrip():
    # Use test bucket
    storage = PdfStorage(bucket_name="test-bucket")
    
    pdf_id, url = storage.generate_upload_url("test.pdf")
    # Upload via URL
    # Download via pdf_id
    # Assert content matches
```

---

## 🔄 Backward Compatibility

During migration:
1. Keep old `documentai_service` singleton
2. Create new services alongside
3. Gradually migrate routers
4. Remove old service once all references updated

```python
# Old (deprecated)
from app.services.documentai import documentai_service

# New
from app.services.document_ai_client import DocumentAIClient
from app.services.document_text_extractor import DocumentTextExtractor
from app.services.region_processor import RegionProcessor

# Both work during migration
```

---

## 💡 Additional Recommendations

1. **Use dependency injection framework**: Consider `python-dependency-injector` or `FastAPI's Depends()`
2. **Add type hints everywhere**: Helps catch interface violations early
3. **Document interfaces**: Clear docstrings on abstract methods
4. **Version APIs**: If changing service signatures, version them (e.g., `v1/`, `v2/`)
5. **Monitor metrics**: Track service call latency/errors per class

---

## 📖 References

- Clean Architecture by Robert C. Martin
- Design Patterns: Elements of Reusable Object-Oriented Software
- FastAPI Best Practices: https://github.com/zhanymkanov/fastapi-best-practices
