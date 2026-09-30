# Tasks

## 1. Project Dependencies and Environment Configuration

- [x] 1.1 Create `requirements.txt` containing `langchain-google-genai`, `google-genai`, `psycopg[binary,pool]`, `pgvector`, `python-dotenv`, `pytest`, and `pytest-mock`, verifying dependencies install cleanly in the virtual environment.
- [x] 1.2 Create `.env.example` documenting `GEMINI_API_KEY` and `DATABASE_URL` variable templates without secrets, and verify `.gitignore` excludes local `.env` files.

## 2. Database Migration for Vector Knowledge Base

- [x] 2.1 Create `db/migrations/001_incident_docs.sql` enabling the `vector` extension, defining `incident_docs` (`id`, `doc_key UNIQUE`, `title`, `content`, `metadata JSONB`, `embedding vector(768)`, `created_at`, `updated_at`), and verify SQL syntax through schema inspection tests.
- [x] 2.2 Add `match_incident_docs` stored function to `db/migrations/001_incident_docs.sql` supporting cosine similarity matching (`<=>`) and metadata filtering, verifying the RPC signature matches the spec.

## 3. Runbook Embedding and Ingestion Implementation

- [x] 3.1 Implement the Gemini embedding client in `seed_rag.py` using 768 dimensions and `RETRIEVAL_DOCUMENT` task type, verifying embedding generation via unit tests with mocked Google AI Studio clients.
- [x] 3.2 Author the three seed runbooks (Auth 504 Timeouts, Database High Latency, Payment Gateway Failures) with service tags and diagnostic steps inside `seed_rag.py`.
- [x] 3.3 Implement idempotent upsert logic in `seed_rag.py` using PostgreSQL `ON CONFLICT (doc_key) DO UPDATE`, verifying with unit tests that rerun executions do not create duplicate records.

## 4. Test Suite and Mock Verification

- [x] 4.1 Create `tests/test_seed_rag.py` with pytest test cases validating runbook embedding dimensions, idempotent database insertion, and similarity query parsing using mocked database and LLM fixtures.
- [x] 4.2 Run `pytest` and verify that all unit tests pass completely offline without external network or live database connections.
