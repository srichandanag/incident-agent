# Design

## Context

With the runbook knowledge base established in PostgreSQL pgvector, this change implements the core LangGraph autonomous incident triage engine (`agent.py`). The triage agent must safely inspect infrastructure symptoms and search relevant remediation runbooks without performing any state-altering operations.

The runtime operates within zero-cost constraints (Supabase PostgreSQL, Gemini via Google AI Studio, Render hosting) and relies on environment variables (`GEMINI_API_KEY`, `DATABASE_URL`).

## Goals / Non-Goals

**Goals:**
- Provide a reusable connection pool factory returning `psycopg_pool.ConnectionPool` configured with `max_size=10`, `autocommit=True`, `connect_timeout=15`, and `prepare_threshold=None`.
- Implement `query_service_health`: read-only diagnostic tool returning simulated/mockable health status for `auth`, `database`, and `payments`.
- Implement `search_remediation_runbooks`: read-only semantic search tool querying `incident_docs` in pgvector.
- Build the LangGraph agent state graph: `agent` -> `safe_tools` -> `agent` using `ChatGoogleGenerativeAI`.
- Integrate `PostgresSaver` for thread checkpoint persistence over the connection pool.
- Keep the agent strictly read-only and safe (zero modifying or escalation tools).
- Structure components to be 100% mockable for offline unit testing.

**Non-Goals:**
- Escalation tools (`escalate_ticket`, paging on-call, Slack/webhook alerts) — deferred to Change 3 (HITL Escalation).
- Human-in-the-loop interrupts (`interrupt()`) — deferred to Change 3.
- FastAPI REST endpoints and Gradio web interface — deferred to Change 4.

## Decisions

### 1. Database Connection Pool Configuration
- **Decision**: Create a connection pool factory `get_connection_pool(database_url: Optional[str] = None) -> ConnectionPool` with:
  - `max_size=10`: Caps pool size to prevent exceeding Supabase connection limits.
  - `autocommit=True`: Required by `PostgresSaver` for checkpoint writes without manual transaction commits.
  - `connect_timeout=15`: Fails fast if Supabase is cold-starting or un-pausing.
  - `prepare_threshold=None`: Disables prepared statements, which is strictly required when connecting through Supabase's transaction pooler (PgBouncer port 6543).
- **Alternatives Considered**:
  - *Standard `psycopg.connect()` per request*: Rejected because creating and tearing down TLS database connections on every agent turn introduces high latency.
  - *SQLAlchemy QueuePool*: Rejected to keep dependencies lightweight and directly compatible with `PostgresSaver`.

### 2. LangGraph Architecture and Agent Loop
- **Decision**: Use LangGraph `MessagesState` with two primary nodes:
  - `agent`: Invokes `ChatGoogleGenerativeAI` bound with `[query_service_health, search_remediation_runbooks]`.
  - `safe_tools`: A LangGraph `ToolNode` containing only the safe read-only tools.
  - Conditional edge `should_continue`: Routes to `safe_tools` if the model requested tool calls; routes to `END` if the model produced a final synthesis response.
- **Alternatives Considered**:
  - *ReAct agent prebuilt helper (`create_react_agent`)*: Rejected because the project will extend the graph with custom human-in-the-loop pause nodes and approval branches in subsequent changes. A custom `StateGraph` provides explicit control over node transitions and checkpointing.

### 3. Tool Implementation and Mockability
- **Decision**:
  - `query_service_health`: Backed by an in-memory dictionary of service diagnostic metrics (latency, error rate, active alerts) that can be overridden or mocked in tests.
  - `search_remediation_runbooks`: Calls `search_runbooks` from `seed_rag.py` using cosine similarity on `incident_docs`.
  - Both tools are wrapped with `@tool` from `langchain_core.tools`.

### 4. Checkpointer Persistence with PostgresSaver
- **Decision**: Use `PostgresSaver(conn_pool)` from `langgraph-checkpoint-postgres`. Call `checkpointer.setup()` during application startup or initial pool creation to ensure checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) exist.
- **Alternatives Considered**:
  - *MemorySaver*: Rejected for production because instance restarts or Render sleep would lose incident state.
  - *Custom JSON serialization in Postgres*: Rejected because `PostgresSaver` is the native, supported checkpointer for LangGraph with out-of-the-box support for thread history and upcoming HITL interrupts.

## Free-Tier Limits and Constraints

- **Supabase Connection Limit**: Free tier restricts concurrent connections. A pool `max_size=10` with PgBouncer compatibility (`prepare_threshold=None`) prevents connection exhaustion.
- **Google AI Studio Quota**: 15 requests per minute for Gemini reasoning models. Offline unit testing with mocked LLM fixtures ensures zero quota consumption during testing.
- **Render Memory Limits**: 512 MB RAM free tier. `psycopg_pool` and `langgraph` have negligible memory footprint compared to local neural networks or heavy ORMs.

## Risks / Trade-offs

- **[Risk] Supabase PgBouncer Transaction Pooler Incompatibilities**:
  - *Mitigation*: Setting `prepare_threshold=None` prevents "prepared statement does not exist" errors in PgBouncer.
- **[Risk] Accidental Side Effects or Escalations**:
  - *Mitigation*: The tool registry strictly includes only `query_service_health` and `search_remediation_runbooks`. No escalation tools exist in this change.
- **[Risk] Stale or Mocked Infrastructure Drift**:
  - *Mitigation*: The service health dictionary is structured with realistic metric keys (`status`, `error_rate_pct`, `p99_latency_ms`, `dependencies`) that can easily integrate with real health endpoints in future iterations.

## Migration Plan

1. Install updated dependencies: `pip install -r requirements.txt`.
2. When the agent first runs with a live database, `PostgresSaver.setup()` creates required checkpoint tables in PostgreSQL.
3. Verify agent behavior with unit tests.
4. **Rollback**: Remove `agent.py` and revert `requirements.txt`.
