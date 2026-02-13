"""
ChromaDB Service

Handles all interactions with ChromaDB vector database.
"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential


class ChromaDBService:
    """
    Service for interacting with ChromaDB
    """
    
    def __init__(self, host: str, port: int, collection_name: str):
        """
        Initialize ChromaDB service
        
        Args:
            host: ChromaDB host
            port: ChromaDB port
            collection_name: Name of the collection to use
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        
        self._connect()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _connect(self):
        """
        Connect to ChromaDB with retry logic
        """
        try:
            self.client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(self.collection_name)
                print(f"✓ Connected to ChromaDB collection: {self.collection_name}")
            except:
                print(f"⚠️  Collection '{self.collection_name}' not found. Will be created by Airflow.")
                self.collection = None
            
        except Exception as e:
            print(f"✗ Failed to connect to ChromaDB: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test if ChromaDB connection is alive
        
        Returns:
            True if connected
        """
        try:
            if self.client:
                self.client.heartbeat()
                return True
            return False
        except:
            return False
    
    def query(
        self,
        query_embeddings: List[List[float]],
        top_k: int = 5
    ) -> Dict:
        """
        Query ChromaDB for similar documents
        
        Args:
            query_embeddings: Embedding vectors for the query
            top_k: Number of results to return
            
        Returns:
            Query results from ChromaDB
        """
        if not self.collection:
            raise Exception("Collection not initialized. Run Airflow DAG first to populate data.")
        
        try:
            results = self.collection.query(
                query_embeddings=query_embeddings,
                n_results=top_k
            )
            
            return results
        
        except Exception as e:
            print(f"Query error: {str(e)}")
            raise
    
    def get_document_count(self) -> int:
        """
        Get total number of documents in collection
        
        Returns:
            Document count
        """
        try:
            if not self.collection:
                return 0
            return self.collection.count()
        except:
            return 0
    
    def get_collection_stats(self) -> Dict:
        """
        Get collection statistics
        
        Returns:
            Statistics dictionary
        """
        try:
            if not self.collection:
                return {
                    'document_count': 0,
                    'collection_exists': False
                }
            
            count = self.collection.count()
            metadata = self.collection.metadata
            
            return {
                'document_count': count,
                'collection_exists': True,
                'metadata': metadata,
                'last_updated': None  # ChromaDB doesn't track this by default
            }
        
        except Exception as e:
            print(f"Error getting stats: {str(e)}")
            return {'document_count': 0, 'collection_exists': False}
