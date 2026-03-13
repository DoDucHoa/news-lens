"""Quick script to check ChromaDB contents"""
import sys
sys.path.insert(0, '/opt/airflow/scripts')
from utils.chromadb_client import ChromaDBClient

client = ChromaDBClient()
collection = client.get_collection('news_articles')

# Get sample documents
results = collection.get(limit=10, include=['metadatas'])
metadatas = results.get('metadatas', [])

print(f"\n{'='*60}")
print(f"Total documents in ChromaDB: {collection.count()}")
print(f"{'='*60}\n")

print("Sample documents:")
for i, meta in enumerate(metadatas[:5], 1):
    print(f"\n{i}. Title: {meta.get('title', 'No title')}")
    print(f"   Date: {meta.get('date', 'N/A')}")
    print(f"   URL: {meta.get('url', 'N/A')[:80]}")
    print(f"   Source: {meta.get('source_name', 'Unknown')}")

print(f"\n{'='*60}")
