# Proposal

## Why

When an incident cannot be remediated automatically or service degradation persists, the agent must be able to escalate by creating tickets or paging teams. However, autonomous execution of sensitive actions poses operational risk; therefore, all escalation actions must pause and wait for an engineer's explicit approval or rejection, and paused investigations must reliably survive system restarts.

## What Changes

- Add sensitive tool `escalate_ticket` to `agent.py`, requiring explicit human approval before execution.
- Maintain existing safe tools (`query_service_health`, `search_remediation_runbooks`) without modification.
- Introduce a distinct `sensitive_tools` ToolNode in the LangGraph graph topology.
- Configure graph compilation with `interrupt_before=["sensitive_tools"]` so execution halts automatically when sensitive tool calls are generated.
- Provide helper functions to inspect pending approval requests (tool call name and arguments) for paused threads.
- Implement explicit `APPROVE` and `REJECT` resumption workflows:
  - On `APPROVE`: The graph resumes and executes `escalate_ticket`, returning ticket confirmation.
  - On `REJECT`: The sensitive tool is bypassed, and a `ToolMessage` is injected informing the agent that the action was rejected.
- Leverage `PostgresSaver` so paused threads survive server restarts or process termination.
- Add comprehensive unit tests covering approval execution, rejection handling, and checkpoint persistence across restarts.

## Capabilities

### New Capabilities
- `hitl-escalation`: Human-in-the-loop escalation workflow, sensitive tool registration, LangGraph pause/resume mechanics (`interrupt_before`), explicit approval/rejection handling, and state recovery.

### Modified Capabilities
*(None - existing capabilities `runbook-knowledge-base` and `triage-agent-core` remain unchanged)*

## Impact

- **Affected capability**: `hitl-escalation`.
- **Codebase**: Updates `agent.py` to add `escalate_ticket`, `sensitive_tools` node, approval helpers, and graph routing; updates `tests/test_agent.py`.
- **Persistence**: Persists paused interrupt states in `PostgresSaver` checkpoint storage.

## Rollback Note

To roll back this change:
1. Revert changes in `agent.py` to restore the read-only graph topology.
2. Remove HITL escalation tests from `tests/test_agent.py`.
3. Checkpoint tables in Supabase continue to store standard conversation checkpoints without interruption metadata.
