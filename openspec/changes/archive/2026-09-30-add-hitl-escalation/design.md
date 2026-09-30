# Design

## Context

Building on the safe autonomous triage engine (`triage-agent-core`), this change introduces human-in-the-loop (HITL) escalation controls. When an incident diagnosis requires human intervention or service degradation persists, the agent must be able to escalate by creating an incident ticket, but it must never execute sensitive operations autonomously.

State persistence uses the existing Supabase PostgreSQL connection pool with `PostgresSaver`, ensuring paused incident investigations survive server restarts on Render.

## Goals / Non-Goals

**Goals:**
- Implement sensitive tool `escalate_ticket` capturing service name, severity level, problem summary, and recommended action.
- Isolate tools into two distinct nodes: `safe_tools` (autonomous execution) and `sensitive_tools` (gated execution).
- Configure the LangGraph StateGraph with `interrupt_before=["sensitive_tools"]` so execution halts immediately when sensitive actions are requested.
- Provide helper utilities `get_pending_approval()` and `resume_approval()`:
  - `get_pending_approval`: inspects thread checkpoint state to extract pending tool calls and arguments.
  - `resume_approval(decision="APPROVE")`: continues execution to run `sensitive_tools` and returns to the agent.
  - `resume_approval(decision="REJECT")`: bypasses tool execution, updates thread state with a rejection `ToolMessage`, and allows the agent to acknowledge the rejection gracefully.
- Ensure paused states survive process restarts via `PostgresSaver`.
- Provide automated unit tests verifying approval, rejection, and restart resilience with mocked fixtures.

**Non-Goals:**
- Implementing the web interface or REST endpoints (deferred to Change 4).
- Connecting to live third-party ticketing APIs (e.g. Jira, PagerDuty, ServiceNow); structured ticket records are generated and logged.

## Decisions

### 1. Dual ToolNode Graph Architecture
- **Decision**: Segregate tools into two separate nodes in the LangGraph topology:
  - `safe_tools`: ToolNode containing `[query_service_health, search_remediation_runbooks]` (runs autonomously).
  - `sensitive_tools`: ToolNode containing `[escalate_ticket]`.
  - Conditional router `route_agent`:
    - If last message has tool calls matching `escalate_ticket`: route to `sensitive_tools`.
    - If last message has tool calls matching safe tools: route to `safe_tools`.
    - Otherwise: route to `END`.
- **Alternatives Considered**:
  - *Single ToolNode with internal `interrupt()` call*: Rejected because static graph interrupts via `interrupt_before=["sensitive_tools"]` make pending actions explicit in `state.next == ("sensitive_tools",)` and allow inspecting the graph topology cleanly.

### 2. Approval vs Rejection Resumption Pattern
- **Decision**:
  - **On APPROVE**: Invoke `graph.invoke(None, config)`. LangGraph resumes execution at `sensitive_tools`, runs `escalate_ticket`, appends the tool response, and returns to `agent` for final synthesis.
  - **On REJECT**: Call `graph.update_state(config, {"messages": [ToolMessage(content="Action rejected by engineer: Incident ticket escalation was declined.", tool_call_id=tool_call_id, name="escalate_ticket")]}, as_node="sensitive_tools")` followed by `graph.invoke(None, config)`. This injects the rejection tool message as if `sensitive_tools` completed, avoiding actual tool execution and allowing the agent to synthesize an acknowledgment.
- **Alternatives Considered**:
  - *Deleting the tool call from history*: Rejected because mutating past LLM messages can break conversation coherence and causes mismatch in API message validation.

### 3. State Checkpointing and Restart Resilience
- **Decision**: When `interrupt_before` triggers, LangGraph commits the pre-node state to `PostgresSaver`. The checkpoint contains the full message history up to the `AIMessage` containing the tool call. A separate process instance initialized with the same database connection pool and checkpointer can call `graph.get_state(config)` and `resume_approval()` seamlessly.

## Free-Tier Limits and Constraints

- **Supabase PostgreSQL**: Checkpoints for paused threads consume minimal storage (< 10 KB per thread), well within 500 MB quota.
- **Render Web Service Spin-Down**: Idle spin-down on Render free tier terminates in-memory processes. Because `PostgresSaver` persists state to Supabase Postgres, engineers can approve or reject tickets hours later upon instance wake-up.
- **Google AI Studio Quota**: Mocked models in unit tests ensure 0 API calls during test runs.

## Risks / Trade-offs

- **[Risk] State Desynchronization During Rejection**:
  - *Mitigation*: The `resume_approval` helper automatically resolves the active `tool_call_id` from the latest checkpoint message, ensuring the injected `ToolMessage` has an exact matching ID.
- **[Risk] Unhandled Simultaneous Tool Calls**:
  - *Mitigation*: The router prioritizes `sensitive_tools` if any sensitive tool call is present in the batch, guaranteeing human approval before any execution.

## Migration Plan

1. Update `agent.py` to add `escalate_ticket`, dual tool nodes, and approval helpers.
2. Verify all approval, rejection, and restart flows using `tests/test_agent.py`.
3. **Rollback**: Revert `agent.py` and `tests/test_agent.py` to restore Change 2 state.
