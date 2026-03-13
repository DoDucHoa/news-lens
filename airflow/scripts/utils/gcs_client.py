"""Google Cloud Storage client utilities for News Lens ETL pipeline."""

import json
import logging
from typing import Any, Dict, Optional
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError
import os

logger = logging.getLogger(__name__)


class GCSClient:
    """Client for interacting with Google Cloud Storage."""
    
    def __init__(self, bucket_name: str):
        """
        Initialize GCS client.
        
        Args:
            bucket_name: Name of the GCS bucket
        """
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        logger.info(f"Initialized GCS client for bucket: {bucket_name}")
    
    def upload_json(
        self,
        blob_path: str,
        data: Dict[str, Any],
        retry_count: int = 3
    ) -> bool:
        """
        Upload JSON data to GCS with retry logic.
        
        Args:
            blob_path: Path within the bucket (e.g., "raw/source=vnexpress/date=2026-03-09/articles.json")
            data: Dictionary to upload as JSON
            retry_count: Number of retry attempts on failure
            
        Returns:
            bool: True if upload successful, False otherwise
        """
        for attempt in range(retry_count):
            try:
                blob = self.bucket.blob(blob_path)
                json_string = json.dumps(data, ensure_ascii=False, indent=2)
                
                blob.upload_from_string(
                    json_string,
                    content_type="application/json"
                )
                
                logger.info(f"✅ Uploaded to gs://{self.bucket_name}/{blob_path}")
                return True
                
            except GoogleCloudError as e:
                logger.warning(f"⚠️ Upload attempt {attempt + 1} failed: {e}")
                if attempt == retry_count - 1:
                    logger.error(f"❌ Failed to upload after {retry_count} attempts: {blob_path}")
                    return False
        
        return False
    
    def download_json(
        self,
        blob_path: str,
        retry_count: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Download JSON data from GCS with retry logic.
        
        Args:
            blob_path: Path within the bucket
            retry_count: Number of retry attempts on failure
            
        Returns:
            Optional[Dict]: Downloaded JSON data or None if failed
        """
        for attempt in range(retry_count):
            try:
                blob = self.bucket.blob(blob_path)
                
                if not blob.exists():
                    logger.warning(f"⚠️ Blob does not exist: gs://{self.bucket_name}/{blob_path}")
                    return None
                
                json_string = blob.download_as_text()
                data = json.loads(json_string)
                
                logger.info(f"✅ Downloaded from gs://{self.bucket_name}/{blob_path}")
                return data
                
            except NotFound:
                logger.warning(f"⚠️ Blob not found: gs://{self.bucket_name}/{blob_path}")
                return None
                
            except GoogleCloudError as e:
                logger.warning(f"⚠️ Download attempt {attempt + 1} failed: {e}")
                if attempt == retry_count - 1:
                    logger.error(f"❌ Failed to download after {retry_count} attempts: {blob_path}")
                    return None
        
        return None
    
    def blob_exists(self, blob_path: str) -> bool:
        """
        Check if a blob exists in GCS.
        
        Args:
            blob_path: Path within the bucket
            
        Returns:
            bool: True if blob exists, False otherwise
        """
        try:
            blob = self.bucket.blob(blob_path)
            return blob.exists()
        except GoogleCloudError as e:
            logger.error(f"❌ Error checking blob existence: {e}")
            return False
    
    def list_blobs(self, prefix: str, max_results: int = 100) -> list:
        """
        List blobs with a given prefix.
        
        Args:
            prefix: Prefix to filter blobs (e.g., "raw/source=vnexpress/")
            max_results: Maximum number of blobs to return
            
        Returns:
            list: List of blob names
        """
        try:
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=prefix,
                max_results=max_results
            )
            blob_names = [blob.name for blob in blobs]
            logger.info(f"📋 Found {len(blob_names)} blobs with prefix: {prefix}")
            return blob_names
            
        except GoogleCloudError as e:
            logger.error(f"❌ Error listing blobs: {e}")
            return []


def create_partition_path(source_name: str, date_str: str, filename: str = "articles.json") -> str:
    """
    Create a partitioned path for GCS storage.
    
    Args:
        source_name: Name of the news source (e.g., "vnexpress", "dw-news")
        date_str: Date string in YYYY-MM-DD format
        filename: Name of the file (default: "articles.json")
        
    Returns:
        str: Partitioned path (e.g., "raw/source=vnexpress/date=2026-03-09/articles.json")
    """
    return f"raw/source={source_name}/date={date_str}/{filename}"


# Example usage
if __name__ == "__main__":
    # Test GCS connection
    import os
    
    bucket_name = os.getenv("GCS_BUCKET_NAME", "newslens-data-lake")
    
    try:
        client = GCSClient(bucket_name)
        
        # Test upload
        test_data = {
            "test": "data",
            "timestamp": "2026-03-09T12:00:00Z"
        }
        
        test_path = "test/test.json"
        success = client.upload_json(test_path, test_data)
        
        if success:
            # Test download
            downloaded = client.download_json(test_path)
            print(f"✅ Test successful: {downloaded}")
        else:
            print("❌ Test failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
