# Tasks

## 1. API Foundation

- [x] 1.1 Add FastAPI application entry point in app.py and verify the application imports successfully with python -c "import app".

- [x] 1.2 Add typed request and response models for incident submission, thread state, triage results, and HITL decisions, and verify model validation with pytest.

- [x] 1.3 Add the incident submission endpoint using the existing LangGraph agent and thread configuration, and verify a mocked submission returns a thread identifier and triage state.

- [x] 1.4 Add thread result retrieval using the persisted LangGraph state, and verify a mocked existing thread returns triage information and escalation status.

## 2. HITL API

- [x] 2.1 Add the explicit approval endpoint for a pending sensitive escalation and verify with mocked agent state that approval resumes the correct thread.

- [x] 2.2 Add the explicit rejection endpoint for a pending sensitive escalation and verify with mocked agent state that rejection resumes the thread without executing the sensitive action.

- [x] 2.3 Ensure no API endpoint can directly execute a sensitive tool without an approval decision, and verify the bypass attempt is rejected by a pytest security test.

- [x] 2.4 Add API tests covering incident submission, thread persistence, result retrieval, approval, rejection, and HITL bypass protection while mocking Gemini and Supabase dependencies.

## 3. Engineer UI

- [x] 3.1 Add a Gradio Blocks interface mounted at / and verify the FastAPI application exposes the UI route.

- [x] 3.2 Add incident submission controls that send incidents through the API and display the returned thread and triage state, and verify the interaction with mocked API/agent behavior.

- [x] 3.3 Add triage result, investigation information, remediation guidance, and escalation status displays, and verify the relevant values are rendered from mocked state.

- [x] 3.4 Add explicit Approve and Reject controls for pending sensitive actions and verify each control calls only its corresponding HITL API operation.

- [x] 3.5 Ensure the UI cannot bypass the approval boundary and verify a pending sensitive action remains unexecuted until an explicit approval is submitted.

## 4. Integration

- [x] 4.1 Run the complete pytest suite with python -m pytest and verify all existing and new tests pass.

- [x] 4.2 Start the FastAPI application locally and verify the API responds and the Gradio interface is reachable at / without requiring committed secrets.

- [x] 4.3 Verify the final implementation preserves the existing LangGraph triage and HITL behavior and that git diff contains no secrets or environment credentials.
