from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime, date
import re

class IngestDocumentRequest(BaseModel):
    """Request schema for document ingestion"""
    s3_key: str = Field(..., description="S3 key path to the PDF document")
    title: str = Field(..., description="Document title")
    author: str = Field(..., description="Document author")
    kind: str = Field(..., description="Document type: newsletter, masterclass, or report")
    published_date: str = Field(..., description="Publication date in YYYY-MM-DD format")
    tags: List[str] = Field(default_factory=list, description="List of tags for categorization")
    
    @validator('s3_key')
    def validate_s3_key(cls, v):
        if not v or not v.strip():
            raise ValueError('S3 key cannot be empty')
        
        # Basic security check
        if '..' in v or v.startswith('/'):
            raise ValueError('Invalid S3 key format')
        
        if not v.lower().endswith('.pdf'):
            raise ValueError('S3 key must point to a PDF file')
        
        return v.strip()
    
    @validator('kind')
    def validate_kind(cls, v):
        allowed_kinds = ['newsletter', 'masterclass', 'report']
        if v not in allowed_kinds:
            raise ValueError(f'Kind must be one of: {", ".join(allowed_kinds)}')
        return v
    
    @validator('published_date')
    def validate_published_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Published date must be in YYYY-MM-DD format')
    
    @validator('tags')
    def validate_tags(cls, v):
        if not isinstance(v, list):
            return []
        # Clean and validate tags
        cleaned_tags = []
        for tag in v:
            if isinstance(tag, str) and tag.strip():
                # Remove special characters and normalize
                clean_tag = re.sub(r'[^a-zA-Z0-9\-_]', '', tag.strip().lower())
                if clean_tag:
                    cleaned_tags.append(clean_tag)
        return cleaned_tags

class IngestDocumentResponse(BaseModel):
    """Response schema for document ingestion"""
    success: bool
    document_id: str
    chunk_count: int
    message: str
    processing_details: Optional[Dict[str, Any]] = None

class SearchKnowledgeRequest(BaseModel):
    """Request schema for knowledge search"""
    query: str = Field(..., description="Search query text")
    k: int = Field(default=8, ge=1, le=50, description="Number of results to return")
    filter_tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    filter_kind: Optional[str] = Field(default=None, description="Filter by document kind")
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        if len(v.strip()) < 3:
            raise ValueError('Query must be at least 3 characters long')
        return v.strip()
    
    @validator('filter_kind')
    def validate_filter_kind(cls, v):
        if v is None:
            return v
        allowed_kinds = ['newsletter', 'masterclass', 'report']
        if v not in allowed_kinds:
            raise ValueError(f'Filter kind must be one of: {", ".join(allowed_kinds)}')
        return v

class SearchResult(BaseModel):
    """Single search result schema"""
    text: str
    document_title: str
    author: str
    published_date: str
    page: Optional[int]
    section: Optional[str]
    relevance_score: float
    document_id: str

class SearchKnowledgeResponse(BaseModel):
    """Response schema for knowledge search"""
    results: List[SearchResult]
    query: str
    total_results: int

class ListDocumentsResponse(BaseModel):
    """Response schema for document listing"""
    documents: List[Dict[str, Any]]
    total_count: int
    offset: int
    limit: int

class LogObservationRequest(BaseModel):
    """Request schema for logging observations"""
    indicators: Dict[str, float] = Field(..., description="Indicator values")
    states: Dict[str, str] = Field(..., description="Indicator states/interpretations")
    interpretation: str = Field(..., description="Overall market interpretation")
    counter_read: Optional[str] = Field(default=None, description="Counter-thesis or alternative view")
    bias_check: Optional[str] = Field(default=None, description="Bias acknowledgment")
    session_label: str = Field(default="Analysis Session", description="Session identifier")
    referenced_documents: Optional[List[str]] = Field(default=None, description="Referenced document IDs")
    
    @validator('interpretation')
    def validate_interpretation(cls, v):
        if not v or not v.strip():
            raise ValueError('Interpretation cannot be empty')
        return v.strip()

class LogObservationResponse(BaseModel):
    """Response schema for observation logging"""
    success: bool
    observation_id: str
    timestamp: datetime
    message: str

class ErrorResponse(BaseModel):
    """Standard error response schema"""
    error: str
    detail: Optional[str] = None
    error_type: Optional[str] = None
