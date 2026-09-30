# Proposal

## Why

When production incidents occur, engineers need immediate diagnostic insights into affected backend services and relevant remediation runbooks. Building a strictly read-only, safe autonomous triage loop allows the agent to diagnose issues and recommend verified solutions while ensuring zero unintended side effects before human-in-the-loop escalation capabilities are introduced.

## What Changes

- Add `langgraph` and `langgraph-checkpoint-postgres` to `requirements.txt`.
- Implement a reusable PostgreSQL connection pool module using `psycopg_pool.ConnectionPool` configured with `max_size=10`, `autocommit=True`, `connect_timeout=15`, and `prepare_threshold=None`.
- Implement a safe, read-only tool `query_service_health` that inspects service metrics and health status (covering auth, database, and payments services) using simulated, mockable infrastructure data.
- Implement a safe tool `search_remediation_runbooks` that queries the `incident_docs` pgvector knowledge base via cosine similarity and metadata filtering.
- Implement the LangGraph agent state graph: `agent` -> `safe_tools` -> `agent` using Gemini via Google AI Studio (`ChatGoogleGenerativeAI`).
- Integrate `PostgresSaver` checkpointer over the connection pool to persist agent conversation state and diagnostic history.
- Ensure strict read-only safety: explicitly exclude any ticketing, paging, or mutating tools from this change.
- Create automated unit tests covering tool execution, graph routing, state checkpointing, and LLM orchestration with offline mocks.

## Capabilities

### New Capabilities
- `triage-agent-core`: Read-only diagnostic triage agent loop with service health inspection, runbook search, LangGraph graph orchestration, and PostgresSaver checkpointing.

### Modified Capabilities
*(None - existing capability `runbook-knowledge-base` remains unchanged)*

## Impact

- **Affected capability**: `triage-agent-core`.
- **Dependencies**: Adds `langgraph` and `langgraph-checkpoint-postgres` to `requirements.txt`.
- **Codebase**: Creates `agent.py` (core agent graph, connection pool, and safe tools) and `tests/test_agent.py`.
- **State Store**: Utilizes Supabase Postgres connection pool for `PostgresSaver` checkpoint storage alongside existing `incident_docs`.

## Rollback Note

To roll back this change:
1. Delete `agent.py` and `tests/test_agent.py`.
2. Revert additions in `requirements.txt`.
3. Checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) created by `PostgresSaver.setup()` in PostgreSQL can be dropped via `DROP TABLE IF EXISTS checkpoint_writes, checkpoint_blobs, checkpoints, checkpoint_migrations;` without impacting `incident_docs`.
