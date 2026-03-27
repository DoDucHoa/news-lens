# Airflow ETL Pipeline for News Lens

This directory contains the Airflow setup for automated news extraction and transformation.

## Overview

The ETL pipeline consists of two main DAGs:

### 1. **News Extraction DAG** (`news_extraction_dag`)
- **Schedule:** Daily at midnight (Berlin timezone)
- **Purpose:** Fetch RSS feeds, scrape article content, upload to GCS
- **Tasks:**
  1. `fetch_rss` - Fetch articles from configured RSS feeds (last 24 hours)
  2. `scrape_content` - Scrape full article content from URLs
  3. `upload_to_gcs` - Upload raw data to GCS (partitioned by source and date)

### 2. **News Transformation DAG** (`news_transformation_dag`)
- **Schedule:** Daily at 1 AM (after extraction completes)
- **Purpose:** Process raw articles and load into ChromaDB
- **Tasks:**
  1. `wait_for_extraction` - Wait for extraction DAG to complete
  2. `download_from_gcs` - Download raw articles from GCS
  3. `clean_and_chunk` - Clean text and split into chunks
  4. `generate_embeddings` - Generate embeddings using Ollama
  5. `upsert_to_chromadb` - Upsert chunks to ChromaDB

## Directory Structure

```
airflow/
├── Dockerfile              # Airflow container with dependencies
├── requirements.txt        # Python dependencies
├── dags/                   # DAG definitions
│   ├── news_extraction_dag.py
│   └── news_transformation_dag.py
└── scripts/                # ETL modules
    ├── extractors/         # RSS and web scraping
    │   ├── rss_fetcher.py
    │   └── content_scraper.py
    ├── transformers/       # Text processing and embeddings
    │   ├── text_cleaner.py
    │   └── embeddings_generator.py
    └── utils/              # Utility clients
        ├── gcs_client.py
        └── chromadb_client.py
```

## Setup Instructions

### 1. Configure GCS (Data Lake)

Follow the guide in [docs/GCS_SETUP.md](../docs/GCS_SETUP.md) to:
- Create GCS bucket: `newslens-data-lake`
- Set up service account with Storage Object Admin permissions
- Download service account key to `secrets/gcs-service-account.json`

### 2. Start Airflow Services

```bash
# Build and start all services (including Airflow)
docker-compose up -d airflow-webserver airflow-scheduler airflow-postgres

# Wait for services to be healthy (~30 seconds)
docker-compose ps

# Check logs if needed
docker-compose logs -f airflow-webserver
```

### 3. Initialize Airflow Variables

Configure RSS feed URLs:

```bash
# Option 1: Using Python script (recommended)
docker-compose exec airflow-webserver python /opt/airflow/scripts/init_airflow_variables.py

# Option 2: Using bash script
docker-compose exec airflow-webserver bash /opt/airflow/scripts/init_airflow_variables.sh
```

### 4. Access Airflow UI

1. Open browser: http://localhost:8080
2. Login credentials:
   - **Username:** `admin`
   - **Password:** `admin`

### 5. Enable and Trigger DAGs

1. Navigate to **DAGs** page
2. Toggle ON for:
   - `news_extraction_dag`
   - `news_transformation_dag`
3. Click ▶️ to trigger manually (or wait for scheduled run)

## Configuration

### RSS Feed Sources

RSS feeds are configured via Airflow Variables (`NEWS_RSS_FEEDS`).

**Add/Update feeds:**
1. Go to Airflow UI → **Admin** → **Variables**
2. Edit `NEWS_RSS_FEEDS`
3. Enter comma-separated URLs:
   ```
   https://vnexpress.net/rss/the-gioi.rss,https://rss.dw.com/rdf/rss-en-top,https://your-feed.com/rss
   ```

**Currently configured feeds:**
- VNExpress (Vietnam): https://vnexpress.net/rss/the-gioi.rss
- DW News (Germany): https://rss.dw.com/rdf/rss-en-top
- VNExpress (Vietnam): https://vnexpress.net/rss/thoi-su.rss

### Environment Variables

Key environment variables (set in `docker-compose.yml`):

```bash
# GCS
GCS_BUCKET_NAME=news-lens-data-lake
GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcs-service-account.json

# Ollama
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
OLLAMA_EMBEDDING_MODEL=mxbai-embed-large

# ChromaDB
CHROMADB_HOST=chromadb
CHROMADB_PORT=8000
CHROMADB_COLLECTION=news_articles
```

