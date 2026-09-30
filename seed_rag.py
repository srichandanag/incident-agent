"""Runbook Knowledge Base Seeder and RAG utilities.

Embeds and idempotently stores operational runbooks in Supabase pgvector using
Gemini embeddings (768-dimensional, RETRIEVAL_DOCUMENT).
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Load local .env if present
load_dotenv()

EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIM = 768

SAMPLE_RUNBOOKS: List[Dict[str, Any]] = [
    {
        "doc_key": "runbook:auth:504-timeout",
        "title": "Auth Service 504 Gateway Timeout Runbook",
        "metadata": {
            "service": "auth",
            "severity": "high",
            "tags": ["timeout", "gateway", "504", "token", "redis"]
        },
        "content": (
            "# Runbook: Auth Service 504 Gateway Timeout\n\n"
            "## Symptoms\n"
            "- Ingress returns HTTP 504 Gateway Timeout on /api/v1/auth/* endpoints.\n"
            "- Increased client login failures and auth token validation spikes.\n\n"
            "## Diagnostic Steps\n"
            "1. Verify upstream Redis session store latency: check connection pool saturation and CPU spikes.\n"
            "2. Inspect auth pod health metrics: look for high memory usage causing slow GC pauses.\n"
            "3. Check database connection pool for auth service: confirm max_connections is not reached.\n\n"
            "## Immediate Remediation\n"
            "1. If Redis is unresponsive, trigger cache failover or flush expired session keys.\n"
            "2. If pod memory is pegged, scale deployment replicas: `kubectl scale deployment/auth-service --replicas=5`.\n"
            "3. Restart degraded pods sequentially if connection leaks are detected.\n"
            "4. If upstream identity provider is failing, route traffic to degraded mode caching validated JWTs."
        )
    },
    {
        "doc_key": "runbook:database:high-latency",
        "title": "Database High Latency and Connection Exhaustion Runbook",
        "metadata": {
            "service": "database",
            "severity": "critical",
            "tags": ["postgres", "latency", "slow-query", "lock", "pool"]
        },
        "content": (
            "# Runbook: PostgreSQL High Query Latency\n\n"
            "## Symptoms\n"
            "- Database query response times exceed p99 SLA (> 2000ms).\n"
            "- Connection pooler reports client queue delays and timeout alerts.\n\n"
            "## Diagnostic Steps\n"
            "1. Query `pg_stat_activity` for active long-running queries (> 30s) or transaction open states.\n"
            "2. Identify lock contention: check `pg_locks` for blocked backend processes.\n"
            "3. Check disk I/O utilization and autovacuum queue depth.\n\n"
            "## Immediate Remediation\n"
            "1. Terminate offending long-running blocking query: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE ...`.\n"
            "2. If connection pooler is saturated, temporarily increase pool limits or throttle non-critical background jobs.\n"
            "3. Route read-heavy analytics queries to the read replica.\n"
            "4. Trigger manual VACUUM ANALYZE on bloated hot tables during low-traffic windows."
        )
    },
    {
        "doc_key": "runbook:payments:gateway-failure",
        "title": "Payment Gateway Failure and Webhook Drop Runbook",
        "metadata": {
            "service": "payments",
            "severity": "critical",
            "tags": ["payments", "stripe", "gateway", "webhook", "checkout"]
        },
        "content": (
            "# Runbook: Payment Gateway Failure and Webhook Drops\n\n"
            "## Symptoms\n"
            "- Checkout completion rates drop by > 50%.\n"
            "- Spikes in payment capture exceptions (HTTP 502/503 from payment provider API).\n"
            "- Dead-letter queue (DLQ) accumulation for asynchronous payment webhooks.\n\n"
            "## Diagnostic Steps\n"
            "1. Verify third-party provider status (e.g., Stripe/Adyen status dashboard and API error rate).\n"
            "2. Inspect payment microservice logs for webhook signature mismatch or timeout exceptions.\n"
            "3. Check payment credentials and certificate/webhook secret expiration.\n\n"
            "## Immediate Remediation\n"
            "1. If primary payment gateway is experiencing an outage, switch feature flag to fallback gateway provider.\n"
            "2. Enable graceful checkout retry with idempotency keys for pending transactions.\n"
            "3. Pause webhook consumer DLQ alerts and queue unprocessed webhook events for delayed replay.\n"
            "4. Escalate to financial operations and post customer status banner on checkout page."
        )
    }
]


def get_embedding_client(api_key: Optional[str] = None, task_type: str = "retrieval_document") -> Any:
    """Initializes GoogleGenAIEmbeddings client."""
    from langchain_google_genai import GoogleGenAIEmbeddings

    resolved_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set and no api_key was provided.")

    return GoogleGenAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=resolved_key,
        task_type=task_type
    )


def get_embedding(
    text: str,
    api_key: Optional[str] = None,
    client: Optional[Any] = None,
    task_type: str = "retrieval_document"
) -> List[float]:
    """Generates a 768-dimensional embedding vector for text using Gemini."""
    if client is None:
        client = get_embedding_client(api_key=api_key, task_type=task_type)

    if hasattr(client, "embed_documents"):
        vectors = client.embed_documents([text])
        vector = vectors[0]
    elif hasattr(client, "embed_query"):
        vector = client.embed_query(text)
    else:
        raise TypeError("Provided client does not have embed_documents or embed_query method")

    if len(vector) != EMBEDDING_DIM:
        raise ValueError(f"Expected embedding dimension {EMBEDDING_DIM}, got {len(vector)}")

    return [float(x) for x in vector]


def seed_runbooks(
    db_url: Optional[str] = None,
    api_key: Optional[str] = None,
    runbooks: Optional[List[Dict[str, Any]]] = None,
    embedding_client: Optional[Any] = None,
    db_conn: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Idempotently embeds and inserts runbooks into incident_docs."""
    import psycopg
    from psycopg.types.json import Jsonb

    docs_to_seed = runbooks if runbooks is not None else SAMPLE_RUNBOOKS
    resolved_db_url = db_url or os.getenv("DATABASE_URL")
    if db_conn is None and not resolved_db_url:
        raise ValueError("DATABASE_URL environment variable is not set and no db_conn was provided.")

    seeded_records: List[Dict[str, Any]] = []

    def _execute_seeding(conn: Any) -> List[Dict[str, Any]]:
        # Register pgvector adapter if available
        try:
            from pgvector.psycopg import register_vector
            register_vector(conn)
        except Exception as e:
            logger.debug("pgvector adapter registration skipped or failed: %s", e)

        results = []
        with conn.cursor() as cur:
            for item in docs_to_seed:
                doc_key = item["doc_key"]
                title = item["title"]
                content = item["content"]
                metadata = item.get("metadata", {})

                logger.info("Generating embedding for %s (%s)...", title, doc_key)
                vector = get_embedding(
                    text=content,
                    api_key=api_key,
                    client=embedding_client,
                    task_type="retrieval_document"
                )

                # Upsert query with ON CONFLICT (doc_key) DO UPDATE
                query = """
                INSERT INTO incident_docs (doc_key, title, content, metadata, embedding, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (doc_key) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
                RETURNING id, doc_key;
                """
                # Format vector either as string or list
                vector_param = f"[{','.join(f'{x:.8f}' for x in vector)}]"
                metadata_param = Jsonb(metadata) if not isinstance(metadata, str) else metadata

                cur.execute(query, (doc_key, title, content, metadata_param, vector_param))
                row = cur.fetchone()
                row_id = row[0] if row else None
                results.append({"id": row_id, "doc_key": doc_key, "title": title})
                logger.info("Successfully seeded: %s (id: %s)", doc_key, row_id)

        conn.commit()
        return results

    if db_conn is not None:
        seeded_records = _execute_seeding(db_conn)
    else:
        with psycopg.connect(resolved_db_url) as conn:
            seeded_records = _execute_seeding(conn)

    return seeded_records


