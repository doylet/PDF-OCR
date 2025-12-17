from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Union
import json


class Settings(BaseSettings):
    # Application
    app_name: str = "PDF-OCR API"
    debug: bool = False
    
    # GCP Configuration
    gcp_project_id: str
    gcp_location: str = "us"
    gcp_processor_id: str
    
    # Cloud Storage
    gcs_bucket_name: str
    gcs_pdf_folder: str = "pdfs"
    gcs_results_folder: str = "results"
    
    # Firestore (DEPRECATED - migrating to BigQuery)
    firestore_collection: str = "extraction_jobs"
    
    # BigQuery
    bigquery_dataset: str = "data_hero"
    
    # Cloud Tasks
    cloud_tasks_queue: str = "extraction-queue"
    cloud_tasks_location: str = "us-central1"
    worker_service_url: str = "https://placeholder.run.app"
    
    # LLM Configuration (Google Gemini)
    gemini_api_key: str = ""  # Optional - enables agentic features
    enable_llm_agents: bool = True  # Use LLM for ambiguous decisions
    
    # CORS - can be JSON array string or comma-separated string
    cors_origins: Union[list[str], str] = "http://localhost:3000,http://localhost:3001"
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try to parse as JSON first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # Try comma-separated
            if ',' in v:
                return [origin.strip() for origin in v.split(',') if origin.strip()]
            # Fall back to space-separated
            return [origin.strip() for origin in v.split() if origin.strip()]
        return v
    
    # API
    api_key: str = "dev-api-key-change-in-production"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
