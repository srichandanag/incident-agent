# Tasks

## 1. Dependencies and Connection Pool Factory

- [x] 1.1 Add `langgraph` and `langgraph-checkpoint-postgres` to `requirements.txt` and verify dependencies install in the virtual environment.
- [x] 1.2 Implement `get_connection_pool()` in `agent.py` using `psycopg_pool.ConnectionPool` with `max_size=10`, `autocommit=True`, `connect_timeout=15`, and `prepare_threshold=None`, verified with unit tests asserting configuration arguments.

## 2. Safe Read-Only Diagnostic Tools

- [x] 2.1 Implement `query_service_health` tool in `agent.py` covering `auth`, `database`, and `payments` using mockable infrastructure data, verified by unit tests asserting structured metric outputs.
- [x] 2.2 Implement `search_remediation_runbooks` tool in `agent.py` querying `incident_docs` via `seed_rag.search_runbooks`, verified by unit tests with mocked database connections.

## 3. LangGraph Agent Loop and Checkpointing

- [x] 3.1 Implement LangGraph agent graph (`agent` -> `safe_tools` -> `agent`) in `agent.py` binding Gemini reasoning models to safe tools, verified by unit tests asserting graph routing and strict exclusion of sensitive tools.
- [x] 3.2 Integrate `PostgresSaver` checkpointer setup over the connection pool in `agent.py`, verified by unit tests validating checkpoint persistence under thread IDs.

## 4. Test Suite and Verification

- [x] 4.1 Create `tests/test_agent.py` covering connection pool configuration, tool execution, graph routing, and offline agent execution using mocked Gemini and PostgreSQL fixtures.
- [x] 4.2 Run `pytest` to verify all existing and new test suites pass offline without network or database dependencies.
