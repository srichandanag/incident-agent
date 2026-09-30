# Proposal

## Why

To autonomously triage production incidents, the agent needs fast, semantically relevant access to internal remediation guides. This change establishes the runbook knowledge base with pgvector in Supabase, an idempotent seed pipeline using Gemini 768-dimensional embeddings, and similarity search functionality to ground agent triage in verified runbooks.

## What Changes

- Add project dependencies in `requirements.txt` (`google-genai` / `langchain-google-genai`, `psycopg[binary,pool]`, `pgvector`, `python-dotenv`, `pytest`, etc.).
- Create database migration `db/migrations/001_incident_docs.sql` to enable `pgvector`, define the `incident_docs` table (id, content, metadata JSONB, 768-dimensional embedding vector, and timestamp), and create the `match_incident_docs` similarity search stored procedure.
- Create `seed_rag.py` to embed and seed three initial runbooks (auth 504 timeouts, database high latency, and payment gateway failures) using Gemini embeddings with task type `RETRIEVAL_DOCUMENT`.
- Implement idempotent seeding so re-running the script updates existing entries or skips duplicates rather than inserting duplicate records.
- Create unit tests with mocked LLM/embedding calls and database connections.

## Capabilities

### New Capabilities
- `runbook-knowledge-base`: Schema definition, Gemini 768-dim vector embeddings, idempotent ingestion, and cosine similarity matching for incident runbooks.

### Modified Capabilities
*(None - this is a new capability)*

## Impact

- **Affected capability**: `runbook-knowledge-base`.
- **Database**: Adds `incident_docs` table and `match_incident_docs` function in Supabase Postgres with `vector` extension.
- **Dependencies**: Introduces core dependencies in `requirements.txt`.
- **Runtime Scripts**: Introduces `seed_rag.py` CLI utility for initial knowledge ingestion.
- **Testing**: Adds unit test suite in `tests/` mocking external Gemini and Supabase interactions.

## Rollback Note

If this change needs to be reverted:
1. Database: Execute a teardown migration or script executing `DROP FUNCTION IF EXISTS match_incident_docs; DROP TABLE IF EXISTS incident_docs;` (and `DROP EXTENSION IF EXISTS vector;` if no other systems rely on it).
2. Code: Remove `db/migrations/001_incident_docs.sql`, `seed_rag.py`, and associated test files; revert `requirements.txt`.
