"""
Initialize Airflow Variables for News Lens ETL Pipeline

This script sets up required Airflow Variables programmatically.

Usage:
    docker-compose exec airflow-webserver python /opt/airflow/scripts/init_airflow_variables.py
"""

import subprocess
import sys


def run_airflow_command(cmd: list) -> bool:
    """Run an Airflow CLI command."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Error: airflow CLI not found")
        return False


def set_variable(key: str, value: str, description: str = "") -> bool:
    """Set an Airflow variable."""
    print(f"Setting {key}...")
    
    cmd = ["airflow", "variables", "set", key, value]
    if description:
        cmd.extend(["--description", description])
    
    return run_airflow_command(cmd)


def main():
    print("🚀 Initializing Airflow Variables for News Lens...\n")
    
    # Define variables to set
    variables = {
        "NEWS_RSS_FEEDS": {
            "value": "https://vnexpress.net/rss/the-gioi.rss,https://rss.dw.com/rdf/rss-en-top,https://vnexpress.net/rss/thoi-su.rss",
            "description": "Comma-separated list of RSS feed URLs to fetch news from"
        }
    }
    
    success_count = 0
    
    for key, config in variables.items():
        if set_variable(key, config["value"], config.get("description", "")):
            success_count += 1
            print(f"✅ Set {key}\n")
        else:
            print(f"❌ Failed to set {key}\n")
    
    # List all variables
    print("\n🔍 Verifying variables...")
    run_airflow_command(["airflow", "variables", "list"])
    
    print(f"\n✅ Initialized {success_count}/{len(variables)} variables successfully!")
    print("\n📝 Next steps:")
    print("  1. Go to Airflow UI: http://localhost:8080")
    print("  2. Login with credentials: admin / admin")
    print("  3. Enable DAGs: news_extraction_dag and news_transformation_dag")
    print("  4. Trigger manually or wait for scheduled run")
    print("\n💡 To add more RSS feeds via UI:")
    print("   Admin > Variables > Edit NEWS_RSS_FEEDS")
    print("   Add feeds as comma-separated URLs")
    

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
