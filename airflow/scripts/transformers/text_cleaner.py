"""Text processing utilities for cleaning and chunking article content."""

import re
import logging
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """
    Clean text by removing HTML entities, extra whitespace, and artifacts.
    
    Args:
        text: Raw text to clean
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
    
    # Remove HTML entities
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://\S+', '', text)
    
    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separators: List[str] = None
) -> List[str]:
    """
    Split text into chunks using recursive character splitting.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum size of each chunk (default: 1000 characters)
        chunk_overlap: Number of characters to overlap between chunks (default: 200)
        separators: List of separators to use for splitting (default: paragraph/sentence separators)
        
    Returns:
        List[str]: List of text chunks
    """
    if not text:
        return []
    
    # Default separators optimized for news articles
    if separators is None:
        separators = [
            "\n\n",  # Paragraphs
            "\n",    # Lines
            ". ",    # Sentences
            "! ",
            "? ",
            ", ",    # Clauses
            " ",     # Words
            ""       # Characters
        ]
    
    try:
        # Initialize text splitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
            is_separator_regex=False
        )
        
        # Split text
        chunks = splitter.split_text(text)
        
        # Filter out very small chunks (likely just whitespace or artifacts)
        chunks = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 50]
        
        logger.info(f"📄 Split text into {len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})")
        return chunks
        
    except Exception as e:
        logger.error(f"❌ Error chunking text: {e}", exc_info=True)
        # Fallback: return text as single chunk
        return [text]


def prepare_article_for_embedding(
    title: str,
    content: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[str]:
    """
    Prepare article for embedding by cleaning and chunking.
    Prepends title to first chunk for better context.
    
    Args:
        title: Article title
        content: Article content
        chunk_size: Maximum chunk size
        chunk_overlap: Chunk overlap
        
    Returns:
        List[str]: List of text chunks ready for embedding
    """
    # Clean content
    cleaned_content = clean_text(content)
    
    if not cleaned_content:
        logger.warning("⚠️ Empty content after cleaning")
        return []
    
    # Chunk content
    chunks = chunk_text(cleaned_content, chunk_size, chunk_overlap)
    
    if not chunks:
        logger.warning("⚠️ No chunks generated")
        return []
    
    # Prepend title to first chunk for better context
    if title:
        cleaned_title = clean_text(title)
        chunks[0] = f"{cleaned_title}\n\n{chunks[0]}"
    
    logger.info(f"✅ Prepared {len(chunks)} chunks for embedding")
    return chunks


def estimate_token_count(text: str, chars_per_token: int = 4) -> int:
    """
    Estimate token count for text (rough approximation).
    
    Args:
        text: Text to estimate
        chars_per_token: Average characters per token (default: 4)
        
    Returns:
        int: Estimated token count
    """
    return len(text) // chars_per_token


def truncate_text(text: str, max_tokens: int = 8000, chars_per_token: int = 4) -> str:
    """
    Truncate text to maximum token count.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum number of tokens
        chars_per_token: Average characters per token
        
    Returns:
        str: Truncated text
    """
    max_chars = max_tokens * chars_per_token
    
    if len(text) <= max_chars:
        return text
    
    logger.warning(f"⚠️ Truncating text from {len(text)} to {max_chars} characters")
    return text[:max_chars]


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test text
    sample_text = """
    OpenAI announces GPT-5 with revolutionary capabilities. The new model 
    demonstrates unprecedented performance across multiple benchmarks.
    
    According to CEO Sam Altman, GPT-5 represents a significant leap forward 
    in artificial intelligence. The model can now handle complex reasoning 
    tasks that were previously impossible.
    
    Industry experts are calling this a game-changer. The technology could 
    revolutionize fields from healthcare to education. Early testing shows 
    promising results across all domains.
    """ * 10  # Repeat to create longer text
    
    title = "OpenAI Announces GPT-5"
    
    # Test cleaning
    cleaned = clean_text(sample_text)
    print(f"Original length: {len(sample_text)} chars")
    print(f"Cleaned length: {len(cleaned)} chars")
    
    # Test chunking
    chunks = prepare_article_for_embedding(title, sample_text, chunk_size=500, chunk_overlap=100)
    
    print(f"\n📊 Generated {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"\n--- Chunk {i} ({len(chunk)} chars) ---")
        print(chunk[:200] + "...")
