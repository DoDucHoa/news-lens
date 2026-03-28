# News Lens: End-to-End News ETL + RAG Platform

News Lens is an end-to-end news ETL and RAG platform that turns scattered daily articles into a searchable knowledge base.

It solves news overload by automatically ingesting RSS content, storing raw data in a partitioned lake, generating embeddings, and serving fast natural-language answers through API and web UI.

## Why This Project

- Demonstrates end-to-end ETL design with orchestration (Airflow)
- Shows a production-style raw-first data lake pattern in Google Cloud Storage
- Uses local, low-cost GenAI inference with Ollama instead of paid APIs
- Delivers practical user value: fast question-answering over recent news using RAG
- Runs as a multi-service Docker stack suitable for portfolio demonstration

## Architecture Overview
![System Architecture Sequence](documents/System%20Architecture%20Sequence.png)
Core components:

- Airflow: scheduled extraction and transformation pipelines
- GCS Data Lake: partitioned raw/processed storage
- Ollama: local LLM + embedding generation
- ChromaDB: vector database for semantic retrieval
- FastAPI backend: retrieval + generation API
- Next.js frontend: user query interface

High-level flow:

1. Extraction DAG fetches RSS feeds and scrapes article content.
2. Raw payloads are written to GCS partitions.
3. Transformation DAG downloads raw data, cleans/chunks text, generates embeddings, and upserts into ChromaDB.
4. Backend receives user queries, retrieves top-k chunks, and generates an answer via Ollama.
5. Frontend calls backend APIs and displays answers with sources.

Mermaid high-level system sequence:

- `docs/diagrams/system-architecture-sequence.mmd`


## Main Flow

This flow describes how a user question travels from the frontend to retrieval and generation, then streams back to the UI.

![Prompt Submission Flow](documents/Prompt%20Submission%20Flow.png)

### 1) Input Validation (Frontend)

1. User enters a prompt and clicks submit.
2. Frontend validates the input before calling backend services.
3. If the prompt is empty or invalid, the UI shows a validation message and stops the request.

### 2) Retrieval + Generation (Backend RAG Path)

1. For valid prompts, frontend opens a WebSocket request to `/ws/query`.
2. Backend generates a query embedding via Ollama embedding model.
3. Backend sends that vector to ChromaDB to retrieve top-k relevant chunks.
4. ChromaDB returns context chunks and source metadata.
5. Backend calls Ollama LLM with retrieved context to generate a grounded answer.

### 3) Streaming Response (User Experience)

1. Backend streams progress events, partial answer text, and sources back to frontend.
2. Frontend renders the answer with source citations as data arrives.

### 4) Failure Handling

1. If a runtime failure occurs (embedding service, vector DB, or LLM), backend returns an error event/response.
2. Frontend surfaces retry guidance so users can resubmit safely.

## Project Structure

```text
news-lens/
|-- airflow/                # DAGs and ETL scripts
|-- backend/                # FastAPI RAG service
|-- frontend/               # Next.js UI
|-- chromadb/               # Persistent ChromaDB data
|-- scripts/                # Utility scripts
|-- secrets/                # Local secret mounts (not for git)
|-- docker-compose.yml
|-- .env.example
```

## Tech Stack

- Orchestration: Apache Airflow
- Backend: FastAPI (Python)
- Frontend: Next.js (React, TypeScript)
- Vector DB: ChromaDB
- Local AI runtime: Ollama
- LLM model: `qwen3.5:0.8b` (default)
- Embedding model: `mxbai-embed-large`
- Data Lake: Google Cloud Storage (required in standard setup)
- Infrastructure: Docker Compose

## Quick Start (Docker-First)

### 1) Prerequisites

- Docker + Docker Compose
- NVIDIA GPU + NVIDIA Container Toolkit (recommended for Ollama performance)
- Google Cloud project with a GCS bucket and service account key

### 2) Configure Environment

1. Copy environment template:

```bash
cp .env.example .env
```

2. Place service account key at:

```text
secrets/gcs-service-account.json
```

3. Ensure `.env` values are set (especially `GCS_BUCKET_NAME`).


### 3) Start Core Services

```bash
docker-compose up -d --build
```

### 4) Pull Ollama Models (inside container)

```bash
docker exec news-lens-ollama ollama pull qwen3.5:0.8b
docker exec news-lens-ollama ollama pull qwen3.5:2b
docker exec news-lens-ollama ollama pull qwen3.5:4b
docker exec news-lens-ollama ollama pull mxbai-embed-large
```

### 5) Initialize Airflow Variables

```bash
docker-compose exec airflow-webserver python /opt/airflow/scripts/init_airflow_variables.py
```

### 6) Run Frontend (currently local)

Frontend is currently run outside Docker.

```bash
cd frontend
npm install
npm run dev
```

### 7) Access Services

- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs
- Airflow UI: http://localhost:8080 (admin/admin)
- Frontend UI: http://localhost:3000

## API Endpoints

- `GET /health` - service and ChromaDB health
- `GET /stats` - collection statistics
- `POST /query` - RAG query endpoint

Query model selection:

- Frontend dropdown supports: `qwen3.5:0.8b`, `qwen3.5:2b`, `qwen3.5:4b`
- Selection is persisted in browser localStorage
- Backend returns explicit errors for unsupported or unavailable selected models (no silent fallback)

Example query:

```bash
curl -X POST "http://localhost:8001/query" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are today\'s key world news themes?","top_k":5,"llm_model":"qwen3.5:0.8b"}'
```

## ETL DAGs

- `news_extraction_dag`: RSS fetch -> content scrape -> raw upload to GCS
- `news_transformation_dag`: download raw -> clean/chunk -> embeddings -> upsert to ChromaDB

## Security Notes

- ChromaDB is intentionally not exposed to the public host port.
- Keep service account keys in `secrets/` and out of source control.
- Use strong non-default credentials for production deployments.

## Current Status

- Dockerized backend, Airflow, Ollama, ChromaDB stack is configured.
- Frontend Docker service is currently commented out in `docker-compose.yml` and run locally.
