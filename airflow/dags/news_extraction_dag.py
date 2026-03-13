"""
News Extraction DAG - Fetch RSS feeds and scrape article content.

This DAG runs daily to:
1. Fetch articles from configured RSS feeds (last 24 hours)
2. Scrape full content from article URLs
3. Upload raw data to GCS for persistence

Schedule: Daily at midnight (Berlin timezone)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
import logging
import sys
import os

# Add scripts directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from extractors.rss_fetcher import fetch_rss_feeds, map_feed_to_source_name
from extractors.content_scraper import scrape_article, clean_scraped_text
from utils.gcs_client import GCSClient, create_partition_path

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
    'news_extraction_dag',
    default_args=default_args,
    description='Extract news articles from RSS feeds and upload to GCS',
    schedule_interval='0 0 * * *',  # Daily at midnight
    catchup=False,
    tags=['news', 'extraction', 'rss', 'gcs'],
)


def fetch_rss_task(**context):
    """
    Task 1: Fetch articles from RSS feeds.
    
    Reads RSS feed URLs from Airflow Variable 'NEWS_RSS_FEEDS' (comma-separated).
    Filters articles from last 24 hours.
    Pushes article list to XCom.
    """
    logger.info("📡 Starting RSS feed fetching...")
    
    # Get RSS feed URLs from Airflow Variables
    try:
        rss_feeds_str = Variable.get("NEWS_RSS_FEEDS")
        feed_urls = [url.strip() for url in rss_feeds_str.split(',') if url.strip()]
    except Exception as e:
        logger.error(f"❌ Failed to get NEWS_RSS_FEEDS variable: {e}")
        # Fallback to default feeds
        feed_urls = [
            "https://vnexpress.net/rss/the-gioi.rss",
            "https://rss.dw.com/rdf/rss-en-top"
        ]
        logger.info(f"Using default feeds: {feed_urls}")
    
    logger.info(f"Fetching from {len(feed_urls)} RSS feeds")
    
    # Fetch articles
    articles = fetch_rss_feeds(feed_urls, hours=24, timezone="Europe/Berlin")
    
    logger.info(f"✅ Fetched {len(articles)} articles from RSS feeds")
    
    # Push to XCom for next task
    context['task_instance'].xcom_push(key='raw_articles', value=articles)
    
    return len(articles)


def scrape_content_task(**context):
    """
    Task 2: Scrape full content for each article.
    
    Pulls article list from XCom.
    Scrapes content from each URL.
    Pushes enriched articles to XCom.
    """
    logger.info("🌐 Starting content scraping...")
    
    # Pull articles from previous task
    task_instance = context['task_instance']
    articles = task_instance.xcom_pull(task_ids='fetch_rss', key='raw_articles')
    
    if not articles:
        logger.warning("⚠️ No articles to scrape")
        return 0
    
    logger.info(f"Scraping content for {len(articles)} articles...")
    
    enriched_articles = []
    success_count = 0
    failed_count = 0
    
    for i, article in enumerate(articles, 1):
        url = article.get('link', '')
        
        if not url:
            logger.warning(f"⚠️ Article {i}/{len(articles)} has no URL, skipping")
            failed_count += 1
            continue
        
        logger.info(f"📄 Scraping {i}/{len(articles)}: {url[:80]}...")
        
        # Scrape content
        content = scrape_article(url, timeout=15, max_retries=2)
        
        if content:
            # Clean content
            cleaned_content = clean_scraped_text(content)
            
            # Add to enriched articles
            enriched_article = {
                **article,
                'content': cleaned_content,
                'scraped_at': datetime.utcnow().isoformat(),
                'content_length': len(cleaned_content)
            }
            enriched_articles.append(enriched_article)
            success_count += 1
            
            logger.info(f"✅ Scraped {len(cleaned_content)} chars")
        else:
            logger.warning(f"⚠️ Failed to scrape: {url[:80]}...")
            failed_count += 1
    
    logger.info(f"✅ Scraping complete: {success_count} success, {failed_count} failed")
    
    # Push to XCom for next task
    task_instance.xcom_push(key='enriched_articles', value=enriched_articles)
    
    return success_count


def upload_to_gcs_task(**context):
    """
    Task 3: Upload enriched articles to GCS.
    
    Pulls enriched articles from XCom.
    Partitions by source and date.
    Uploads to GCS bucket.
    """
    logger.info("☁️ Starting GCS upload...")
    
    # Pull articles from previous task
    task_instance = context['task_instance']
    articles = task_instance.xcom_pull(task_ids='scrape_content', key='enriched_articles')
    
    if not articles:
        logger.warning("⚠️ No articles to upload")
        return 0
    
    logger.info(f"Uploading {len(articles)} articles to GCS...")
    
    # Initialize GCS client
    bucket_name = os.getenv('GCS_BUCKET_NAME', 'newslens-data-lake')
    gcs_client = GCSClient(bucket_name)
    
    # Get execution date for partitioning
    execution_date = context['ds']  # YYYY-MM-DD format
    
    # Group articles by source
    articles_by_source = {}
    for article in articles:
        # Map feed URL to source name
        feed_url = article.get('feed_url', '')
        source_name = map_feed_to_source_name(feed_url)
        
        if source_name not in articles_by_source:
            articles_by_source[source_name] = []
        
        articles_by_source[source_name].append(article)
    
    # Upload each source separately
    upload_count = 0
    
    for source_name, source_articles in articles_by_source.items():
        logger.info(f"📤 Uploading {len(source_articles)} articles from {source_name}...")
        
        # Create partition path
        blob_path = create_partition_path(source_name, execution_date, "articles.json")
        
        # Check if already exists (idempotency)
        if gcs_client.blob_exists(blob_path):
            logger.info(f"⏭️ Partition already exists: {blob_path}")
            continue
        
        # Prepare data
        upload_data = {
            "source": source_name,
            "date": execution_date,
            "article_count": len(source_articles),
            "articles": source_articles,
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        # Upload to GCS
        success = gcs_client.upload_json(blob_path, upload_data)
        
        if success:
            upload_count += len(source_articles)
            logger.info(f"✅ Uploaded {source_name}: {blob_path}")
        else:
            logger.error(f"❌ Failed to upload {source_name}")
    
    logger.info(f"✅ GCS upload complete: {upload_count} articles uploaded")
    
    return upload_count


# Define tasks
task_fetch_rss = PythonOperator(
    task_id='fetch_rss',
    python_callable=fetch_rss_task,
    provide_context=True,
    dag=dag,
)

task_scrape_content = PythonOperator(
    task_id='scrape_content',
    python_callable=scrape_content_task,
    provide_context=True,
    dag=dag,
)

task_upload_to_gcs = PythonOperator(
    task_id='upload_to_gcs',
    python_callable=upload_to_gcs_task,
    provide_context=True,
    dag=dag,
)

# Define task dependencies
task_fetch_rss >> task_scrape_content >> task_upload_to_gcs
