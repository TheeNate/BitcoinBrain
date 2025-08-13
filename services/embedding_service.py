import logging
import asyncio
from typing import List, Dict, Any
from openai import AsyncOpenAI
from config import settings
import time

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating OpenAI embeddings"""
    
    def __init__(self):
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        # However, for embeddings we use text-embedding-3-small as specified
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.max_batch_size = 100  # OpenAI limit
        self.max_retries = 3
        self.base_delay = 1.0
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            if not text.strip():
                raise ValueError("Cannot generate embedding for empty text")
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding with {len(embedding)} dimensions")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts with batching and retry logic"""
        if not texts:
            return []
        
        # Filter out empty texts and keep track of original indices
        filtered_data = [(i, text) for i, text in enumerate(texts) if text.strip()]
        
        if not filtered_data:
            return [[] for _ in texts]  # Return empty embeddings for all
        
        embeddings_result = [[] for _ in texts]  # Initialize with empty lists
        
        # Process in batches
        for batch_start in range(0, len(filtered_data), self.max_batch_size):
            batch_end = min(batch_start + self.max_batch_size, len(filtered_data))
            batch_data = filtered_data[batch_start:batch_end]
            batch_texts = [text for _, text in batch_data]
            
            # Generate embeddings for batch with retry logic
            batch_embeddings = await self._generate_batch_with_retry(batch_texts)
            
            # Map results back to original positions
            for i, embedding in enumerate(batch_embeddings):
                original_index = batch_data[i][0]
                embeddings_result[original_index] = embedding
        
        successful_embeddings = sum(1 for emb in embeddings_result if emb)
        logger.info(f"Generated {successful_embeddings}/{len(texts)} embeddings successfully")
        return embeddings_result
    
    async def _generate_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings with exponential backoff retry"""
        for attempt in range(self.max_retries):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=texts
                )
                
                embeddings = [data.embedding for data in response.data]
                logger.debug(f"Batch embedding successful for {len(texts)} texts")
                return embeddings
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to generate batch embeddings after {self.max_retries} attempts: {e}")
                    # Return empty embeddings for failed batch
                    return [[] for _ in texts]
                
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Embedding attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
        
        return [[] for _ in texts]  # Fallback
    
    async def generate_embeddings_for_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate embeddings for chunks and add to chunk data"""
        if not chunks:
            return []
        
        # Extract texts for embedding
        texts = [chunk.get("text", "") for chunk in chunks]
        
        # Generate embeddings in batches
        embeddings = await self.generate_embeddings_batch(texts)
        
        # Add embeddings to chunks
        enriched_chunks = []
        for i, chunk in enumerate(chunks):
            enriched_chunk = chunk.copy()
            enriched_chunk["embedding"] = embeddings[i]
            enriched_chunk["has_embedding"] = bool(embeddings[i])
            enriched_chunks.append(enriched_chunk)
        
        successful_count = sum(1 for chunk in enriched_chunks if chunk["has_embedding"])
        logger.info(f"Added embeddings to {successful_count}/{len(chunks)} chunks")
        
        return enriched_chunks

# Global embedding service instance
embedding_service = EmbeddingService()
