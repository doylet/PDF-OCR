"""
Domain Models

Pure business logic models without infrastructure dependencies.
These represent core business concepts independent of storage.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class ClaimType(Enum):
    """Supported claim types."""
    LOAN_AMOUNT = "loan_amount"
    ACCOUNT_NUMBER = "account_number"
    DATE = "date"
    PARTY_NAME = "party_name"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    MONETARY_AMOUNT = "monetary_amount"
    PERCENTAGE = "percentage"
    OTHER = "other"


class ProcessingRunStatus(Enum):
    """Processing run states."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BoundingBox:
    """Bounding box coordinates."""
    x: float
    y: float
    width: float
    height: float
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "BoundingBox":
        """Create from dictionary."""
        return cls(**data)
    
    def overlaps(self, other: "BoundingBox") -> bool:
        """Check if this bbox overlaps with another."""
        return not (
            self.x + self.width < other.x or
            other.x + other.width < self.x or
            self.y + self.height < other.y or
            other.y + other.height < self.y
        )


@dataclass
class Claim:
    """
    Domain model for a Claim.
    
    Represents an atomic piece of extracted information with provenance.
    """
    id: str
    document_version_id: str
    step_run_id: str
    claim_type: ClaimType
    value: str
    confidence: float
    page_number: int
    bbox: BoundingBox
    created_at: datetime
    
    # Optional fields
    normalized_value: Optional[str] = None
    source_text: Optional[str] = None
    room_id: Optional[str] = None
    user_feedback: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate claim after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")
        
        if self.page_number < 1:
            raise ValueError(f"Page number must be >= 1, got {self.page_number}")
        
        if not self.value.strip():
            raise ValueError("Claim value cannot be empty")
    
    def is_high_confidence(self, threshold: float = 0.9) -> bool:
        """Check if claim has high confidence."""
        return self.confidence >= threshold
    
    def is_verified(self) -> bool:
        """Check if claim has been verified by a human."""
        return self.user_feedback is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "document_version_id": self.document_version_id,
            "step_run_id": self.step_run_id,
            "room_id": self.room_id,
            "claim_type": self.claim_type.value,
            "value": self.value,
            "normalized_value": self.normalized_value or self.value,
            "confidence": self.confidence,
            "page_number": self.page_number,
            "bbox_x": self.bbox.x,
            "bbox_y": self.bbox.y,
            "bbox_width": self.bbox.width,
            "bbox_height": self.bbox.height,
            "source_text": self.source_text,
            "user_feedback_json": self.user_feedback,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Claim":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            document_version_id=data["document_version_id"],
            step_run_id=data["step_run_id"],
            claim_type=ClaimType(data["claim_type"]),
            value=data["value"],
            confidence=data["confidence"],
            page_number=data["page_number"],
            bbox=BoundingBox(
                x=data["bbox_x"],
                y=data["bbox_y"],
                width=data["bbox_width"],
                height=data["bbox_height"]
            ),
            created_at=datetime.fromisoformat(data["created_at"]),
            normalized_value=data.get("normalized_value"),
            source_text=data.get("source_text"),
            room_id=data.get("room_id"),
            user_feedback=data.get("user_feedback_json"),
            metadata=data.get("metadata", {})
        )


@dataclass
class ProcessingRun:
    """
    Domain model for a ProcessingRun.
    
    Represents the execution of a document processing pipeline.
    """
    id: str
    document_version_id: str
    status: ProcessingRunStatus
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    # Optional fields
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_by_user_id: Optional[str] = None
    
    def can_transition_to(self, new_status: ProcessingRunStatus) -> bool:
        """Check if transition to new status is valid."""
        valid_transitions = {
            ProcessingRunStatus.PENDING: [ProcessingRunStatus.PROCESSING, ProcessingRunStatus.CANCELLED],
            ProcessingRunStatus.PROCESSING: [ProcessingRunStatus.COMPLETED, ProcessingRunStatus.FAILED],
            ProcessingRunStatus.COMPLETED: [],
            ProcessingRunStatus.FAILED: [ProcessingRunStatus.PROCESSING],  # Allow retry
            ProcessingRunStatus.CANCELLED: []
        }
        
        return new_status in valid_transitions.get(self.status, [])
    
    def is_terminal(self) -> bool:
        """Check if run is in a terminal state."""
        return self.status in [
            ProcessingRunStatus.COMPLETED,
            ProcessingRunStatus.FAILED,
            ProcessingRunStatus.CANCELLED
        ]
    
    def duration_seconds(self) -> Optional[float]:
        """Calculate run duration in seconds."""
        if not self.started_at or not self.completed_at:
            return None
        
        return (self.completed_at - self.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "document_version_id": self.document_version_id,
            "status": self.status.value,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "created_by_user_id": self.created_by_user_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingRun":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            document_version_id=data["document_version_id"],
            status=ProcessingRunStatus(data["status"]),
            config=data["config"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error_message=data.get("error_message"),
            created_by_user_id=data.get("created_by_user_id")
        )


@dataclass
class Room:
    """
    Domain model for a Room.
    
    Represents a multi-document analysis context.
    """
    id: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    # Optional fields
    description: Optional[str] = None
    set_template_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if room is active."""
        return self.status == "active"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "set_template_id": self.set_template_id,
            "created_by_user_id": self.created_by_user_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Room":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            description=data.get("description"),
            set_template_id=data.get("set_template_id"),
            created_by_user_id=data.get("created_by_user_id"),
            metadata=data.get("metadata", {})
        )
