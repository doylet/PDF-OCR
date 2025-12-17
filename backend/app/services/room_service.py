"""
Room Service

Manages Rooms (multi-document analysis contexts) and their document memberships.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

from google.cloud import bigquery

from app.services.bigquery_service import BigQueryService


logger = logging.getLogger(__name__)

ROOMS_TABLE = "rooms"
ROOM_DOCUMENTS_TABLE = "room_documents"


class RoomService:
    """Service for managing Rooms and their associated DocumentVersions."""
    
    def __init__(self, bq_service: BigQueryService):
        self.bq = bq_service
    
    def create_room(
        self,
        name: str,
        description: Optional[str] = None,
        set_template_id: Optional[str] = None,
        created_by_user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new Room for multi-document analysis.
        
        Args:
            name: Human-readable room name
            description: Optional description
            set_template_id: Optional template defining required document types
            created_by_user_id: User who created the room
            metadata: Optional additional metadata
            
        Returns:
            Dictionary containing the room data
        """
        room_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        room_data = {
            "id": room_id,
            "name": name,
            "description": description,
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "set_template_id": set_template_id,
            "created_by_user_id": created_by_user_id,
            "metadata": metadata
        }
        
        self.bq.insert_row(ROOMS_TABLE, room_data)
        logger.info(f"Created room {room_id} with name '{name}'")
        
        return room_data
    
    def get_room(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a room by its ID."""
        return self.bq.get_by_id(ROOMS_TABLE, room_id)
    
    def update_room(
        self,
        room_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Update room metadata."""
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if status is not None:
            updates["status"] = status
        if metadata is not None:
            updates["metadata"] = metadata
        
        success = self.bq.update_row(ROOMS_TABLE, room_id, updates)
        
        if success:
            return self.get_room(room_id)
        return None
    
    def add_document_to_room(
        self,
        room_id: str,
        document_version_id: str,
        added_by_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a DocumentVersion to a Room.
        
        Creates a many-to-many relationship record. The same DocumentVersion
        can be added to multiple Rooms.
        """
        relationship_data = {
            "room_id": room_id,
            "document_version_id": document_version_id,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "added_by_user_id": added_by_user_id
        }
        
        self.bq.insert_row(ROOM_DOCUMENTS_TABLE, relationship_data)
        logger.info(
            f"Added document_version {document_version_id} to room {room_id}"
        )
        
        return relationship_data
    
    def remove_document_from_room(
        self, room_id: str, document_version_id: str
    ) -> bool:
        """
        Remove a DocumentVersion from a Room.
        
        Note: This is a soft delete that doesn't physically remove the row,
        but marks it as inactive via deletion timestamp.
        """
        query = f"""
            DELETE FROM `{self.bq.project}.{self.bq.dataset}.{ROOM_DOCUMENTS_TABLE}`
            WHERE room_id = @room_id
              AND document_version_id = @document_version_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("room_id", "STRING", room_id),
                bigquery.ScalarQueryParameter("document_version_id", "STRING", document_version_id)
            ]
        )
        
        try:
            self.bq.client.query(query, job_config=job_config).result()
            logger.info(
                f"Removed document_version {document_version_id} from room {room_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to remove document from room: {e}")
            return False
    
    def get_documents_in_room(
        self, room_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all DocumentVersions in a Room.
        
        Returns full document_versions data joined with room_documents.
        """
        query = f"""
            SELECT 
                rd.room_id,
                rd.document_version_id,
                rd.added_at,
                rd.added_by_user_id,
                dv.document_id,
                dv.file_size_bytes,
                dv.gcs_uri,
                dv.mime_type,
                dv.original_filename,
                dv.created_at as version_created_at
            FROM `{self.bq.project}.{self.bq.dataset}.{ROOM_DOCUMENTS_TABLE}` rd
            JOIN `{self.bq.project}.{self.bq.dataset}.document_versions` dv
              ON rd.document_version_id = dv.id
            WHERE rd.room_id = @room_id
            ORDER BY rd.added_at DESC
            LIMIT @limit OFFSET @offset
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("room_id", "STRING", room_id),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
                bigquery.ScalarQueryParameter("offset", "INT64", offset)
            ]
        )
        
        results = self.bq.client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]
    
    def count_documents_in_room(self, room_id: str) -> int:
        """Count the number of DocumentVersions in a Room."""
        query = f"""
            SELECT COUNT(*) as count
            FROM `{self.bq.project}.{self.bq.dataset}.{ROOM_DOCUMENTS_TABLE}`
            WHERE room_id = @room_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("room_id", "STRING", room_id)
            ]
        )
        
        results = list(self.bq.client.query(query, job_config=job_config).result())
        return results[0]["count"] if results else 0
    
    def get_rooms_for_document_version(
        self, document_version_id: str
    ) -> List[Dict[str, Any]]:
        """
        Find all Rooms containing a specific DocumentVersion.
        
        Useful for showing "where is this document used?" queries.
        """
        query = f"""
            SELECT 
                r.*,
                rd.added_at
            FROM `{self.bq.project}.{self.bq.dataset}.{ROOM_DOCUMENTS_TABLE}` rd
            JOIN `{self.bq.project}.{self.bq.dataset}.{ROOMS_TABLE}` r
              ON rd.room_id = r.id
            WHERE rd.document_version_id = @document_version_id
            ORDER BY rd.added_at DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("document_version_id", "STRING", document_version_id)
            ]
        )
        
        results = self.bq.client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]
    
    def check_room_completeness(
        self, room_id: str, required_document_roles: List[str]
    ) -> Dict[str, Any]:
        """
        Check if a Room contains all required document types.
        
        Queries document_profiles to check if all required roles are present.
        Returns missing roles and a boolean completeness flag.
        
        Args:
            room_id: The Room to check
            required_document_roles: List of required document_role values
            
        Returns:
            Dictionary with is_complete, present_roles, missing_roles
        """
        query = f"""
            SELECT DISTINCT dp.document_role
            FROM `{self.bq.project}.{self.bq.dataset}.{ROOM_DOCUMENTS_TABLE}` rd
            JOIN `{self.bq.project}.{self.bq.dataset}.document_profiles` dp
              ON rd.document_version_id = dp.document_version_id
            WHERE rd.room_id = @room_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("room_id", "STRING", room_id)
            ]
        )
        
        results = self.bq.client.query(query, job_config=job_config).result()
        present_roles = {row["document_role"] for row in results}
        
        required_set = set(required_document_roles)
        missing_roles = required_set - present_roles
        
        return {
            "room_id": room_id,
            "is_complete": len(missing_roles) == 0,
            "required_roles": list(required_set),
            "present_roles": list(present_roles),
            "missing_roles": list(missing_roles)
        }
    
    def list_rooms(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List all rooms with optional status filtering."""
        conditions = []
        params = []
        
        if status:
            conditions.append("status = @status")
            params.append(bigquery.ScalarQueryParameter("status", "STRING", status))
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT * FROM `{self.bq.project}.{self.bq.dataset}.{ROOMS_TABLE}`
            {where_clause}
            ORDER BY created_at DESC
            LIMIT @limit OFFSET @offset
        """
        
        params.extend([
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
            bigquery.ScalarQueryParameter("offset", "INT64", offset)
        ])
        
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        results = self.bq.client.query(query, job_config=job_config).result()
        
        return [dict(row) for row in results]
