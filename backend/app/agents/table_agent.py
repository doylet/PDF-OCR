"""
Table Agent: Extracts structured tables from token regions.

Responsibilities:
1. Column clustering on tokens (vertical alignment)
2. Row grouping (horizontal lines)
3. Output generic table grid (rows/cols + cell text)
4. Does NOT assume schema yet (that's Schema Agent's job)

This agent is deterministic and geometry-based.
"""
import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from app.models.document_graph import (
    DocumentGraph, Token, Region, Extraction,
    BBox, ValidationStatus, ExtractionMethod
)

logger = logging.getLogger(__name__)


class TableAgent:
    """
    Extracts tables using token geometry (column clustering + row grouping).
    """
    
    # Clustering tolerances
    X_TOLERANCE = 0.02  # Column alignment tolerance (normalized coords)
    Y_TOLERANCE = 0.015  # Row alignment tolerance
    
    @staticmethod
    def extract_table(graph: DocumentGraph, region: Region) -> Optional[Extraction]:
        """
        Main entry point: extract table from a region.
        
        Args:
            graph: Document graph with tokens
            region: Table region to extract from
        
        Returns:
            Extraction with structured table data
        """
        logger.info(f"TableAgent extracting from {region.region_id}")
        
        # Get tokens in region
        tokens = graph.get_tokens_in_region(region.region_id)
        
        if not tokens:
            logger.warning(f"No tokens in region {region.region_id} (token_ids={region.token_ids[:5] if region.token_ids else []})")
            return None
        
        logger.info(f"Found {len(tokens)} tokens in {region.region_id}")
        
        # Sample tokens for debugging
        sample_tokens = [f"{t.text}@({t.bbox.x:.3f},{t.bbox.y:.3f})" for t in tokens[:5]]
        logger.info(f"Sample tokens: {sample_tokens}")
        
        # Step 1: Cluster tokens into columns (vertical alignment)
        columns = TableAgent._cluster_columns(tokens)
        
        if len(columns) < 2:
            # Try with more lenient tolerance for single-column tables or narrow regions
            logger.info(f"Only {len(columns)} columns with X_TOLERANCE={TableAgent.X_TOLERANCE}, trying lenient mode")
            
            # If we have at least a few tokens, try to extract as simple list
            if len(tokens) >= 3:
                # Fallback: treat as single column, group into rows
                rows = TableAgent._group_rows(tokens, [[t] for t in tokens])
                if len(rows) >= 2:
                    table_data = [[t.text for t in row] for row in rows]
                    logger.info(f"Extracted {len(rows)} rows as single-column table")
                    
                    extraction = Extraction(
                        extraction_id=f"ext_{region.region_id}",
                        region_id=region.region_id,
                        data={
                            "rows": table_data,
                            "columns": ["col_0"],
                            "num_rows": len(table_data),
                            "num_cols": 1
                        },
                        schema=None,
                        confidence=0.6,  # Lower confidence for single-column
                        validation_status=ValidationStatus.PENDING,
                        extracted_by="table_agent",
                        method=ExtractionMethod.AGENT_INFERRED
                    )
                    return extraction
            
            logger.warning(f"Found only {len(columns)} columns, need at least 2 (tokens={len(tokens)})")
            return None
        
        # Step 2: Group tokens into rows (horizontal alignment)
        rows = TableAgent._group_rows(tokens, columns)
        
        if len(rows) < 2:  # Need header + at least 1 data row
            logger.warning(f"Found only {len(rows)} rows, need at least 2 (columns={len(columns)}, tokens={len(tokens)})")
            return None
        
        # Step 3: Build table grid
        table_data = TableAgent._build_table_grid(rows, len(columns))
        
        # Step 4: Create extraction
        extraction = Extraction(
            extraction_id=f"ext_{region.region_id}",
            region_id=region.region_id,
            data={
                "rows": table_data,
                "columns": [f"col_{i}" for i in range(len(columns))],
                "num_rows": len(table_data),
                "num_cols": len(columns)
            },
            schema=None,  # Schema Agent will determine this
            confidence=0.8,
            validation_status=ValidationStatus.PENDING,
            extracted_by="table_agent",
            method=ExtractionMethod.AGENT_INFERRED
        )
        
        logger.info(f"Extracted table: {len(table_data)} rows × {len(columns)} cols")
        
        return extraction
    
    @staticmethod
    def _cluster_columns(tokens: List[Token]) -> List[List[Token]]:
        """
        Cluster tokens into columns based on vertical alignment (x position).
        
        Returns:
            List of columns, each containing tokens at similar x positions
        """
        if not tokens:
            return []
        
        # Sort tokens by x position
        sorted_tokens = sorted(tokens, key=lambda t: t.bbox.x)
        
        columns = []
        current_column = [sorted_tokens[0]]
        current_x = sorted_tokens[0].bbox.x
        
        for token in sorted_tokens[1:]:
            # Check if token is aligned with current column
            if abs(token.bbox.x - current_x) <= TableAgent.X_TOLERANCE:
                current_column.append(token)
            else:
                # Start new column
                columns.append(current_column)
                current_column = [token]
                current_x = token.bbox.x
        
        # Add last column
        if current_column:
            columns.append(current_column)
        
        logger.info(f"Clustered {len(tokens)} tokens into {len(columns)} columns")
        
        return columns
    
    @staticmethod
    def _group_rows(tokens: List[Token], columns: List[List[Token]]) -> List[List[Token]]:
        """
        Group tokens into rows based on horizontal alignment (y position).
        
        Returns:
            List of rows, each containing tokens at similar y positions
        """
        # Sort all tokens by y position
        sorted_tokens = sorted(tokens, key=lambda t: t.bbox.y)
        
        rows = []
        current_row = [sorted_tokens[0]]
        current_y = sorted_tokens[0].bbox.y
        
        for token in sorted_tokens[1:]:
            # Check if token is aligned with current row
            if abs(token.bbox.y - current_y) <= TableAgent.Y_TOLERANCE:
                current_row.append(token)
            else:
                # Start new row
                rows.append(current_row)
                current_row = [token]
                current_y = token.bbox.y
        
        # Add last row
        if current_row:
            rows.append(current_row)
        
        logger.info(f"Grouped {len(tokens)} tokens into {len(rows)} rows")
        
        return rows
    
    @staticmethod
    def _build_table_grid(rows: List[List[Token]], num_cols: int) -> List[List[str]]:
        """
        Build a rectangular grid from row groups.
        
        Args:
            rows: List of token groups (one per row)
            num_cols: Expected number of columns
        
        Returns:
            2D array of cell values (strings)
        """
        grid = []
        
        for row_tokens in rows:
            # Sort tokens in row by x position (left to right)
            sorted_tokens = sorted(row_tokens, key=lambda t: t.bbox.x)
            
            # Build row
            row_cells = []
            for token in sorted_tokens:
                row_cells.append(token.text)
            
            # Pad or truncate to match column count
            while len(row_cells) < num_cols:
                row_cells.append("")
            
            if len(row_cells) > num_cols:
                row_cells = row_cells[:num_cols]
            
            grid.append(row_cells)
        
        return grid
    
    @staticmethod
    def merge_adjacent_cells(grid: List[List[str]]) -> List[List[str]]:
        """
        Merge cells that were split by tokenization but belong together.
        
        Example: ["$", "45.67"] → ["$45.67"]
        
        This is a post-processing step to clean up the grid.
        """
        merged_grid = []
        
        for row in grid:
            merged_row = []
            i = 0
            
            while i < len(row):
                cell = row[i]
                
                # Check if next cell should be merged
                if i + 1 < len(row):
                    next_cell = row[i + 1]
                    
                    # Merge patterns
                    should_merge = False
                    
                    # 1. Currency symbol + number
                    if cell in ['$', '£', '€', '¥'] and next_cell and next_cell[0].isdigit():
                        should_merge = True
                    
                    # 2. Number + unit
                    if cell and cell[-1].isdigit() and next_cell in ['MB', 'GB', 'KB', 'TB']:
                        should_merge = True
                    
                    if should_merge:
                        merged_row.append(cell + next_cell)
                        i += 2
                        continue
                
                merged_row.append(cell)
                i += 1
            
            merged_grid.append(merged_row)
        
        return merged_grid
