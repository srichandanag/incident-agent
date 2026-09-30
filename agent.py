"""Autonomous Incident Triage Agent - Core Engine.

Implements the safe, read-only LangGraph triage agent loop with PostgreSQL
connection pooling, service health diagnostics, and runbook RAG search.
"""

import json
import logging
import os
from typing import Any, Callable, Dict, List, Literal, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from psycopg_pool import ConnectionPool

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration constants
DEFAULT_POOL_MAX_SIZE = 10
DEFAULT_CONNECT_TIMEOUT = 15
DEFAULT_MODEL_NAME = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are an Autonomous Incident Triage Agent. "
    "Your purpose is to investigate production incidents safely, diagnose root causes, "
    "and retrieve relevant remediation runbooks from the internal knowledge base. "
    "You have access to read-only diagnostic tools: 'query_service_health' and 'search_remediation_runbooks'. "
    "You are strictly prohibited from performing destructive actions, modifying configurations, "
    "or escalating tickets/paging teams without engineer approval. "
    "Perform thorough diagnostics, search runbooks for remediation steps, and provide clear actionable findings."
)

# Simulated infrastructure health database (mockable for testing)
DEFAULT_INFRASTRUCTURE_HEALTH: Dict[str, Dict[str, Any]] = {
    "auth": {
        "service": "auth",
        "status": "degraded",
        "http_status": "504 Gateway Timeout",
        "error_rate_pct": 14.8,
        "p99_latency_ms": 3200,
        "active_incidents": ["INC-8421: Ingress timeouts on /api/v1/auth/* endpoints"],
        "dependencies": {
            "redis_session_store": "high_latency (850ms)",
            "postgres_auth_db": "healthy"
        },
        "recent_deployments": ["auth-service v2.4.1 (deployed 45m ago)"]
    },
    "database": {
        "service": "database",
        "status": "degraded",
        "active_connections": 98,
        "max_connections": 100,
        "p99_latency_ms": 4500,
        "waiting_queries": 23,
        "lock_contention": "ExclusiveLock on table 'user_sessions' blocked by PID 14092",
        "active_incidents": ["INC-8419: Connection pool queue depth > 50"]
    },
    "payments": {
        "service": "payments",
        "status": "outage",
        "provider": "Stripe Primary Gateway",
        "error_rate_pct": 68.2,
        "p99_latency_ms": 12000,
        "webhook_dlq_size": 1420,
        "active_incidents": ["INC-8415: Webhook signature verification timeouts"],
        "fallback_available": True
    }
}

# In-memory store for infrastructure health data
_current_infrastructure_health: Dict[str, Dict[str, Any]] = dict(DEFAULT_INFRASTRUCTURE_HEALTH)

# Hook for overriding search_runbooks in tests
_search_runbooks_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None


def set_infrastructure_health(service: str, health_data: Dict[str, Any]) -> None:
    """Update or override health data for a service (useful in tests)."""
    _current_infrastructure_health[service.strip().lower()] = health_data


def reset_infrastructure_health() -> None:
    """Reset infrastructure health to default simulated state."""
    global _current_infrastructure_health
    _current_infrastructure_health = dict(DEFAULT_INFRASTRUCTURE_HEALTH)


def set_search_runbooks_fn(fn: Optional[Callable[..., List[Dict[str, Any]]]]) -> None:
    """Set custom search runbooks function (useful in tests to mock DB/embedding)."""
    global _search_runbooks_fn
    _search_runbooks_fn = fn


# ---------------------------------------------------------------------------
# 1. Connection Pool Factory
# ---------------------------------------------------------------------------

def get_connection_pool(
    database_url: Optional[str] = None,
    max_size: int = DEFAULT_POOL_MAX_SIZE,
    autocommit: bool = True,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
    prepare_threshold: Optional[int] = None,
    open: bool = True,
    **kwargs: Any
) -> ConnectionPool:
    """Creates a psycopg_pool.ConnectionPool with Supabase PgBouncer and PostgresSaver compatible settings.

    Settings:
    - max_size=10: Prevents exceeding Supabase free-tier connection limits.
    - autocommit=True: Required by PostgresSaver for automatic checkpoint commits.
    - connect_timeout=15: Fails quickly on connection failures.
    - prepare_threshold=None: Disables prepared statements for Supabase transaction pooler (port 6543).
    """
    resolved_url = database_url or os.getenv("DATABASE_URL")
    if not resolved_url:
        raise ValueError("DATABASE_URL environment variable is not set and no database_url was provided.")

    pool_kwargs: Dict[str, Any] = {
        "conninfo": resolved_url,
        "max_size": max_size,
        "open": open,
        "kwargs": {
            "autocommit": autocommit,
            "connect_timeout": connect_timeout,
            "prepare_threshold": prepare_threshold,
        },
    }
    pool_kwargs.update(kwargs)
    return ConnectionPool(**pool_kwargs)


