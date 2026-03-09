"""
RAG Service

Handles Retrieval-Augmented Generation using ChromaDB and Ollama.
"""
from typing import List, Dict, Any
import ollama
from app.services.chromadb_service import ChromaDBService
from app.models.schemas import SourceItem


class RAGService:
    """
    Service for performing RAG queries on news articles using local Ollama models
    """
    
    def __init__(
        self,
        chroma_service: ChromaDBService,
        ollama_host: str,
        llm_model: str,
        embedding_model: str,
        top_k: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 500
    ):
        """
        Initialize RAG service with Ollama
        
        Args:
            chroma_service: ChromaDB service instance
            ollama_host: Ollama server host URL (e.g., "http://ollama:11434")
            llm_model: LLM model name (e.g., "qwen3.5:4b")
            embedding_model: Embedding model name (e.g., "mxbai-embed-large")
            top_k: Default number of results to retrieve
            temperature: LLM temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
        """
        self.chroma_service = chroma_service
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.default_top_k = top_k
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize Ollama client
        self.client = ollama.Client(host=ollama_host)
        
        # Verify models are available
        try:
            available_models = self.client.list()
            model_names = [m['name'] for m in available_models.get('models', [])]
            
            if llm_model not in model_names:
                print(f"⚠️  Warning: LLM model '{llm_model}' not found in Ollama")
            else:
                print(f"✓ LLM model '{llm_model}' ready")
                
            if embedding_model not in model_names:
                print(f"⚠️  Warning: Embedding model '{embedding_model}' not found in Ollama")
            else:
                print(f"✓ Embedding model '{embedding_model}' ready")
                
        except Exception as e:
            print(f"⚠️  Warning: Could not verify Ollama models: {str(e)}")
        
        print(f"✓ RAG Service initialized with Ollama at {ollama_host}")
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Ollama
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            response = self.client.embed(
                model=self.embedding_model,
                input=text
            )
            
            # Ollama returns embeddings in different formats depending on version
            # Handle both single embedding and batch embeddings
            if 'embeddings' in response:
                return response['embeddings'][0] if isinstance(response['embeddings'][0], list) else response['embeddings']
            elif 'embedding' in response:
                return response['embedding']
            else:
                raise ValueError(f"Unexpected response format from Ollama: {response.keys()}")
                
        except Exception as e:
            raise Exception(f"Embedding generation failed: {str(e)}")
    
    def _generate_answer(self, question: str, context: str) -> str:
        """
        Generate answer using Ollama LLM based on context
        
        Args:
            question: User's question
            context: Context from retrieved documents
            
        Returns:
            Generated answer
        """
        # Build prompt
        system_prompt = """You are a helpful news assistant. Answer the user's question based on the provided news articles.
Be concise and factual. If the context doesn't contain relevant information, say so clearly.
Always cite which source(s) you're referencing when possible."""
        
        user_prompt = f"""Context from recent news articles:
{context}

Question: {question}

Answer:"""
        
        # Debug logging
        print(f"DEBUG: System prompt length: {len(system_prompt)}")
        print(f"DEBUG: User prompt length: {len(user_prompt)}")
        print(f"DEBUG: Context length: {len(context)}")
        print(f"DEBUG: First 500 chars of user_prompt: {user_prompt[:500]}")
        
        try:
            response = self.client.chat(
                model=self.llm_model,
                messages=[
                    {
                        'role': 'system',
                        'content': system_prompt
                    },
                    {
                        'role': 'user',
                        'content': user_prompt
                    }
                ],
                options={
                    'temperature': self.temperature,
                    'num_predict': self.max_tokens,
                },
                stream=False  # Explicitly disable streaming
            )
            
            # Debug logging
            print(f"DEBUG: Ollama response type: {type(response)}")
            print(f"DEBUG: Ollama response: {response}")
            
            # Handle both dict and object responses
            if hasattr(response, 'message'):
                content = response.message.content if response.message.content else ""
                answer = content.strip()
            elif isinstance(response, dict):
                content = response.get('message', {}).get('content', '')
                answer = content.strip()
            else:
                raise ValueError(f"Unexpected response type: {type(response)}")
            
            # If answer is empty, it might be a streaming issue - check if we need to collect chunks
            if not answer and hasattr(response, 'done') and response.done:
                print(f"WARNING: Empty answer despite done=True. Done reason: {response.done_reason if hasattr(response, 'done_reason') else 'unknown'}")
            
            print(f"DEBUG: Generated answer length: {len(answer)}")
            print(f"DEBUG: Generated answer: {answer[:200] if len(answer) > 200 else answer}")
            return answer
            
        except Exception as e:
            print(f"ERROR in answer generation: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Answer generation failed: {str(e)}")
    
    def query(self, question: str, top_k: int = None) -> Dict[str, Any]:
        """
        Perform RAG query: embed question, retrieve relevant docs, generate answer
        
        Args:
            question: User's question
            top_k: Number of documents to retrieve (uses default if None)
            
        Returns:
            Dictionary with 'answer' and 'sources' keys
        """
        if top_k is None:
            top_k = self.default_top_k
        
        # Step 1: Generate embedding for question
        question_embedding = self._get_embedding(question)
        
        # Step 2: Query ChromaDB for relevant documents
        results = self.chroma_service.query(
            query_embeddings=[question_embedding],
            top_k=top_k
        )
        
        # Step 3: Extract and format results
        if not results or not results.get('documents') or len(results['documents'][0]) == 0:
            return {
                'answer': "I don't have any news articles to answer your question. The database appears to be empty.",
                'sources': []
            }
        
        documents = results['documents'][0]  # First query's documents
        metadatas = results['metadatas'][0]  # First query's metadata
        distances = results['distances'][0]  # First query's distances
        
        # Step 4: Build context and sources
        context_parts = []
        sources = []
        
        for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
            # Add to context
            context_parts.append(f"[Source {i+1}] {doc}")
            
            # Convert distance to score (lower distance = higher relevance)
            # Using formula: score = 1 / (1 + distance)
            score = 1.0 / (1.0 + distance)
            
            # Create snippet (first 200 chars)
            snippet = doc[:200] + "..." if len(doc) > 200 else doc
            
            # Build source item
            source = SourceItem(
                url=metadata.get('url', 'N/A'),
                title=metadata.get('title', 'Untitled'),
                date=metadata.get('date', 'Unknown'),
                snippet=snippet,
                score=round(score, 4),
                source_name=metadata.get('source_name', 'Unknown Source')
            )
            sources.append(source)
        
        context = "\n\n".join(context_parts)
        
        # Step 5: Generate answer using Ollama LLM
        answer = self._generate_answer(question, context)
        
        return {
            'answer': answer,
            'sources': sources
        }
    
