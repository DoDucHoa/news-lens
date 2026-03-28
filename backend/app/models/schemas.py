"""
Pydantic Models for API Request/Response
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class SourceItem(BaseModel):
    """
    Individual source item with article metadata
    """
    url: str = Field(..., description="Article URL")
    title: str = Field(..., description="Article title")
    date: str = Field(..., description="Publication date")
    snippet: str = Field(..., description="Text excerpt from article")
    score: float = Field(..., description="Relevance score (0-1, higher is more relevant)")
    source_name: str = Field(..., description="News source/publisher name")


class QueryRequest(BaseModel):
    """
    Request model for news query endpoint
    """
    question: str = Field(..., description="User's question about the news", min_length=1)
    top_k: Optional[int] = Field(None, description="Number of sources to retrieve (default: 5)", ge=1, le=20)
    llm_model: Optional[str] = Field(
        None,
        description="LLM model to use for this query. Allowed: qwen3.5:0.8b, qwen3.5:2b, qwen3.5:4b",
    )


class QueryResponse(BaseModel):
    """
    Response model for news query endpoint
    """
    answer: str = Field(..., description="Generated answer from LLM")
    sources: List[SourceItem] = Field(..., description="Source articles used to generate answer")
    query_time_ms: int = Field(..., description="Query execution time in milliseconds")


class HealthResponse(BaseModel):
    """
    Response model for health check endpoint
    """
    status: str = Field(..., description="Service status (healthy/degraded/unhealthy)")
    chromadb_connected: bool = Field(..., description="ChromaDB connection status")
    collection_count: int = Field(..., description="Number of documents in collection")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class StatsResponse(BaseModel):
    """
    Response model for statistics endpoint
    """
    total_documents: int = Field(..., description="Total number of documents")
    collections: List[str] = Field(..., description="List of collection names")
    last_updated: Optional[str] = Field(None, description="Last update timestamp")