def search_runbooks(
    query: str,
    db_url: Optional[str] = None,
    api_key: Optional[str] = None,
    match_threshold: float = 0.0,
    match_count: int = 5,
    filter_metadata: Optional[Dict[str, Any]] = None,
    embedding_client: Optional[Any] = None,
    db_conn: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Performs cosine similarity search against incident_docs via match_incident_docs."""
    import psycopg
    from psycopg.types.json import Jsonb

    resolved_db_url = db_url or os.getenv("DATABASE_URL")
    if db_conn is None and not resolved_db_url:
        raise ValueError("DATABASE_URL environment variable is not set and no db_conn was provided.")

    query_vector = get_embedding(
        text=query,
        api_key=api_key,
        client=embedding_client,
        task_type="retrieval_query"
    )

    filter_dict = filter_metadata or {}
    vector_param = f"[{','.join(f'{x:.8f}' for x in query_vector)}]"
    filter_param = Jsonb(filter_dict) if not isinstance(filter_dict, str) else filter_dict

    def _execute_search(conn: Any) -> List[Dict[str, Any]]:
        try:
            from pgvector.psycopg import register_vector
            register_vector(conn)
        except Exception:
            pass

        with conn.cursor() as cur:
            sql = """
            SELECT id, doc_key, title, content, metadata, similarity
            FROM match_incident_docs(%s, %s, %s, %s);
            """
            cur.execute(sql, (vector_param, match_threshold, match_count, filter_param))
            rows = cur.fetchall()
            matches = []
            for r in rows:
                matches.append({
                    "id": r[0],
                    "doc_key": r[1],
                    "title": r[2],
                    "content": r[3],
                    "metadata": r[4],
                    "similarity": float(r[5])
                })
            return matches

    if db_conn is not None:
        return _execute_search(db_conn)
    else:
        with psycopg.connect(resolved_db_url) as conn:
            return _execute_search(conn)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed runbooks into Supabase pgvector.")
    parser.add_argument("--search", type=str, help="Search for runbooks matching a query")
    parser.add_argument("--threshold", type=float, default=0.5, help="Similarity threshold for search")
    parser.add_argument("--count", type=int, default=3, help="Max results to return")
    args = parser.parse_args()

    if args.search:
        logger.info("Searching runbooks for query: '%s'...", args.search)
        results = search_runbooks(
            query=args.search,
            match_threshold=args.threshold,
            match_count=args.count
        )
        print(f"\nFound {len(results)} matches:\n")
        for match in results:
            print(f"[{match['similarity']:.4f}] {match['title']} ({match['doc_key']})")
            print(f"Service: {match['metadata'].get('service', 'unknown')}")
            print(f"Content excerpt: {match['content'][:150]}...\n")
    else:
        logger.info("Starting runbook seeding process...")
        results = seed_runbooks()
        print(f"\nSuccessfully seeded {len(results)} runbooks:")
        for r in results:
            print(f" - {r['doc_key']}: {r['title']} (ID: {r['id']})")


if __name__ == "__main__":
    main()
