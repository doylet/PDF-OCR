"""
Layout Agent: Builds tokens, lines, blocks, and detects document structure.

Responsibilities:
1. Extract tokens from PDF (native text preferred)
2. Cluster tokens into lines and blocks
3. Detect headings and section boundaries
4. Propose region candidates (tables, key-value blocks)

This agent is deterministic and geometry-based, not LLM-heavy.
"""
import re
import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from app.models.document_graph import (
    DocumentGraph, Token, Region, BBox, 
    TokenType, RegionType, ExtractionMethod
)

logger = logging.getLogger(__name__)


class LayoutAgent:
    """
    Builds document structure from tokens using geometry and text patterns.
    """
    
    # Type inference patterns
    PATTERNS = {
        TokenType.DATE: [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}',
            r'\d{1,2}\s+[A-Z][a-z]{2}',  # "06 Oct"
        ],
        TokenType.TIME: [
            r'\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?',
        ],
        TokenType.PHONE: [
            r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        ],
        TokenType.CURRENCY: [
            r'[$£€¥]\s*\d+(?:,\d{3})*(?:\.\d{2})?',
            r'\d+(?:,\d{3})*(?:\.\d{2})??\s*(?:USD|EUR|GBP|AUD)',
        ],
        TokenType.DATA_VOLUME: [
            r'\d+(?:\.\d+)?\s*(?:KB|MB|GB|TB)',
        ],
        TokenType.DURATION: [
            r'\d{1,2}:\d{2}:\d{2}',
        ],
        TokenType.EMAIL: [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        ],
        TokenType.NUMBER: [
            r'^\d+(?:\.\d+)?$',
        ],
    }
    
    # Heading keywords
    HEADING_KEYWORDS = [
        'summary', 'total', 'calls', 'messages', 'data', 'usage',
        'invoice', 'statement', 'billing', 'charges', 'details',
        'mobile', 'sms', 'mms', 'international', 'roaming'
    ]
    
    # Table stop cues (semantic end-of-table indicators)
    TABLE_STOP_CUES = [
        'total', 'subtotal', 'balance', 'grand total',
        'gigabyte', 'megabyte', 'kilobyte',
        '1 gigabyte', '1 megabyte', '1 gb =', '1 mb ='
    ]
    
    @staticmethod
    def infer_token_type(text: str) -> TokenType:
        """Classify token by pattern matching"""
        text = text.strip()
        
        for token_type, patterns in LayoutAgent.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return token_type
        
        return TokenType.TEXT
    
    @staticmethod
    def extract_tokens_from_pdf(pdf_path: str, page_num: int) -> List[Token]:
        """
        Extract tokens from PDF using pdfplumber for accurate word-level bounding boxes.
        Falls back to OCR if needed.
        """
        import pdfplumber
        
        tokens = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if page_num >= len(pdf.pages):
                    logger.error(f"Page {page_num} out of range (PDF has {len(pdf.pages)} pages)")
                    return []
                
                page = pdf.pages[page_num]
                page_width = page.width
                page_height = page.height
                
                # Extract words with accurate bounding boxes
                words = page.extract_words(use_text_flow=True, keep_blank_chars=False)
                
                for word in words:
                    text = word["text"].strip()
                    if not text:
                        continue
                    
                    # pdfplumber coordinates: x0, top, x1, bottom
                    x0 = word["x0"]
                    x1 = word["x1"]
                    top = word["top"]
                    bottom = word["bottom"]
                    
                    # Normalize to 0..1 range
                    norm_x = x0 / page_width if page_width > 0 else 0
                    norm_y = top / page_height if page_height > 0 else 0
                    norm_width = (x1 - x0) / page_width if page_width > 0 else 0.1
                    norm_height = (bottom - top) / page_height if page_height > 0 else 0.01
                    
                    token = Token(
                        text=text,
                        bbox=BBox(norm_x, norm_y, norm_width, norm_height),
                        page=page_num,
                        token_type=LayoutAgent.infer_token_type(text),
                        confidence=1.0,
                        source=ExtractionMethod.PDF_NATIVE
                    )
                    tokens.append(token)
                
                if len(tokens) < 10:
                    logger.info(f"Page {page_num} has little native text ({len(tokens)} tokens), OCR recommended")
                    return []
                
                logger.info(f"Extracted {len(tokens)} tokens from page {page_num} using pdfplumber")
            
        except Exception as e:
            logger.error(f"Failed to extract tokens from PDF: {e}")
            return []
        
        return tokens
    
    @staticmethod
    def cluster_tokens_into_lines(tokens: List[Token], y_tolerance: Optional[float] = None) -> List[List[Token]]:
        """
        Group tokens into lines based on vertical position using adaptive tolerance.
        
        Args:
            tokens: List of tokens to cluster
            y_tolerance: Maximum y-distance to be considered same line (normalized).
                        If None, uses median token height * 0.5
        """
        if not tokens:
            return []
        
        # Calculate adaptive tolerance based on median token height if not provided
        if y_tolerance is None:
            token_heights = [t.bbox.h for t in tokens if t.bbox.h > 0]
            if token_heights:
                median_height = sorted(token_heights)[len(token_heights) // 2]
                y_tolerance = median_height * 0.5
                logger.info(f"Using adaptive y_tolerance: {y_tolerance:.4f} (median height: {median_height:.4f})")
            else:
                y_tolerance = 0.01
        
        # Sort by y position (top to bottom), then x (left to right)
        sorted_tokens = sorted(tokens, key=lambda t: (t.bbox.y, t.bbox.x))
        
        lines = []
        current_line = [sorted_tokens[0]]
        current_y = sorted_tokens[0].bbox.y
        
        for token in sorted_tokens[1:]:
            # Use vertical center for more accurate line clustering
            token_y = token.bbox.y + (token.bbox.h / 2)
            current_center_y = current_y + (current_line[0].bbox.h / 2)
            
            if abs(token_y - current_center_y) <= y_tolerance:
                current_line.append(token)
            else:
                # Sort tokens in line by x position (left to right)
                current_line.sort(key=lambda t: t.bbox.x)
                lines.append(current_line)
                current_line = [token]
                current_y = token.bbox.y
        
        if current_line:
            current_line.sort(key=lambda t: t.bbox.x)
            lines.append(current_line)
        
        logger.info(f"Clustered {len(tokens)} tokens into {len(lines)} lines (tolerance: {y_tolerance:.4f})")
        return lines
    
    @staticmethod
    def detect_headings(lines: List[List[Token]]) -> List[Tuple[int, str]]:
        """
        Detect heading lines that indicate section boundaries.
        
        Returns:
            List of (line_index, heading_text) tuples
        """
        headings = []
        
        for idx, line_tokens in enumerate(lines):
            if not line_tokens:
                continue
                
            line_text = ' '.join(t.text for t in line_tokens)
            line_text_lower = line_text.lower()
            
            # Exclude lines with data values (these are table rows, not headings)
            has_data_values = any(t.token_type in [TokenType.NUMBER, TokenType.CURRENCY, 
                                                    TokenType.DATA_VOLUME, TokenType.DATE,
                                                    TokenType.TIME, TokenType.DURATION] 
                                 for t in line_tokens)
            
            if has_data_values:
                continue
            
            # Exclude single-word lines (too short to be meaningful headings)
            if len(line_tokens) == 1 and len(line_text) < 8:
                continue
            
            # Heading must match ONE of these strict criteria:
            is_heading = False
            
            # 1. Strong heading keyword match (specific section indicators)
            strong_keywords = ['summary', 'total calls', 'total messages', 'total data', 
                              'invoice', 'statement', 'billing details', 'charges',
                              'mobile number', 'plan details', 'account summary']
            if any(keyword in line_text_lower for keyword in strong_keywords):
                is_heading = True
            
            # 2. All caps AND substantive (not just noise)
            elif len(line_text) > 10:
                caps_ratio = sum(1 for c in line_text if c.isupper()) / len(line_text)
                # Require very high caps ratio and no lowercase (strict)
                if caps_ratio > 0.85 and len(line_tokens) >= 2:
                    is_heading = True
            
            if is_heading:
                headings.append((idx, line_text))
                logger.info(f"Detected heading at line {idx}: '{line_text}'")
        
        return headings
    
    @staticmethod
    def propose_table_regions(lines: List[List[Token]], page_num: int, token_id_map: Dict[Token, int] = None) -> List[Region]:
        """
        Detect table-like structures in lines.
        
        Heuristics:
        - Multiple consecutive lines with similar token counts
        - Tokens roughly aligned vertically (similar x positions)
        - Contains dates, numbers, or data volumes
        """
        if len(lines) < 3:
            return []
        
        if token_id_map is None:
            token_id_map = {}
        
        regions = []
        current_table_start = None
        current_table_lines = []
        
        for idx, line_tokens in enumerate(lines):
            # Check for semantic stop cues (totals, unit explanations)
            line_text = ' '.join(t.text for t in line_tokens).lower()
            is_stop_cue = any(cue in line_text for cue in LayoutAgent.TABLE_STOP_CUES)
            
            # Check if line looks table-like
            has_structure = len(line_tokens) >= 2
            has_numbers = any(t.token_type in [TokenType.NUMBER, TokenType.CURRENCY, 
                                               TokenType.DATA_VOLUME, TokenType.DATE] 
                             for t in line_tokens)
            
            # Stop cues end the table
            if is_stop_cue and current_table_lines:
                logger.info(f"Stop cue detected at line {idx}: '{line_text[:50]}'")
                if len(current_table_lines) >= 3:
                    region = LayoutAgent._create_table_region(
                        current_table_lines, page_num, current_table_start
                    )
                    if region:
                        regions.append(region)
                current_table_start = None
                current_table_lines = []
            elif has_structure and has_numbers and not is_stop_cue:
                if current_table_start is None:
                    current_table_start = idx
                current_table_lines.append(line_tokens)
            else:
                # End of potential table
                if len(current_table_lines) >= 3:
                    region = LayoutAgent._create_table_region(
                        current_table_lines, page_num, current_table_start, token_id_map
                    )
                    if region:
                        regions.append(region)
                
                current_table_start = None
                current_table_lines = []
        
        # CRITICAL: Flush any open table at end of page
        if current_table_lines and len(current_table_lines) >= 3:
            logger.info(f"Flushing open table at end of page: {len(current_table_lines)} lines")
            region = LayoutAgent._create_table_region(
                current_table_lines, page_num, current_table_start, token_id_map
            )
            if region:
                regions.append(region)
        
        return regions
    
    @staticmethod
    def _create_table_region(
        table_lines: List[List[Token]], 
        page_num: int, 
        start_idx: int,
        token_id_map: Dict[Token, int] = None
    ) -> Optional[Region]:
        """Create a table region from accumulated lines"""
        all_tokens = [t for line in table_lines for t in line]
        if not all_tokens:
            return None
        
        # Calculate bounding box
        min_x = min(t.bbox.x for t in all_tokens)
        min_y = min(t.bbox.y for t in all_tokens)
        max_x = max(t.bbox.x + t.bbox.width for t in all_tokens)
        max_y = max(t.bbox.y + t.bbox.height for t in all_tokens)
        
        # Get token IDs if mapping provided
        token_ids = []
        if token_id_map:
            token_ids = [token_id_map[id(t)] for t in all_tokens if id(t) in token_id_map]
        
        region = Region(
            region_id=f"table_p{page_num}_l{start_idx}",
            region_type=RegionType.TABLE,
            bbox=BBox(min_x, min_y, max_x - min_x, max_y - min_y),
            page=page_num,
            detected_by="layout_agent",
            confidence=0.7,
            hints={"lines": len(table_lines)},
            token_ids=token_ids
        )
        logger.info(f"Proposed table region with {len(table_lines)} lines, {len(token_ids)} tokens")
        return region
    
    @staticmethod
    def process_page(graph: DocumentGraph, page_num: int, pdf_path: str) -> None:
        """
        Main entry point: process a page and populate the graph.
        
        Steps:
        1. Extract tokens
        2. Cluster into lines
        3. Detect headings
        4. Propose regions
        """
        logger.info(f"LayoutAgent processing page {page_num}")
        
        # Step 1: Extract tokens
        tokens = LayoutAgent.extract_tokens_from_pdf(pdf_path, page_num)
        
        if not tokens:
            logger.warning(f"No tokens extracted from page {page_num}, OCR needed")
            graph.decisions.append({
                "agent": "layout_agent",
                "page": page_num,
                "decision": "ocr_needed",
                "reason": "No native PDF text found"
            })
            return
        
        # Add tokens to graph and build token ID map (using id() as key since Token is unhashable)
        token_id_map = {}
        for token in tokens:
            token_id = graph.add_token(token)
            token_id_map[id(token)] = token_id
        
        # Step 2: Cluster into lines
        lines = LayoutAgent.cluster_tokens_into_lines(tokens)
        
        # Step 3: Detect headings
        headings = LayoutAgent.detect_headings(lines)
        
        for line_idx, heading_text in headings:
            # Create heading regions
            line_tokens = lines[line_idx]
            if line_tokens:
                min_x = min(t.bbox.x for t in line_tokens)
                min_y = min(t.bbox.y for t in line_tokens)
                max_x = max(t.bbox.x + t.bbox.width for t in line_tokens)
                max_y = max(t.bbox.y + t.bbox.height for t in line_tokens)
                
                # Get token IDs for this heading
                heading_token_ids = [token_id_map[id(t)] for t in line_tokens if id(t) in token_id_map]
                
                region = Region(
                    region_id=f"heading_p{page_num}_l{line_idx}",
                    region_type=RegionType.HEADING,
                    bbox=BBox(min_x, min_y, max_x - min_x, max_y - min_y),
                    page=page_num,
                    detected_by="layout_agent",
                    confidence=0.8,
                    hints={"text": heading_text},
                    token_ids=heading_token_ids
                )
                graph.add_region(region)
        
        # Step 4: Propose table regions
        table_regions = LayoutAgent.propose_table_regions(lines, page_num, token_id_map)
        for region in table_regions:
            graph.add_region(region)
        
        logger.info(f"LayoutAgent completed page {page_num}: "
                   f"{len(tokens)} tokens, {len(lines)} lines, "
                   f"{len(headings)} headings, {len(table_regions)} tables")
