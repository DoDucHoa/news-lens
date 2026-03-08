#!/usr/bin/env python3
"""
ChromaDB Collection Initialization Script

Creates the news_articles collection in ChromaDB if it doesn't exist.
This script is idempotent and safe to run multiple times.

Usage:
    docker-compose exec backend python scripts/init_chromadb.py
"""
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.services.chromadb_service import ChromaDBService


def main():
    """
    Initialize ChromaDB collection
    """
    print("=" * 60)
    print("ChromaDB Collection Initialization")
    print("=" * 60)
    print(f"Host: {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")
    print(f"Collection: {settings.CHROMA_COLLECTION_NAME}")
    print()
    
    try:
        # Initialize ChromaDB service
        print("Connecting to ChromaDB...")
        chroma_service = ChromaDBService(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
            collection_name=settings.CHROMA_COLLECTION_NAME
        )
        
        # Test connection
        if not chroma_service.test_connection():
            print("✗ Failed to connect to ChromaDB")
            print("  Make sure ChromaDB service is running:")
            print("  docker-compose up chromadb -d")
            return 1
        
        print("✓ Connected to ChromaDB")
        print()
        
        # Check if collection exists
        if chroma_service.collection is not None:
            count = chroma_service.get_document_count()
            print(f"✓ Collection '{settings.CHROMA_COLLECTION_NAME}' already exists")
            print(f"  Documents: {count}")
            print()
            print("Collection is ready for use!")
            return 0
        
        # Create collection
        print(f"Creating collection '{settings.CHROMA_COLLECTION_NAME}'...")
        
        collection = chroma_service.client.create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={
                "description": "News articles for RAG queries",
                "created_by": "init_chromadb.py"
            }
        )
        
        print(f"✓ Collection '{settings.CHROMA_COLLECTION_NAME}' created successfully")
        print()
        print("Next steps:")
        print("1. Configure RSS feeds in Airflow Variables")
        print("2. Run the news_extraction_dag to fetch articles")
        print("3. Run the news_transformation_dag to populate ChromaDB")
        print()
        
        return 0
    
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        print()
        print("Troubleshooting:")
        print("- Ensure ChromaDB service is running")
        print("- Check network connectivity between services")
        print("- Verify CHROMA_HOST and CHROMA_PORT environment variables")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
