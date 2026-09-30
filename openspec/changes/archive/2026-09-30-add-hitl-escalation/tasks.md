# Tasks

## 1. Sensitive Escalation Tool Implementation

- [ ] 1.1 Implement `escalate_ticket` tool in `agent.py` accepting service, severity, summary, and suggested remediation, verified by unit tests asserting structured ticket attributes and unique ticket IDs.

## 2. Graph Topology and Interrupt Configuration

- [ ] 2.1 Update LangGraph topology in `agent.py` to introduce `sensitive_tools` ToolNode and compile with `interrupt_before=["sensitive_tools"]`, verified by unit tests confirming execution pauses before the node.
- [ ] 2.2 Update conditional routing in `agent.py` to route sensitive tool calls to `sensitive_tools` and safe tool calls to `safe_tools`, verified by unit tests covering safe, sensitive, and mixed routing scenarios.

## 3. Approval and Rejection Execution Mechanics

- [ ] 3.1 Implement `get_pending_approval()` in `agent.py` to inspect paused graph state and extract pending action details, verified by unit tests validating tool name and argument extraction.
- [ ] 3.2 Implement `resume_approval()` in `agent.py` supporting `APPROVE` (executing sensitive tool) and `REJECT` (bypassing execution and injecting rejection ToolMessage), verified by unit tests covering both decision branches.

## 4. Checkpoint State Persistence and Test Verification

- [ ] 4.1 Add unit tests in `tests/test_agent.py` validating that a paused thread survives process restart via checkpointer and can be successfully resumed on a fresh graph instance.
- [ ] 4.2 Run `pytest` to verify that all test suites across the repository pass completely offline without external network or database connections.
