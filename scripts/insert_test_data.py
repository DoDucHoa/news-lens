#!/usr/bin/env python3
"""
Insert Test Data into ChromaDB

This script inserts sample news articles for testing the RAG pipeline
without waiting for Airflow to run.

Usage:
    docker-compose exec backend python scripts/insert_test_data.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.chromadb_service import ChromaDBService
from app.services.rag_service import RAGService
from app.config import settings


def main():
    """
    Insert test news articles into ChromaDB
    """
    print("=" * 60)
    print("ChromaDB Test Data Insertion")
    print("=" * 60)
    print()

    # Test documents (realistic news articles)
    documents = [
        "OpenAI released GPT-5 today with breakthrough reasoning capabilities. The model shows significant improvements in math and coding tasks, achieving 95% accuracy on challenging benchmarks. The company claims this represents a major leap in artificial general intelligence development.",
        "Google announced a new quantum computing chip called Willow that solves complex problems 100x faster than previous generations. The breakthrough could revolutionize drug discovery and climate modeling. Scientists at Google Quantum AI demonstrated the chip solving a problem in minutes that would take classical supercomputers thousands of years.",
        "Microsoft acquired a leading AI startup for $10 billion, marking the largest AI acquisition this year. The acquisition will strengthen Microsoft's position in enterprise AI solutions. Industry analysts predict this will accelerate AI adoption across Fortune 500 companies.",
        "Tesla unveiled its new electric truck model with 500-mile range and advanced autonomous driving features. The vehicle includes cutting-edge battery technology and solar charging capabilities. Pre-orders exceeded 100,000 units in the first 24 hours.",
        "Scientists discovered a new treatment for Alzheimer's disease showing promising results in clinical trials. The therapy targets protein buildup in the brain and showed significant cognitive improvement in 70% of patients. Major pharmaceutical companies are now fast-tracking development."
    ]

    metadatas = [
        {
            "url": "https://example.com/openai-gpt5",
            "title": "OpenAI Releases GPT-5 with Breakthrough Capabilities",
            "date": "2026-02-14",
            "source_name": "TechCrunch"
        },
        {
            "url": "https://example.com/google-quantum",
            "title": "Google's Quantum Chip Achieves Major Breakthrough",
            "date": "2026-02-14",
            "source_name": "Science Daily"
        },
        {
            "url": "https://example.com/microsoft-acquisition",
            "title": "Microsoft Makes Largest AI Acquisition",
            "date": "2026-02-14",
            "source_name": "Business Wire"
        },
        {
            "url": "https://example.com/tesla-truck",
            "title": "Tesla Unveils Revolutionary Electric Truck",
            "date": "2026-02-13",
            "source_name": "Automotive News"
        },
        {
            "url": "https://example.com/alzheimers-treatment",
            "title": "New Alzheimer's Treatment Shows Promise",
            "date": "2026-02-13",
            "source_name": "Medical Today"
        }
    ]

    try:
        # Initialize ChromaDB service
        print("Connecting to ChromaDB...")
        chroma_service = ChromaDBService(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
            collection_name=settings.CHROMA_COLLECTION_NAME
        )

        if not chroma_service.collection:
            print("✗ Collection not found. Run init_chromadb.py first.")
            return 1

        print(f"✓ Connected to ChromaDB collection: {settings.CHROMA_COLLECTION_NAME}")
        print(f"  Current document count: {chroma_service.get_document_count()}")
        print()

        # Initialize RAG service for embeddings with Ollama
        print(f"Initializing RAG service with Ollama...")
        print(f"  Ollama Host: {settings.get_ollama_base_url()}")
        print(f"  LLM Model: {settings.OLLAMA_LLM_MODEL}")
        print(f"  Embedding Model: {settings.OLLAMA_EMBEDDING_MODEL}")
        rag_service = RAGService(
            chroma_service=chroma_service,
            ollama_host=settings.get_ollama_base_url(),
            llm_model=settings.OLLAMA_LLM_MODEL,
            embedding_model=settings.OLLAMA_EMBEDDING_MODEL,
            top_k=settings.RAG_TOP_K,
            temperature=settings.RAG_TEMPERATURE,
            max_tokens=settings.RAG_MAX_TOKENS
        )
        print()

        # Generate embeddings
        print(f"Generating embeddings for {len(documents)} documents...")
        embeddings = []
        for i, doc in enumerate(documents, 1):
            print(f"  [{i}/{len(documents)}] {metadatas[i-1]['title'][:50]}...")
            embedding = rag_service._get_embedding(doc)
            embeddings.append(embedding)

        print("✓ All embeddings generated")
        print()

        # Insert into ChromaDB
        print("Inserting documents into ChromaDB...")
        chroma_service.collection.add(
            ids=[f"test_article_{i}" for i in range(len(documents))],
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        print(f"✓ Successfully inserted {len(documents)} test documents")
        print()

        # Verify insertion
        new_count = chroma_service.get_document_count()
        print(f"Total documents in collection: {new_count}")
        print()

        print("=" * 60)
        print("Test Data Ready!")
        print("=" * 60)
        print()
        print("Try querying the API:")
        print('  curl -X POST http://localhost:8001/query \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"question":"What did OpenAI announce?","top_k":3}\'')
        print()

        return 0

    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)