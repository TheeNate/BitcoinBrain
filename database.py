import logging
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)

class SupabaseClient:
    """Supabase database client wrapper"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client"""
        try:
            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
                logger.warning("Supabase credentials not provided. Database operations will fail.")
                self.client = None
                return
                
            self.client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY
            )
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            self.client = None
    
    async def insert_document(self, document_data: Dict[str, Any]) -> str:
        """Insert document metadata and return document_id"""
        if not self.client:
            raise ValueError("Database service not configured. Please provide Supabase credentials.")
        try:
            result = self.client.table("documents").insert(document_data).execute()
            document_id = result.data[0]["id"]
            logger.info(f"Document inserted with ID: {document_id}")
            return document_id
        except Exception as e:
            logger.error(f"Failed to insert document: {e}")
            raise
    
    async def insert_chunks(self, chunks_data: List[Dict[str, Any]]) -> int:
        """Insert document chunks and return count"""
        try:
            result = self.client.table("doc_chunks").insert(chunks_data).execute()
            chunk_count = len(result.data)
            logger.info(f"Inserted {chunk_count} chunks")
            return chunk_count
        except Exception as e:
            logger.error(f"Failed to insert chunks: {e}")
            raise
    
    async def search_documents(
        self,
        query_embedding: List[float],
        match_count: int = 8,
        filter_tags: Optional[List[str]] = None,
        filter_kind: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        if not self.client:
            raise ValueError("Database service not configured. Please provide Supabase credentials.")
        try:
            # Build the RPC call parameters
            params = {
                'query_embedding': query_embedding,
                'match_count': match_count
            }
            
            if filter_tags:
                params['filter_tags'] = filter_tags
            if filter_kind:
                params['filter_kind'] = filter_kind
            
            result = self.client.rpc('match_documents', params).execute()
            logger.info(f"Search returned {len(result.data)} results")
            return result.data
        except Exception as e:
            logger.error(f"Search failed: {e}")
            # Fallback to basic search without RPC
            return await self._basic_search(query_embedding, match_count, filter_tags, filter_kind)
    
    async def _basic_search(
        self,
        query_embedding: List[float],
        match_count: int,
        filter_tags: Optional[List[str]] = None,
        filter_kind: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Basic search fallback using Supabase client"""
        try:
            query = self.client.table("doc_chunks").select("""
                *,
                documents(title, author, published_date, kind, tags)
            """)
            
            # Apply filters if provided
            if filter_kind:
                query = query.eq("documents.kind", filter_kind)
            
            # Execute query and perform similarity search client-side
            result = query.limit(match_count * 2).execute()  # Get more results for filtering
            
            # Simple similarity calculation (dot product for normalized embeddings)
            results_with_score = []
            for chunk in result.data:
                if chunk.get("embedding"):
                    # Calculate similarity score
                    score = sum(a * b for a, b in zip(query_embedding, chunk["embedding"]))
                    chunk["relevance_score"] = score
                    results_with_score.append(chunk)
            
            # Sort by relevance and return top results
            results_with_score.sort(key=lambda x: x["relevance_score"], reverse=True)
            return results_with_score[:match_count]
            
        except Exception as e:
            logger.error(f"Basic search failed: {e}")
            return []
    
    async def list_documents(
        self,
        kind: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List documents with filtering"""
        try:
            query = self.client.table("documents").select("*")
            
            if kind:
                query = query.eq("kind", kind)
            
            if search:
                query = query.ilike("title", f"%{search}%")
            
            if tags:
                # Filter by tags (assuming tags is a JSON array)
                for tag in tags:
                    query = query.contains("tags", [tag])
            
            result = query.order("published_date", desc=True).range(offset, offset + limit - 1).execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []
    
    async def insert_observation(self, observation_data: Dict[str, Any]) -> str:
        """Insert observation and return observation_id"""
        try:
            result = self.client.table("observations").insert(observation_data).execute()
            observation_id = result.data[0]["id"]
            logger.info(f"Observation inserted with ID: {observation_id}")
            return observation_id
        except Exception as e:
            logger.error(f"Failed to insert observation: {e}")
            raise
    
    async def update_document_status(self, document_id: str, status: Dict[str, Any]):
        """Update document processing status"""
        try:
            self.client.table("documents").update(status).eq("id", document_id).execute()
            logger.info(f"Document {document_id} status updated")
        except Exception as e:
            logger.error(f"Failed to update document status: {e}")

# Global database client
db = SupabaseClient()
