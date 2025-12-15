from google.cloud import documentai_v1 as documentai
from app.config import get_settings
from app.dependencies import get_documentai_client
from app.models import Region, ExtractionResult
from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from PIL import Image
import io
import logging
from typing import List

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentAIService:
    """Service for Document AI processing"""
    
    def __init__(self):
        self.client = get_documentai_client()
        self.processor_name = f"projects/{settings.gcp_project_id}/locations/{settings.gcp_location}/processors/{settings.gcp_processor_id}"
    
    def crop_pdf_region(self, pdf_bytes: bytes, region: Region) -> bytes:
        """Crop a region from a PDF page and return as image bytes"""
        try:
            # Convert PDF page to image
            images = convert_from_bytes(
                pdf_bytes,
                first_page=region.page,
                last_page=region.page,
                dpi=200
            )
            
            if not images:
                raise ValueError(f"Could not convert page {region.page} to image")
            
            image = images[0]
            W, H = image.size
            
            # Region coordinates are normalized fractions (0-1), convert to pixels
            # Add 5% padding on all sides to handle imperfect user selection
            pad_fraction = 0.05
            
            x0 = max(0, int((region.x - pad_fraction) * W))
            y0 = max(0, int((region.y - pad_fraction) * H))
            x1 = min(W, int((region.x + region.width + pad_fraction) * W))
            y1 = min(H, int((region.y + region.height + pad_fraction) * H))
            
            logger.info(f"Cropping normalized region ({region.x:.3f}, {region.y:.3f}, {region.width:.3f}, {region.height:.3f}) to pixels ({x0}, {y0}, {x1}, {y1}) with 5% padding on {W}x{H} image")
            cropped_image = image.crop((x0, y0, x1, y1))
            
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            cropped_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return img_byte_arr.getvalue()
        
        except Exception as e:
            logger.error(f"Error cropping PDF region: {e}")
            raise
    
    def process_document(self, document_bytes: bytes, mime_type: str = "image/png") -> documentai.Document:
        """Process document with Document AI"""
        try:
            raw_document = documentai.RawDocument(
                content=document_bytes,
                mime_type=mime_type
            )
            
            request = documentai.ProcessRequest(
                name=self.processor_name,
                raw_document=raw_document
            )
            
            result = self.client.process_document(request=request)
            return result.document
        
        except Exception as e:
            logger.error(f"Error processing document with Document AI: {e}")
            raise
    
    def extract_text_from_document(self, document: documentai.Document) -> tuple[str, float]:
        """Extract text and confidence from Document AI result"""
        text = document.text
        
        # Calculate average confidence
        confidences = [page.layout.confidence for page in document.pages if hasattr(page.layout, 'confidence')]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return text, avg_confidence
    
    def extract_structured_data(self, document: documentai.Document) -> dict:
        """Extract structured data (tables, form fields) from Document AI result"""
        structured_data = {
            "tables": [],
            "form_fields": []
        }
        
        # Extract tables
        for page in document.pages:
            if hasattr(page, 'tables'):
                for table in page.tables:
                    table_data = []
                    
                    # Add header rows first
                    if hasattr(table, 'header_rows'):
                        for row in table.header_rows:
                            row_data = []
                            for cell in row.cells:
                                cell_text = self._get_text_from_layout(document.text, cell.layout)
                                row_data.append(cell_text)
                            table_data.append(row_data)
                    
                    # Add body rows
                    for row in table.body_rows:
                        row_data = []
                        for cell in row.cells:
                            cell_text = self._get_text_from_layout(document.text, cell.layout)
                            row_data.append(cell_text)
                        table_data.append(row_data)
                    
                    if table_data:  # Only add non-empty tables
                        structured_data["tables"].append(table_data)
        
        # Extract form fields
        for page in document.pages:
            if hasattr(page, 'form_fields'):
                for field in page.form_fields:
                    field_name = self._get_text_from_layout(document.text, field.field_name)
                    field_value = self._get_text_from_layout(document.text, field.field_value)
                    structured_data["form_fields"].append({
                        "name": field_name,
                        "value": field_value
                    })
        
        return structured_data
    
    def _get_text_from_layout(self, full_text: str, layout) -> str:
        """Extract text from a layout element"""
        if not hasattr(layout, 'text_anchor') or not layout.text_anchor.text_segments:
            return ""
        
        text_segments = []
        for segment in layout.text_anchor.text_segments:
            start = int(segment.start_index) if hasattr(segment, 'start_index') else 0
            end = int(segment.end_index) if hasattr(segment, 'end_index') else len(full_text)
            text_segments.append(full_text[start:end])
        
        return "".join(text_segments).strip()
    
    def process_regions(self, pdf_bytes: bytes, regions: List[Region], job_id: str = None) -> List[ExtractionResult]:
        """Process multiple regions and return extraction results"""
        from app.services.table_extractor import TableExtractionService
        from app.services.text_parser import TextParser
        from app.services.storage import storage_service
        from app.services.region_analyzer import RegionAnalyzer, RegionType
        
        results = []
        
        for idx, region in enumerate(regions):
            try:
                # First attempt: Try Camelot for table extraction
                camelot_tables = TableExtractionService.extract_tables_from_region(
                    pdf_bytes,
                    region.page,
                    region.x,
                    region.y,
                    region.width,
                    region.height
                )
                
                if camelot_tables:
                    # Successfully extracted table with Camelot
                    logger.info(f"Camelot extracted {len(camelot_tables)} rows from region {idx}")
                    
                    # Convert to text representation
                    text = "\n".join(["\t".join(row) for row in camelot_tables])
                    
                    result = ExtractionResult(
                        region_index=idx,
                        page=region.page,
                        text=text,
                        confidence=0.95,  # Camelot extractions are generally reliable
                        structured_data={"tables": [camelot_tables], "form_fields": []}
                    )
                    results.append(result)
                    continue
                
                # Second attempt: Use Document AI OCR
                logger.info(f"Camelot found no tables, using Document AI for region {idx}")
                
                # Crop region to PNG (with padding to avoid clipping)
                cropped_png_bytes = self.crop_pdf_region(pdf_bytes, region)
                
                # Upload debug artifact: cropped region image
                if job_id:
                    try:
                        debug_url = storage_service.upload_debug_artifact(
                            job_id,
                            f"region_{idx}_page_{region.page}.png",
                            cropped_png_bytes,
                            content_type="image/png"
                        )
                        logger.info(f"Debug artifact uploaded for region {idx}: {debug_url}")
                    except Exception as e:
                        logger.warning(f"Failed to upload debug artifact: {e}")
                
                # Process with Document AI using PNG (better OCR than PDF)
                document = self.process_document(cropped_png_bytes, mime_type="image/png")
                
                # Extract text and confidence
                text, confidence = self.extract_text_from_document(document)
                
                # Upload debug artifact: raw OCR text
                if job_id:
                    try:
                        ocr_debug = f"Region {idx} - Page {region.page}\nConfidence: {confidence:.4f}\n\n{text}"
                        storage_service.upload_debug_artifact(
                            job_id,
                            f"region_{idx}_ocr_raw.txt",
                            ocr_debug.encode('utf-8'),
                            content_type="text/plain"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to upload OCR debug artifact: {e}")
                
                # Extract structured data from Document AI
                structured_data = self.extract_structured_data(document)
                
                # Third attempt: If no structured data from Document AI, use intelligent routing
                if not (structured_data["tables"] or structured_data["form_fields"]):
                    # Analyze region type and get extraction hints
                    region_type, hints = RegionAnalyzer.analyze_region(text)
                    logger.info(f"Region {idx} detected as type: {region_type} with hints: {hints}")
                    
                    # Route to appropriate parser based on region type
                    if region_type == RegionType.TABLE:
                        parsed_table = TextParser.parse_to_table(text)
                        if parsed_table:
                            logger.info(f"Text parser extracted {len(parsed_table)-1} rows from region {idx}")
                            structured_data = {"tables": [parsed_table], "form_fields": []}
                            # Convert to text representation
                            text = "\n".join(["\t".join(row) for row in parsed_table])
                    elif region_type == RegionType.KEY_VALUE:
                        # Future: implement key-value extractor
                        logger.info(f"Region {idx} identified as key-value, but extractor not yet implemented")
                    elif region_type == RegionType.LIST:
                        # Future: implement list extractor
                        logger.info(f"Region {idx} identified as list, but extractor not yet implemented")
                
                result = ExtractionResult(
                    region_index=idx,
                    page=region.page,
                    text=text,
                    confidence=confidence,
                    structured_data=structured_data if structured_data["tables"] or structured_data["form_fields"] else None
                )
                
                results.append(result)
                logger.info(f"Processed region {idx} with Document AI")
            
            except Exception as e:
                logger.error(f"Error processing region {idx}: {e}")
                # Add error result
                results.append(ExtractionResult(
                    region_index=idx,
                    page=region.page,
                    text=f"ERROR: {str(e)}",
                    confidence=0.0,
                    structured_data=None
                ))
        
        return results


documentai_service = DocumentAIService()
