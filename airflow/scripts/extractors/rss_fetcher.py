"""RSS feed fetcher for News Lens ETL pipeline."""

import feedparser
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dateutil import parser as date_parser
import pytz

logger = logging.getLogger(__name__)


def parse_published_date(entry: Dict) -> Optional[datetime]:
    """
    Parse published date from RSS entry.
    
    Args:
        entry: RSS feed entry
        
    Returns:
        Optional[datetime]: Parsed datetime or None if parsing fails
    """
    # Try different date fields in order of preference
    date_fields = [
        'published_parsed',
        'updated_parsed',
        'created_parsed',
        'published',
        'updated',
        'created'
    ]
    
    for field in date_fields:
        if field not in entry:
            continue
            
        try:
            # Handle time.struct_time (from _parsed fields)
            if field.endswith('_parsed') and entry[field]:
                time_struct = entry[field]
                dt = datetime(*time_struct[:6])
                # Assume UTC if no timezone
                return dt.replace(tzinfo=pytz.UTC)
            
            # Handle string dates
            if isinstance(entry[field], str):
                dt = date_parser.parse(entry[field])
                # Add UTC timezone if naive
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=pytz.UTC)
                return dt
                
        except Exception as e:
            logger.debug(f"Failed to parse date field '{field}': {e}")
            continue
    
    logger.warning(f"No valid published date found for entry: {entry.get('title', 'Unknown')}")
    return None


def fetch_rss_feeds(
    feed_urls: List[str],
    hours: int = 24,
    timezone: str = "Europe/Berlin"
) -> List[Dict]:
    """
    Fetch articles from RSS feeds published in the last N hours.
    
    Args:
        feed_urls: List of RSS feed URLs
        hours: Number of hours to look back (default: 24)
        timezone: Timezone for date calculations (default: "Europe/Berlin")
        
    Returns:
        List[Dict]: List of article dictionaries with keys:
            - title: Article title
            - link: Article URL
            - published_date: ISO format datetime string
            - source_name: Name of the source
            - summary: Article summary/description
            - feed_url: Original feed URL
    """
    tz = pytz.timezone(timezone)
    cutoff_time = datetime.now(tz) - timedelta(hours=hours)
    
    logger.info(f"📡 Fetching articles published after: {cutoff_time.isoformat()}")
    
    all_articles = []
    
    for feed_url in feed_urls:
        try:
            logger.info(f"📥 Fetching feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:
                logger.warning(f"⚠️ Feed parsing warning for {feed_url}: {feed.bozo_exception}")
            
            # Extract source name from feed
            source_name = feed.feed.get('title', 'Unknown')
            logger.info(f"📰 Source: {source_name}")
            
            articles_count = 0
            
            for entry in feed.entries:
                # Parse published date
                published_date = parse_published_date(entry)
                
                if published_date is None:
                    logger.debug(f"⏭️ Skipping entry without date: {entry.get('title', 'Unknown')}")
                    continue
                
                # Convert to target timezone for comparison
                published_date_tz = published_date.astimezone(tz)
                
                # Filter by date
                if published_date_tz < cutoff_time:
                    logger.debug(f"⏭️ Skipping old article: {entry.get('title', 'Unknown')} ({published_date_tz.isoformat()})")
                    continue
                
                # Extract article data
                article = {
                    "title": entry.get('title', 'No Title'),
                    "link": entry.get('link', ''),
                    "published_date": published_date.isoformat(),
                    "source_name": source_name,
                    "summary": entry.get('summary', entry.get('description', '')),
                    "feed_url": feed_url
                }
                
                all_articles.append(article)
                articles_count += 1
                
                logger.debug(f"✅ Added: {article['title'][:50]}...")
            
            logger.info(f"✅ Found {articles_count} recent articles from {source_name}")
            
        except Exception as e:
            logger.error(f"❌ Error fetching feed {feed_url}: {e}", exc_info=True)
            continue
    
    logger.info(f"📊 Total articles fetched: {len(all_articles)}")
    return all_articles


def map_feed_to_source_name(feed_url: str) -> str:
    """
    Map feed URL to a canonical source name for partitioning.
    
    Args:
        feed_url: Feed URL
        
    Returns:
        str: Canonical source name (e.g., "vnexpress", "dw-news")
    """
    url_to_name = {
        "vnexpress.net": "vnexpress",
        "rss.dw.com": "dw-news",
    }
    
    for domain, name in url_to_name.items():
        if domain in feed_url:
            return name
    
    # Fallback: extract domain
    from urllib.parse import urlparse
    parsed = urlparse(feed_url)
    domain = parsed.netloc.replace("www.", "").replace("rss.", "").split(".")[0]
    return domain


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test feeds
    test_feeds = [
        "https://vnexpress.net/rss/the-gioi.rss",
        "https://rss.dw.com/rdf/rss-en-top",
        "https://vnexpress.net/rss/thoi-su.rss"
    ]
    
    articles = fetch_rss_feeds(test_feeds, hours=24)
    
    print(f"\n📊 Fetched {len(articles)} articles:")
    for i, article in enumerate(articles[:5], 1):
        print(f"\n{i}. {article['title']}")
        print(f"   Source: {article['source_name']}")
        print(f"   Published: {article['published_date']}")
        print(f"   URL: {article['link'][:80]}...")
