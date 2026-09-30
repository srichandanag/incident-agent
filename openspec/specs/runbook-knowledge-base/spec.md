# runbook-knowledge-base Specification

## Purpose
Provides a persistent vector-indexed knowledge base for operational runbooks, enabling semantic retrieval of remediation procedures during incident triage.

## Requirements

### Requirement: Database schema and vector storage
The system SHALL provide a PostgreSQL migration that enables the `pgvector` extension, creates the `incident_docs` table (with columns for `id`, `content`, `metadata` JSONB, 768-dimensional `embedding` vector, and `created_at`), and creates the `match_incident_docs` RPC function for cosine similarity vector search with metadata filtering.

#### Scenario: Migration applies vector schema
- **GIVEN** a PostgreSQL database with the pgvector extension available
- **WHEN** migration `db/migrations/001_incident_docs.sql` is executed
- **THEN** the `incident_docs` table and `match_incident_docs` function are created with 768-dimension vector support.

#### Scenario: Schema syntax verifiable without live database
- **GIVEN** a test environment without active Supabase credentials
- **WHEN** the SQL migration file is inspected or parsed in automated tests
- **THEN** the schema and function syntax validate successfully without requiring a live database connection.

### Requirement: Runbook document embedding
The system SHALL generate 768-dimensional vector embeddings for runbook documents using Gemini embeddings with task type `RETRIEVAL_DOCUMENT`.

#### Scenario: Successful document embedding
- **GIVEN** runbook content text and a configured embedding client
- **WHEN** the document embedding function is invoked
- **THEN** it generates a 768-dimensional floating point embedding vector using task type `RETRIEVAL_DOCUMENT`.

#### Scenario: Document embedding testable with mock client
- **GIVEN** a mocked Gemini embedding client
- **WHEN** runbook text is embedded during unit testing
- **THEN** the embedding pipeline returns a 768-dimensional mock vector without sending network requests to Google AI Studio.

### Requirement: Idempotent runbook seeding
The system SHALL provide a CLI script `seed_rag.py` that embeds and seeds three sample runbooks (auth 504 timeouts, database high latency, and payment gateway failures) into `incident_docs`, ensuring repeated executions do not create duplicate records.

#### Scenario: Initial seeding of runbooks
- **GIVEN** an empty `incident_docs` table and mocked external services
- **WHEN** `seed_rag.py` is executed
- **THEN** three runbooks (auth, database, payments) are embedded and inserted with service tags and issue metadata.

#### Scenario: Repeated seeding is idempotent
- **GIVEN** the three sample runbooks already exist in the database
- **WHEN** `seed_rag.py` is executed again
- **THEN** no duplicate records are created in `incident_docs` and existing records remain valid.

### Requirement: Similarity search retrieval
The system SHALL support cosine similarity querying against `incident_docs` through `match_incident_docs`, allowing retrieval of top-matching runbooks filtered by similarity threshold and optional metadata.

#### Scenario: Query returns matching runbooks
- **GIVEN** seeded runbooks in `incident_docs` and a query embedding vector
- **WHEN** `match_incident_docs` is invoked with the query vector and a match count limit
- **THEN** matching runbook records are returned in descending order of similarity score.

#### Scenario: Retrieval testable with mocked database
- **GIVEN** a mocked database connection returning simulated runbook rows
- **WHEN** similarity search is executed in a unit test
- **THEN** the search function parses and returns the expected runbook objects without contacting a live database.
