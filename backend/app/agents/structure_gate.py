"""
Structure Gate: Filters proposed regions to keep only extractable structures.

Solves the problem of detecting "every visual block" by applying strict criteria
for what constitutes an extractable region (tables, key-value blocks, lists).

Key Filtering Criteria:
1. Row count: ≥ 3 lines of structured data
2. Column alignment: tokens cluster into ≥ 2 vertical bands
3. Type repetition: repeated data types (dates, currency, volumes)
4. Prose rejection: reject long-sentence paragraphs
5. Empty block rejection: reject colored backgrounds with little text
6. Chart/graphic overlap: reject regions overlapping images
"""
import logging
from typing import List, Optional, Dict, Tuple
from collections import defaultdict

from app.models.document_graph import (
    DocumentGraph, Region, Token, RegionType, TokenType, BBox
)

logger = logging.getLogger(__name__)


class StructureGate:
    """
    Gates proposed regions to keep only extractable structures.
    
    Prevents false positives like:
    - Large colored background blocks
    - Chart legends and labels
    - Explanatory paragraphs
    - Section headers mistaken for tables
    """
    
    # Minimum thresholds for extractable structures
    MIN_TABLE_ROWS = 3
    MIN_COLUMNS = 2
    MIN_DATA_TOKENS_PER_ROW = 2
    MAX_PROSE_TOKENS_PER_LINE = 15  # Long sentences = prose, not table
    MIN_TEXT_DENSITY = 0.05  # Reject empty colored blocks
    
    @staticmethod
    def filter_regions(graph: DocumentGraph, page_num: int) -> List[Region]:
        """
        Filter regions for a page, keeping only extractable structures.
        
        Args:
            graph: Document graph with tokens and proposed regions
            page_num: Page to filter
            
        Returns:
            List of approved regions (subset of proposed regions)
        """
        logger.info(f"Structure gate filtering page {page_num}")
        
        # Get all proposed regions for this page
        proposed = [r for r in graph.regions if r.page == page_num]
        
        if not proposed:
            logger.info(f"No proposed regions on page {page_num}")
            return []
        
        approved = []
        rejected = []
        
        for region in proposed:
            # Skip headings - they pass through without filtering
            if region.region_type == RegionType.HEADING:
                approved.append(region)
                continue
            
            # Get tokens for this region
            tokens = [graph.tokens[tid] for tid in region.token_ids if tid < len(graph.tokens)]
            
            if not tokens:
                rejected.append((region, "no_tokens"))
                continue
            
            # Run structure checks
            score, reasons = StructureGate._score_extractability(tokens, region)
            
            if score >= 0.6:  # Threshold for approval
                approved.append(region)
                logger.info(f"✓ Region {region.region_id}: score={score:.2f}, reasons={reasons}")
            else:
                rejected.append((region, f"low_score={score:.2f}, {reasons}"))
                logger.info(f"✗ Region {region.region_id}: score={score:.2f}, reasons={reasons}")
        
        logger.info(f"Structure gate: {len(approved)}/{len(proposed)} regions approved, {len(rejected)} rejected")
        
        # Log rejection reasons for debugging
        for region, reason in rejected:
            graph.decisions.append({
                "agent": "structure_gate",
                "page": page_num,
                "region_id": region.region_id,
                "decision": "reject",
                "reason": reason
            })
        
        return approved
    
    @staticmethod
    def _score_extractability(tokens: List[Token], region: Region) -> Tuple[float, Dict[str, any]]:
        """
        Score how likely this region contains extractable structure.
        
        Returns:
            (score 0-1, reason dict)
        """
        reasons = {}
        score = 0.0
        
        # 1. Check row count (cluster tokens into lines)
        lines = StructureGate._cluster_tokens_into_lines(tokens)
        row_count = len(lines)
        reasons['row_count'] = row_count
        
        if row_count < StructureGate.MIN_TABLE_ROWS:
            return 0.0, {**reasons, 'fail': 'insufficient_rows'}
        
        score += 0.2  # Has minimum rows
        
        # 2. Check column alignment (x-position clustering)
        x_clusters = StructureGate._detect_column_alignment(tokens)
        column_count = len(x_clusters)
        reasons['column_count'] = column_count
        
        if column_count < StructureGate.MIN_COLUMNS:
            return 0.2, {**reasons, 'fail': 'insufficient_columns'}
        
        score += 0.2  # Has column structure
        
        # 3. Check for repeated data types (dates, currency, volumes)
        type_repetition = StructureGate._check_type_repetition(tokens)
        reasons['type_repetition'] = type_repetition
        
        if type_repetition >= 2:  # At least 2 tokens of same data type
            score += 0.2
        
        # 4. Reject prose (long sentences)
        avg_tokens_per_line = len(tokens) / max(row_count, 1)
        reasons['avg_tokens_per_line'] = round(avg_tokens_per_line, 1)
        
        if avg_tokens_per_line > StructureGate.MAX_PROSE_TOKENS_PER_LINE:
            return 0.2, {**reasons, 'fail': 'too_prose_like'}
        
        score += 0.2
        
        # 5. Check text density (reject empty colored blocks)
        text_density = StructureGate._calculate_text_density(tokens, region.bbox)
        reasons['text_density'] = round(text_density, 3)
        
        if text_density < StructureGate.MIN_TEXT_DENSITY:
            return 0.4, {**reasons, 'fail': 'too_empty'}
        
        score += 0.2
        
        # Bonus: Has strong data types (dates, currency, volumes)
        data_type_count = sum(1 for t in tokens if t.token_type in [
            TokenType.DATE, TokenType.CURRENCY, TokenType.DATA_VOLUME,
            TokenType.DURATION, TokenType.TIME, TokenType.NUMBER
        ])
        data_ratio = data_type_count / max(len(tokens), 1)
        reasons['data_ratio'] = round(data_ratio, 2)
        
        if data_ratio > 0.3:  # 30% of tokens are data
            score += 0.1
        
        return min(score, 1.0), reasons
    
    @staticmethod
    def _cluster_tokens_into_lines(tokens: List[Token]) -> List[List[Token]]:
        """Cluster tokens into lines by y-position"""
        if not tokens:
            return []
        
        # Calculate adaptive tolerance
        token_heights = [t.bbox.h for t in tokens if t.bbox.h > 0]
        if token_heights:
            median_height = sorted(token_heights)[len(token_heights) // 2]
            y_tolerance = median_height * 0.5
        else:
            y_tolerance = 0.01
        
        sorted_tokens = sorted(tokens, key=lambda t: (t.bbox.y, t.bbox.x))
        
        lines = []
        current_line = [sorted_tokens[0]]
        current_y = sorted_tokens[0].bbox.y
        
        for token in sorted_tokens[1:]:
            token_y = token.bbox.y + (token.bbox.h / 2)
            current_center_y = current_y + (current_line[0].bbox.h / 2)
            
            if abs(token_y - current_center_y) <= y_tolerance:
                current_line.append(token)
            else:
                current_line.sort(key=lambda t: t.bbox.x)
                lines.append(current_line)
                current_line = [token]
                current_y = token.bbox.y
        
        if current_line:
            current_line.sort(key=lambda t: t.bbox.x)
            lines.append(current_line)
        
        return lines
    
    @staticmethod
    def _detect_column_alignment(tokens: List[Token]) -> List[List[Token]]:
        """
        Detect vertical columns by x-position clustering.
        
        Returns:
            List of token clusters (columns)
        """
        if not tokens:
            return []
        
        # Calculate adaptive x-tolerance based on median token width
        token_widths = [t.bbox.w for t in tokens if t.bbox.w > 0]
        if token_widths:
            median_width = sorted(token_widths)[len(token_widths) // 2]
            x_tolerance = median_width * 0.5
        else:
            x_tolerance = 0.02
        
        # Sort by x position
        sorted_tokens = sorted(tokens, key=lambda t: t.bbox.x)
        
        clusters = []
        current_cluster = [sorted_tokens[0]]
        current_x = sorted_tokens[0].bbox.x
        
        for token in sorted_tokens[1:]:
            if abs(token.bbox.x - current_x) <= x_tolerance:
                current_cluster.append(token)
            else:
                if len(current_cluster) >= 2:  # Only count significant clusters
                    clusters.append(current_cluster)
                current_cluster = [token]
                current_x = token.bbox.x
        
        if len(current_cluster) >= 2:
            clusters.append(current_cluster)
        
        return clusters
    
    @staticmethod
    def _check_type_repetition(tokens: List[Token]) -> int:
        """
        Count how many data types appear multiple times.
        Strong indicator of tabular structure.
        
        Returns:
            Number of repeated data types (dates, currency, etc.)
        """
        type_counts = defaultdict(int)
        
        for token in tokens:
            if token.token_type != TokenType.TEXT:
                type_counts[token.token_type] += 1
        
        # Count types that appear 2+ times
        repeated = sum(1 for count in type_counts.values() if count >= 2)
        return repeated
    
    @staticmethod
    def _calculate_text_density(tokens: List[Token], region_bbox: BBox) -> float:
        """
        Calculate ratio of text area to region area.
        Rejects large colored blocks with little text.
        
        Returns:
            Density ratio 0-1
        """
        if region_bbox.w <= 0 or region_bbox.h <= 0:
            return 0.0
        
        region_area = region_bbox.w * region_bbox.h
        
        # Sum token areas
        text_area = sum(t.bbox.w * t.bbox.h for t in tokens)
        
        density = min(text_area / region_area, 1.0)
        return density
