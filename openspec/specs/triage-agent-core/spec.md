# triage-agent-core Specification

## Purpose
Provides a strictly safe, read-only autonomous incident triage agent loop that inspects backend service health, queries verified runbooks, and persists conversation checkpoints.

## Requirements

### Requirement: Database connection pool configuration
The system SHALL provide a reusable PostgreSQL connection pool using `psycopg_pool.ConnectionPool` configured with `max_size=10`, `autocommit=True`, `connect_timeout=15`, and `prepare_threshold=None`.

#### Scenario: Connection pool initialized with required parameters
- **GIVEN** a configured database connection string
- **WHEN** the connection pool factory is invoked
- **THEN** the instantiated `ConnectionPool` is configured with `max_size=10`, `autocommit=True`, `connect_timeout=15`, and `prepare_threshold=None`.

#### Scenario: Pool initialization is mockable
- **GIVEN** a test runner without network access
- **WHEN** connection pool creation is validated with test arguments
- **THEN** the pool configuration succeeds without attempting an external database handshake.

### Requirement: Safe service health diagnostic tool
The system SHALL provide a read-only tool `query_service_health` that accepts a service name (`auth`, `database`, or `payments`) and returns diagnostic status, error rates, and metric observations from mockable infrastructure data without modifying system state.

#### Scenario: Query existing service health
- **GIVEN** a request to inspect the health of the "auth" service
- **WHEN** `query_service_health` is executed with `service="auth"`
- **THEN** it returns structured diagnostic metrics (status, error rate, p99 latency, active incidents) without performing state mutations.

#### Scenario: Query unrecognized service
- **GIVEN** a request to inspect an unrecognized service name
- **WHEN** `query_service_health` is executed with `service="unknown-svc"`
- **THEN** it returns a clear descriptive message listing supported services without raising an uncaught exception.

### Requirement: Safe runbook knowledge base search tool
The system SHALL provide a read-only tool `search_remediation_runbooks` that queries the `incident_docs` table via cosine similarity and returns top-matching runbook procedures with title, content, metadata, and similarity score.

#### Scenario: Search runbooks returns matching procedures
- **GIVEN** an incident diagnostic search query
- **WHEN** `search_remediation_runbooks` is invoked
- **THEN** it performs a similarity search against `incident_docs` and returns matching runbooks ordered by similarity score.

#### Scenario: Runbook search operates offline with mock database
- **GIVEN** a mocked database connection and embedding client
- **WHEN** `search_remediation_runbooks` is executed in an automated test
- **THEN** it returns formatted runbook matches without contacting external Gemini or Supabase APIs.

### Requirement: LangGraph agent graph loop
The system SHALL implement a LangGraph agent loop where the agent node evaluates messages, routes to `safe_tools` when tool calls are requested, and returns to `agent` until final synthesis is reached.

#### Scenario: Agent invokes safe tool and synthesizes answer
- **GIVEN** an incident prompt and a mocked Gemini model emitting a tool call for `query_service_health` followed by an analysis response
- **WHEN** the agent graph executes
- **THEN** the graph transitions from `agent` to `safe_tools` and back to `agent`, producing a final synthesis containing the diagnostic findings.

#### Scenario: Sensitive tool action rejection and exclusion
- **GIVEN** the compiled safe triage agent graph
- **WHEN** the agent tool registry is inspected
- **THEN** only safe read-only tools (`query_service_health`, `search_remediation_runbooks`) are registered, and any unapproved sensitive actions (such as ticket escalation or paging) are rejected and prohibited from execution.

### Requirement: Agent state checkpoint persistence
The system SHALL configure LangGraph checkpointing using `PostgresSaver` backed by the PostgreSQL connection pool, persisting conversation and diagnostic state per thread ID.

#### Scenario: Checkpointer initialized with connection pool
- **GIVEN** a configured `psycopg_pool.ConnectionPool`
- **WHEN** `PostgresSaver` is instantiated for the agent graph
- **THEN** the checkpointer is established over the connection pool and can save and load thread checkpoints.

#### Scenario: Checkpointer operates with mock pool in tests
- **GIVEN** an automated test with a mocked checkpointer
- **WHEN** an agent execution step completes for a given `thread_id`
- **THEN** conversation state and message history are persisted under that thread ID.
