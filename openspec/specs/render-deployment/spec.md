# render-deployment Specification

## Purpose
Deploy the incident triage FastAPI + Gradio application to Render, providing a managed hosting environment with zero‑cost deployment.

## Requirements

### Requirement: Render deployment configuration
The system SHALL provide a `render.yaml` file that defines a Render web service for the FastAPI application, specifies the start command, and includes the necessary environment variables.

#### Scenario: Successful deployment configuration
- **WHEN** the repository is deployed to Render using the provided `render.yaml`
- **THEN** Render shall start the service with `uvicorn app:app --host 0.0.0.0 --port $PORT` and the application shall be reachable at the service URL.

### Requirement: Health endpoint
The system SHALL expose a `/health` HTTP endpoint that returns a JSON payload `{"status": "ok"}` with HTTP 200 when the service is healthy.

#### Scenario: Health check passes
- **WHEN** an HTTP GET request is sent to `/health`
- **THEN** the service returns status code 200 and body `{"status": "ok"}`.
