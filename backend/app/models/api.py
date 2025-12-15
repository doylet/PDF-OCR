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
