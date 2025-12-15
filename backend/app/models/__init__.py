"""Data models for document understanding"""
# API models (for FastAPI endpoints)
from .api import (
    Region,
    ExtractionRequest,
    JobStatus,
    ExtractionResult,
    UploadResponse
)

# Document graph models (for agentic pipeline)
from .document_graph import (
    DocumentGraph,
    Token,
    Region as GraphRegion,
    Extraction,
    BBox,
    TokenType,
    RegionType,
    ExtractionMethod,
    ValidationStatus,
    AgentDecision
)

__all__ = [
    # API models
    'Region',
    'ExtractionRequest',
    'JobStatus',
    'ExtractionResult',
    'UploadResponse',
    # Document graph models
    'DocumentGraph',
    'Token',
    'GraphRegion',
    'Extraction',
    'BBox',
    'TokenType',
    'RegionType',
    'ExtractionMethod',
    'ValidationStatus',
    'AgentDecision'
]
