import io
import logging
import os
import subprocess
from typing import List, Optional
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

# Ensure Ghostscript paths are at the FRONT of PATH (before shell aliases)
gs_paths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]
current_path = os.environ.get("PATH", "")
new_paths = [p for p in gs_paths if p not in current_path]
if new_paths:
    os.environ["PATH"] = ":".join(new_paths) + ":" + current_path
    logger.debug(f"Prepended Ghostscript paths to PATH: {new_paths}")

# Check if Camelot and Ghostscript are available
CAMELOT_AVAILABLE = False
try:
    import camelot
    
    # Set Ghostscript path explicitly for Camelot
    try:
        import camelot.utils
        # Camelot uses shutil.which to find gs - ensure it's in PATH
        import shutil
        gs_path = shutil.which("gs")
        if gs_path:
            logger.info(f"✓ Ghostscript found at: {gs_path}")
            # Monkey-patch camelot to use explicit path
            camelot.utils.GS = gs_path
        else:
            # Try explicit paths
            for path in ["/opt/homebrew/bin/gs", "/usr/local/bin/gs", "/usr/bin/gs"]:
                try:
                    result = subprocess.run([path, "--version"], capture_output=True, check=True, timeout=5)
                    logger.info(f"✓ Ghostscript found at: {path}")
                    camelot.utils.GS = path
                    gs_path = path
                    break
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    continue
        
        if not gs_path:
            logger.warning("Ghostscript not found - Camelot table extraction may fail")
    except Exception as e:
        logger.warning(f"Could not configure Ghostscript path for Camelot: {e}")
    
    CAMELOT_AVAILABLE = True
    logger.info("Camelot library loaded successfully")
except ImportError as e:
    logger.warning(f"Camelot not available: {e}. Table extraction will be limited.")

# Ghostscript check - try multiple possible command names
import subprocess

GHOSTSCRIPT_AVAILABLE = False
for cmd in ["/opt/homebrew/bin/gs", "/usr/local/bin/gs", "/usr/bin/gs", "gs"]:
    try:
        subprocess.run([cmd, "--version"], capture_output=True, check=True, timeout=5)
        GHOSTSCRIPT_AVAILABLE = True
        logger.info(f"✓ Ghostscript is available: {cmd}")
        break
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        continue

if not GHOSTSCRIPT_AVAILABLE:
    logger.error(
        "Ghostscript is not installed! Install it via:\n"
        "  macOS: brew install ghostscript\n"
        "  Ubuntu/Debian: sudo apt-get install ghostscript\n"
        "  Docs: https://camelot-py.readthedocs.io/en/master/user/install-deps.html"
    )


class TableExtractor:
    """Service for extracting tables from PDFs using Camelot"""
    
    @staticmethod
    def is_available() -> bool:
        """Check if table extraction is available (requires Ghostscript)"""
        return CAMELOT_AVAILABLE and GHOSTSCRIPT_AVAILABLE
    
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
        # Check if Camelot is available
        if not CAMELOT_AVAILABLE:
            logger.warning(
                "Camelot not available - table extraction disabled. "
                "Install: pip install 'camelot-py[cv]'"
            )
            return None
        
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
                    logger.debug(f"Attempting Camelot lattice extraction for page {page}")
                    tables = camelot.read_pdf(
                        tmp_path,
                        pages=str(page),
                        flavor='lattice',
                        table_areas=[table_area],
                        strip_text='\n'
                    )
                    
                    if tables and len(tables) > 0 and len(tables[0].df) > 0:
                        logger.info(f"✓ Camelot lattice mode extracted {len(tables)} table(s) from page {page}")
                        return TableExtractor._convert_tables_to_rows(tables)
                    else:
                        logger.debug(f"Lattice mode found no tables on page {page}")
                except Exception as e:
                    logger.warning(f"Camelot lattice mode failed on page {page}: {e}")
                    if "Ghostscript" in str(e):
                        logger.error(
                            "CRITICAL: Ghostscript is not installed! "
                            "This will prevent table extraction. Install via:\n"
                            "  macOS: brew install ghostscript\n"
                            "  Ubuntu/Debian: sudo apt-get install ghostscript"
                        )
                
                # Try stream mode (for tables without visible borders)
                try:
                    logger.debug(f"Attempting Camelot stream extraction for page {page}")
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
                        logger.info(f"✓ Camelot stream mode extracted {len(tables)} table(s) from page {page}")
                        return TableExtractor._convert_tables_to_rows(tables)
                    else:
                        logger.debug(f"Stream mode found no tables on page {page}")
                except Exception as e:
                    logger.warning(f"Camelot stream mode failed on page {page}: {e}")
                    if "Ghostscript" in str(e):
                        logger.error(
                            "CRITICAL: Ghostscript is not installed! "
                            "This will prevent table extraction. Install via:\n"
                            "  macOS: brew install ghostscript\n"
                            "  Ubuntu/Debian: sudo apt-get install ghostscript"
                        )
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
            logger.info(f"No tables detected by Camelot on page {page} in specified region")
            return None
            
        except Exception as e:
            logger.error(
                f"Camelot extraction failed for page {page}: {e}",
                exc_info=True,
                extra={"page": page, "region": f"x={x}, y={y}, w={width}, h={height}"}
            )
            if "Ghostscript" in str(e):
                logger.error(
                    "CRITICAL: Ghostscript dependency missing! "
                    "All Camelot table extractions will fail until installed."
                )
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
