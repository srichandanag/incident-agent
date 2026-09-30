"""Unit tests for runbook knowledge base seeding and RAG utilities.

Validates schema migrations, embedding logic, and idempotent database operations
using mocks to ensure tests run offline without network or database dependencies.
"""

from pathlib import Path
from unittest.mock import MagicMock, call
import pytest

from seed_rag import (
    EMBEDDING_DIM,
    SAMPLE_RUNBOOKS,
    get_embedding,
    search_runbooks,
    seed_runbooks,
)


def test_sql_migration_syntax_and_schema():
    """Verify SQL migration file contains the required schema and function definitions."""
    migration_path = Path(__file__).parent.parent / "db" / "migrations" / "001_incident_docs.sql"
    assert migration_path.exists(), f"Migration file not found at {migration_path}"

    sql_content = migration_path.read_text(encoding="utf-8")

    # Extension check
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in sql_content

    # Table and column checks
    assert "CREATE TABLE IF NOT EXISTS incident_docs" in sql_content
    assert "doc_key TEXT NOT NULL UNIQUE" in sql_content
    assert f"embedding vector({EMBEDDING_DIM})" in sql_content
    assert "metadata JSONB" in sql_content
    assert "title TEXT NOT NULL" in sql_content
    assert "content TEXT NOT NULL" in sql_content

    # RPC function check
    assert "CREATE OR REPLACE FUNCTION match_incident_docs" in sql_content
    assert f"query_embedding vector({EMBEDDING_DIM})" in sql_content
    assert "match_threshold float" in sql_content
    assert "match_count int" in sql_content
    assert "filter_metadata jsonb" in sql_content
    assert "<=>" in sql_content  # Cosine distance operator in pgvector


def test_sample_runbooks_definition():
    """Verify the three required sample runbooks exist with proper metadata and structure."""
    assert len(SAMPLE_RUNBOOKS) == 3

    keys = {doc["doc_key"] for doc in SAMPLE_RUNBOOKS}
    expected_keys = {
        "runbook:auth:504-timeout",
        "runbook:database:high-latency",
        "runbook:payments:gateway-failure",
    }
    assert keys == expected_keys

    services = {doc["metadata"]["service"] for doc in SAMPLE_RUNBOOKS}
    assert services == {"auth", "database", "payments"}

    for doc in SAMPLE_RUNBOOKS:
        assert doc["title"]
        assert len(doc["content"]) > 100
        assert "Symptoms" in doc["content"]
        assert "Remediation" in doc["content"]


def test_get_embedding_with_mock_client():
    """Verify embedding function interacts correctly with embedding client and validates dimension."""
    mock_vector = [0.01 * (i % 10) for i in range(EMBEDDING_DIM)]
    mock_client = MagicMock()
    mock_client.embed_documents.return_value = [mock_vector]

    result = get_embedding("test content", client=mock_client)

    assert len(result) == EMBEDDING_DIM
    assert result == mock_vector
    mock_client.embed_documents.assert_called_once_with(["test content"])


def test_get_embedding_invalid_dimension_raises():
    """Verify ValueError is raised if embedding dimension does not match 768."""
    bad_vector = [0.1] * 512
    mock_client = MagicMock()
    mock_client.embed_documents.return_value = [bad_vector]

    with pytest.raises(ValueError, match="Expected embedding dimension 768"):
        get_embedding("test content", client=mock_client)


def test_seed_runbooks_idempotent_mock_db():
    """Verify seed_runbooks performs upserts with ON CONFLICT DO UPDATE for idempotency."""
    mock_vector = [0.05] * EMBEDDING_DIM
    mock_client = MagicMock()
    mock_client.embed_documents.return_value = [mock_vector]

    # Mock DB Connection and Cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    # Simulate RETURNING id, doc_key
    mock_cursor.fetchone.side_effect = [(1, "runbook:auth:504-timeout"),
                                        (2, "runbook:database:high-latency"),
                                        (3, "runbook:payments:gateway-failure")]

    results = seed_runbooks(
        runbooks=SAMPLE_RUNBOOKS,
        embedding_client=mock_client,
        db_conn=mock_conn
    )

    assert len(results) == 3
    assert mock_cursor.execute.call_count == 3

    # Inspect executed queries to confirm ON CONFLICT (doc_key) DO UPDATE
    for executed_call in mock_cursor.execute.call_args_list:
        query, params = executed_call[0]
        assert "ON CONFLICT (doc_key) DO UPDATE" in query
        assert params[0].startswith("runbook:")  # doc_key
        assert params[4].startswith("[")  # formatted vector string

    mock_conn.commit.assert_called_once()

    # Re-run seeding to verify idempotency on subsequent execution
    mock_cursor.reset_mock()
    mock_conn.reset_mock()
    mock_cursor.fetchone.side_effect = [(1, "runbook:auth:504-timeout"),
                                        (2, "runbook:database:high-latency"),
                                        (3, "runbook:payments:gateway-failure")]

    re_results = seed_runbooks(
        runbooks=SAMPLE_RUNBOOKS,
        embedding_client=mock_client,
        db_conn=mock_conn
    )
    assert len(re_results) == 3
    assert mock_cursor.execute.call_count == 3
    mock_conn.commit.assert_called_once()


def test_search_runbooks_with_mock_db():
    """Verify search_runbooks queries match_incident_docs with query embedding and threshold."""
    mock_vector = [0.02] * EMBEDDING_DIM
    mock_client = MagicMock()
    mock_client.embed_documents.return_value = [mock_vector]

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [
        (1, "runbook:auth:504-timeout", "Auth Service 504", "Remediation content", {"service": "auth"}, 0.92)
    ]

    results = search_runbooks(
        query="auth service timeout",
        match_threshold=0.7,
        match_count=2,
        embedding_client=mock_client,
        db_conn=mock_conn
    )

    assert len(results) == 1
    match = results[0]
    assert match["id"] == 1
    assert match["doc_key"] == "runbook:auth:504-timeout"
    assert match["similarity"] == 0.92
    assert match["metadata"]["service"] == "auth"

    mock_cursor.execute.assert_called_once()
    query_str, params = mock_cursor.execute.call_args[0]
    assert "match_incident_docs" in query_str
    assert params[1] == 0.7  # threshold
    assert params[2] == 2    # match_count
