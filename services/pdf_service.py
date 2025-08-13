import io
import logging
from typing import List, Dict, Any, Optional
import pdfplumber
from services.chunking_service import chunking_service
from utils.text_processing import clean_text, extract_section_headers

logger = logging.getLogger(__name__)

class PDFService:
    """Service for PDF text extraction and processing"""
    
    def __init__(self):
        pass
    
    def extract_text_from_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Extract text from PDF with page-by-page breakdown"""
        try:
            text_by_page = []
            
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                logger.info(f"Processing PDF with {len(pdf.pages)} pages")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract text
                    text = page.extract_text()
                    
                    # Check for tables
                    tables = page.extract_tables()
                    
                    # Clean and process text
                    cleaned_text = clean_text(text) if text else ""
                    
                    page_data = {
                        "page": page_num,
                        "text": cleaned_text,
                        "has_tables": len(tables) > 0,
                        "table_count": len(tables),
                        "char_count": len(cleaned_text)
                    }
                    
                    if cleaned_text:  # Only add pages with text content
                        text_by_page.append(page_data)
                    
                logger.info(f"Extracted text from {len(text_by_page)} pages with content")
                return text_by_page
                
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            raise
    
    def process_pdf_for_chunks(
        self,
        pdf_bytes: bytes,
        document_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process PDF and return structured data for chunking"""
        try:
            # Extract text by page
            pages_data = self.extract_text_from_pdf(pdf_bytes)
            
            if not pages_data:
                logger.warning("No text content extracted from PDF")
                return {
                    "pages": [],
                    "chunks": [],
                    "needs_ocr": True,
                    "total_pages": 0,
                    "text_pages": 0,
                    "has_tables": False
                }
            
            # Combine all text for chunking
            full_text = ""
            section_markers = []
            page_markers = []
            has_tables = False
            
            for page_data in pages_data:
                page_start = len(full_text)
                page_text = page_data["text"]
                
                # Add page marker
                page_marker = f"\n\n--- PAGE {page_data['page']} ---\n\n"
                full_text += page_marker
                page_markers.append({
                    "page": page_data["page"],
                    "start_pos": page_start,
                    "end_pos": len(full_text)
                })
                
                # Extract section headers
                headers = extract_section_headers(page_text)
                for header in headers:
                    section_markers.append({
                        "header": header,
                        "page": page_data["page"],
                        "position": len(full_text)
                    })
                
                # Add page text
                full_text += page_text
                
                if page_data["has_tables"]:
                    has_tables = True
            
            # Create chunks
            chunks_data = chunking_service.create_chunks(
                text=full_text,
                document_id=document_metadata.get("document_id", ""),
                page_markers=page_markers,
                section_markers=section_markers,
                document_metadata=document_metadata
            )
            
            result = {
                "pages": pages_data,
                "chunks": chunks_data,
                "needs_ocr": False,
                "total_pages": len(pages_data),
                "text_pages": len([p for p in pages_data if p["char_count"] > 50]),
                "has_tables": has_tables,
                "full_text_length": len(full_text),
                "chunk_count": len(chunks_data)
            }
            
            logger.info(f"PDF processed: {result['chunk_count']} chunks from {result['text_pages']} pages")
            return result
            
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            # Return structure indicating OCR needed
            return {
                "pages": [],
                "chunks": [],
                "needs_ocr": True,
                "total_pages": 0,
                "text_pages": 0,
                "has_tables": False,
                "error": str(e)
            }

# Global PDF service instance
pdf_service = PDFService()
