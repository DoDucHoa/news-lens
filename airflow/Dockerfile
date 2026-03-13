FROM apache/airflow:2.8.1-python3.11

USER root

# Install system dependencies for web scraping
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Copy requirements file
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Configure Airflow to not load example DAGs
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
ENV AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=True
ENV AIRFLOW__WEBSERVER__EXPOSE_CONFIG=True
