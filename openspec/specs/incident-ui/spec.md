# incident-ui Specification

## Purpose
Engineer-facing web interface for submitting incidents, viewing triage information, and making human decisions on pending escalations.

## Requirements

### Requirement: Incident submission interface

The system SHALL provide a user interface for entering and submitting an incident.

#### Scenario: Submit incident through UI

- **WHEN** an engineer enters an incident and submits it
- **THEN** the interface SHALL display the resulting triage state and thread information

### Requirement: Triage results display

The system SHALL display the available triage result and remediation guidance.

#### Scenario: View triage results

- **WHEN** triage produces a result
- **THEN** the interface SHALL present the result and remediation guidance

### Requirement: Escalation status display

The system SHALL clearly indicate when a sensitive action is pending human approval.

#### Scenario: Human approval required

- **WHEN** the agent reaches a pending sensitive action
- **THEN** the interface SHALL display that human approval is required

### Requirement: Escalation approval control

The system SHALL provide an explicit control for approving a pending sensitive action.

#### Scenario: Approve escalation through UI

- **WHEN** an engineer explicitly approves a pending escalation
- **THEN** the interface SHALL submit the approval and display the resumed agent state

### Requirement: Escalation rejection control

The system SHALL provide an explicit control for rejecting a pending sensitive action.

#### Scenario: Reject escalation through UI

- **WHEN** an engineer explicitly rejects a pending escalation
- **THEN** the interface SHALL submit the rejection and display the resulting agent state

### Requirement: HITL security boundary

The interface SHALL NOT allow sensitive actions to execute without human approval.

#### Scenario: UI cannot bypass approval

- **WHEN** an engineer interacts with the interface without approving a pending sensitive action
- **THEN** the sensitive action SHALL remain unexecuted
