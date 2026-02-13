"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    # ChromaDB Configuration
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "news_articles"
    
    # OpenAI Configuration
    OPENAI_API_KEY: str
    OPENAI_LLM_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Google Gemini Configuration (optional)
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    
    # RAG Configuration
    RAG_TOP_K: int = 5
    RAG_TEMPERATURE: float = 0.7
    RAG_MAX_TOKENS: int = 500
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # API Configuration
    API_TITLE: str = "News Lens API"
    API_VERSION: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
