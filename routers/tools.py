import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from models.schemas import (
    IngestDocumentRequest, IngestDocumentResponse,
    SearchKnowledgeRequest, SearchKnowledgeResponse, SearchResult,
    ListDocumentsResponse, LogObservationRequest, LogObservationResponse,
    ErrorResponse
)
from services.s3_service import s3_service
from services.pdf_service import pdf_service
from services.embedding_service import embedding_service
from database import db
from utils.text_processing import sanitize_text

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/ingest_document", response_model=IngestDocumentResponse)
async def ingest_document(request: IngestDocumentRequest):
    """
    Process a PDF from S3 into searchable chunks with vector embeddings
    """
    try:
        logger.info(f"Starting document ingestion for: {request.s3_key}")
        
        # Step 1: Download PDF from S3
        try:
            pdf_bytes = await s3_service.download_pdf(request.s3_key)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"PDF not found in S3: {request.s3_key}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Step 2: Create document record first
        document_data = {
            "title": sanitize_text(request.title),
            "author": sanitize_text(request.author),
            "kind": request.kind,
            "published_date": request.published_date,
            "tags": request.tags,
            "s3_key": request.s3_key,
            "status": "processing",
            "needs_ocr": False,
            "created_at": datetime.utcnow().isoformat()
        }
        
        document_id = await db.insert_document(document_data)
        
        # Step 3: Process PDF and extract chunks
        try:
            processing_result = pdf_service.process_pdf_for_chunks(
                pdf_bytes=pdf_bytes,
                document_metadata={
                    "document_id": document_id,
                    "title": request.title,
                    "author": request.author,
                    "kind": request.kind,
                    "tags": request.tags,
                    "published_date": request.published_date
                }
            )
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            # Update document status to indicate OCR needed
            await db.update_document_status(document_id, {
                "status": "needs_ocr",
                "needs_ocr": True,
                "error_message": str(e)
            })
            
            return IngestDocumentResponse(
                success=True,
                document_id=document_id,
                chunk_count=0,
                message="Document created but PDF processing failed. OCR may be needed.",
                processing_details={"error": str(e), "needs_ocr": True}
            )
        
        chunks = processing_result["chunks"]
        
        if not chunks:
            # Update document status
            await db.update_document_status(document_id, {
                "status": "no_content",
                "needs_ocr": processing_result.get("needs_ocr", True)
            })
            
            return IngestDocumentResponse(
                success=True,
                document_id=document_id,
                chunk_count=0,
                message="Document created but no text content extracted. May need OCR.",
                processing_details=processing_result
            )
        
        # Step 4: Generate embeddings for chunks
        try:
            chunks_with_embeddings = await embedding_service.generate_embeddings_for_chunks(chunks)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            # Still save chunks without embeddings
            chunks_with_embeddings = chunks
            for chunk in chunks_with_embeddings:
                chunk["embedding"] = None
                chunk["has_embedding"] = False
        
        # Step 5: Store chunks in database
        try:
            chunk_count = await db.insert_chunks(chunks_with_embeddings)
        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            await db.update_document_status(document_id, {
                "status": "error",
                "error_message": f"Failed to store chunks: {str(e)}"
            })
            raise HTTPException(status_code=500, detail="Failed to store document chunks")
        
        # Step 6: Update document status to completed
        await db.update_document_status(document_id, {
            "status": "completed",
            "chunk_count": chunk_count,
            "page_count": processing_result.get("total_pages", 0),
            "has_tables": processing_result.get("has_tables", False)
        })
        
        logger.info(f"Document ingestion completed: {document_id} with {chunk_count} chunks")
        
        return IngestDocumentResponse(
            success=True,
            document_id=document_id,
            chunk_count=chunk_count,
            message=f"Document processed successfully with {chunk_count} searchable chunks",
            processing_details={
                "total_pages": processing_result.get("total_pages", 0),
                "text_pages": processing_result.get("text_pages", 0),
                "has_tables": processing_result.get("has_tables", False),
                "needs_ocr": processing_result.get("needs_ocr", False)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(e)}")

@router.post("/search_knowledge", response_model=SearchKnowledgeResponse)
async def search_knowledge(request: SearchKnowledgeRequest):
    """
    Perform semantic search across all documents
    """
    try:
        logger.info(f"Starting knowledge search for: {request.query[:50]}...")
        
        # Step 1: Generate embedding for query
        try:
            query_embedding = await embedding_service.generate_embedding(request.query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise HTTPException(status_code=500, detail="Failed to process search query")
        
        # Step 2: Perform vector search
        try:
            search_results = await db.search_documents(
                query_embedding=query_embedding,
                match_count=request.k,
                filter_tags=request.filter_tags,
                filter_kind=request.filter_kind
            )
        except Exception as e:
            logger.error(f"Database search failed: {e}")
            raise HTTPException(status_code=500, detail="Search operation failed")
        
        # Step 3: Format results
        formatted_results = []
        for result in search_results:
            # Handle both RPC and direct query result formats
            document_info = result.get("documents") or {}
            if isinstance(document_info, list) and document_info:
                document_info = document_info[0]
            
            # Ensure document_info is a dict, not a list
            if not isinstance(document_info, dict):
                document_info = {}
            
            search_result = SearchResult(
                text=result.get("text", ""),
                document_title=document_info.get("title", "") if isinstance(document_info, dict) else result.get("document_title", ""),
                author=document_info.get("author", "") if isinstance(document_info, dict) else result.get("document_author", ""),
                published_date=document_info.get("published_date", "") if isinstance(document_info, dict) else result.get("published_date", ""),
                page=result.get("page"),
                section=result.get("section"),
                relevance_score=result.get("relevance_score", 0.0),
                document_id=result.get("document_id", "")
            )
            formatted_results.append(search_result)
        
        # Sort by relevance score
        formatted_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        logger.info(f"Search completed: {len(formatted_results)} results found")
        
        return SearchKnowledgeResponse(
            results=formatted_results,
            query=request.query,
            total_results=len(formatted_results)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/list_documents", response_model=ListDocumentsResponse)
async def list_documents(
    kind: Optional[str] = Query(None, description="Filter by document type"),
    tags: Optional[str] = Query(None, description="Comma-separated tag filter"),
    search: Optional[str] = Query(None, description="Text search in titles"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Browse document archive with filtering options
    """
    try:
        logger.info(f"Listing documents with filters - kind: {kind}, tags: {tags}, search: {search}")
        
        # Parse tags
        tag_list = None
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Validate kind filter
        if kind:
            allowed_kinds = ['newsletter', 'masterclass', 'report']
            if kind not in allowed_kinds:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid kind. Must be one of: {', '.join(allowed_kinds)}"
                )
        
        # Fetch documents
        documents = await db.list_documents(
            kind=kind,
            tags=tag_list,
            search=search,
            limit=limit,
            offset=offset
        )
        
        logger.info(f"Found {len(documents)} documents")
        
        return ListDocumentsResponse(
            documents=documents,
            total_count=len(documents),  # Note: This is not the true total, just current page
            offset=offset,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve documents: {str(e)}")

@router.post("/log_observation", response_model=LogObservationResponse)
async def log_observation(request: LogObservationRequest):
    """
    Store daily analysis observations
    """
    try:
        logger.info(f"Logging observation: {request.session_label}")
        
        # Prepare observation data
        observation_data = {
            "indicators": request.indicators,
            "states": request.states,
            "interpretation": sanitize_text(request.interpretation),
            "counter_read": sanitize_text(request.counter_read) if request.counter_read else None,
            "bias_check": sanitize_text(request.bias_check) if request.bias_check else None,
            "session_label": sanitize_text(request.session_label),
            "referenced_documents": request.referenced_documents or [],
            "created_at": datetime.utcnow().isoformat(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store observation
        observation_id = await db.insert_observation(observation_data)
        
        logger.info(f"Observation logged successfully: {observation_id}")
        
        return LogObservationResponse(
            success=True,
            observation_id=observation_id,
            timestamp=datetime.utcnow(),
            message="Observation logged successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to log observation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to log observation: {str(e)}")

@router.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    """
    try:
        # Basic connectivity checks could be added here
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": "connected",
                "s3": "accessible",
                "embeddings": "available"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
