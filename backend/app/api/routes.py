"""
API Routes
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import time

from app.models.schemas import QueryRequest, QueryResponse, HealthResponse, StatsResponse
from app.services.rag_service import RAGService
from app.services.chromadb_service import ChromaDBService
from app.config import settings

router = APIRouter()

# Initialize services
chroma_service = ChromaDBService(
    host=settings.CHROMA_HOST,
    port=settings.CHROMA_PORT,
    collection_name=settings.CHROMA_COLLECTION_NAME
)

rag_service = RAGService(
    chroma_service=chroma_service,
    ollama_host=settings.get_ollama_base_url(),
    llm_model=settings.OLLAMA_LLM_MODEL,
    embedding_model=settings.OLLAMA_EMBEDDING_MODEL,
    top_k=settings.RAG_TOP_K,
    temperature=settings.RAG_TEMPERATURE,
    max_tokens=settings.RAG_MAX_TOKENS
)



@router.get("/", tags=["Root"])
async def root() -> Dict[str, str]:
    """
    Root endpoint
    """
    return {
        "message": "News Lens API",
        "version": settings.API_VERSION,
        "docs": "/docs"
    }


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    
    Returns:
        Health status including ChromaDB connection status
    """
    try:
        # Test ChromaDB connection
        is_connected = chroma_service.test_connection()
        collection_count = chroma_service.get_document_count() if is_connected else 0
        
        return HealthResponse(
            status="healthy" if is_connected else "degraded",
            chromadb_connected=is_connected,
            collection_count=collection_count
        )
    
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            chromadb_connected=False,
            collection_count=0,
            error=str(e)
        )


@router.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats() -> StatsResponse:
    """
    Get database statistics
    
    Returns:
        Database statistics including document count
    """
    try:
        stats = chroma_service.get_collection_stats()
        
        return StatsResponse(
            total_documents=stats.get('document_count', 0),
            collections=[settings.CHROMA_COLLECTION_NAME],
            last_updated=stats.get('last_updated', None)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/query", response_model=QueryResponse, tags=["Query"])
async def query_news(request: QueryRequest) -> QueryResponse:
    """
    Query news articles using RAG
    
    Args:
        request: Query request with question and optional parameters
        
    Returns:
        Generated answer with sources
    """
    start_time = time.time()
    
    try:
        # Use custom top_k if provided, otherwise use default
        top_k = request.top_k or settings.RAG_TOP_K
        
        # Perform RAG query
        result = rag_service.query(
            question=request.question,
            top_k=top_k
        )
        
        query_time_ms = int((time.time() - start_time) * 1000)
        
        return QueryResponse(
            answer=result['answer'],
            sources=result['sources'],
            query_time_ms=query_time_ms
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/test", tags=["Test"])
async def test_endpoint() -> Dict[str, Any]:
    """
    Test endpoint for debugging
    """
    return {
        "chroma_host": settings.CHROMA_HOST,
        "chroma_port": settings.CHROMA_PORT,
        "collection_name": settings.CHROMA_COLLECTION_NAME,
        "model_provider": settings.MODEL_PROVIDER,
        "llm_model": settings.get_llm_model(),
        "embedding_model": settings.get_embedding_model(),
        "top_k": settings.RAG_TOP_K
    }
