"""Content scraper for News Lens ETL pipeline with site-specific extractors."""

import requests
from bs4 import BeautifulSoup
import logging
from typing import Optional
import time

logger = logging.getLogger(__name__)

# User agent to avoid being blocked
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"


def scrape_vnexpress(soup: BeautifulSoup, url: str) -> Optional[str]:
    """
    Extract article content from VNExpress.
    
    Args:
        soup: BeautifulSoup object
        url: Article URL
        
    Returns:
        Optional[str]: Extracted article text or None
    """
    try:
        # VNExpress stores content in specific divs
        content_selectors = [
            "article.fck_detail",
            "div.fck_detail",
            "div.sidebar_1",
            "article.content_detail"
        ]
        
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Remove ads and related content
                for unwanted in content_div.select('div.box_category, div.lazier, div.box-tinlienquanv2, div.box_comment'):
                    unwanted.decompose()
                
                # Extract paragraphs
                paragraphs = content_div.find_all(['p', 'div.Normal'])
                if paragraphs:
                    text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                    
                    if len(text) > 100:  # Minimum content length
                        logger.debug(f"✅ VNExpress scraper: {len(text)} chars")
                        return text
        
        logger.warning(f"⚠️ VNExpress: No content found with standard selectors")
        return None
        
    except Exception as e:
        logger.error(f"❌ VNExpress scraper error: {e}")
        return None


def scrape_dw_news(soup: BeautifulSoup, url: str) -> Optional[str]:
    """
    Extract article content from Deutsche Welle (DW).
    
    Args:
        soup: BeautifulSoup object
        url: Article URL
        
    Returns:
        Optional[str]: Extracted article text or None
    """
    try:
        # DW News content structure
        content_selectors = [
            "div.longText",
            "article",
            "div.article-content"
        ]
        
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Remove ads and navigation
                for unwanted in content_div.select('aside, .advertisement, .related-content, nav'):
                    unwanted.decompose()
                
                # Extract paragraphs
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                    
                    if len(text) > 100:
                        logger.debug(f"✅ DW News scraper: {len(text)} chars")
                        return text
        
        logger.warning(f"⚠️ DW News: No content found")
        return None
        
    except Exception as e:
        logger.error(f"❌ DW News scraper error: {e}")
        return None


def scrape_generic(soup: BeautifulSoup, url: str) -> Optional[str]:
    """
    Generic content extractor for unknown news sites.
    
    Args:
        soup: BeautifulSoup object
        url: Article URL
        
    Returns:
        Optional[str]: Extracted article text or None
    """
    try:
        # Try common article selectors
        content_selectors = [
            "article",
            "div.article-body",
            "div.article-content",
            "div.entry-content",
            "div.post-content",
            "main"
        ]
        
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                # Remove common unwanted elements
                for unwanted in content.select('aside, footer, nav, .advertisement, .related, .comments, script, style'):
                    unwanted.decompose()
                
                paragraphs = content.find_all('p')
                if paragraphs:
                    text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                    
                    if len(text) > 100:
                        logger.debug(f"✅ Generic scraper: {len(text)} chars")
                        return text
        
        # Fallback: extract all paragraphs
        all_paragraphs = soup.find_all('p')
        if len(all_paragraphs) > 3:
            text = "\n\n".join(p.get_text(strip=True) for p in all_paragraphs if len(p.get_text(strip=True)) > 50)
            if len(text) > 200:
                logger.debug(f"✅ Generic fallback: {len(text)} chars")
                return text
        
        logger.warning(f"⚠️ Generic scraper: No content found")
        return None
        
    except Exception as e:
        logger.error(f"❌ Generic scraper error: {e}")
        return None


def scrape_article(url: str, timeout: int = 10, max_retries: int = 2) -> Optional[str]:
    """
    Scrape article content from URL with site-specific extractors.
    
    Args:
        url: Article URL
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        
    Returns:
        Optional[str]: Extracted article text or None if scraping fails
    """
    if not url:
        logger.warning("⚠️ Empty URL provided")
        return None
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"🌐 Scraping (attempt {attempt + 1}/{max_retries}): {url[:80]}...")
            
            # Make request
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Detect site and use appropriate scraper
            if "vnexpress.net" in url:
                content = scrape_vnexpress(soup, url)
            elif "dw.com" in url:
                content = scrape_dw_news(soup, url)
            else:
                content = scrape_generic(soup, url)
            
            if content:
                logger.info(f"✅ Scraped {len(content)} chars from: {url[:80]}...")
                return content
            else:
                logger.warning(f"⚠️ No content extracted from: {url[:80]}...")
                return None
                
        except requests.Timeout:
            logger.warning(f"⏱️ Timeout scraping: {url[:80]}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retry
                continue
            return None
            
        except requests.HTTPError as e:
            logger.warning(f"⚠️ HTTP error {e.response.status_code}: {url[:80]}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"❌ Request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
            
        except Exception as e:
            logger.error(f"❌ Unexpected error scraping {url}: {e}", exc_info=True)
            return None
    
    return None


def clean_scraped_text(text: str) -> str:
    """
    Clean scraped text by removing extra whitespace and artifacts.
    
    Args:
        text: Raw scraped text
        
    Returns:
        str: Cleaned text
    """
    import re
    
    # Remove multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)
    
    return text.strip()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test URLs
    test_urls = {
        "VNExpress": "https://vnexpress.net/nga-co-the-tan-cong-ba-lan-bom-4856296.html",
        "DW News": "https://www.dw.com/en/top-stories/s-9097"
    }
    
    for source, url in test_urls.items():
        print(f"\n{'='*60}")
        print(f"Testing {source}")
        print(f"{'='*60}")
        
        content = scrape_article(url)
        
        if content:
            cleaned = clean_scraped_text(content)
            print(f"✅ Success: {len(cleaned)} characters")
            print(f"\nFirst 300 chars:\n{cleaned[:300]}...")
        else:
            print(f"❌ Failed to scrape {source}")
