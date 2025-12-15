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
        Extract tokens from PDF using pypdf (native text).
        Falls back to OCR if needed.
        """
        from pypdf import PdfReader
        
        tokens = []
        
        try:
            reader = PdfReader(pdf_path)
            page = reader.pages[page_num]
            
            # Get page dimensions for bbox normalization
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            
            # Extract text with positions
            # Note: This is simplified - real implementation would use
            # page.extract_text() with visitor pattern for exact positions
            text = page.extract_text()
            
            if not text or len(text.strip()) < 20:
                logger.info(f"Page {page_num} has little native text, OCR recommended")
                return []
            
            # Split into words and create tokens
            # In production, use proper PDF text extraction with positions
            for word in text.split():
                if not word.strip():
                    continue
                
                token = Token(
                    text=word.strip(),
                    bbox=BBox(0, 0, 0.1, 0.1),  # Placeholder - need real extraction
                    page=page_num,
                    token_type=LayoutAgent.infer_token_type(word),
                    confidence=1.0,
                    source=ExtractionMethod.PDF_NATIVE
                )
                tokens.append(token)
            
            logger.info(f"Extracted {len(tokens)} tokens from page {page_num} (PDF native)")
            
        except Exception as e:
            logger.error(f"Failed to extract tokens from PDF: {e}")
            return []
        
        return tokens
    
    @staticmethod
    def cluster_tokens_into_lines(tokens: List[Token], y_tolerance: float = 0.01) -> List[List[Token]]:
        """
        Group tokens into lines based on vertical position.
        
        Args:
            tokens: List of tokens to cluster
            y_tolerance: Maximum y-distance to be considered same line (normalized)
        """
        if not tokens:
            return []
        
        # Sort by y position, then x
        sorted_tokens = sorted(tokens, key=lambda t: (t.bbox.y, t.bbox.x))
        
        lines = []
        current_line = [sorted_tokens[0]]
        current_y = sorted_tokens[0].bbox.y
        
        for token in sorted_tokens[1:]:
            if abs(token.bbox.y - current_y) <= y_tolerance:
                current_line.append(token)
            else:
                lines.append(current_line)
                current_line = [token]
                current_y = token.bbox.y
        
        if current_line:
            lines.append(current_line)
        
        logger.info(f"Clustered {len(tokens)} tokens into {len(lines)} lines")
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
            line_text = ' '.join(t.text for t in line_tokens).lower()
            
            # Check for heading patterns
            is_heading = False
            
            # 1. Contains heading keywords
            if any(keyword in line_text for keyword in LayoutAgent.HEADING_KEYWORDS):
                is_heading = True
            
            # 2. All caps (excluding short words)
            if len(line_text) > 10:
                caps_ratio = sum(1 for c in line_text if c.isupper()) / len(line_text)
                if caps_ratio > 0.7:
                    is_heading = True
            
            # 3. Short line with few tokens (likely a heading)
            if len(line_tokens) <= 5 and len(line_text) < 50:
                if any(keyword in line_text for keyword in LayoutAgent.HEADING_KEYWORDS):
                    is_heading = True
            
            if is_heading:
                heading_text = ' '.join(t.text for t in line_tokens)
                headings.append((idx, heading_text))
                logger.info(f"Detected heading at line {idx}: '{heading_text}'")
        
        return headings
    
    @staticmethod
    def propose_table_regions(lines: List[List[Token]], page_num: int) -> List[Region]:
        """
        Detect table-like structures in lines.
        
        Heuristics:
        - Multiple consecutive lines with similar token counts
        - Tokens roughly aligned vertically (similar x positions)
        - Contains dates, numbers, or data volumes
        """
        if len(lines) < 3:
            return []
        
        regions = []
        current_table_start = None
        current_table_lines = []
        
        for idx, line_tokens in enumerate(lines):
            # Check if line looks table-like
            has_structure = len(line_tokens) >= 2
            has_numbers = any(t.token_type in [TokenType.NUMBER, TokenType.CURRENCY, 
                                               TokenType.DATA_VOLUME, TokenType.DATE] 
                             for t in line_tokens)
            
            if has_structure and has_numbers:
                if current_table_start is None:
                    current_table_start = idx
                current_table_lines.append(line_tokens)
            else:
                # End of potential table
                if len(current_table_lines) >= 3:
                    # Create region
                    all_tokens = [t for line in current_table_lines for t in line]
                    if all_tokens:
                        # Calculate bounding box
                        min_x = min(t.bbox.x for t in all_tokens)
                        min_y = min(t.bbox.y for t in all_tokens)
                        max_x = max(t.bbox.x + t.bbox.width for t in all_tokens)
                        max_y = max(t.bbox.y + t.bbox.height for t in all_tokens)
                        
                        region = Region(
                            region_id=f"table_p{page_num}_l{current_table_start}",
                            region_type=RegionType.TABLE,
                            bbox=BBox(min_x, min_y, max_x - min_x, max_y - min_y),
                            page=page_num,
                            detected_by="layout_agent",
                            confidence=0.7,
                            hints={"lines": len(current_table_lines)}
                        )
                        regions.append(region)
                        logger.info(f"Proposed table region with {len(current_table_lines)} lines")
                
                current_table_start = None
                current_table_lines = []
        
        return regions
    
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
        
        # Add tokens to graph
        token_ids = [graph.add_token(token) for token in tokens]
        
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
                
                region = Region(
                    region_id=f"heading_p{page_num}_l{line_idx}",
                    region_type=RegionType.HEADING,
                    bbox=BBox(min_x, min_y, max_x - min_x, max_y - min_y),
                    page=page_num,
                    detected_by="layout_agent",
                    confidence=0.8,
                    hints={"text": heading_text}
                )
                graph.add_region(region)
        
        # Step 4: Propose table regions
        table_regions = LayoutAgent.propose_table_regions(lines, page_num)
        for region in table_regions:
            graph.add_region(region)
        
        logger.info(f"LayoutAgent completed page {page_num}: "
                   f"{len(tokens)} tokens, {len(lines)} lines, "
                   f"{len(headings)} headings, {len(table_regions)} tables")
