#!/usr/bin/env python3
"""
Manual script to process March 11, 2026 data into ChromaDB.
Bypasses Airflow execution_date issues by directly specifying the target date.
"""
import sys
sys.path.insert(0, '/opt/airflow')

from scripts.utils.gcs_client import GCSClient
from scripts.transformers.text_cleaner import prepare_article_for_embedding
from scripts.transformers.embeddings_generator import generate_embeddings
from scripts.utils.chromadb_client import ChromaDBClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    target_date = "2026-03-11"
    bucket_name = "newslens-data-lake"
    sources = ["dw-news", "vnexpress"]
    
    # Initialize clients
    gcs_client = GCSClient(bucket_name=bucket_name)
    chromadb_client = ChromaDBClient()
    
    logger.info(f"Processing articles from {target_date}")
    
    # List all blobs in GCS with raw/ prefix
    all_blobs = gcs_client.list_blobs(prefix="raw/", max_results=1000)
    
    # Filter for target date
    target_blobs = [
        blob for blob in all_blobs
        if f"date={target_date}" in blob and blob.endswith('.json')
    ]
    
    logger.info(f"Found {len(target_blobs)} files for {target_date}")
    
    all_articles = []
    for blob_path in target_blobs:
        logger.info(f"📥 Downloading: {blob_path}")
        data = gcs_client.download_json(blob_path)
        
        if data and 'articles' in data:
            articles = data['articles']
            all_articles.extend(articles)
            logger.info(f"Downloaded {len(articles)} articles from {blob_path}")
    
    logger.info(f"Total articles: {len(all_articles)}")
    
    # Process each article
    for article in all_articles:
        # Chunk text - extract title and content separately
        chunks = prepare_article_for_embedding(
            title=article.get('title', ''),
            content=article.get('content', ''),
            chunk_size=1000,
            chunk_overlap=200
        )
        
        if not chunks:
            logger.warning(f"No chunks for article: {article.get('url')}")
            continue
        
        # Generate embeddings
        embeddings = generate_embeddings(chunks)
        
        if not embeddings:
            logger.warning(f"No embeddings for article: {article.get('url')}")
            continue
        
        # Prepare metadata
        metadatas = [{
            "url": article.get("url", ""),
            "title": article.get("title", ""),
            "published_date": article.get("published_date", ""),
            "source": article.get("source", ""),
            "chunk_index": i
        } for i in range(len(chunks))]
        
        # Upsert to ChromaDB
        success = chromadb_client.upsert_chunks(
            chunks=chunks,
            embeddings=embeddings,
            metadata=metadatas
        )
        
        if success:
            logger.info(f"✅ Upserted {len(chunks)} chunks for: {article.get('title')}")
        else:
            logger.warning(f"⚠️ Failed to upsert chunks for: {article.get('title')}")
    
    logger.info("✅ Processing complete!")

if __name__ == "__main__":
    main()
