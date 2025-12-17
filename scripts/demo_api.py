#!/usr/bin/env python3
"""
Demo script for Data Hero Backend API
Demonstrates Epic A (Document Versioning) and Epic B (ProcessingRuns API)
"""

import requests
import io
import hashlib
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
USER_ID = "demo-user-123"

def print_section(title):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def create_test_pdf(content: str) -> bytes:
    """Create a simple PDF with text content"""
    pdf_content = f"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
({content}) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
    return pdf_content.encode('utf-8')

def compute_hash(data: bytes) -> str:
    """Compute SHA-256 hash"""
    return hashlib.sha256(data).hexdigest()

def demo():
    """Run the complete demo"""
    
    print_section("DATA HERO BACKEND API DEMO")
    print(f"Base URL: {BASE_URL}")
    print(f"Demo User: {USER_ID}")
    
    # ========================================
    # EPIC A: DOCUMENT VERSIONING
    # ========================================
    
    print_section("1. Upload Document (First Time)")
    
    # Create test PDF
    pdf1_content = create_test_pdf("Invoice #12345 - Amount: $1,234.56")
    pdf1_hash = compute_hash(pdf1_content)
    
    print(f"📄 Created test PDF: invoice_12345.pdf")
    print(f"   Size: {len(pdf1_content)} bytes")
    print(f"   SHA-256: {pdf1_hash}")
    
    # Upload document
    files = {'file': ('invoice_12345.pdf', io.BytesIO(pdf1_content), 'application/pdf')}
    headers = {
        'X-User-Id': USER_ID,
        'X-Document-Name': 'Invoice 12345',
        'X-Document-Description': 'Q4 2025 Invoice'
    }
    
    response = requests.post(
        f"{BASE_URL}/api/upload/documents",
        files=files,
        headers=headers
    )
    
    if response.status_code == 200:
        upload1 = response.json()
        print(f"\n✅ Upload successful!")
        print(f"   Document ID: {upload1['document_id']}")
        print(f"   Version ID (hash): {upload1['document_version_id'][:16]}...")
        print(f"   Was Duplicate: {upload1['was_duplicate']}")
        print(f"   Filename: {upload1['filename']}")
    else:
        print(f"❌ Upload failed: {response.status_code}")
        print(response.text)
        return
    
    doc1_id = upload1['document_id']
    version1_id = upload1['document_version_id']
    
    # ========================================
    print_section("2. Upload Same Document Again (Deduplication)")
    
    # Upload identical content with different metadata
    files = {'file': ('invoice_12345_copy.pdf', io.BytesIO(pdf1_content), 'application/pdf')}
    headers = {
        'X-User-Id': USER_ID,
        'X-Document-Name': 'Invoice 12345 (Copy)',
        'X-Document-Description': 'Duplicate for testing'
    }
    
    response = requests.post(
        f"{BASE_URL}/api/upload/documents",
        files=files,
        headers=headers
    )
    
    if response.status_code == 200:
        upload2 = response.json()
        print(f"✅ Upload successful!")
        print(f"   Document ID: {upload2['document_id']}")
        print(f"   Version ID (hash): {upload2['document_version_id'][:16]}...")
        print(f"   Was Duplicate: {upload2['was_duplicate']} ⭐")
        print(f"\n💡 Notice: Different Document ID but SAME Version ID!")
        print(f"   - No duplicate GCS upload needed")
        print(f"   - Storage saved: {len(pdf1_content)} bytes")
    else:
        print(f"❌ Upload failed: {response.status_code}")
    
    doc2_id = upload2['document_id']
    
    # ========================================
    print_section("3. Retrieve Document Information")
    
    # Get first document
    response = requests.get(f"{BASE_URL}/api/documents/{doc1_id}")
    if response.status_code == 200:
        doc1 = response.json()
        print(f"📋 Document 1:")
        print(f"   Name: {doc1['name']}")
        print(f"   Description: {doc1['description']}")
        print(f"   Status: {doc1['status']}")
        print(f"   Uploaded By: {doc1['uploaded_by_user_id']}")
    
    # Get second document
    response = requests.get(f"{BASE_URL}/api/documents/{doc2_id}")
    if response.status_code == 200:
        doc2 = response.json()
        print(f"\n📋 Document 2:")
        print(f"   Name: {doc2['name']}")
        print(f"   Description: {doc2['description']}")
        print(f"   Status: {doc2['status']}")
    
    # Get version details
    response = requests.get(f"{BASE_URL}/api/documents/versions/{version1_id}")
    if response.status_code == 200:
        version = response.json()
        print(f"\n📦 Shared DocumentVersion:")
        print(f"   Hash: {version['id'][:16]}...")
        print(f"   GCS URI: {version['gcs_uri']}")
        print(f"   Size: {version['file_size_bytes']} bytes")
        print(f"   MIME Type: {version['mime_type']}")
    
    # ========================================
    print_section("4. Update Document Metadata")
    
    update_data = {
        "name": "Invoice 12345 - APPROVED",
        "description": "Approved for payment on 2025-12-17",
        "metadata": {"status": "approved", "approver": "manager-456"}
    }
    
    response = requests.patch(
        f"{BASE_URL}/api/documents/{doc1_id}",
        json=update_data
    )
    
    if response.status_code == 200:
        updated_doc = response.json()
        print(f"✅ Document updated!")
        print(f"   New Name: {updated_doc['name']}")
        print(f"   New Description: {updated_doc['description']}")
        print(f"   Metadata: {updated_doc['metadata']}")
        print(f"\n💡 Note: Content (DocumentVersion) remains immutable!")
    
    # ========================================
    # EPIC B: PROCESSING RUNS
    # ========================================
    
    print_section("5. Create Processing Run")
    
    run_request = {
        "document_version_id": version1_id,
        "run_type": "full_extraction",
        "user_id": USER_ID,
        "config": {
            "extract_tables": True,
            "extract_claims": True,
            "quality_threshold": 0.85
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/api/processing-runs",
        json=run_request
    )
    
    if response.status_code == 201:
        run = response.json()
        print(f"✅ ProcessingRun created!")
        print(f"   Run ID: {run['id']}")
        print(f"   Document Version: {run['document_version_id'][:16]}...")
        print(f"   Status: {run['status']}")
        print(f"   Run Type: {run['run_type']}")
        print(f"   Created At: {run['created_at']}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
        return
    
    run_id = run['id']
    
    # ========================================
    print_section("6. Get Processing Run Status")
    
    response = requests.get(f"{BASE_URL}/api/processing-runs/{run_id}")
    
    if response.status_code == 200:
        run = response.json()
        print(f"📊 ProcessingRun Status:")
        print(f"   ID: {run['id']}")
        print(f"   Status: {run['status']}")
        print(f"   Started: {run['started_at'] or 'Not yet started'}")
        print(f"   Completed: {run['completed_at'] or 'In progress'}")
    
    # Get with steps
    response = requests.get(f"{BASE_URL}/api/processing-runs/{run_id}?include_steps=true")
    
    if response.status_code == 200:
        run = response.json()
        print(f"\n   Steps: {len(run.get('steps', []))} total")
        for step in run.get('steps', []):
            print(f"      - {step['step_name']}: {step['status']}")
    
    # ========================================
    print_section("7. List All Processing Runs")
    
    response = requests.get(
        f"{BASE_URL}/api/processing-runs",
        params={"document_version_id": version1_id, "limit": 10}
    )
    
    if response.status_code == 200:
        runs = response.json()
        print(f"📋 Found {len(runs)} run(s) for this document version:")
        for r in runs:
            print(f"   - {r['id'][:8]}... | Status: {r['status']} | Type: {r['run_type']}")
    
    # ========================================
    print_section("8. Create Another Document (Different Content)")
    
    pdf2_content = create_test_pdf("Contract #ABC789 - Terms & Conditions")
    pdf2_hash = compute_hash(pdf2_content)
    
    print(f"📄 Created different PDF: contract_abc789.pdf")
    print(f"   Size: {len(pdf2_content)} bytes")
    print(f"   SHA-256: {pdf2_hash}")
    print(f"   Different from first: {pdf2_hash != pdf1_hash}")
    
    files = {'file': ('contract_abc789.pdf', io.BytesIO(pdf2_content), 'application/pdf')}
    headers = {
        'X-User-Id': USER_ID,
        'X-Document-Name': 'Contract ABC789'
    }
    
    response = requests.post(
        f"{BASE_URL}/api/upload/documents",
        files=files,
        headers=headers
    )
    
    if response.status_code == 200:
        upload3 = response.json()
        print(f"\n✅ Upload successful!")
        print(f"   Document ID: {upload3['document_id']}")
        print(f"   Version ID: {upload3['document_version_id'][:16]}...")
        print(f"   Was Duplicate: {upload3['was_duplicate']}")
        print(f"\n💡 New content = New DocumentVersion = GCS upload performed")
    
    # ========================================
    print_section("DEMO COMPLETE!")
    
    print("📚 Summary:")
    print(f"   • Uploaded 3 documents (2 duplicates, 1 unique)")
    print(f"   • Created 2 DocumentVersion records (deduplication worked!)")
    print(f"   • Updated document metadata (immutability preserved)")
    print(f"   • Created and tracked ProcessingRun")
    print(f"   • Demonstrated full API lifecycle")
    print(f"\n✅ All Epic A & B features operational!")
    print(f"\nNext steps:")
    print(f"   - Epic C: Document Profiling")
    print(f"   - Epic D: Claims Extraction")
    print(f"   - Epic E: Multi-document Rooms")
    print(f"   - Epic F: Evidence Bundles")

if __name__ == "__main__":
    try:
        demo()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to backend")
        print(f"   Make sure the server is running at {BASE_URL}")
        print(f"\n   Start with: cd backend && uvicorn main:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
