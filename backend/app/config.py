"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import ClassVar, List, Union


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    # ChromaDB Configuration
    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "news_articles"
    
    # Ollama Configuration (Local LLM with GPU)
    OLLAMA_HOST: str = "ollama"
    OLLAMA_PORT: int = 11434
    OLLAMA_LLM_MODEL: str = "qwen3.5:4b"
    OLLAMA_EMBEDDING_MODEL: str = "mxbai-embed-large"
    
    # RAG Configuration
    RAG_TOP_K: int = 5
    RAG_TEMPERATURE: float = 0.7
    RAG_MAX_TOKENS: int = 2000
    
    # CORS Configuration
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000"

    DEFAULT_LOCAL_CORS_ORIGINS: ClassVar[List[str]] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://0.0.0.0:3000",
        "http://0.0.0.0:3001",
    ]
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string or list"""
        if v == "*":
            return ["*"]

        if isinstance(v, str):
            # Split by comma and strip whitespace
            parsed = [origin.strip() for origin in v.split(',') if origin.strip()]
        else:
            parsed = list(v)

        if "*" in parsed:
            return ["*"]

        merged: List[str] = []
        for origin in [*parsed, *cls.DEFAULT_LOCAL_CORS_ORIGINS]:
            if origin and origin not in merged:
                merged.append(origin)

        return merged
    
    # API Configuration
    API_TITLE: str = "News Lens API"
    API_VERSION: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def get_ollama_base_url(self) -> str:
        """Get Ollama base URL"""
        return f"http://{self.OLLAMA_HOST}:{self.OLLAMA_PORT}"


# Global settings instance
settings = Settings()
