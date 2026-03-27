#!/bin/bash

# ======================================================================
# Initialize Airflow Variables for News Lens ETL Pipeline
# ======================================================================
# This script sets up required Airflow Variables for the news extraction
# and transformation DAGs.
#
# Usage:
#   1. Start Airflow services: docker-compose up airflow-webserver
#   2. Run this script: docker-compose exec airflow-webserver bash /opt/airflow/scripts/init_airflow_variables.sh
#
# Or manually via Airflow UI:
#   Admin > Variables > Create
# ======================================================================

set -e

echo "🚀 Initializing Airflow Variables for News Lens..."

# Check if airflow CLI is available
if ! command -v airflow &> /dev/null; then
    echo "❌ Error: airflow CLI not found. Make sure you're inside the Airflow container."
    exit 1
fi

echo ""
echo "📋 Setting RSS Feed URLs..."
# Set NEWS_RSS_FEEDS variable (comma-separated list of RSS feed URLs)
airflow variables set NEWS_RSS_FEEDS \
    "https://vnexpress.net/rss/the-gioi.rss,https://rss.dw.com/rdf/rss-en-top,https://vnexpress.net/rss/thoi-su.rss" \
    --description "Comma-separated list of RSS feed URLs to fetch news from"

echo "✅ Set NEWS_RSS_FEEDS"

# Verify variables are set
echo ""
echo "🔍 Verifying variables..."
airflow variables list

echo ""
echo "✅ Airflow variables initialized successfully!"
echo ""
echo "📝 Next steps:"
echo "  1. Go to Airflow UI: http://localhost:8080"
echo "  2. Login with credentials: admin / admin"
echo "  3. Enable DAGs: news_extraction_dag and news_transformation_dag"
echo "  4. Trigger manually or wait for scheduled run"
echo ""
echo "💡 To add more RSS feeds, update the NEWS_RSS_FEEDS variable:"
echo "   airflow variables set NEWS_RSS_FEEDS \"feed1,feed2,feed3\""
echo ""
