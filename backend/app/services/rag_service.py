"""
RAG Service

Handles Retrieval-Augmented Generation using ChromaDB and Ollama.
"""
from collections.abc import Iterator
from typing import List, Dict, Any
import time
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

    @staticmethod
    def _extract_chunk_text(chunk: Any) -> str:
        """
        Extract token text from an Ollama streaming chunk.
        """
        if chunk is None:
            return ""

        if isinstance(chunk, dict):
            message = chunk.get("message", {})
            if isinstance(message, dict):
                content = message.get("content", "")
                return content if isinstance(content, str) else ""
            return ""

        if hasattr(chunk, "message") and getattr(chunk, "message") is not None:
            message = getattr(chunk, "message")
            content = getattr(message, "content", "")
            return content if isinstance(content, str) else ""

        return ""

    def _build_fallback_answer(self, question: str, sources: List[SourceItem]) -> str:
        """
        Build a deterministic fallback answer when LLM generation fails.
        """
        if not sources:
            return "I could not generate an answer right now. Please try again in a moment."

        lines = [
            "I could not generate a full answer from the LLM right now, but these relevant sources were found:",
        ]

        for idx, source in enumerate(sources[:3], start=1):
            title = source.title if source.title else source.url
            lines.append(f"{idx}. {title} ({source.source_name})")

        lines.append(f"Question received: {question}")
        lines.append("Please retry once; the model may have timed out or returned an empty output.")

        return "\n".join(lines)
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Ollama
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.client.embed(
                    model=self.embedding_model,
                    input=text
                )
            
                # Ollama returns embeddings in different formats depending on version
                # Handle both single embedding and batch embeddings
                if 'embeddings' in response:
                    return response['embeddings'][0] if isinstance(response['embeddings'][0], list) else response['embeddings']
                if 'embedding' in response:
                    return response['embedding']

                raise ValueError(f"Unexpected response format from Ollama: {response.keys()}")
            except Exception as e:
                last_error = e
                if attempt < 3:
                    print(f"WARNING: Embedding attempt {attempt}/3 failed, retrying: {str(e)}")
                    time.sleep(1.0 * attempt)
                else:
                    break

        raise Exception(f"Embedding generation failed after retries: {str(last_error)}")
    
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
        
        last_error: Exception | None = None
        for attempt in range(1, 4):
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

                if not answer:
                    raise ValueError("LLM returned empty content")
            
                print(f"DEBUG: Generated answer length: {len(answer)}")
                print(f"DEBUG: Generated answer: {answer[:200] if len(answer) > 200 else answer}")
                return answer
            except Exception as e:
                last_error = e
                if attempt < 3:
                    print(f"WARNING: LLM generation attempt {attempt}/3 failed, retrying: {str(e)}")
                    time.sleep(1.5 * attempt)
                    continue

                print(f"ERROR in answer generation: {str(e)}")
                import traceback
                traceback.print_exc()
                break

        raise Exception(f"Answer generation failed after retries: {str(last_error)}")

    def _stream_answer(self, question: str, context: str) -> Iterator[str]:
        """
        Generate answer in streaming mode and yield token chunks.
        """
        system_prompt = """You are a helpful news assistant. Answer the user's question based on the provided news articles.
Be concise and factual. If the context doesn't contain relevant information, say so clearly.
Always cite which source(s) you're referencing when possible."""

        user_prompt = f"""Context from recent news articles:
{context}

Question: {question}

Answer:"""

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                stream = self.client.chat(
                    model=self.llm_model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    options={
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                    stream=True,
                )

                yielded = False
                for chunk in stream:
                    token = self._extract_chunk_text(chunk)
                    if token:
                        yielded = True
                        yield token

                if not yielded:
                    raise ValueError("LLM streaming returned no content")

                return
            except Exception as e:
                last_error = e
                if attempt < 3:
                    print(f"WARNING: LLM streaming attempt {attempt}/3 failed, retrying: {str(e)}")
                    time.sleep(1.5 * attempt)
                    continue
                break

        raise Exception(f"Streaming generation failed after retries: {str(last_error)}")

    def _retrieve_context_and_sources(self, question: str, top_k: int) -> tuple[str, List[SourceItem]]:
        """
        Retrieve relevant context and normalized source list for a question.
        """
        question_embedding = self._get_embedding(question)

        results = self.chroma_service.query(
            query_embeddings=[question_embedding],
            top_k=top_k,
        )

        if not results or not results.get("documents") or len(results["documents"][0]) == 0:
            return "", []

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        context_parts: List[str] = []
        sources: List[SourceItem] = []
        for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
            context_doc = doc[:1200] + "..." if len(doc) > 1200 else doc
            context_parts.append(f"[Source {i + 1}] {context_doc}")

            score = 1.0 / (1.0 + distance)
            snippet = doc[:200] + "..." if len(doc) > 200 else doc

            sources.append(
                SourceItem(
                    url=metadata.get("url", "N/A"),
                    title=metadata.get("title", "Untitled"),
                    date=metadata.get("date", "Unknown"),
                    snippet=snippet,
                    score=round(score, 4),
                    source_name=metadata.get("source_name", "Unknown Source"),
                )
            )

        return "\n\n".join(context_parts), sources

    def query_stream(self, question: str, top_k: int = None) -> Iterator[Dict[str, Any]]:
        """
        Perform a streaming RAG query and yield structured events.
        """
        resolved_top_k = top_k if top_k is not None else self.default_top_k

        yield {
            "type": "status",
            "stage": "embedding",
            "message": "Generating query embedding",
        }

        context, sources = self._retrieve_context_and_sources(question, resolved_top_k)

        yield {
            "type": "status",
            "stage": "retrieval",
            "message": f"Retrieved {len(sources)} relevant source(s)",
            "source_count": len(sources),
        }

        if not sources:
            fallback = "I don't have any news articles to answer your question. The database appears to be empty."
            yield {
                "type": "warning",
                "message": "No relevant sources found in vector store",
            }
            yield {
                "type": "sources",
                "sources": [],
            }
            yield {
                "type": "complete",
                "answer": fallback,
                "sources": [],
            }
            return

        yield {
            "type": "sources",
            "sources": [source.model_dump() for source in sources],
        }

        yield {
            "type": "status",
            "stage": "generation",
            "message": "Generating answer from retrieved context",
        }

        answer_parts: List[str] = []
        try:
            for token in self._stream_answer(question, context):
                answer_parts.append(token)
                yield {
                    "type": "token",
                    "token": token,
                }
        except Exception as e:
            yield {
                "type": "warning",
                "message": f"Streaming generation failed, using fallback answer: {str(e)}",
            }
            fallback = self._build_fallback_answer(question, sources)
            answer_parts = [fallback]

        answer = "".join(answer_parts).strip()
        if not answer:
            answer = self._build_fallback_answer(question, sources)

        yield {
            "type": "complete",
            "answer": answer,
            "sources": [source.model_dump() for source in sources],
        }
    
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

        context, sources = self._retrieve_context_and_sources(question, top_k)

        if not sources:
            return {
                'answer': "I don't have any news articles to answer your question. The database appears to be empty.",
                'sources': []
            }

        # Step 5: Generate answer using Ollama LLM
        try:
            answer = self._generate_answer(question, context)
        except Exception as e:
            print(f"WARNING: Falling back after generation failure: {str(e)}")
            answer = self._build_fallback_answer(question, sources)

        if not answer or not answer.strip():
            answer = self._build_fallback_answer(question, sources)
        
        return {
            'answer': answer,
            'sources': sources
        }
    
