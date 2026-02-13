"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import routes

# Initialize FastAPI app
app = FastAPI(
    title="News Lens API",
    description="RAG-powered news query API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.router)


@app.on_event("startup")
async def startup_event():
    """
    Initialize services on startup
    """
    print("Starting News Lens API...")
    print(f"ChromaDB: {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")
    print(f"LLM Model: {settings.OPENAI_LLM_MODEL}")
    print(f" RAG Top-K: {settings.RAG_TOP_K}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on shutdown
    """
    print("Shutting down News Lens API...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
