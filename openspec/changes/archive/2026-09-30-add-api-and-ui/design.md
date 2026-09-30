# Design

## Context

The existing system provides a LangGraph-based incident triage agent with safe investigation tools and a human-in-the-loop boundary for sensitive escalation actions. The current implementation does not expose these capabilities through an HTTP API or engineer-facing web interface.

See proposal.md for the motivation and specs/incident-api/spec.md and specs/incident-ui/spec.md for the required behavior.

The application must preserve the existing thread-based LangGraph state and HITL approval mechanism. Gemini and Supabase remain external dependencies accessed through environment variables. The implementation must remain compatible with the Windows + PowerShell development environment and the zero-cost deployment target.

## Goals / Non-Goals

**Goals:**

- Add a FastAPI application layer around the existing LangGraph agent.
- Preserve LangGraph thread identifiers across API requests.
- Expose triage results, investigation information, remediation guidance, and escalation state.
- Provide explicit API operations for approving and rejecting pending sensitive actions.
- Mount a Gradio Blocks interface at / for engineer interaction.
- Keep sensitive actions behind the existing HITL approval boundary.
- Make Gemini and Supabase dependencies mockable in tests.
- Keep the implementation compatible with the existing Python 3.11 stack.

**Non-Goals:**

- Changing the existing LangGraph triage logic.
- Changing the existing sensitive-tool approval mechanism.
- Adding deployment configuration; deployment is handled by a later change.
- Adding authentication or authorization beyond the existing explicit approval boundary.
- Introducing additional databases or vector stores.

## Decisions

### 1. FastAPI as the HTTP application layer

The API will use FastAPI because it integrates naturally with the existing Python application and provides straightforward request validation and testability.

**Alternative considered:** Flask.

FastAPI was selected because the project already targets a Python API application and FastAPI provides typed request/response models and convenient testing support without introducing another service architecture.

### 2. Reuse the existing LangGraph thread state

Each API request will use a conversation/thread identifier as the LangGraph configuration key. Existing PostgresSaver persistence will remain the source of durable agent state.

**Alternative considered:** Maintain a separate API session store.

A separate session store would duplicate state and could diverge from the LangGraph checkpointer. Reusing the existing thread state keeps API behavior aligned with the agent's persisted execution state.

### 3. Explicit approval and rejection API operations

Approval and rejection will be represented by dedicated API operations that resume the appropriate persisted thread. The API will not expose a general-purpose endpoint capable of directly executing a sensitive tool.

**Alternative considered:** Allow clients to submit arbitrary tool commands.

This would weaken the existing HITL security boundary. Dedicated approval/rejection operations preserve the requirement that sensitive actions require an explicit human decision.

### 4. Gradio Blocks mounted under FastAPI

The engineer-facing interface will use Gradio Blocks and be mounted at / through the FastAPI application.

**Alternative considered:** Build a separate JavaScript frontend.

A separate frontend would add another build and deployment surface. Gradio Blocks provides the required engineer-facing interaction while remaining within the existing Python application stack.

### 5. Mock external services in tests

Tests will mock Gemini and Supabase interactions rather than requiring live credentials or network access.

**Alternative considered:** Integration tests against live Gemini and Supabase services.

Live integration tests would consume external resources and could violate the project's zero-cost development constraint. Mocking provides deterministic tests and allows the API/UI behavior to be verified independently.

### 6. Preserve the existing application state model

The API and UI will consume the existing agent outputs and escalation state rather than creating a second triage representation.

This prevents the API/UI layer from becoming a separate source of truth.

## Risks / Trade-offs

- **[Risk] API and agent state could become inconsistent** ? Use the existing LangGraph thread identifier and PostgresSaver state as the source of truth.

- **[Risk] UI could accidentally bypass HITL approval** ? Approval and rejection controls will call explicit API operations, while sensitive tools remain protected by the existing interrupt mechanism.

- **[Risk] Gemini or Supabase availability could make tests unreliable** ? Mock external dependencies in unit tests.

- **[Risk] Gradio adds application overhead on the Render free tier** ? Keep the UI lightweight and avoid introducing unnecessary background services.

- **[Risk] Concurrent requests could operate on the same thread** ? Reuse the existing persisted thread/checkpoint model and keep API operations scoped to the requested thread.

- **[Risk] Sensitive approval state could be lost after a process restart** ? Continue using the existing PostgresSaver persistence rather than in-memory approval state.

## Migration Plan

1. Add the FastAPI application layer without changing the existing triage-agent implementation.
2. Add API tests using mocked Gemini and Supabase dependencies.
3. Add the Gradio Blocks interface and connect it to the API operations.
4. Run the complete existing and new test suite.
5. Verify that sensitive actions still require explicit approval.
6. If rollback is required, revert the API/UI files and tests; the existing triage and HITL implementation remains available.

## Open Questions

None. The specifications and existing architecture provide sufficient information for the implementation and task breakdown.
