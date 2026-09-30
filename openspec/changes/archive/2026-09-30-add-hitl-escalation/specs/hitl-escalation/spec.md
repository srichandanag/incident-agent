# Spec Delta

## Purpose

Enforces human-in-the-loop (HITL) safety controls for sensitive operational actions, ensuring incident ticket escalation pauses for explicit engineer approval or rejection.

## ADDED Requirements

### Requirement: Sensitive escalation tool
The system SHALL provide a sensitive tool `escalate_ticket` that formats an incident escalation ticket (including service name, severity, summary, and recommended action) and requires human approval before executing any dispatch.

#### Scenario: Sensitive tool payload creation
- **GIVEN** an agent identifying an unresolvable incident for service "auth" with severity "critical"
- **WHEN** `escalate_ticket` is invoked
- **THEN** it generates a structured escalation ticket object containing a unique ticket ID, service name, severity, and summary.

### Requirement: LangGraph human-in-the-loop pause on sensitive tools
The system SHALL configure the agent graph topology with a distinct `sensitive_tools` node and set `interrupt_before=["sensitive_tools"]` so that graph execution pauses immediately before executing any sensitive tool.

#### Scenario: Execution halts before sensitive tool execution
- **GIVEN** an incident prompt requiring escalation and an LLM emitting an `escalate_ticket` tool call
- **WHEN** the agent graph executes
- **THEN** graph execution pauses immediately prior to the `sensitive_tools` node, preserving the tool call in the checkpoint without executing it.

### Requirement: Explicit approval and rejection handling
The system SHALL support explicit `APPROVE` and `REJECT` decisions for paused sensitive actions. On approval, the graph SHALL resume and execute the sensitive tool. On rejection, the sensitive tool SHALL NOT execute, and a `ToolMessage` explaining the rejection SHALL be provided to the agent.

#### Scenario: Engineer approves sensitive escalation action
- **GIVEN** an agent graph paused before `sensitive_tools` with a pending `escalate_ticket` action
- **WHEN** an engineer provides an `APPROVE` decision
- **THEN** the graph resumes execution, `escalate_ticket` executes, and the ticket creation confirmation is returned to the agent for final synthesis.

#### Scenario: Engineer rejects sensitive escalation action
- **GIVEN** an agent graph paused before `sensitive_tools` with a pending `escalate_ticket` action
- **WHEN** an engineer provides a `REJECT` decision
- **THEN** `escalate_ticket` is not executed, a `ToolMessage` stating the escalation was rejected is appended to message state, and the agent synthesizes a response acknowledging the rejection.

### Requirement: State survival across restarts during pause
The system SHALL ensure that paused human-in-the-loop states persisted in `PostgresSaver` survive process termination and can be reloaded and resumed on a separate process instance hours later using the thread ID.

#### Scenario: Paused investigation resumed on new process instance
- **GIVEN** an incident thread paused on a pending `escalate_ticket` action and checkpointed via `PostgresSaver`
- **WHEN** the process restarts and a new agent graph instance loads the checkpoint with the same `thread_id`
- **THEN** the pending state and interrupt details are successfully retrieved from the checkpointer, enabling subsequent approval or rejection.

#### Scenario: Rejection verifiable without external network access
- **GIVEN** an automated test suite with mocked LLM and database fixtures
- **WHEN** the approval and rejection workflows are exercised
- **THEN** all approval and rejection behaviors execute and validate offline without calling live Gemini or Supabase endpoints.
