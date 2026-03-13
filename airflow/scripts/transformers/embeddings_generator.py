"""Embeddings generator using Ollama for News Lens ETL pipeline."""

import logging
from typing import List, Optional
import ollama
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class EmbeddingsGenerator:
    """Generate embeddings using Ollama."""
    
    def __init__(
        self,
        ollama_host: str = "http://ollama:11434",
        model: str = "mxbai-embed-large",
        max_retries: int = 3,
        batch_size: int = 10
    ):
        """
        Initialize embeddings generator.
        
        Args:
            ollama_host: Ollama server host URL
            model: Embedding model name (default: mxbai-embed-large)
            max_retries: Maximum retry attempts for failed requests
            batch_size: Number of texts to process in parallel
        """
        self.ollama_host = ollama_host
        self.model = model
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.client = ollama.Client(host=ollama_host)
        
        logger.info(f"🤖 Initialized EmbeddingsGenerator with {model} @ {ollama_host}")
        
        # Verify connection
        self._check_connection()
    
    def _check_connection(self) -> bool:
        """
        Check if Ollama server is accessible and model is available.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Try to list models
            response = self.client.list()
            
            # Handle different response formats from ollama library
            models_data = response.get('models', []) if isinstance(response, dict) else getattr(response, 'models', [])
            
            # Extract model names safely
            models = []
            for m in models_data:
                if isinstance(m, dict):
                    models.append(m.get('name', m.get('model', '')))
                else:
                    # Handle object with attributes
                    models.append(getattr(m, 'model', getattr(m, 'name', '')))
            
            logger.info(f"✅ Connected to Ollama. Available models: {models}")
            
            if self.model not in models:
                logger.warning(f"⚠️ Model '{self.model}' not found. Available: {models}")
                logger.info(f"💡 Trying to pull {self.model}...")
                # Model will be auto-pulled on first use
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Ollama: {e}")
            raise ConnectionError(f"Cannot connect to Ollama at {self.ollama_host}")
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Optional[List[float]]: Embedding vector or None if failed
        """
        if not text or not text.strip():
            logger.warning("⚠️ Empty text provided for embedding")
            return None
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.embed(
                    model=self.model,
                    input=text
                )
                
                # Handle both 'embedding' and 'embeddings' response formats
                if 'embedding' in response:
                    embedding = response['embedding']
                elif 'embeddings' in response:
                    embedding = response['embeddings'][0] if response['embeddings'] else None
                else:
                    logger.error(f"❌ Unexpected response format: {response.keys()}")
                    return None
                
                if embedding:
                    logger.debug(f"✅ Generated embedding: {len(embedding)} dimensions")
                    return embedding
                else:
                    logger.warning("⚠️ Empty embedding returned")
                    return None
                    
            except Exception as e:
                logger.warning(f"⚠️ Embedding attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"❌ Failed to generate embedding after {self.max_retries} attempts")
                    return None
        
        return None
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        show_progress: bool = True
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts with parallel processing.
        
        Args:
            texts: List of texts to embed
            show_progress: Whether to log progress
            
        Returns:
            List[Optional[List[float]]]: List of embeddings (None for failed texts)
        """
        if not texts:
            logger.warning("⚠️ Empty text list provided")
            return []
        
        logger.info(f"🚀 Generating embeddings for {len(texts)} texts...")
        
        embeddings = [None] * len(texts)
        
        # Process in batches with parallel execution
        with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self.generate_embedding, text): i
                for i, text in enumerate(texts)
            }
            
            completed = 0
            failed = 0
            
            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    embedding = future.result()
                    embeddings[index] = embedding
                    
                    if embedding:
                        completed += 1
                    else:
                        failed += 1
                        
                    if show_progress and (completed + failed) % 10 == 0:
                        logger.info(f"📊 Progress: {completed + failed}/{len(texts)} ({completed} ✅, {failed} ❌)")
                        
                except Exception as e:
                    logger.error(f"❌ Error processing text {index}: {e}")
                    embeddings[index] = None
                    failed += 1
        
        logger.info(f"✅ Embedding generation complete: {completed} success, {failed} failed")
        return embeddings


def generate_embeddings(
    chunks: List[str],
    ollama_host: str = "http://ollama:11434",
    model: str = "mxbai-embed-large",
    batch_size: int = 10
) -> List[Optional[List[float]]]:
    """
    Convenience function to generate embeddings for a list of text chunks.
    
    Args:
        chunks: List of text chunks
        ollama_host: Ollama server host
        model: Embedding model name
        batch_size: Parallel processing batch size
        
    Returns:
        List[Optional[List[float]]]: List of embedding vectors
    """
    generator = EmbeddingsGenerator(
        ollama_host=ollama_host,
        model=model,
        batch_size=batch_size
    )
    
    return generator.generate_embeddings_batch(chunks)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test texts
    test_texts = [
        "OpenAI announces GPT-5 with revolutionary capabilities.",
        "The new AI model demonstrates unprecedented performance.",
        "Industry experts call this a game-changer for technology."
    ]
    
    # Generate embeddings
    try:
        embeddings = generate_embeddings(
            test_texts,
            ollama_host="http://localhost:11434",
            model="mxbai-embed-large"
        )
        
        print(f"\n📊 Generated {len(embeddings)} embeddings:")
        for i, emb in enumerate(embeddings, 1):
            if emb:
                print(f"  {i}. ✅ {len(emb)} dimensions")
            else:
                print(f"  {i}. ❌ Failed")
                
    except Exception as e:
        print(f"❌ Error: {e}")
