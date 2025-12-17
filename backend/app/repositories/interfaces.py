"""
Repository Interfaces

Abstract data access patterns to decouple business logic from storage implementation.
Follows Repository pattern for clean architecture.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime


class IRepository(ABC):
    """Base repository interface for CRUD operations."""
    
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> str:
        """Create a new entity and return its ID."""
        pass
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an entity by ID."""
        pass
    
    @abstractmethod
    def update(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """Update an entity. Returns True if successful."""
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Delete an entity. Returns True if successful."""
        pass
    
    @abstractmethod
    def query(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query entities with filters."""
        pass


class IClaimRepository(IRepository):
    """Repository interface for Claim entities."""
    
    @abstractmethod
    def get_by_document_version(
        self,
        document_version_id: str,
        claim_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all claims for a document version, optionally filtered by type."""
        pass
    
    @abstractmethod
    def get_by_step_run(self, step_run_id: str) -> List[Dict[str, Any]]:
        """Get all claims produced by a step run."""
        pass
    
    @abstractmethod
    def get_verified_claims(
        self,
        document_version_id: str
    ) -> List[Dict[str, Any]]:
        """Get claims that have been verified by humans."""
        pass
    
    @abstractmethod
    def batch_create(self, claims: List[Dict[str, Any]]) -> List[str]:
        """Batch create multiple claims. Returns list of IDs."""
        pass


class IProcessingRunRepository(IRepository):
    """Repository interface for ProcessingRun entities."""
    
    @abstractmethod
    def get_by_document_version(
        self,
        document_version_id: str
    ) -> List[Dict[str, Any]]:
        """Get all processing runs for a document version."""
        pass
    
    @abstractmethod
    def get_latest_run(
        self,
        document_version_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent run for a document version."""
        pass
    
    @abstractmethod
    def get_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all runs with a specific status."""
        pass
    
    @abstractmethod
    def update_status(
        self,
        run_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update run status with optional error message."""
        pass


class IRoomRepository(IRepository):
    """Repository interface for Room entities."""
    
    @abstractmethod
    def get_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all rooms created by a user."""
        pass
    
    @abstractmethod
    def add_document(
        self,
        room_id: str,
        document_version_id: str,
        role: Optional[str] = None
    ) -> bool:
        """Add a document to a room."""
        pass
    
    @abstractmethod
    def remove_document(
        self,
        room_id: str,
        document_version_id: str
    ) -> bool:
        """Remove a document from a room."""
        pass
    
    @abstractmethod
    def get_documents(self, room_id: str) -> List[Dict[str, Any]]:
        """Get all documents in a room."""
        pass
    
    @abstractmethod
    def check_completeness(
        self,
        room_id: str
    ) -> Dict[str, Any]:
        """Check if room has all required documents."""
        pass


class IEvidenceBundleRepository(IRepository):
    """Repository interface for EvidenceBundle entities."""
    
    @abstractmethod
    def add_claims(
        self,
        bundle_id: str,
        claim_ids: List[str]
    ) -> bool:
        """Add claims to a bundle."""
        pass
    
    @abstractmethod
    def get_with_claims(
        self,
        bundle_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get bundle with all associated claim data."""
        pass
    
    @abstractmethod
    def get_statistics(
        self,
        bundle_id: str
    ) -> Dict[str, Any]:
        """Get statistics for a bundle."""
        pass


class IDocumentProfileRepository(IRepository):
    """Repository interface for DocumentProfile entities."""
    
    @abstractmethod
    def get_by_document_version(
        self,
        document_version_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get profile for a document version."""
        pass
    
    @abstractmethod
    def get_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Get all profiles matching a role."""
        pass
    
    @abstractmethod
    def get_skewed_documents(
        self,
        skew_threshold: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Get documents with excessive skew."""
        pass
