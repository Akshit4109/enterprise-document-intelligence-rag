# Enterprise Document Intelligence & RAG Platform

> A production-minded, full-stack platform for securely ingesting enterprise documents, retrieving grounded context, and delivering citation-backed answers.

Built with FastAPI, PostgreSQL + pgvector, React, and Docker. The application demonstrates the engineering behind a practical Retrieval-Augmented Generation (RAG) system: document lifecycle management, hybrid retrieval, access-aware filtering, conversational memory, and operational health checks.

## Why this project

Most RAG demos stop at "upload a PDF and ask a question." This project explores the concerns required to move beyond a demo:

- **Reliable ingestion** — validates and parses PDF, DOCX, and TXT files before chunking and embedding.
- **Search quality** — combines semantic vector search, keyword retrieval, metadata filters, and optional cross-encoder reranking.
- **Trustworthy answers** — grounds responses in retrieved context and returns source citations.
- **Enterprise controls** — supports ownership isolation, department scoping, tags, document versioning, and active-version selection.
- **Operational readiness** — includes Alembic migrations, containerized services, structured logging, health checks, and automated tests.

## Architecture

```mermaid
flowchart LR
    U["React web client"] --> API["FastAPI API"]
    API --> ING["Ingestion pipeline\nvalidate → parse → chunk → embed"]
    API --> RET["Retrieval engine\nvector + keyword + reranking"]
    API --> RAG["RAG orchestration\ncontext + citations + history"]
    ING --> DB[("PostgreSQL + pgvector")]
    RET --> DB
    RAG --> DB
    ING --> FS["Document storage"]
```

## Highlights

| Area | Implementation |
| --- | --- |
| Document processing | PDF, DOCX, and TXT parsing; MIME and magic-byte validation; recursive semantic chunking |
| Retrieval | pgvector cosine similarity, keyword retrieval, metadata filters, HNSW indexing, and reranking adapters |
| RAG | Grounded prompts, relevance thresholds, source citations, and multi-turn conversation context |
| Data model | Documents, immutable versions, chunks, conversations, and messages with Alembic migrations |
| Security | Owner/department scoping, safe local-path resolution, credential redaction, and centralized exception responses |
| UX | React/Vite dashboard for documents, search, assistant conversations, and system health |

## Tech stack

- **Backend:** Python, FastAPI, SQLAlchemy 2.0, Pydantic, Alembic
- **Data:** PostgreSQL 16, pgvector, Psycopg
- **AI:** Sentence Transformers; pluggable OpenAI and Gemini providers; LangChain/LangGraph adapters
- **Frontend:** React 18, TypeScript, Vite, Axios, Lucide
- **Delivery:** Docker Compose, Nginx, GitHub Actions

## Quick start

### Run the complete stack

```bash
git clone https://github.com/<your-username>/enterprise-document-intelligence-rag.git
cd enterprise-document-intelligence-rag
docker compose up --build
```

Once running:

- Web app: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/health`

### Run locally for development

```bash
# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start the database and apply schema migrations
docker compose up -d postgres
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

## Configuration

Create a local `.env` file only when overriding defaults. Never commit it.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://rag_user:rag_password@localhost:5433/enterprise_rag_db` | Database connection |
| `EMBEDDING_PROVIDER` | `local` | `local`, `mock`, or `openai` |
| `LLM_PROVIDER` | `mock` | `mock`, `openai`, or `gemini` |
| `OPENAI_API_KEY` | — | Required only for the OpenAI provider |
| `GEMINI_API_KEY` | — | Required only for the Gemini provider |
| `RAG_MIN_RELEVANCE_THRESHOLD` | `0.25` | Guardrail for low-confidence retrieval |

For the default local configuration, embeddings use `sentence-transformers/all-MiniLM-L6-v2` with 384 dimensions.

## API at a glance

| Capability | Endpoint |
| --- | --- |
| Upload a document | `POST /api/v1/documents/upload` |
| Upload asynchronously | `POST /api/v1/documents/upload/async` |
| List documents / versions | `GET /api/v1/documents`, `GET /api/v1/documents/{id}/versions` |
| Activate a version | `PUT /api/v1/documents/{id}/versions/{version_id}/activate` |
| Search documents | `POST /api/v1/search` |
| Ask a grounded question | `POST /api/v1/query` |
| Continue a conversation | `POST /api/v1/conversations/{id}/messages` |

Example search request:

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What is the vacation policy?",
    "top_k": 3,
    "filters": {"department": "HR", "requesting_user_id": "usr_hr"}
  }'
```

Explore the complete request and response schemas in the interactive OpenAPI documentation at `/docs`.

## Quality checks

```bash
# Backend test suite
pytest -q

# Frontend checks
cd frontend
npm run test
npm run build
```

The automated suite covers parsing, storage safety, embeddings, retrieval behavior, versioning, conversation isolation, RAG citations, API validation, and production hardening.

## Repository structure

```text
app/            FastAPI application, domain services, retrieval, RAG, and schemas
alembic/        Versioned database migrations
frontend/       React + TypeScript web application
tests/          Backend unit and integration tests
scripts/        Evaluation and developer utilities
```

## Roadmap

- [ ] Add authentication provider integration and role-based policies
- [ ] Add background-job observability and ingestion metrics
- [ ] Add retrieval evaluation datasets and benchmark reporting
- [ ] Add cloud object-storage deployment configuration

## Contributing

Contributions and feedback are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

Released under the [MIT License](LICENSE).
