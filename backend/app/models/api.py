from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


class Region(BaseModel):
    """Represents a selected region on a PDF page"""
    x: float = Field(..., description="X coordinate (pixels)")
    y: float = Field(..., description="Y coordinate (pixels)")
    width: float = Field(..., description="Width (pixels)")
    height: float = Field(..., description="Height (pixels)")
    label: Optional[str] = Field(None, description="Optional label for the region")
    page: int = Field(..., description="Page number (1-indexed)")


class ExtractionRequest(BaseModel):
    """Request to extract data from PDF regions"""
    pdf_id: str = Field(..., description="ID of the uploaded PDF in Cloud Storage")
    regions: List[Region] = Field(..., description="List of regions to extract")
    output_format: Literal["csv", "tsv", "json"] = Field(default="csv", description="Output format")


class DetectedRegion(BaseModel):
    """Region detected by structure gate"""
    region_id: str
    page: int
    bbox: dict
    region_type: str
    confidence: float


class JobStatus(BaseModel):
    """Status of an extraction job"""
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    pdf_id: str
    regions_count: int
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    debug_graph_url: Optional[str] = None
    approved_regions: Optional[List[DetectedRegion]] = None
    output_format: Optional[Literal["csv", "tsv", "json"]] = None


class ExtractionResult(BaseModel):
    """Result of a single region extraction"""
    region_index: int
    page: int
    text: str
    confidence: float
    structured_data: Optional[dict] = None


class UploadResponse(BaseModel):
    """Response after PDF upload"""
    pdf_id: str
    upload_url: str
    file_name: str


class DocumentUploadRequest(BaseModel):
    """Request to upload a document"""
    filename: str = Field(..., description="Original filename")
    uploaded_by_user_id: str = Field(..., description="User ID uploading the document")
    name: Optional[str] = Field(None, description="Optional display name (defaults to filename)")
    description: Optional[str] = Field(None, description="Optional document description")


class DocumentUploadResponse(BaseModel):
    """Response after document upload with versioning"""
    document_id: str = Field(..., description="Document entity ID")
    document_version_id: str = Field(..., description="SHA-256 hash of content")
    upload_url: str = Field(..., description="Signed URL for uploading PDF bytes")
    was_duplicate: bool = Field(..., description="True if content hash already existed")
    filename: str = Field(..., description="Original filename")
