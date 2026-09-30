# Design

## Context

The incident triage system requires grounded operational runbooks to provide reliable remediation guidance. This design covers the storage layer (Supabase PostgreSQL with pgvector), embedding generation (Gemini embeddings via Google AI Studio), and idempotent seeding CLI (`seed_rag.py`).

The project operates entirely within zero-cost free tiers with no credit cards required, driven by environment variables (`GEMINI_API_KEY`, `DATABASE_URL`).

## Goals / Non-Goals

**Goals:**
- Provide a clear SQL migration (`db/migrations/001_incident_docs.sql`) establishing the `incident_docs` table and `match_incident_docs` RPC function with cosine distance.
- Establish core project dependencies in `requirements.txt`.
- Build an idempotent seeding script (`seed_rag.py`) embedding 3 domain runbooks (auth, database, payments) using Gemini 768-dimensional embeddings (`RETRIEVAL_DOCUMENT`).
- Implement unit tests mocking embedding APIs and PostgreSQL interactions so tests run fast, offline, and without consuming API quotas.

**Non-Goals:**
- Implementing the LangGraph agent triage loop or human-in-the-loop escalation (handled in future changes).
- Building the FastAPI web server or Gradio UI.
- Dynamically ingesting arbitrary external wiki or documentation sources beyond the sample seed runbooks.

## Decisions

### 1. Database Schema and Vector Store
- **Decision**: Use Supabase PostgreSQL with `pgvector` directly via raw SQL migration rather than an ORM. The `incident_docs` table schema:
  - `id`: BIGSERIAL PRIMARY KEY (or UUID)
  - `doc_key`: TEXT UNIQUE (deterministic identifier such as `runbook:auth:504-timeout`)
  - `title`: TEXT NOT NULL
  - `content`: TEXT NOT NULL
  - `metadata`: JSONB DEFAULT '{}'::jsonb
  - `embedding`: vector(768) NOT NULL
  - `created_at`: TIMESTAMPTZ DEFAULT NOW()
  - `updated_at`: TIMESTAMPTZ DEFAULT NOW()
- **Decision**: Define stored procedure `match_incident_docs(query_embedding vector(768), match_threshold float, match_count int, filter_metadata jsonb default '{}'::jsonb)` using cosine distance (`<=>`).
- **Alternatives Considered**:
  - *SQLAlchemy / Alembic*: Rejected to eliminate heavy ORM dependencies and keep database operations lightweight.
  - *Pure JSON file vector search (e.g. Chroma/FAISS in memory)*: Rejected because the project architecture requires shared, durable state across server restarts in Render.

### 2. Embedding Model and Dimension Selection
- **Decision**: Use Google Gemini embeddings (`text-embedding-004` or latest `gemini-embedding` via `google-genai` / `langchain-google-genai`) configured for 768 dimensions and `task_type="RETRIEVAL_DOCUMENT"`.
- **Alternatives Considered**:
  - *OpenAI `text-embedding-3-small`*: Rejected because it requires a paid account/credit card.
  - *HuggingFace local embeddings (SentenceTransformers)*: Rejected because downloading models locally in Render free tier exceeds memory and disk limits (512MB RAM).

### 3. Idempotent Ingestion Strategy
- **Decision**: Use deterministic `doc_key` unique constraints and PostgreSQL `ON CONFLICT (doc_key) DO UPDATE SET content = EXCLUDED.content, metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding, updated_at = NOW()`.
- **Alternatives Considered**:
  - *Truncate and re-insert*: Rejected because it generates unnecessary churn and breaks foreign key references if other tables link to document IDs.
  - *Ignore duplicates (`ON CONFLICT DO NOTHING`)*: Rejected because runbook content updates would not be refreshed upon re-seeding.

### 4. Vector Indexing
- **Decision**: For the initial seed set (and typical internal runbook collections under 1,000 documents), sequential scan with cosine distance (`<=>`) provides microsecond retrieval with zero indexing overhead. Add an IVFFlat or HNSW index once document scale exceeds hundreds of entries.

## Free-Tier Limits and Constraints

- **Google AI Studio Quota**: Free tier imposes rate limits (1500 requests per minute for embeddings). The seed script batches or sequentially processes 3 documents in < 2 seconds, safely below limits.
- **Supabase Free Tier**:
  - 500 MB database storage limit (a few thousand runbooks with 768-dim float vectors consume < 20 MB).
  - Project auto-pauses after 7 days of inactivity; scripts should provide descriptive error handling if connection is refused.
  - Connection limits: Supabase direct connection allows limited concurrent connections; transaction pooling (port 6543) or connection recycling via `psycopg` pool ensures limits are respected.
- **Render Free Web Service**: Spin-down on idle requires database-backed durability (satisfying the requirement that runbook RAG and agent state survive instance restarts).

## Risks / Trade-offs

- **[Risk] Supabase IPv6 / Connection Issues**:
  - *Mitigation*: Support `DATABASE_URL` with SSL mode `sslmode=require` and document using the connection pooler URL if IPv4 Direct is unavailable.
- **[Risk] Gemini Embedding API Model Deprecations or Dimension Mismatch**:
  - *Mitigation*: Explicitly assert embedding length is 768 before database insertion; encapsulate embedding calls in a helper module.
- **[Risk] Testing Dependency on Live Services**:
  - *Mitigation*: Structure database and LLM calls so all unit tests mock the network layer, ensuring offline CI/CD and zero API token usage during testing.

## Migration Plan

1. Execute `db/migrations/001_incident_docs.sql` on the target PostgreSQL database.
2. Verify migration success by checking extension `vector` and table `incident_docs`.
3. Set `GEMINI_API_KEY` and `DATABASE_URL` in `.env`.
4. Run `python seed_rag.py` to populate initial runbooks.
5. **Rollback**: Run SQL statement:
   ```sql
   DROP FUNCTION IF EXISTS match_incident_docs(vector, float, int, jsonb);
   DROP TABLE IF EXISTS incident_docs;
   ```
