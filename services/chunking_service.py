import logging
import tiktoken
from typing import List, Dict, Any, Optional
from config import settings
import re

logger = logging.getLogger(__name__)

class ChunkingService:
    """Service for intelligent text chunking with token counting"""
    
    def __init__(self):
        self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        self.max_tokens = settings.MAX_CHUNK_TOKENS
        self.overlap_tokens = settings.CHUNK_OVERLAP_TOKENS
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        if not text:
            return 0
        return len(self.encoding.encode(text))
    
    def create_chunks(
        self,
        text: str,
        document_id: str,
        page_markers: List[Dict[str, Any]],
        section_markers: List[Dict[str, Any]],
        document_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create intelligent chunks with metadata preservation"""
        if not text.strip():
            return []
        
        # First, try to split by paragraphs to find natural boundaries
        paragraphs = self._split_into_paragraphs(text)
        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_start_pos = 0
        
        for paragraph in paragraphs:
            paragraph_tokens = self.count_tokens(paragraph)
            
            # If paragraph alone exceeds max tokens, split it further
            if paragraph_tokens > self.max_tokens:
                # First, add current chunk if it has content
                if current_chunk.strip():
                    chunk_data = self._create_chunk_metadata(
                        text=current_chunk,
                        document_id=document_id,
                        start_pos=chunk_start_pos,
                        end_pos=chunk_start_pos + len(current_chunk),
                        page_markers=page_markers,
                        section_markers=section_markers,
                        document_metadata=document_metadata
                    )
                    chunks.append(chunk_data)
                
                # Split large paragraph into smaller chunks
                large_para_chunks = self._chunk_large_text(
                    paragraph, 
                    document_id, 
                    chunk_start_pos + len(current_chunk),
                    page_markers, 
                    section_markers, 
                    document_metadata
                )
                chunks.extend(large_para_chunks)
                
                # Reset for next chunk
                current_chunk = ""
                current_tokens = 0
                chunk_start_pos = chunk_start_pos + len(current_chunk) + len(paragraph)
                
            elif current_tokens + paragraph_tokens > self.max_tokens:
                # Current chunk would exceed limit, finalize it
                if current_chunk.strip():
                    chunk_data = self._create_chunk_metadata(
                        text=current_chunk,
                        document_id=document_id,
                        start_pos=chunk_start_pos,
                        end_pos=chunk_start_pos + len(current_chunk),
                        page_markers=page_markers,
                        section_markers=section_markers,
                        document_metadata=document_metadata
                    )
                    chunks.append(chunk_data)
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + paragraph
                current_tokens = self.count_tokens(current_chunk)
                chunk_start_pos = chunk_start_pos + len(current_chunk) - len(overlap_text)
                
            else:
                # Add paragraph to current chunk
                current_chunk += paragraph
                current_tokens += paragraph_tokens
        
        # Add final chunk if it has content
        if current_chunk.strip():
            chunk_data = self._create_chunk_metadata(
                text=current_chunk,
                document_id=document_id,
                start_pos=chunk_start_pos,
                end_pos=chunk_start_pos + len(current_chunk),
                page_markers=page_markers,
                section_markers=section_markers,
                document_metadata=document_metadata
            )
            chunks.append(chunk_data)
        
        logger.info(f"Created {len(chunks)} chunks from text")
        return chunks
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs while preserving structure"""
        # Split by double newlines first (paragraph breaks)
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Further split very long paragraphs at sentence boundaries
        refined_paragraphs = []
        for para in paragraphs:
            if self.count_tokens(para) > self.max_tokens // 2:
                # Split long paragraph at sentence boundaries
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current_para = ""
                
                for sentence in sentences:
                    if self.count_tokens(current_para + sentence) > self.max_tokens // 2:
                        if current_para:
                            refined_paragraphs.append(current_para)
                            current_para = sentence
                        else:
                            refined_paragraphs.append(sentence)
                    else:
                        current_para += " " + sentence if current_para else sentence
                
                if current_para:
                    refined_paragraphs.append(current_para)
            else:
                refined_paragraphs.append(para)
        
        return [p.strip() for p in refined_paragraphs if p.strip()]
    
    def _chunk_large_text(
        self,
        text: str,
        document_id: str,
        start_pos: int,
        page_markers: List[Dict[str, Any]],
        section_markers: List[Dict[str, Any]],
        document_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Split large text into token-based chunks"""
        tokens = self.encoding.encode(text)
        chunks = []
        
        chunk_start = 0
        while chunk_start < len(tokens):
            chunk_end = min(chunk_start + self.max_tokens, len(tokens))
            chunk_tokens = tokens[chunk_start:chunk_end]
            chunk_text = self.encoding.decode(chunk_tokens)
            
            chunk_data = self._create_chunk_metadata(
                text=chunk_text,
                document_id=document_id,
                start_pos=start_pos,
                end_pos=start_pos + len(chunk_text),
                page_markers=page_markers,
                section_markers=section_markers,
                document_metadata=document_metadata
            )
            chunks.append(chunk_data)
            
            # Move start position with overlap
            chunk_start = chunk_end - self.overlap_tokens if chunk_end < len(tokens) else chunk_end
            start_pos += len(chunk_text)
        
        return chunks
    
    def _get_overlap_text(self, text: str) -> str:
        """Get overlap text for chunk continuity"""
        if not text:
            return ""
        
        tokens = self.encoding.encode(text)
        if len(tokens) <= self.overlap_tokens:
            return text
        
        overlap_tokens = tokens[-self.overlap_tokens:]
        return self.encoding.decode(overlap_tokens)
    
    def _create_chunk_metadata(
        self,
        text: str,
        document_id: str,
        start_pos: int,
        end_pos: int,
        page_markers: List[Dict[str, Any]],
        section_markers: List[Dict[str, Any]],
        document_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create chunk with metadata"""
        # Find relevant page
        page_number = self._find_page_for_position(start_pos, page_markers)
        
        # Find relevant section
        section = self._find_section_for_position(start_pos, section_markers)
        
        # Count tokens
        token_count = self.count_tokens(text)
        
        chunk_data = {
            "document_id": document_id,
            "text": text.strip(),
            "token_count": token_count,
            "char_start": start_pos,
            "char_end": end_pos,
            "page": page_number,
            "section": section,
            "chunk_index": len([]),  # Will be updated when all chunks are known
            # Metadata from document
            "document_title": document_metadata.get("title", ""),
            "document_author": document_metadata.get("author", ""),
            "document_kind": document_metadata.get("kind", ""),
            "document_tags": document_metadata.get("tags", []),
            "published_date": document_metadata.get("published_date", "")
        }
        
        return chunk_data
    
    def _find_page_for_position(self, position: int, page_markers: List[Dict[str, Any]]) -> Optional[int]:
        """Find page number for text position"""
        for marker in page_markers:
            if marker["start_pos"] <= position <= marker["end_pos"]:
                return marker["page"]
        return None
    
    def _find_section_for_position(self, position: int, section_markers: List[Dict[str, Any]]) -> Optional[str]:
        """Find section header for text position"""
        relevant_section = None
        for marker in section_markers:
            if marker["position"] <= position:
                relevant_section = marker["header"]
            else:
                break
        return relevant_section

# Global chunking service instance
chunking_service = ChunkingService()
