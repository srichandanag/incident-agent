# incident-api Specification

## Purpose
HTTP API for submitting incidents, retrieving triage results, and approving or rejecting pending sensitive actions.

## Requirements

### Requirement: Incident submission

The system SHALL provide an API operation that accepts an incident description and starts triage.

#### Scenario: Submit an incident

- **WHEN** an engineer submits a valid incident description
- **THEN** the system SHALL start triage and return a thread identifier and current triage state

### Requirement: Thread persistence

The system SHALL preserve the conversation/thread identifier for subsequent requests.

#### Scenario: Resume an existing thread

- **WHEN** an engineer submits a request using an existing thread identifier
- **THEN** the system SHALL continue from the persisted agent state

### Requirement: Triage result retrieval

The system SHALL expose the current triage result and escalation status for a thread.

#### Scenario: Retrieve triage result

- **WHEN** an engineer requests the result for an existing thread
- **THEN** the system SHALL return the available triage result and escalation state

### Requirement: HITL approval

The system SHALL provide an explicit operation for approving a pending sensitive escalation.

#### Scenario: Approve pending escalation

- **WHEN** an engineer approves a pending escalation
- **THEN** the system SHALL resume the thread and allow the sensitive action to execute

### Requirement: HITL rejection

The system SHALL provide an explicit operation for rejecting a pending sensitive escalation.

#### Scenario: Reject pending escalation

- **WHEN** an engineer rejects a pending escalation
- **THEN** the system SHALL resume the thread without executing the rejected sensitive action

### Requirement: HITL protection

The API SHALL NOT provide a mechanism that bypasses human approval for sensitive actions.

#### Scenario: Attempt to bypass approval

- **WHEN** a request attempts to execute a pending sensitive action without approval
- **THEN** the system SHALL prevent execution and report that human approval is required
