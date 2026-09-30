"""Unit tests for Autonomous Incident Triage Agent Core Engine.

Validates connection pool configuration, safe tools, LangGraph routing loop,
and checkpointing using mocked LLM and database fixtures for complete offline testing.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END

import agent
from agent import (
    DEFAULT_POOL_MAX_SIZE,
    SAFE_TOOLS,
    create_triage_graph,
    get_checkpointer,
    get_connection_pool,
    query_service_health,
    reset_infrastructure_health,
    route_agent,
    search_remediation_runbooks,
    set_infrastructure_health,
    set_search_runbooks_fn,
)


@pytest.fixture(autouse=True)
def clean_agent_state():
    """Ensure infrastructure and mock hooks are reset before and after each test."""
    reset_infrastructure_health()
    set_search_runbooks_fn(None)
    yield
    reset_infrastructure_health()
    set_search_runbooks_fn(None)


# ---------------------------------------------------------------------------
# 1. Connection Pool Tests
# ---------------------------------------------------------------------------

def test_connection_pool_configuration():
    """Verify get_connection_pool sets max_size=10, autocommit=True, connect_timeout=15, prepare_threshold=None."""
    test_url = "postgresql://postgres:secret@localhost:5432/testdb"
    pool = get_connection_pool(database_url=test_url, open=False)

    assert pool.max_size == DEFAULT_POOL_MAX_SIZE
    assert pool.max_size == 10
    assert pool.kwargs["autocommit"] is True
    assert pool.kwargs["connect_timeout"] == 15
    assert pool.kwargs["prepare_threshold"] is None


def test_connection_pool_missing_url_raises():
    """Verify get_connection_pool raises ValueError when no database_url is provided or set."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="DATABASE_URL environment variable is not set"):
            get_connection_pool(database_url=None)


# ---------------------------------------------------------------------------
# 2. Safe Diagnostic Tools Tests
# ---------------------------------------------------------------------------

def test_query_service_health_valid_services():
    """Verify query_service_health returns structured metrics for auth, database, payments."""
    for service_name in ["auth", "database", "payments"]:
        result_json = query_service_health.invoke({"service": service_name})
        data = json.loads(result_json)
        assert data["service"] == service_name
        assert "status" in data
        assert "p99_latency_ms" in data


def test_query_service_health_unknown_service():
    """Verify query_service_health returns clear message for unknown services without error."""
    result = query_service_health.invoke({"service": "nonexistent-microservice"})
    assert "Unknown service 'nonexistent-microservice'" in result
    assert "Supported services: auth, database, payments" in result


def test_query_service_health_override_mock():
    """Verify set_infrastructure_health allows dynamic override during testing."""
    set_infrastructure_health("auth", {"service": "auth", "status": "healthy", "p99_latency_ms": 42})
    result_json = query_service_health.invoke({"service": "auth"})
    data = json.loads(result_json)
    assert data["status"] == "healthy"
    assert data["p99_latency_ms"] == 42


def test_search_remediation_runbooks_with_mock():
    """Verify search_remediation_runbooks formats runbook matches from knowledge base."""
    mock_runbooks = [
        {
            "id": 1,
            "doc_key": "runbook:auth:504-timeout",
            "title": "Auth 504 Timeout Runbook",
            "content": "Step 1: Check Redis session latency.",
            "metadata": {"service": "auth"},
            "similarity": 0.9412
        }
    ]
    set_search_runbooks_fn(lambda query, match_count: mock_runbooks)

    result = search_remediation_runbooks.invoke({"query": "auth 504 timeout", "match_count": 1})
    assert "Auth 504 Timeout Runbook" in result
    assert "runbook:auth:504-timeout" in result
    assert "0.9412" in result
    assert "Step 1: Check Redis session latency." in result


def test_search_remediation_runbooks_empty():
    """Verify search_remediation_runbooks handles zero matches gracefully."""
    set_search_runbooks_fn(lambda query, match_count: [])
    result = search_remediation_runbooks.invoke({"query": "unrelated issue"})
    assert "No matching runbooks found" in result


# ---------------------------------------------------------------------------
# 3. Safe Tool Registry and Prohibition of Sensitive Tools
# ---------------------------------------------------------------------------

def test_safe_tools_registry_contains_only_read_only_tools():
    """Verify that only safe read-only tools are registered and sensitive actions are excluded."""
    registered_names = {t.name for t in SAFE_TOOLS}
    expected_names = {"query_service_health", "search_remediation_runbooks"}

    assert registered_names == expected_names

    # Explicit check: sensitive / mutating tools MUST NOT be registered in this core change
    prohibited_names = {"escalate_ticket", "page_oncall", "create_incident_ticket", "restart_pod"}
    for prohibited in prohibited_names:
        assert prohibited not in registered_names, f"Sensitive tool '{prohibited}' must not be in safe tools"


def test_route_agent_logic():
    """Verify conditional router transitions to safe_tools on tool_calls and END on final message."""
    # State with tool call
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"name": "query_service_health", "args": {"service": "auth"}, "id": "call_123"}]
    )
    assert route_agent({"messages": [tool_call_msg]}) == "safe_tools"

    # State with plain text response
    final_msg = AIMessage(content="Triage complete. The auth service is degraded.")
    assert route_agent({"messages": [final_msg]}) == END

    # Empty state
    assert route_agent({"messages": []}) == END


# ---------------------------------------------------------------------------
# 4. LangGraph Loop and Offline Model Execution
# ---------------------------------------------------------------------------

def test_triage_graph_execution_with_mock_model():
    """Verify LangGraph loop executes agent -> safe_tools -> agent with mocked model."""
    # Mock LLM behavior:
    # Call 1: Emits tool call for query_service_health
    # Call 2: Receives tool message and emits final diagnostic synthesis
    response_1 = AIMessage(
        content="",
        tool_calls=[{"name": "query_service_health", "args": {"service": "database"}, "id": "call_db_1"}]
    )
    response_2 = AIMessage(
        content="Diagnosis: The database has connection pool exhaustion and lock contention."
    )

    mock_model = MagicMock()
    mock_bound_model = MagicMock()
    mock_model.bind_tools.return_value = mock_bound_model
    mock_bound_model.invoke.side_effect = [response_1, response_2]

    # Compile graph without checkpointer for fast in-memory execution
    app = create_triage_graph(model=mock_model)

    initial_input = {"messages": [HumanMessage(content="Investigate database latency alerts.")]}
    final_state = app.invoke(initial_input)

    messages = final_state["messages"]
    # Messages expected: HumanMessage, AIMessage (tool call), ToolMessage (result), AIMessage (final answer)
    assert len(messages) == 4
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert messages[1].tool_calls[0]["name"] == "query_service_health"
    assert isinstance(messages[2], ToolMessage)
    assert "ExclusiveLock" in messages[2].content
    assert isinstance(messages[3], AIMessage)
    assert "connection pool exhaustion" in messages[3].content


# ---------------------------------------------------------------------------
# 5. Checkpointer Tests
# ---------------------------------------------------------------------------

def test_get_checkpointer_calls_setup():
    """Verify get_checkpointer initializes PostgresSaver and attempts setup."""
    mock_conn = MagicMock()
    with patch("agent.PostgresSaver") as mock_saver_cls:
        mock_saver = MagicMock()
        mock_saver_cls.return_value = mock_saver

        saver = get_checkpointer(mock_conn, auto_setup=True)
        mock_saver_cls.assert_called_once_with(mock_conn)
        mock_saver.setup.assert_called_once()
        assert saver == mock_saver
