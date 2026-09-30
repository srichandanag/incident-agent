# Proposal

## Why

The autonomous incident triage agent currently has the core investigation and human-in-the-loop escalation capabilities, but it does not yet provide an HTTP API or engineer-facing interface. This change adds the application layer needed to submit incidents, inspect triage results, and explicitly approve or reject pending sensitive actions.

## What Changes

- Add a FastAPI application for incident submission and thread-based triage.
- Add endpoints for retrieving triage results and escalation status.
- Add explicit approval and rejection endpoints for pending sensitive actions.
- Add a Gradio Blocks interface mounted at /.
- Display triage results, investigation information, remediation guidance, and escalation status.
- Ensure the API and UI cannot bypass the existing HITL approval boundary.
- Add tests for API and UI behavior using mocked Gemini and Supabase dependencies.
- Deployment configuration is not part of this change.

## Capabilities

### New Capabilities

- incident-api
- incident-ui

### Modified Capabilities

- None.

## Impact

This change adds the HTTP and UI application layer on top of the existing LangGraph triage agent and HITL escalation workflow. It introduces API/UI files and tests but does not change the existing sensitive-tool approval mechanism.

## Rollback

The change can be rolled back by reverting the API/UI implementation and associated tests. The existing triage-agent and HITL functionality remains unchanged.
