"""
News Transformation DAG - Process raw articles and load into ChromaDB.

This DAG runs after extraction to:
1. Download raw articles from GCS
2. Clean text and chunk into smaller pieces
3. Generate embeddings using Ollama
4. Upsert chunks + embeddings to ChromaDB

Triggered: Automatically after extraction DAG completes
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import logging
import sys
import os

# Add scripts directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from utils.gcs_client import GCSClient, create_partition_path
from transformers.text_cleaner import prepare_article_for_embedding
from transformers.embeddings_generator import generate_embeddings
from utils.chromadb_client import ChromaDBClient

logger = logging.getLogger(__name__)

# Default arguments for the DAG
default_args = {
    'owner': 'news-lens',
    'depends_on_past': False,
    'start_date': datetime(2026, 3, 1, tzinfo=None),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    'news_transformation_dag',
    default_args=default_args,
    description='Transform raw articles and load into ChromaDB',
    schedule_interval=None,  # Triggered by extraction DAG after upload_to_gcs succeeds
    catchup=False,
    tags=['news', 'transformation', 'embeddings', 'chromadb'],
)


def download_from_gcs_task(**context):
    """
    Task 1: Download raw articles from GCS.
    
    Downloads articles from yesterday's partition.
    Pushes articles to XCom.
    """
    logger.info("☁️ Downloading articles from GCS...")
    
    # Initialize GCS client
    bucket_name = os.getenv('GCS_BUCKET_NAME', 'newslens-data-lake')
    gcs_client = GCSClient(bucket_name)
    
    # Get execution date (yesterday's data)
    execution_date = context['ds']  # YYYY-MM-DD format
    logger.info(f"Processing data for date: {execution_date}")
    
    # List all blobs with date partition
    prefix = f"raw/source="
    all_blobs = gcs_client.list_blobs(prefix, max_results=1000)
    
    # Filter blobs for target date
    target_blobs = [
        blob for blob in all_blobs
        if f"date={execution_date}" in blob and blob.endswith('.json')
    ]
    
    logger.info(f"Found {len(target_blobs)} partitions for {execution_date}")
    
    # Download all partitions
    all_articles = []
    
    for blob_path in target_blobs:
        logger.info(f"📥 Downloading: {blob_path}")
        
        data = gcs_client.download_json(blob_path)
        
        if data and 'articles' in data:
            articles = data['articles']
            all_articles.extend(articles)
            logger.info(f"✅ Downloaded {len(articles)} articles from {blob_path}")
        else:
            logger.warning(f"⚠️ No articles found in {blob_path}")
    
    logger.info(f"✅ Downloaded total {len(all_articles)} articles from GCS")
    
    # Push to XCom
    context['task_instance'].xcom_push(key='raw_articles', value=all_articles)
    
    return len(all_articles)


def clean_and_chunk_task(**context):
    """
    Task 2: Clean text and chunk into smaller pieces.
    
    Pulls articles from XCom.
    Cleans and chunks each article.
    Pushes chunked articles to XCom.
    """
    logger.info("✂️ Starting text cleaning and chunking...")
    
    # Pull articles from previous task
    task_instance = context['task_instance']
    articles = task_instance.xcom_pull(task_ids='download_from_gcs', key='raw_articles')
    
    if not articles:
        logger.warning("⚠️ No articles to process")
        return 0
    
    logger.info(f"Processing {len(articles)} articles...")
    
    chunked_articles = []
    total_chunks = 0
    
    for i, article in enumerate(articles, 1):
        url = article.get('link', article.get('url', ''))
        title = article.get('title', 'No Title')
        content = article.get('content', '')
        
        if not content or len(content) < 100:
            logger.warning(f"⚠️ Article {i}/{len(articles)} has insufficient content, skipping")
            continue
        
        logger.info(f"📄 Processing {i}/{len(articles)}: {title[:50]}...")
        
        # Prepare article (clean + chunk)
        chunks = prepare_article_for_embedding(
            title=title,
            content=content,
            chunk_size=1000,
            chunk_overlap=200
        )
        
        if chunks:
            chunked_article = {
                'url': url,
                'title': title,
                'chunks': chunks,
                'source_name': article.get('source_name', 'Unknown'),
                'published_date': article.get('published_date', ''),
                'scraped_at': article.get('scraped_at', ''),
                'chunk_count': len(chunks)
            }
            chunked_articles.append(chunked_article)
            total_chunks += len(chunks)
            
            logger.info(f"✅ Generated {len(chunks)} chunks")
        else:
            logger.warning(f"⚠️ Failed to chunk article")
    
    logger.info(f"✅ Chunking complete: {len(chunked_articles)} articles, {total_chunks} total chunks")
    
    # Push to XCom
    task_instance.xcom_push(key='chunked_articles', value=chunked_articles)
    
    return len(chunked_articles)


def generate_embeddings_task(**context):
    """
    Task 3: Generate embeddings for all chunks.
    
    Pulls chunked articles from XCom.
    Generates embeddings using Ollama.
    Pushes articles with embeddings to XCom.
    """
    logger.info("🤖 Starting embeddings generation...")
    
    # Pull chunked articles from previous task
    task_instance = context['task_instance']
    articles = task_instance.xcom_pull(task_ids='clean_and_chunk', key='chunked_articles')
    
    if not articles:
        logger.warning("⚠️ No articles to generate embeddings for")
        return 0
    
    logger.info(f"Generating embeddings for {len(articles)} articles...")
    
    # Get Ollama configuration
    ollama_host = os.getenv('OLLAMA_HOST', 'ollama')
    ollama_port = os.getenv('OLLAMA_PORT', '11434')
    ollama_url = f"http://{ollama_host}:{ollama_port}"
    embedding_model = os.getenv('OLLAMA_EMBEDDING_MODEL', 'mxbai-embed-large')
    
    logger.info(f"Using Ollama at {ollama_url} with model {embedding_model}")
    
    articles_with_embeddings = []
    total_embedded = 0
    
    for i, article in enumerate(articles, 1):
        chunks = article['chunks']
        logger.info(f"🔢 Generating embeddings for article {i}/{len(articles)} ({len(chunks)} chunks)...")
        
        try:
            # Generate embeddings for all chunks
            embeddings = generate_embeddings(
                chunks=chunks,
                ollama_host=ollama_url,
                model=embedding_model,
                batch_size=5  # Process 5 chunks in parallel
            )
            
            # Count successful embeddings
            success_count = sum(1 for emb in embeddings if emb is not None)
            
            if success_count > 0:
                article['embeddings'] = embeddings
                articles_with_embeddings.append(article)
                total_embedded += success_count
                
                logger.info(f"✅ Generated {success_count}/{len(chunks)} embeddings")
            else:
                logger.warning(f"⚠️ No embeddings generated for article")
                
        except Exception as e:
            logger.error(f"❌ Failed to generate embeddings: {e}", exc_info=True)
            continue
    
    logger.info(f"✅ Embeddings generation complete: {total_embedded} chunks embedded from {len(articles_with_embeddings)} articles")
    
    # Push to XCom
    task_instance.xcom_push(key='articles_with_embeddings', value=articles_with_embeddings)
    
    return len(articles_with_embeddings)


def upsert_to_chromadb_task(**context):
    """
    Task 4: Upsert chunks + embeddings to ChromaDB.
    
    Pulls articles with embeddings from XCom.
    Upserts to ChromaDB collection.
    """
    logger.info("🗄️ Starting ChromaDB upsert...")
    
    # Pull articles from previous task
    task_instance = context['task_instance']
    articles = task_instance.xcom_pull(task_ids='generate_embeddings', key='articles_with_embeddings')
    
    if not articles:
        logger.warning("⚠️ No articles to upsert")
        return 0
    
    logger.info(f"Upserting {len(articles)} articles to ChromaDB...")
    
    # Get ChromaDB configuration
    chromadb_host = os.getenv('CHROMADB_HOST', 'chromadb')
    chromadb_port = int(os.getenv('CHROMADB_PORT', '8000'))
    collection_name = os.getenv('CHROMADB_COLLECTION', 'news_articles')
    
    # Initialize ChromaDB client
    chroma_client = ChromaDBClient(
        host=chromadb_host,
        port=chromadb_port,
        collection_name=collection_name
    )
    
    success_count = 0
    total_chunks = 0
    
    for i, article in enumerate(articles, 1):
        logger.info(f"📤 Upserting article {i}/{len(articles)}: {article['title'][:50]}...")
        
        try:
            success = chroma_client.upsert_article(
                url=article['url'],
                title=article['title'],
                chunks=article['chunks'],
                embeddings=article['embeddings'],
                source_name=article['source_name'],
                published_date=article['published_date'],
                scraped_at=article.get('scraped_at')
            )
            
            if success:
                success_count += 1
                total_chunks += sum(1 for emb in article['embeddings'] if emb is not None)
                logger.info(f"✅ Upserted successfully")
            else:
                logger.warning(f"⚠️ Failed to upsert article")
                
        except Exception as e:
            logger.error(f"❌ Error upserting article: {e}", exc_info=True)
            continue
    
    logger.info(f"✅ ChromaDB upsert complete: {total_chunks} chunks from {success_count} articles")
    
    # Log final collection stats
    stats = chroma_client.get_collection_stats()
    logger.info(f"📊 Collection stats: {stats['total_documents']} total documents")
    
    return success_count


# Define tasks

task_download_from_gcs = PythonOperator(
    task_id='download_from_gcs',
    python_callable=download_from_gcs_task,
    provide_context=True,
    dag=dag,
)

task_clean_and_chunk = PythonOperator(
    task_id='clean_and_chunk',
    python_callable=clean_and_chunk_task,
    provide_context=True,
    dag=dag,
)

task_generate_embeddings = PythonOperator(
    task_id='generate_embeddings',
    python_callable=generate_embeddings_task,
    provide_context=True,
    dag=dag,
)

task_upsert_to_chromadb = PythonOperator(
    task_id='upsert_to_chromadb',
    python_callable=upsert_to_chromadb_task,
    provide_context=True,
    dag=dag,
)

# Define task dependencies
task_download_from_gcs >> task_clean_and_chunk >> task_generate_embeddings >> task_upsert_to_chromadb
