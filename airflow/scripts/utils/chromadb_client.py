"""ChromaDB client utilities for News Lens ETL pipeline."""

import logging
from typing import List, Dict, Optional, Any
import chromadb
from chromadb.config import Settings
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


class ChromaDBClient:
    """Client for interacting with ChromaDB."""
    
    def __init__(
        self,
        host: str = "chromadb",
        port: int = 8000,
        collection_name: str = "news_articles"
    ):
        """
        Initialize ChromaDB client.
        
        Args:
            host: ChromaDB server host
            port: ChromaDB server port
            collection_name: Name of the collection
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        
        # Initialize client
        self.client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False
            )
        )
        
        logger.info(f"🗄️ Connected to ChromaDB at {host}:{port}")
        
        # Get or create collection
        self.collection = self._get_or_create_collection()
    
    def _get_or_create_collection(self):
        """Get existing collection or create new one."""
        try:
            collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "News articles embeddings for RAG"}
            )
            
            count = collection.count()
            logger.info(f"✅ Collection '{self.collection_name}' ready ({count} documents)")
            
            return collection
            
        except Exception as e:
            logger.error(f"❌ Failed to get/create collection: {e}")
            raise
    
    def generate_chunk_id(self, url: str, chunk_index: int) -> str:
        """
        Generate deterministic ID for a chunk.
        Ensures idempotency when DAGs rerun.
        
        Args:
            url: Article URL
            chunk_index: Index of the chunk
            
        Returns:
            str: Unique deterministic ID
        """
        # Create deterministic hash from URL + chunk index
        content = f"{url}__chunk_{chunk_index}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def upsert_chunks(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata: List[Dict[str, Any]]
    ) -> bool:
        """
        Upsert chunks with embeddings and metadata to ChromaDB.
        Uses upsert to ensure idempotency (no duplicates on reruns).
        
        Args:
            chunks: List of text chunks
            embeddings: List of embedding vectors
            metadata: List of metadata dictionaries (one per chunk)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not chunks or not embeddings or not metadata:
            logger.warning("⚠️ Empty input provided to upsert_chunks")
            return False
        
        if len(chunks) != len(embeddings) or len(chunks) != len(metadata):
            logger.error(f"❌ Length mismatch: chunks={len(chunks)}, embeddings={len(embeddings)}, metadata={len(metadata)}")
            return False
        
        # Filter out None embeddings (failed generations)
        valid_data = [
            (chunk, emb, meta)
            for chunk, emb, meta in zip(chunks, embeddings, metadata)
            if emb is not None
        ]
        
        if not valid_data:
            logger.warning("⚠️ No valid embeddings to upsert")
            return False
        
        chunks, embeddings, metadata = zip(*valid_data)
        
        # Generate deterministic IDs
        ids = [
            self.generate_chunk_id(meta['url'], meta['chunk_index'])
            for meta in metadata
        ]
        
        try:
            logger.info(f"📥 Upserting {len(chunks)} chunks to ChromaDB...")
            
            # Upsert to collection
            self.collection.upsert(
                ids=ids,
                documents=list(chunks),
                embeddings=list(embeddings),
                metadatas=list(metadata)
            )
            
            logger.info(f"✅ Successfully upserted {len(chunks)} chunks")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upsert chunks: {e}", exc_info=True)
            return False
    
    def upsert_article(
        self,
        url: str,
        title: str,
        chunks: List[str],
        embeddings: List[List[float]],
        source_name: str,
        published_date: str,
        scraped_at: Optional[str] = None
    ) -> bool:
        """
        Upsert all chunks from a single article.
        
        Args:
            url: Article URL
            title: Article title
            chunks: List of text chunks
            embeddings: List of embedding vectors
            source_name: Name of the news source
            published_date: Publication date (ISO format)
            scraped_at: Scraping timestamp (ISO format, optional)
            
        Returns:
            bool: True if successful
        """
        if scraped_at is None:
            scraped_at = datetime.utcnow().isoformat()
        
        # Create metadata for each chunk
        metadata = [
            {
                "url": url,
                "title": title,
                "source_name": source_name,
                "published_date": published_date,
                "scraped_at": scraped_at,
                "chunk_index": i,
                "total_chunks": len(chunks)
            }
            for i in range(len(chunks))
        ]
        
        return self.upsert_chunks(chunks, embeddings, metadata)
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.
        
        Returns:
            Dict with collection statistics
        """
        try:
            count = self.collection.count()
            
            # Try to get a sample document to check metadata structure
            sample = self.collection.peek(limit=1)
            
            return {
                "collection_name": self.collection_name,
                "total_documents": count,
                "sample_metadata": sample['metadatas'][0] if sample['metadatas'] else None
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {
                "collection_name": self.collection_name,
                "error": str(e)
            }
    
    def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict:
        """
        Query the collection with an embedding.
        
        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Optional metadata filter
            
        Returns:
            Dict with query results
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            return {"error": str(e)}


# Convenience functions

def upsert_articles_batch(
    articles: List[Dict],
    chromadb_host: str = "chromadb",
    chromadb_port: int = 8000,
    collection_name: str = "news_articles"
) -> int:
    """
    Upsert multiple articles to ChromaDB.
    
    Args:
        articles: List of article dictionaries with keys:
            - url, title, chunks, embeddings, source_name, published_date
        chromadb_host: ChromaDB server host
        chromadb_port: ChromaDB server port
        collection_name: Collection name
        
    Returns:
        int: Number of articles successfully upserted
    """
    client = ChromaDBClient(
        host=chromadb_host,
        port=chromadb_port,
        collection_name=collection_name
    )
    
    success_count = 0
    
    for article in articles:
        try:
            success = client.upsert_article(
                url=article['url'],
                title=article['title'],
                chunks=article['chunks'],
                embeddings=article['embeddings'],
                source_name=article['source_name'],
                published_date=article['published_date'],
                scraped_at=article.get('scraped_at')
            )
            
            if success:
                success_count += 1
                
        except Exception as e:
            logger.error(f"❌ Failed to upsert article {article.get('url', 'Unknown')}: {e}")
            continue
    
    logger.info(f"✅ Upserted {success_count}/{len(articles)} articles")
    return success_count


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test connection
    try:
        client = ChromaDBClient(
            host="localhost",
            port=8000,
            collection_name="news_articles"
        )
        
        # Get stats
        stats = client.get_collection_stats()
        print(f"\n📊 Collection Stats:")
        print(f"  Name: {stats['collection_name']}")
        print(f"  Documents: {stats['total_documents']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
