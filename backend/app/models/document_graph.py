"""
Document Graph: Shared intermediate representation for agentic extraction.

All agents read/write to this deterministic structure, keeping the system
grounded and inspectable. No "magic extraction" - agents decide and validate
based on tokens + geometry.
"""
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class TokenType(str, Enum):
    """Classification of text tokens"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    TIME = "time"
    PHONE = "phone"
    CURRENCY = "currency"
    DATA_VOLUME = "data_volume"  # MB, GB, KB
    DURATION = "duration"  # 00:01:23
    EMAIL = "email"
    URL = "url"
    UNKNOWN = "unknown"


class RegionType(str, Enum):
    """Type of document region"""
    TABLE = "table"
    KEY_VALUE = "key_value"
    LIST = "list"
    TOTALS = "totals"
    HEADING = "heading"
    FOOTER = "footer"
    UNKNOWN = "unknown"


class ExtractionMethod(str, Enum):
    """Provenance: how was this data extracted?"""
    PDF_NATIVE = "pdf_native"
    CAMELOT = "camelot"
    DOCUMENT_AI = "document_ai"
    OCR_FALLBACK = "ocr_fallback"
    AGENT_INFERRED = "agent_inferred"


class ValidationStatus(str, Enum):
    """Result of validation checks"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    PENDING = "pending"


class JobOutcome(str, Enum):
    """Overall job result classification"""
    SUCCESS = "success"  # At least one valid extraction
    PARTIAL_SUCCESS = "partial_success"  # Some extractions failed/low confidence
    NO_MATCH = "no_match"  # Agent ran but found nothing
    FAILED = "failed"  # Processing error


@dataclass
class BBox:
    """Bounding box in normalized coordinates (0-1)"""
    x: float  # left
    y: float  # top
    width: float
    height: float
    
    def contains(self, other: 'BBox') -> bool:
        """Check if this bbox contains another"""
        return (self.x <= other.x and 
                self.y <= other.y and
                self.x + self.width >= other.x + other.width and
                self.y + self.height >= other.y + other.height)
    
    def intersects(self, other: 'BBox') -> bool:
        """Check if this bbox intersects another"""
        return not (self.x + self.width < other.x or
                   other.x + other.width < self.x or
                   self.y + self.height < other.y or
                   other.y + other.height < self.y)
    
    def area(self) -> float:
        """Calculate area"""
        return self.width * self.height


@dataclass
class Token:
    """
    A single text token with geometry and type.
    This is the atomic unit - everything builds from tokens.
    """
    text: str
    bbox: BBox
    page: int
    token_type: TokenType = TokenType.UNKNOWN
    confidence: float = 1.0
    
    # Provenance
    source: ExtractionMethod = ExtractionMethod.PDF_NATIVE
    
    def __repr__(self) -> str:
        return f"Token('{self.text}', {self.token_type}, p{self.page})"


@dataclass
class Region:
    """
    A candidate region (table, key-value block, etc.)
    Contains references to tokens, not raw text.
    """
    region_id: str
    region_type: RegionType
    bbox: BBox
    page: int
    
    # Tokens contained in this region
    token_ids: List[int] = field(default_factory=list)
    
    # Provenance
    detected_by: str = "unknown"  # which agent proposed this?
    confidence: float = 0.0
    
    # Schema hints
    hints: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return f"Region({self.region_id}, {self.region_type}, {len(self.token_ids)} tokens)"


@dataclass
class Extraction:
    """
    Typed extraction output from a region.
    This is what agents produce after processing a region.
    """
    extraction_id: str
    region_id: str
    
    # The actual extracted data
    data: Dict[str, Any]  # structured output (table, key-value pairs, etc.)
    schema: Optional[str] = None  # schema name if matched
    
    # Quality metrics
    confidence: float = 0.0
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validation_errors: List[str] = field(default_factory=list)
    
    # Provenance
    extracted_by: str = "unknown"  # which agent/extractor?
    method: ExtractionMethod = ExtractionMethod.AGENT_INFERRED
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __repr__(self) -> str:
        return f"Extraction({self.extraction_id}, {self.schema}, {self.validation_status})"


@dataclass
class DebugArtifact:
    """Debug artifacts for inspection"""
    artifact_id: str
    artifact_type: str  # "cropped_png", "ocr_json", "token_visualization"
    gcs_path: str
    description: str
    related_region_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentDecision:
    """
    Structured decision from an agent.
    No free-form actions - agents must use this enum-based interface.
    """
    class Action(str, Enum):
        ACCEPT = "accept"
        RETRY_PAD = "retry_pad"  # expand crop margins
        RETRY_OCR = "retry_ocr"  # force OCR instead of PDF text
        RETRY_HIGHER_DPI = "retry_higher_dpi"
        SPLIT_REGION = "split_region"  # detected multiple sections
        ESCALATE = "escalate"  # needs human review
        REJECT = "reject"
    
    action: Action
    confidence: float
    evidence: List[str]  # pointers to tokens/regions/spans
    explanation: str
    next_params: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return f"Decision({self.action}, conf={self.confidence:.2f})"


@dataclass
class DocumentGraph:
    """
    The shared state for a single extraction job.
    All agents read/write to this structure.
    """
    job_id: str
    pdf_path: str
    
    # Core data structures
    pages: List[Dict[str, Any]] = field(default_factory=list)  # page metadata
    tokens: List[Token] = field(default_factory=list)
    regions: List[Region] = field(default_factory=list)
    extractions: List[Extraction] = field(default_factory=list)
    debug_artifacts: List[DebugArtifact] = field(default_factory=list)
    
    # Agent decisions and audit trail
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Job state
    status: str = "pending"
    outcome: Optional[JobOutcome] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Trace/Summary for observability
    trace: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_token(self, token: Token) -> int:
        """Add a token and return its ID"""
        token_id = len(self.tokens)
        self.tokens.append(token)
        return token_id
    
    def add_region(self, region: Region) -> str:
        """Add a region and return its ID"""
        self.regions.append(region)
        return region.region_id
    
    def add_extraction(self, extraction: Extraction) -> str:
        """Add an extraction and return its ID"""
        self.extractions.append(extraction)
        return extraction.extraction_id
    
    def get_tokens_in_region(self, region_id: str) -> List[Token]:
        """Get all tokens contained in a region"""
        region = next((r for r in self.regions if r.region_id == region_id), None)
        if not region:
            return []
        return [self.tokens[tid] for tid in region.token_ids if tid < len(self.tokens)]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for Firestore storage"""
        return {
            "job_id": self.job_id,
            "pdf_path": self.pdf_path,
            "status": self.status,
            "num_pages": len(self.pages),
            "num_tokens": len(self.tokens),
            "num_regions": len(self.regions),
            "num_extractions": len(self.extractions),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
