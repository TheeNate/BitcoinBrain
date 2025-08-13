import re
import html
from typing import List
import logging

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """Clean and normalize extracted text"""
    if not text:
        return ""
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Remove excessive whitespace while preserving paragraph breaks
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
    text = re.sub(r' +\n', '\n', text)  # Remove trailing spaces before newlines
    text = re.sub(r'\n +', '\n', text)  # Remove leading spaces after newlines
    
    # Fix common OCR/extraction issues
    text = re.sub(r'(\w)- *\n *(\w)', r'\1\2', text)  # Fix hyphenated words across lines
    text = re.sub(r'([.!?])\n([A-Z])', r'\1 \2', text)  # Fix sentence breaks
    
    # Remove page numbers and headers/footers patterns
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)  # Standalone page numbers
    text = re.sub(r'\n\s*Page \d+.*?\n', '\n', text, flags=re.IGNORECASE)
    
    # Clean up special characters but preserve structure
    text = re.sub(r'[^\w\s\-.,!?;:()\[\]{}"/\'%$#@&*+=<>|\\~`]', ' ', text)
    
    return text.strip()

def sanitize_text(text: str) -> str:
    """Sanitize text for safe storage (remove potential XSS vectors)"""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Remove or escape potentially dangerous characters
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    
    # Remove control characters except common whitespace
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    return text.strip()

def extract_section_headers(text: str) -> List[str]:
    """Extract section headers from text"""
    if not text:
        return []
    
    headers = []
    
    # Common header patterns
    patterns = [
        r'^([A-Z][A-Za-z\s]{5,50})$',  # ALL CAPS or Title Case lines
        r'^\d+\.?\s+([A-Z][A-Za-z\s]{5,50})$',  # Numbered headers
        r'^([A-Z][A-Za-z\s]{5,50}):',  # Headers ending with colon
        r'^\*\*([^*]+)\*\*',  # Bold text (markdown style)
        r'^#{1,6}\s+(.+)$',  # Markdown headers
    ]
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in patterns:
            match = re.match(pattern, line, re.MULTILINE)
            if match:
                header = match.group(1) if match.groups() else match.group(0)
                header = header.strip()
                
                # Filter out common false positives
                if (len(header) > 5 and 
                    len(header) < 80 and 
                    not header.lower().startswith('page ') and
                    not header.isdigit() and
                    not re.match(r'^[A-Z]{1,3}\d+', header)):  # Skip codes like "BTC123"
                    headers.append(header)
                break
    
    # Remove duplicates while preserving order
    seen = set()
    unique_headers = []
    for header in headers:
        if header not in seen:
            seen.add(header)
            unique_headers.append(header)
    
    logger.debug(f"Extracted {len(unique_headers)} section headers")
    return unique_headers

def highlight_query_matches(text: str, query: str, max_length: int = 200) -> str:
    """
    Highlight query matches in text and return a snippet
    """
    if not text or not query:
        return text[:max_length] + "..." if len(text) > max_length else text
    
    # Simple highlighting - find first occurrence
    query_words = query.lower().split()
    text_lower = text.lower()
    
    # Find the best match position
    best_pos = -1
    for word in query_words:
        pos = text_lower.find(word)
        if pos != -1:
            best_pos = pos
            break
    
    if best_pos == -1:
        # No matches found, return beginning of text
        return text[:max_length] + "..." if len(text) > max_length else text
    
    # Extract snippet around the match
    start = max(0, best_pos - max_length // 2)
    end = min(len(text), start + max_length)
    
    snippet = text[start:end]
    
    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    return snippet

def extract_key_phrases(text: str) -> List[str]:
    """
    Extract key phrases from text (simple implementation)
    """
    if not text:
        return []
    
    # Simple approach: find capitalized phrases and technical terms
    phrases = []
    
    # Find capitalized phrases
    capitalized_phrases = re.findall(r'\b[A-Z][A-Za-z\s]{2,20}\b', text)
    phrases.extend([p.strip() for p in capitalized_phrases if len(p.strip()) > 3])
    
    # Find technical terms (numbers with units/percentages)
    technical_terms = re.findall(r'\d+(?:\.\d+)?%?[\s]*(?:BTC|USD|percent|basis points|points)', text, re.IGNORECASE)
    phrases.extend(technical_terms)
    
    # Remove duplicates and sort by length (longer phrases first)
    unique_phrases = list(set(phrases))
    unique_phrases.sort(key=len, reverse=True)
    
    return unique_phrases[:10]  # Return top 10 phrases
