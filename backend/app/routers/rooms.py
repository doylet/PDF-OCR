"""
Rooms API Router

Endpoints for managing multi-document analysis contexts.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.bigquery import BigQuery
from app.services.room import Room
from app.dependencies import get_bigquery_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


class CreateRoomRequest(BaseModel):
    """Request to create a new Room."""
    
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    set_template_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    metadata: Optional[dict] = None


class RoomResponse(BaseModel):
    """Room entity response."""
    
    id: str
    name: str
    description: Optional[str] = None
    created_at: str
    updated_at: str
    status: str
    set_template_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    metadata: Optional[dict] = None


class AddDocumentRequest(BaseModel):
    """Request to add a DocumentVersion to a Room."""
    
    document_version_id: str
    added_by_user_id: Optional[str] = None


class RoomDocumentResponse(BaseModel):
    """Document membership in a Room."""
    
    room_id: str
    document_version_id: str
    added_at: str
    added_by_user_id: Optional[str] = None
    document_id: str
    file_size_bytes: int
    gcs_uri: str
    mime_type: str
    original_filename: str
    version_created_at: str


class CompletenessResponse(BaseModel):
    """Room completeness check result."""
    
    room_id: str
    is_complete: bool
    required_roles: List[str]
    present_roles: List[str]
    missing_roles: List[str]


@router.post("", response_model=RoomResponse, status_code=201)
async def create_room(
    request: CreateRoomRequest,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """Create a new Room for multi-document analysis."""
    
    service = Room(bq_service)
    
    room = service.create_room(
        name=request.name,
        description=request.description,
        set_template_id=request.set_template_id,
        created_by_user_id=request.created_by_user_id,
        metadata=request.metadata
    )
    
    return RoomResponse(**room)


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: str,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """Retrieve a Room by ID."""
    
    service = Room(bq_service)
    room = service.get_room(room_id)
    
    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    
    return RoomResponse(**room)


@router.get("", response_model=List[RoomResponse])
async def list_rooms(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """List all rooms with optional status filtering."""
    
    service = Room(bq_service)
    rooms = service.list_rooms(status=status, limit=limit, offset=offset)
    
    return [RoomResponse(**room) for room in rooms]


@router.post("/{room_id}/documents", response_model=RoomDocumentResponse, status_code=201)
async def add_document_to_room(
    room_id: str,
    request: AddDocumentRequest,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Add a DocumentVersion to a Room.
    
    Creates a many-to-many relationship. The same DocumentVersion can
    be added to multiple Rooms for different analysis contexts.
    """
    
    service = Room(bq_service)
    
    room = service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    
    service.add_document_to_room(
        room_id=room_id,
        document_version_id=request.document_version_id,
        added_by_user_id=request.added_by_user_id
    )
    
    documents = service.get_documents_in_room(room_id, limit=1000)
    
    matching_doc = next(
        (doc for doc in documents if doc["document_version_id"] == request.document_version_id),
        None
    )
    
    if not matching_doc:
        raise HTTPException(
            status_code=500,
            detail="Document added but could not retrieve details"
        )
    
    return RoomDocumentResponse(**matching_doc)


@router.get("/{room_id}/documents", response_model=List[RoomDocumentResponse])
async def get_documents_in_room(
    room_id: str,
    limit: int = 100,
    offset: int = 0,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """Retrieve all DocumentVersions in a Room."""
    
    service = Room(bq_service)
    
    room = service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    
    documents = service.get_documents_in_room(room_id, limit=limit, offset=offset)
    
    return [RoomDocumentResponse(**doc) for doc in documents]


@router.delete("/{room_id}/documents/{document_version_id}", status_code=204)
async def remove_document_from_room(
    room_id: str,
    document_version_id: str,
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """Remove a DocumentVersion from a Room."""
    
    service = Room(bq_service)
    
    success = service.remove_document_from_room(room_id, document_version_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to remove document from room"
        )
    
    return None


@router.post("/{room_id}/completeness", response_model=CompletenessResponse)
async def check_room_completeness(
    room_id: str,
    required_roles: List[str],
    bq_service: BigQuery = Depends(get_bigquery_service)
):
    """
    Check if a Room contains all required document types.
    
    Validates against a list of required document_role values from document_profiles.
    
    Example required_roles:
    - ["primary_claim_form", "medical_evidence", "billing_statement"]
    
    Returns which roles are present and which are missing.
    """
    
    service = Room(bq_service)
    
    room = service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    
    completeness = service.check_room_completeness(room_id, required_roles)
    
    return CompletenessResponse(**completeness)
