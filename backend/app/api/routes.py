"""
API Routes
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
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


def _now_iso8601_utc() -> str:
    """Create UTC timestamp without microseconds for event payloads."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())



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


@router.websocket("/ws/query")
async def query_news_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for realtime RAG query streaming.

    Event protocol:
    - Client -> Server: {"type":"query","question":"...","top_k":5}
    - Server -> Client: status | token | sources | warning | error | complete
    """
    await websocket.accept()

    await websocket.send_json(
        {
            "type": "status",
            "stage": "connected",
            "message": "WebSocket connection established",
            "timestamp": _now_iso8601_utc(),
        }
    )

    try:
        while True:
            payload = await websocket.receive_json()
            request_type = payload.get("type")

            if request_type != "query":
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Unsupported message type. Expected 'query'.",
                        "recoverable": True,
                        "timestamp": _now_iso8601_utc(),
                    }
                )
                continue

            question = payload.get("question", "")
            top_k = payload.get("top_k")

            if not isinstance(question, str) or not question.strip():
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Field 'question' is required and must be a non-empty string.",
                        "recoverable": True,
                        "timestamp": _now_iso8601_utc(),
                    }
                )
                continue

            if top_k is not None:
                if not isinstance(top_k, int) or top_k < 1 or top_k > 20:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Field 'top_k' must be an integer between 1 and 20.",
                            "recoverable": True,
                            "timestamp": _now_iso8601_utc(),
                        }
                    )
                    continue

            started_at = time.time()

            await websocket.send_json(
                {
                    "type": "status",
                    "stage": "query_started",
                    "message": "Processing query",
                    "timestamp": _now_iso8601_utc(),
                }
            )

            try:
                for event in rag_service.query_stream(question=question.strip(), top_k=top_k):
                    event_with_ts = {**event, "timestamp": _now_iso8601_utc()}

                    if event.get("type") == "complete":
                        event_with_ts["query_time_ms"] = int((time.time() - started_at) * 1000)

                    await websocket.send_json(event_with_ts)

            except Exception as e:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Realtime query failed: {str(e)}",
                        "recoverable": False,
                        "timestamp": _now_iso8601_utc(),
                    }
                )

    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"WebSocket error: {str(e)}",
                    "recoverable": False,
                    "timestamp": _now_iso8601_utc(),
                }
            )
        except Exception:
            return


@router.get("/test", tags=["Test"])
async def test_endpoint() -> Dict[str, Any]:
    """
    Test endpoint for debugging
    """
    return {
        "chroma_host": settings.CHROMA_HOST,
        "chroma_port": settings.CHROMA_PORT,
        "collection_name": settings.CHROMA_COLLECTION_NAME,
        "llm_model": settings.OLLAMA_LLM_MODEL,
        "embedding_model": settings.OLLAMA_EMBEDDING_MODEL,
        "top_k": settings.RAG_TOP_K
    }
