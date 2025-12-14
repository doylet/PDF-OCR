import camelot
import io
import logging
from typing import List, Optional
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


class TableExtractionService:
    """Service for extracting tables from PDFs using Camelot"""
    
    @staticmethod
    def extract_tables_from_region(
        pdf_bytes: bytes, 
        page: int, 
        x: float, 
        y: float, 
        width: float, 
        height: float
    ) -> Optional[List[List[str]]]:
        """
        Extract tables from a specific region of a PDF page using Camelot.
        
        Args:
            pdf_bytes: PDF file content as bytes
            page: Page number (1-indexed)
            x, y: Top-left coordinates in pixels at 200 DPI
            width, height: Region dimensions in pixels at 200 DPI
            
        Returns:
            List of rows (each row is a list of cell values), or None if no tables found
        """
        try:
            import tempfile
            import os
            
            # Camelot requires a file path, not BytesIO - write to temp file
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_path = tmp_file.name
            
            try:
                # Convert pixel coordinates (200 DPI) to PDF points (72 DPI)
                # PDF coordinates are from bottom-left, so we need page height
                pdf_file = io.BytesIO(pdf_bytes)
                reader = PdfReader(pdf_file)
                pdf_page = reader.pages[page - 1]  # 0-indexed
                page_height_points = float(pdf_page.mediabox.height)
                
                # Convert coordinates
                dpi_ratio = 72 / 200  # Convert from 200 DPI to 72 DPI points
                left = x * dpi_ratio
                top = page_height_points - (y * dpi_ratio)  # Flip Y axis
                right = (x + width) * dpi_ratio
                bottom = page_height_points - ((y + height) * dpi_ratio)  # Flip Y axis
                
                # Camelot table_areas format: "x1,y1,x2,y2" where y is from bottom
                table_area = f"{left},{bottom},{right},{top}"
                
                logger.info(f"Extracting tables from page {page} area: {table_area}")
                
                # Try lattice mode first (for tables with visible borders)
                try:
                    tables = camelot.read_pdf(
                        tmp_path,
                        pages=str(page),
                        flavor='lattice',
                        table_areas=[table_area],
                        strip_text='\n'
                    )
                    
                    if tables and len(tables) > 0 and len(tables[0].df) > 0:
                        logger.info(f"Lattice mode found {len(tables)} table(s)")
                        return TableExtractionService._convert_tables_to_rows(tables)
                except Exception as e:
                    logger.warning(f"Lattice mode failed: {e}")
                
                # Try stream mode (for tables without visible borders)
                try:
                    tables = camelot.read_pdf(
                        tmp_path,
                        pages=str(page),
                        flavor='stream',
                        table_areas=[table_area],
                        strip_text='\n',
                        edge_tol=50,  # More lenient edge tolerance
                        row_tol=10,   # Row tolerance
                        column_tol=5  # Column tolerance
                    )
                    
                    if tables and len(tables) > 0 and len(tables[0].df) > 0:
                        logger.info(f"Stream mode found {len(tables)} table(s)")
                        return TableExtractionService._convert_tables_to_rows(tables)
                except Exception as e:
                    logger.warning(f"Stream mode failed: {e}")
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
            logger.warning("No tables detected by Camelot")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting tables with Camelot: {e}")
            return None
    
    @staticmethod
    def _convert_tables_to_rows(tables) -> List[List[str]]:
        """Convert Camelot tables to list of rows"""
        all_rows = []
        
        for table in tables:
            # Get DataFrame from table
            df = table.df
            
            # Convert DataFrame to list of lists
            # Include all rows (first row might be header)
            for _, row in df.iterrows():
                row_data = [str(cell).strip() for cell in row]
                # Filter out empty rows
                if any(cell for cell in row_data):
                    all_rows.append(row_data)
        
        return all_rows if all_rows else None