## Monitoring

### Check DAG Status

```bash
# List all DAGs
docker-compose exec airflow-scheduler airflow dags list

# Check DAG status
docker-compose exec airflow-scheduler airflow dags state news_extraction_dag

# View task instances
docker-compose exec airflow-scheduler airflow tasks list news_extraction_dag
```

### View Logs

```bash
# Airflow webserver logs
docker-compose logs -f airflow-webserver

# Airflow scheduler logs
docker-compose logs -f airflow-scheduler

# View specific task log via UI:
# DAGs → [DAG Name] → [Task] → Log
```

### Verify Data Pipeline

```bash
# Check GCS for raw data
# Expected structure: gs://newslens-data-lake/raw/source=vnexpress/date=YYYY-MM-DD/articles.json

# Check ChromaDB stats
curl http://localhost:8001/stats
```

## Troubleshooting

### DAG Import Errors

```bash
# Test DAG file syntax
docker-compose exec airflow-scheduler python /opt/airflow/dags/news_extraction_dag.py

# Check for import errors
docker-compose exec airflow-scheduler airflow dags list-import-errors
```

### Connection Issues

**Ollama not reachable:**
- Verify Ollama container is running: `docker-compose ps ollama`
- Check network: All services should be on `news-lens-network`
- Test from Airflow: `docker-compose exec airflow-scheduler curl http://ollama:11434`

**ChromaDB not reachable:**
- Verify ChromaDB is running: `docker-compose ps chromadb`
- Test connection: `docker-compose exec airflow-scheduler curl http://chromadb:8000/api/v1/heartbeat`

**GCS authentication failed:**
- Verify service account key exists: `docker-compose exec airflow-webserver ls -la /secrets/`
- Check key permissions: Should be readable by Airflow user
- Test GCS access: Run a test upload via Python script

### Failed Scraping

If articles fail to scrape:
- Check if website is accessible
- Verify VNExpress/DW News website structure hasn't changed
- Update scraper selectors in `scripts/extractors/content_scraper.py`

### Low Embedding Generation Speed

- Verify GPU is available: `docker exec news-lens-ollama nvidia-smi`
- Check Ollama model is loaded: `docker exec news-lens-ollama ollama list`
- Monitor GPU usage: `watch -n 1 nvidia-smi`

## Data Flow

```
RSS Feeds
   ↓
Extraction DAG → GCS (raw data)
   ↓
Transformation DAG → Ollama (embeddings) → ChromaDB
   ↓
Backend API (RAG queries)
```

## Development

### Testing Scrapers

```bash
# Test RSS fetcher
docker-compose exec airflow-scheduler python /opt/airflow/scripts/extractors/rss_fetcher.py

# Test content scraper
docker-compose exec airflow-scheduler python /opt/airflow/scripts/extractors/content_scraper.py
```

### Adding New News Sources

1. Add RSS feed URL to Airflow Variables (`NEWS_RSS_FEEDS`)
2. If needed, add custom scraper logic in `content_scraper.py`
3. Update `map_feed_to_source_name()` in `rss_fetcher.py`

### Debugging DAGs

```bash
# Test specific task
docker-compose exec airflow-scheduler airflow tasks test news_extraction_dag fetch_rss 2026-03-09

# Clear task state and rerun
docker-compose exec airflow-scheduler airflow tasks clear news_extraction_dag -t fetch_rss -s 2026-03-09
```

## Production Considerations

- [ ] Use strong passwords for Airflow admin (change from `admin/admin`)
- [ ] Rotate GCS service account keys every 90 days
- [ ] Set up Airflow email alerts for failed DAGs
- [ ] Configure log rotation for Airflow logs
- [ ] Monitor GCS bucket size and costs
- [ ] Set up budget alerts in GCP
- [ ] Use secrets backend (e.g., Airflow Connections) instead of environment variables
- [ ] Enable Airflow authentication (LDAP/OAuth)
- [ ] Configure backup for Airflow metadata database

## Support

For issues or questions:
1. Check Airflow logs: `docker-compose logs airflow-scheduler`
2. Review DAG run history in Airflow UI
3. Verify all services are healthy: `docker-compose ps`
4. Consult main project README and GCS setup guide
