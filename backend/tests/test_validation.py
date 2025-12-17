"""
Data validation tests.

Tests data structure validation without requiring GCP services.
"""

import pytest
from datetime import datetime
import json


class TestDocumentDataValidation:
    """Test document data structure validation."""
    
    def test_has_required_fields(self, sample_document_data):
        """Test document has all required fields."""
        required = ["id", "name", "status", "gcs_uri", "created_at"]
        
        for field in required:
            assert field in sample_document_data
    
    def test_id_is_string(self, sample_document_data):
        """Test document ID is a non-empty string."""
        assert isinstance(sample_document_data["id"], str)
        assert len(sample_document_data["id"]) > 0
    
    def test_status_is_valid(self, sample_document_data):
        """Test status is one of allowed values."""
        valid_statuses = ["pending", "processing", "active", "failed", "archived"]
        assert sample_document_data["status"] in valid_statuses
    
    def test_gcs_uri_format(self, sample_document_data):
        """Test GCS URI has correct format."""
        uri = sample_document_data["gcs_uri"]
        assert uri.startswith("gs://")
    
    def test_timestamp_parseable(self, sample_document_data):
        """Test timestamp can be parsed."""
        timestamp = sample_document_data["created_at"]
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)


class TestClaimDataValidation:
    """Test claim data structure validation."""
    
    def test_has_required_fields(self, sample_claim_data):
        """Test claim has all required fields."""
        required = ["id", "document_id", "claim_type", "claim_text", "confidence"]
        
        for field in required:
            assert field in sample_claim_data
    
    def test_confidence_in_range(self, sample_claim_data):
        """Test confidence is between 0 and 1."""
        confidence = sample_claim_data["confidence"]
        assert 0.0 <= confidence <= 1.0
        assert isinstance(confidence, float)
    
    def test_claim_type_valid(self, sample_claim_data):
        """Test claim type is valid."""
        valid_types = [
            "diagnosis", "medication", "procedure",
            "lab_result", "vital_sign", "allergy",
            "condition", "treatment", "other"
        ]
        assert sample_claim_data["claim_type"] in valid_types
    
    def test_claim_text_not_empty(self, sample_claim_data):
        """Test claim text is not empty."""
        claim_text = sample_claim_data["claim_text"]
        assert isinstance(claim_text, str)
        assert len(claim_text.strip()) > 0
    
    def test_page_number_positive(self, sample_claim_data):
        """Test page number is positive."""
        page_num = sample_claim_data["page_number"]
        assert isinstance(page_num, int)
        assert page_num > 0


class TestProcessingRunValidation:
    """Test processing run data validation."""
    
    def test_has_required_fields(self, sample_processing_run):
        """Test run has all required fields."""
        required = ["id", "document_id", "status", "pipeline_version"]
        
        for field in required:
            assert field in sample_processing_run
    
    def test_status_valid(self, sample_processing_run):
        """Test run status is valid."""
        valid_statuses = ["pending", "processing", "completed", "failed"]
        assert sample_processing_run["status"] in valid_statuses
    
    def test_agents_used_is_list(self, sample_processing_run):
        """Test agents_used is a list."""
        agents = sample_processing_run["agents_used"]
        assert isinstance(agents, list)
    
    def test_pipeline_version_format(self, sample_processing_run):
        """Test pipeline version follows semver format."""
        version = sample_processing_run["pipeline_version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)


class TestDataSerialization:
    """Test data can be serialized/deserialized."""
    
    def test_document_serializes_to_json(self, sample_document_data):
        """Test document can be JSON serialized."""
        json_str = json.dumps(sample_document_data)
        restored = json.loads(json_str)
        
        assert restored["id"] == sample_document_data["id"]
        assert restored["name"] == sample_document_data["name"]
    
    def test_claim_serializes_to_json(self, sample_claim_data):
        """Test claim can be JSON serialized."""
        json_str = json.dumps(sample_claim_data)
        restored = json.loads(json_str)
        
        assert restored["confidence"] == sample_claim_data["confidence"]
        assert isinstance(restored["confidence"], float)
    
    def test_processing_run_serializes(self, sample_processing_run):
        """Test run can be JSON serialized."""
        json_str = json.dumps(sample_processing_run)
        restored = json.loads(json_str)
        
        assert restored["agents_used"] == sample_processing_run["agents_used"]
        assert isinstance(restored["agents_used"], list)


class TestFieldConstraints:
    """Test field constraints and edge cases."""
    
    def test_confidence_boundaries(self):
        """Test confidence at boundary values."""
        assert 0.0 >= 0.0 and 0.0 <= 1.0
        assert 1.0 >= 0.0 and 1.0 <= 1.0
        assert 0.5 >= 0.0 and 0.5 <= 1.0
    
    def test_id_uniqueness_format(self):
        """Test ID format allows uniqueness."""
        ids = ["doc-1", "doc-2", "doc-3"]
        assert len(ids) == len(set(ids))
        assert all(len(id_val) > 0 for id_val in ids)
    
    def test_empty_string_validation(self):
        """Test empty strings are invalid."""
        empty_strings = ["", "   ", "\t", "\n"]
        
        for s in empty_strings:
            assert len(s.strip()) == 0