# ---------------------------------------------------------------------------
# 2. Safe Read-Only Diagnostic Tools
# ---------------------------------------------------------------------------

@tool
def query_service_health(service: str) -> str:
    """Inspect current health status, error rates, p99 latency, and active alerts for a backend service.

    Args:
        service: Name of the service to inspect ('auth', 'database', or 'payments').
    """
    clean_service = service.strip().lower()
    if clean_service not in _current_infrastructure_health:
        supported = ", ".join(sorted(_current_infrastructure_health.keys()))
        return f"Unknown service '{service}'. Supported services: {supported}."

    data = _current_infrastructure_health[clean_service]
    return json.dumps(data, indent=2)


@tool
def search_remediation_runbooks(query: str, match_count: int = 3) -> str:
    """Search internal incident runbooks in pgvector for remediation procedures.

    Args:
        query: Symptom or issue description (e.g. 'auth gateway timeout 504' or 'high database latency').
        match_count: Maximum number of matching runbook procedures to retrieve (default: 3).
    """
    try:
        if _search_runbooks_fn is not None:
            matches = _search_runbooks_fn(query=query, match_count=match_count)
        else:
            from seed_rag import search_runbooks
            matches = search_runbooks(query=query, match_count=match_count)

        if not matches:
            return f"No matching runbooks found for query '{query}'."

        formatted_matches: List[str] = []
        for m in matches:
            service_tag = m.get("metadata", {}).get("service", "unknown") if isinstance(m.get("metadata"), dict) else "unknown"
            formatted_matches.append(
                f"### {m.get('title', 'Runbook')} ({m.get('doc_key', 'n/a')})\n"
                f"- Similarity Score: {m.get('similarity', 0.0):.4f}\n"
                f"- Service: {service_tag}\n"
                f"- Content:\n{m.get('content', '')}\n"
            )
        return "\n\n".join(formatted_matches)
    except Exception as e:
        logger.error("Runbook search failed: %s", e)
        return f"Error searching remediation runbooks: {str(e)}"


SAFE_TOOLS = [query_service_health, search_remediation_runbooks]


# ---------------------------------------------------------------------------
# 3. LangGraph Agent Loop and Checkpointing
# ---------------------------------------------------------------------------

def route_agent(state: MessagesState) -> Literal["safe_tools", "__end__"]:
    """Determines whether to transition to safe_tools or finish."""
    messages = state["messages"]
    if not messages:
        return END

    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "safe_tools"
    return END


def create_triage_graph(
    model: Optional[Any] = None,
    checkpointer: Optional[Any] = None,
    api_key: Optional[str] = None,
    model_name: str = DEFAULT_MODEL_NAME
) -> Any:
    """Builds and compiles the read-only triage agent StateGraph.

    Graph Topology:
    [START] --> agent
    agent --> safe_tools (if tool_calls requested)
    agent --> [END] (if final answer)
    safe_tools --> agent
    """
    if model is None:
        from langchain_google_genai import ChatGoogleGenerativeAI
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        if not resolved_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set and no api_key was provided.")
        model = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=resolved_key,
            temperature=0.0
        )

    # Bind strictly safe tools to model
    model_with_tools = model.bind_tools(SAFE_TOOLS)

    def agent_node(state: MessagesState) -> Dict[str, Any]:
        messages = list(state["messages"])
        if not messages or not isinstance(messages[0], SystemMessage):
            full_messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        else:
            full_messages = messages
        response = model_with_tools.invoke(full_messages)
        return {"messages": [response]}

    workflow = StateGraph(MessagesState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("safe_tools", ToolNode(SAFE_TOOLS))

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        route_agent,
        {
            "safe_tools": "safe_tools",
            END: END
        }
    )
    workflow.add_edge("safe_tools", "agent")

    return workflow.compile(checkpointer=checkpointer)


def get_checkpointer(pool_or_conn: Any, auto_setup: bool = True) -> PostgresSaver:
    """Factory for PostgresSaver checkpointer backed by a connection pool."""
    saver = PostgresSaver(pool_or_conn)
    if auto_setup:
        try:
            saver.setup()
        except Exception as e:
            logger.warning("PostgresSaver setup skipped or failed: %s", e)
    return saver
