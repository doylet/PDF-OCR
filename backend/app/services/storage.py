from google.cloud import storage
from app.config import get_settings
from app.dependencies import get_storage_client
import uuid
import logging
from typing import Tuple
from datetime import timedelta

logger = logging.getLogger(__name__)
settings = get_settings()


class StorageService:
    """Service for Cloud Storage operations"""
    
    def __init__(self):
        self.client = get_storage_client()
        self.bucket_name = settings.gcs_bucket_name
    
    def get_bucket(self) -> storage.Bucket:
        """Get or create the storage bucket"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            if not bucket.exists():
                bucket = self.client.create_bucket(self.bucket_name, location=settings.gcp_location)
                logger.info(f"Created bucket: {self.bucket_name}")
            return bucket
        except Exception as e:
            logger.error(f"Error accessing bucket: {e}")
            raise
    
    def generate_upload_url(self, file_name: str) -> Tuple[str, str]:
        """Generate a signed URL for PDF upload"""
        pdf_id = str(uuid.uuid4())
        blob_name = f"{settings.gcs_pdf_folder}/{pdf_id}/{file_name}"
        
        bucket = self.get_bucket()
        blob = bucket.blob(blob_name)
        
        # Generate signed URL (valid for 1 hour)
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="PUT",
            content_type="application/pdf"
        )
        
        logger.info(f"Generated upload URL for PDF: {pdf_id}")
        return pdf_id, upload_url
    
    def get_pdf_blob(self, pdf_id: str) -> storage.Blob:
        """Get blob reference for a PDF"""
        bucket = self.get_bucket()
        # List blobs with prefix to find the PDF
        blobs = list(bucket.list_blobs(prefix=f"{settings.gcs_pdf_folder}/{pdf_id}/"))
        
        if not blobs:
            raise FileNotFoundError(f"PDF not found: {pdf_id}")
        
        return blobs[0]
    
    def download_pdf(self, pdf_id: str) -> bytes:
        """Download PDF content"""
        blob = self.get_pdf_blob(pdf_id)
        return blob.download_as_bytes()
    
    def upload_result(self, job_id: str, content: str, format: str, suffix: str = "") -> str:
        """Upload extraction result and return public URL"""
        blob_name = f"{settings.gcs_results_folder}/{job_id}/result{suffix}.{format}"
        
        bucket = self.get_bucket()
        blob = bucket.blob(blob_name)
        
        # Set appropriate content type
        if format == "json":
            content_type = "application/json"
        elif format == "csv":
            content_type = "text/csv"
        elif format == "tsv":
            content_type = "text/tab-separated-values"
        else:
            content_type = f"text/{format}"
        
        blob.upload_from_string(content, content_type=content_type)
        
        # Generate signed URL (valid for 7 days)
        result_url = blob.generate_signed_url(
            version="v4",
            expiration=604800,
            method="GET"
        )
        
        logger.info(f"Uploaded result{suffix} for job: {job_id}")
        return result_url
    
    def upload_debug_artifact(self, job_id: str, artifact_name: str, content: bytes, content_type: str = "image/png") -> str:
        """Upload debug artifact (cropped image, raw OCR text, etc.) and return URL"""
        blob_name = f"{settings.gcs_results_folder}/{job_id}/debug/{artifact_name}"
        
        bucket = self.get_bucket()
        blob = bucket.blob(blob_name)
        blob.upload_from_string(content, content_type=content_type)
        
        # Generate signed URL (valid for 7 days)
        debug_url = blob.generate_signed_url(
            version="v4",
            expiration=604800,
            method="GET"
        )
        
        logger.info(f"Uploaded debug artifact {artifact_name} for job: {job_id}")
        return debug_url


storage_service = StorageService()
